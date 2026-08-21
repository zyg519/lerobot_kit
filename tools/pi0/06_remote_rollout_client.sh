#!/usr/bin/env bash

# ============================================================
# LeRobot Rollout
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
SCRIPT="${WORKSPACE_FOLDER}/src/lerobot/async_inference/policy_server.py"

# --- 相机配置（YAML 风格，单引号包裹避免 shell 解析花括号）---
CAMERAS='{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, handeye: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}'


# if you want to inference in sync mode, uncomment the following code
# python "${SCRIPT}" \
#     --strategy.type="base" \
#     --policy.path="D:\\worksp\\projects\\lerobot\\outputs\\pi0_training_20260817_1\\checkpoints\\030000\\pretrained_model" \
#     --policy.dtype="bfloat16" \
#     --inference.type="sync" \
#     --robot.type="so101_follower" \
#     --robot.port="COM24" \
#     --robot.id="follower_arm" \
#     --robot.cameras=${CAMERAS}\
#     --task="Grab the ball" \
#     --device="cuda" \
#     --duration="1000" \
#     --fps="10"
#     # --display_data="true",
#     # --display_mode="rerun"


# if you want to inference in rtc mode, uncomment the following code
python -m "${SCRIPT}" \
    --policy_type="pi0" \
    --pretrained_name_or_path="/data/chenzhen/tmp/lerobot/outputs/pi0_training_20260817_1/checkpoints/030000/pretrained_model" \
    --robot.type="so101_follower" \
    --robot.port="COM24" \
    --robot.id="follower_arm" \
    --robot.cameras=${CAMERAS}\
    --actions_per_chunk=50 \
    --task="Grab the ball" \
    --policy_device="cuda" \
    --client_device=cpu \
    --chunk_size_threshold=0.5 \
    --aggregate_fn_name="weighted_average" \
    --duration="1000" \
    --server_address=127.0.0.1:2333
    # --display_data="true",
    # --display_mode="rerun"