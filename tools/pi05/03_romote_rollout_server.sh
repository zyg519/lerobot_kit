#!/usr/bin/env bash

# ============================================================
# LeRobot Rollout server
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 或者激活 conda 环境
# conda activate lerobot


python -m lerobot.async_inference.policy_server \
--host=127.0.0.1 \
--port=2333 \
--fps=20 \
--inference_latency=0.05 \
--obs_queue_timeout=1