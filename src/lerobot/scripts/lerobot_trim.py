#!/usr/bin/env python
"""Remove leading idle (static) frames from every episode of a LeRobot v3.0 dataset.

What it does
------------
For each episode, the per-step change of ``observation.state`` (all robot joints
by default) is computed. The motion onset is the first step whose surrounding
``--onset-window`` steps contain at least ``--onset-displacement`` of cumulative
joint displacement, so tiny early twitches followed by stillness do not count as
the start of the episode. Every frame before the onset is considered idle and
removed; ``--buffer`` static frames are kept right before the onset so each
episode still starts with a brief "ready" context.

Episodes whose total joint displacement is below ``--min-displacement``
(effectively static), or whose remaining length after trimming is below
``--min-length``, are dropped entirely and the remaining episodes are renumbered
contiguously (episode_index 0..N-1).

The original dataset is never modified: data, meta and videos are rewritten to
``--output`` (default: "<dataset>_trim"), with one video file per episode per
camera. info.json, stats.json, meta/episodes and meta/tasks are updated to stay
consistent with the trimmed data.

Requires the ``lerobot`` conda environment (pandas, pyarrow, av, lerobot), e.g.:

    D:/soft/miniconda/envs/lerobot/python lerobot_trim.py \\
        D:/worksp/data/grap_ball_20260815_175420
"""

import argparse
import json
import shutil
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lerobot.configs.video import encoder_config_from_video_info
from lerobot.datasets.compute_stats import (
    RunningQuantileStats,
    aggregate_stats,
    auto_downsample_height_width,
    compute_episode_stats,
)

STAT_KEYS = ["min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99"]


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_motion_onset(delta: np.ndarray, window: int, threshold: float) -> int | None:
    """Return the first moving step inside the first window with enough displacement.

    A step index ``i`` measures the change between frame ``i`` and frame ``i + 1``.
    The onset is the first moving step of the earliest span of ``window``
    consecutive steps whose total displacement reaches ``threshold``. Isolated
    early twitches followed by stillness are therefore ignored.

    Args:
        delta: Per-step absolute displacement of shape (L - 1,).
        window: Number of consecutive steps in the sliding span.
        threshold: Minimum total displacement within the span.

    Returns:
        Step index of the motion onset, or ``None`` if no span reaches the
        threshold (episode effectively static).
    """
    n = len(delta)
    for j in range(0, n - window + 1):
        if delta[j : j + window].sum() >= threshold:
            nz = np.nonzero(delta[j : j + window] > 0)[0]
            return j + int(nz[0])
    return None


def to_native(value):
    """Convert numpy values to plain Python values for JSON serialization."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_native(v) for v in value]
    return value


class EpisodeVideoEncoder:
    """Streams the kept frames of one episode into a single mp4, tracking pixel stats."""

    def __init__(self, path: Path, video_info: dict, fps: int):
        cfg = encoder_config_from_video_info(video_info)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.container = av.open(str(path), mode="w", options={"movflags": "faststart"})
        self.stream = self.container.add_stream(
            cfg.vcodec, fps, options=cfg.get_codec_options(as_strings=True)
        )
        self.stream.pix_fmt = cfg.pix_fmt
        self.stream.width = video_info["video.width"]
        self.stream.height = video_info["video.height"]
        self.stream.time_base = Fraction(1, fps)
        # NOTE: keep a constant frame time_base instead of reading
        # self.stream.time_base later — the mp4 muxer rescales the stream
        # time_base (avoid_negative_ts) after the first packet is muxed.
        self._frame_time_base = Fraction(1, fps)
        self._stats = RunningQuantileStats()
        self._frame_count = 0
        self._episode = path.stem

    def write_frame(self, frame: av.VideoFrame, local_index: int) -> None:
        # Per-channel pixel stats on RGB, same scheme as lerobot's streaming encoder.
        rgb = frame.to_ndarray(format="rgb24")  # (H, W, 3) uint8
        img_chw = np.transpose(rgb, (2, 0, 1))
        down = auto_downsample_height_width(img_chw)  # (C, H', W')
        pixels = down.transpose(1, 2, 0).reshape(-1, down.shape[0])  # (H'*W', C)
        self._stats.update(pixels)

        frame.pts = local_index
        frame.dts = None  # decoded frames carry source dts; let the encoder assign fresh ones
        frame.time_base = self._frame_time_base
        try:
            for packet in self.stream.encode(frame):
                self.container.mux(packet)
        except Exception:
            print(f"  [mux failed] episode {self._episode} local frame {local_index}")
            raise
        self._frame_count += 1

    def finish(self) -> dict:
        """Flush and close; return raw per-channel stats (count in downsampled pixels)."""
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()
        if self._frame_count < 2:
            raise RuntimeError(
                f"Episode has {self._frame_count} frame(s); cannot compute video stats. "
                "Increase --min-length."
            )
        return self._stats.get_statistics()


def video_stats_like_writer(raw: dict) -> dict:
    """Reshape raw per-channel video stats to the episodes-meta layout (lerobot writer)."""
    return {
        k: v if k == "count" else np.squeeze(v.reshape(1, -1, 1, 1) / 255.0, axis=0)
        for k, v in raw.items()
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim leading idle frames from every episode of a LeRobot v3.0 dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("dataset", type=str, help="Path to the source LeRobot v3 dataset.")
    parser.add_argument(
        "--output", type=str, default=None, help='Output path (default: "<dataset>_trim").'
    )
    parser.add_argument(
        "--onset-window",
        type=int,
        default=30,
        help="Number of consecutive steps whose total displacement must reach "
        "--onset-displacement for the motion onset to trigger.",
    )
    parser.add_argument(
        "--onset-displacement",
        type=float,
        default=10.0,
        help="Minimum cumulative |delta state| (sum over joints) within --onset-window "
        "steps that marks the motion onset.",
    )
    parser.add_argument(
        "--min-displacement",
        type=float,
        default=50.0,
        help="Drop episodes whose total joint displacement over the whole episode is "
        "below this (effectively static episodes).",
    )
    parser.add_argument(
        "--buffer",
        type=int,
        default=10,
        help="Number of static frames to keep right before the motion onset.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=50,
        help="Drop episodes whose trimmed length is below this many frames.",
    )
    parser.add_argument(
        "--ignore-gripper",
        action="store_true",
        help="Exclude the last joint (gripper) when detecting motion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be trimmed/dropped; do not write anything.",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite the output directory if it exists."
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    src = Path(args.dataset)
    out = Path(args.output) if args.output else Path(str(src).rstrip("/\\") + "_trim")

    info = load_json(src / "meta" / "info.json")
    fps = info["fps"]
    features = info["features"]
    video_keys = [k for k, v in features.items() if v.get("dtype") == "video"]
    non_video_features = {k: v for k, v in features.items() if v.get("dtype") != "video"}
    if not video_keys:
        raise ValueError("No video features found in the dataset.")

    print(f"Source dataset : {src}")
    print(f"Output dataset : {out}")

    # ---------------------------------------------------------------- load data
    data_tbl = pq.read_table(src / "data" / "chunk-000" / "file-000.parquet")  # 读取每个时刻的数据
    state = np.stack(data_tbl["observation.state"].to_numpy())                 # (N, joints)，每个时刻的关节状态
    epi_col = data_tbl["episode_index"].to_numpy().ravel()                     # 每个时刻的 episode id
    n_joints = state.shape[1] - 1 if args.ignore_gripper else state.shape[1]
    ep_ids = sorted(set(epi_col.tolist()))                                     # 获取 episode id，去掉重复的 id

    ep_meta = pd.read_parquet(src / "meta" / "episodes" / "chunk-000" / "file-000.parquet")   # 每个 episode 的元信息
    ds_from_map = dict(zip(ep_meta["episode_index"], ep_meta["dataset_from_index"]))          # 每个 episode 中的帧的全局起始 id
    ds_to_map = dict(zip(ep_meta["episode_index"], ep_meta["dataset_to_index"]))              # 每个 episode 中的帧的全局结束 id

    # ------------------------------------------------- detect idle prefixes
    plan = []  # dicts: old_ep, trim_start, old_len, new_len, new_ep, drop_reason
    keep_idx = []
    new_ep_idx = 0
    for old_ep in ep_ids:
        rows = np.nonzero(epi_col == old_ep)[0]
        length = int(rows.size)
        delta = np.abs(np.diff(state[rows][:, :n_joints], axis=0)).sum(axis=1)
        total_disp = float(delta.sum())
        if total_disp < args.min_displacement:
            reason = (
                "never moves"
                if total_disp == 0
                else f"total displacement {total_disp:.1f} < {args.min_displacement}"
            )
            plan.append(
                dict(old_ep=old_ep, trim_start=None, old_len=length, new_len=0,
                     new_ep=None, drop_reason=reason)
            )
            continue
        onset = find_motion_onset(delta, args.onset_window, args.onset_displacement)  # 寻找到第一个连续 30 帧的总 displacement > onset_displacement
        trim_start = max(0, onset + 1 - args.buffer)  # 仍然保留 10 帧 idle frame
        new_len = length - trim_start
        if new_len < args.min_length:
            plan.append(
                dict(old_ep=old_ep, trim_start=trim_start, old_len=length, new_len=new_len,
                     new_ep=None, drop_reason=f"trimmed length {new_len} < {args.min_length}")
            )
            continue
        keep_idx.append(rows[trim_start:])   # 缓存所有保存下来的帧 id
        plan.append(
            dict(old_ep=old_ep, trim_start=trim_start, old_len=length, new_len=new_len,
                 new_ep=new_ep_idx, drop_reason=None)
        )
        new_ep_idx += 1

    n_episodes = new_ep_idx
    n_frames = sum(len(r) for r in keep_idx)
    dropped = [p for p in plan if p["drop_reason"]]
    print(f"Episodes kept : {n_episodes} / {len(ep_ids)} (dropped {len(dropped)})")
    print(f"Frames kept   : {n_frames} / {state.shape[0]}")
    for p in dropped:
        print(f"  dropped ep {p['old_ep']:>3}: {p['drop_reason']} (old_len={p['old_len']})")
    if args.dry_run:
        print("\n[dry-run] nothing was written.")
        return

    if out.exists():
        if args.overwrite:
            shutil.rmtree(out)
        else:
            raise FileExistsError(f"Output directory already exists: {out} (use --overwrite)")

    # --------------------------------------------------------------- write data
    keep_idx_flat = np.concatenate(keep_idx)
    new_tbl = data_tbl.take(pa.array(keep_idx_flat, type=pa.int64()))
    frame_index = np.concatenate([np.arange(len(r), dtype=np.int64) for r in keep_idx])   # 为每一帧数据生成其在对应的 episode 中的帧 id
    episode_index = np.concatenate(
        [np.full(len(r), i, dtype=np.int64) for i, r in enumerate(keep_idx)]              # 为每一帧数据生成其在对应的 episode id
    )
    index = np.arange(n_frames, dtype=np.int64)                                           # 为每一帧数据生成其全局 id
    timestamp = (frame_index / fps).astype(np.float32)                                    # 为每一帧数据生成其在对应的 episode 中的时间戳

    def set_col(tbl, name, arr):
        col = pa.array(arr).cast(tbl.schema.field(name).type)
        return tbl.set_column(tbl.schema.names.index(name), name, col)

    new_tbl = set_col(new_tbl, "frame_index", frame_index)        # 更新 frame_index
    new_tbl = set_col(new_tbl, "episode_index", episode_index)    # 更新 episode_index
    new_tbl = set_col(new_tbl, "index", index)                    # 更新 index
    new_tbl = set_col(new_tbl, "timestamp", timestamp)            # 更新 timestamp

    (out / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    pq.write_table(new_tbl, out / "data" / "chunk-000" / "file-000.parquet")
    print("Wrote data parquet.")

    # --------------------------------------------------------------- write videos
    av.logging.set_level(av.logging.WARNING)
    keep_map = {p["old_ep"]: p for p in plan if p["new_ep"] is not None}
    ep_video_stats = {key: {} for key in video_keys}  # key -> new_ep -> stats dict
    for key in video_keys:
        print(f"Re-encoding videos: {key}")
        vinfo = features[key]["info"]
        c_idx = f"videos/{key}/chunk_index"
        f_idx = f"videos/{key}/file_index"
        # Group over ALL episodes: a video file physically contains every episode
        # in its frame range, including dropped ones.
        files = (
            ep_meta.groupby([c_idx, f_idx], sort=True)
            .agg(episodes=("episode_index", list))
        )
        for (chunk, file), grp in files.iterrows():
            ep_list = grp["episodes"]
            # Global original row range covered by this video file.
            file_from = int(ds_from_map[ep_list[0]])
            file_to = int(ds_to_map[ep_list[-1]])
            # local frame index -> (new_ep, local frame index within the new video)
            route = {}
            for old_ep in ep_list:
                p = keep_map.get(old_ep)
                if p is None:  # dropped episode: decode its frames but skip them
                    continue
                start = int(ds_from_map[old_ep]) + p["trim_start"]    # 新片段在旧的视频中的起始帧的 id
                end = int(ds_from_map[old_ep]) + p["old_len"]         # 新片段在旧的视频中的结束帧的 id
                for k in range(start, end):
                    route[k - file_from] = (p["new_ep"], k - start)   # route_key: 原视频中的起始帧 id, route_value: [新 episode_id, 新视频中的帧 id]

            src_path = src / "videos" / key / f"chunk-{chunk:03d}" / f"file-{file:03d}.mp4"
            encoders = {}
            decoded = 0
            with av.open(str(src_path)) as container:    # 遍历视频中的每一帧
                stream = container.streams.video[0]
                for frame in container.decode(stream):
                    r = route.get(decoded)
                    if r is not None:
                        new_ep, local_i = r
                        enc = encoders.get(new_ep)
                        if enc is None:
                            enc = EpisodeVideoEncoder(
                                out / "videos" / key / "chunk-000" / f"file-{new_ep:03d}.mp4",
                                vinfo,
                                fps,
                            )
                            encoders[new_ep] = enc
                        enc.write_frame(frame, local_i)
                    decoded += 1
                    if decoded % 5000 == 0:
                        print(f"  {key}: {decoded}/{file_to - file_from} frames")
            if decoded != file_to - file_from:
                raise RuntimeError(
                    f"{src_path}: expected {file_to - file_from} frames, decoded {decoded}"
                )
            for new_ep, enc in encoders.items():
                ep_video_stats[key][new_ep] = video_stats_like_writer(enc.finish())
        print(f"  {key}: done ({len(ep_video_stats[key])} videos)")

    # ----------------------------------------------------- episodes meta + stats
    keep_p = [p for p in plan if p["new_ep"] is not None]
    ep_orig_rows = {int(r["episode_index"]): r for _, r in ep_meta.iterrows()}
    ep_rows = []
    ep_stats_list = []  # full per-episode stats (non-video + video), for stats.json
    offset = 0
    for p in keep_p:
        row = ep_orig_rows[p["old_ep"]].to_dict()
        row["episode_index"] = p["new_ep"]
        row["length"] = p["new_len"]
        row["data/chunk_index"] = 0
        row["data/file_index"] = 0
        row["dataset_from_index"] = offset
        row["dataset_to_index"] = offset + p["new_len"]
        offset += p["new_len"]
        for key in video_keys:
            row[f"videos/{key}/chunk_index"] = 0
            row[f"videos/{key}/file_index"] = p["new_ep"]
            row[f"videos/{key}/from_timestamp"] = 0.0
            row[f"videos/{key}/to_timestamp"] = p["new_len"] / fps
        row["meta/episodes/chunk_index"] = 0
        row["meta/episodes/file_index"] = 0

        # Per-episode stats over the trimmed data.
        sl = slice(row["dataset_from_index"], row["dataset_to_index"])
        ep_data = {
            "action": np.stack(new_tbl["action"].to_numpy())[sl],
            "observation.state": np.stack(new_tbl["observation.state"].to_numpy())[sl],
        }
        for name in ["timestamp", "frame_index", "episode_index", "index", "task_index"]:
            ep_data[name] = new_tbl[name].to_numpy().astype(np.float32).reshape(-1, 1)[sl]
        stats = compute_episode_stats(ep_data, non_video_features)
        for key in video_keys:
            stats[key] = ep_video_stats[key][p["new_ep"]]
        ep_stats_list.append(stats)
        for ft, ft_stats in stats.items():
            for sk in STAT_KEYS:
                row[f"stats/{ft}/{sk}"] = to_native(ft_stats[sk])
        ep_rows.append(row)

    new_ep_meta = pd.DataFrame(ep_rows, columns=list(ep_meta.columns))
    (out / "meta" / "episodes" / "chunk-000").mkdir(parents=True, exist_ok=True)
    new_ep_meta.to_parquet(out / "meta" / "episodes" / "chunk-000" / "file-000.parquet", index=False)
    print("Wrote meta/episodes.")

    # --------------------------------------------------------------- stats.json
    agg = aggregate_stats(ep_stats_list)
    stats_json = {ft: to_native(s) for ft, s in agg.items()}
    (out / "meta").mkdir(parents=True, exist_ok=True)
    with open(out / "meta" / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats_json, f)
    print("Wrote meta/stats.json.")

    # ---------------------------------------------------------------- info.json
    info["total_episodes"] = n_episodes
    info["total_frames"] = n_frames
    info["splits"] = {"train": f"0:{n_episodes}"}
    with open(out / "meta" / "info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=4)
    print("Wrote meta/info.json.")

    # --------------------------------------------------------------- tasks
    shutil.copy(src / "meta" / "tasks.parquet", out / "meta" / "tasks.parquet")
    print("Copied meta/tasks.parquet.")

    # ------------------------------------------------------------- trim report
    report = {
        "source": str(src),
        "output": str(out),
        "onset_window": args.onset_window,
        "onset_displacement": args.onset_displacement,
        "min_displacement": args.min_displacement,
        "buffer": args.buffer,
        "min_length": args.min_length,
        "ignore_gripper": args.ignore_gripper,
        "episodes_kept": n_episodes,
        "episodes_dropped": len(dropped),
        "frames_kept": n_frames,
        "frames_removed": int(state.shape[0] - n_frames),
        "episodes": [to_native(p) for p in plan],
    }
    with open(out / "meta" / "trim_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Wrote meta/trim_report.json.")

    # ---------------------------------------------------------------- verify
    check_tbl = pq.read_table(out / "data" / "chunk-000" / "file-000.parquet")
    assert check_tbl.num_rows == n_frames, "data row count mismatch"
    check_ep = pd.read_parquet(out / "meta" / "episodes" / "chunk-000" / "file-000.parquet")
    assert len(check_ep) == n_episodes, "episode count mismatch"
    assert (check_ep["length"].values == [p["new_len"] for p in keep_p]).all(), "length mismatch"
    for key in video_keys:
        for p in keep_p:
            vp = out / "videos" / key / "chunk-000" / f"file-{p['new_ep']:03d}.mp4"
            with av.open(str(vp)) as c:
                assert c.streams.video[0].frames == p["new_len"], f"{vp}: frame count mismatch"
    print(f"\nDone. Trimmed dataset written to {out}")
    print(f"  episodes: {n_episodes}, frames: {n_frames}")


if __name__ == "__main__":
    main()
