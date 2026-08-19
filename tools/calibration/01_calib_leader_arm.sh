#!/usr/bin/env bash

# ============================================================
# LeRobot 校准主臂
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
SCRIPT="${WORKSPACE_FOLDER}/src/lerobot/scripts/lerobot_calibrate.py"

# ============================================================
# 执行
# ============================================================
python "${SCRIPT}" \
    --teleop.type="so101_leader" \
    --teleop.port="COM22" \
    --teleop.id="leader_arm"