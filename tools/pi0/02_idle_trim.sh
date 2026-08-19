#!/usr/bin/env bash

# ============================================================
# LeRobot 清除 leading idle frames
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

# --- 工作目录（BASH_SOURCE[0] 当前正在运行脚本的路径，是 bash 内置变量）
WORKSPACE_FOLDER="$(cd "$(dirname $(dirname $(dirname "${BASH_SOURCE[0]}")))" && pwd)"
cd "${WORKSPACE_FOLDER}" || exit 1

# --- 入口脚本 ---
SCRIPT="${WORKSPACE_FOLDER}/src/lerobot/scripts/lerobot_trim.py"


# if you  want to trim dataset directly, uncomment the following code
python "${SCRIPT}" \
    "D:/worksp/data/grap_ball_20260815_175420" \
    --output="D:/worksp/data/grap_ball_20260815_17542_test"

# if you want to test script，uncomment the following code
# python "${SCRIPT}" \
#     "D:/worksp/data/grap_ball_20260815_175420" \
#     --output="D:/worksp/data/grap_ball_20260815_17542_test" \
#     --dry-run