#!/usr/bin/env bash

# ============================================================
# LeRobot 数据采集脚本
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 或者激活 conda 环境
# conda activate lerobot

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

# --- 工作目录（BASH_SOURCE[0] 当前正在运行脚本的路径，是 bash 内置变量）
WORKSPACE_FOLDER="$(cd "$(dirname $(dirname $(dirname "${BASH_SOURCE[0]}")))" && pwd)"
cd "${WORKSPACE_FOLDER}" || exit 1

# --- 入口脚本 ---
SCRIPT="${WORKSPACE_FOLDER}/src/lerobot/scripts/lerobot_record.py"

# --- 相机配置（YAML 风格，单引号包裹避免 shell 解析花括号）---
CAMERAS='{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, handeye: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}'

# --- H264 编码器额外选项（严格 JSON，单引号包裹, 单引号内部所有字符全部原样字面保留，不需要转义双引号）---
RGB_ENCODER_EXTRA='{"tune": "film", "profile:v": "high", "bf": 2}'

# ============================================================
# 执行
# ============================================================
python "${SCRIPT}" \
    --robot.type="so101_follower" \
    --robot.port="COM24" \
    --robot.id="follower_arm" \
    --robot.cameras "${CAMERAS}" \
    --teleop.type="so101_leader" \
    --teleop.port="COM22" \
    --teleop.id="leader_arm" \
    --dataset.repo_id="grap_ball" \
    --dataset.num_episodes="100" \
    --dataset.single_task="Grab the ball" \
    --dataset.streaming_encoding=true \
    --dataset.encoder_threads=2 \
    --dataset.rgb_encoder.vcodec=h264 \
    --dataset.rgb_encoder.preset=fast \
    --dataset.rgb_encoder.extra_options "${RGB_ENCODER_EXTRA}" \
    --dataset.push_to_hub false \
    --display_data true
