#!/bin/bash

# ============================================================
# LeRobot 分布式微调 SmolVLA
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 或者激活 conda 环境
# conda activate lerobot

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

OUTPUT_DIR="./outputs/smolvla_training_20260820_1"
LOG_DIR="${OUTPUT_DIR}_log"
mkdir -p "${LOG_DIR}"

torchrun \
    --nproc_per_node=2 \
    src/lerobot/scripts/lerobot_train.py \
    --policy.type="smolvla" \
    --policy.pretrained_path="/home/zyg/.cache/modelscope/models/lerobot--smolvla_base/snapshots/master" \
    --policy.push_to_hub=false \
    --policy.compile_model=false \
    --policy.freeze_vision_encoder=false \
    --policy.train_expert_only=false \
    --dataset.repo_id="" \
    --dataset.root="/data/chenzhen/tmp/lerobot/data/grap_ball_20260815_175420_trim" \
    --job_name="smolvla_training" \
    --output_dir="${OUTPUT_DIR}" \
    --steps=30000 \
    --batch_size=4 \
    --num_workers=8 \
    --wandb.enable=false \
    --save_checkpoint=true \
2>&1 | tee >(awk '/loss/ {print}' >> "${LOG_DIR}/train.log")
