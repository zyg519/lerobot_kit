#!/bin/bash

# ============================================================
# LeRobot 分布式 Lora 微调 Pi0
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

OUTPUT_DIR="./outputs/pi0_training_20260817_1"
LOG_DIR="${OUTPUT_DIR}_log"
mkdir -p "${LOG_DIR}"

torchrun \
    --nproc_per_node=2 \
    src/lerobot/scripts/lerobot_train.py \
    --policy.type="pi0" \
    --policy.pretrained_path="/home/zyg/.cache/modelscope/models/lerobot--pi0_base/snapshots/master" \
    --policy.push_to_hub=false \
    --policy.compile_model=false \
    --policy.gradient_checkpointing=true \
    --policy.dtype=bfloat16 \
    --policy.freeze_vision_encoder=false \
    --policy.train_expert_only=false \
    --dataset.repo_id="" \
    --dataset.root="/data/chenzhen/tmp/lerobot/data/grap_ball_20260815_175420_trim" \
    --job_name="pi0_training" \
    --output_dir="${OUTPUT_DIR}" \
    --peft.method_type="LORA" \
    --peft.target_modules="all-linear" \
    --peft.r=8 \
    --peft.lora_alpha=16 \
    --steps=30000 \
    --batch_size=4 \
    --num_workers=8 \
    --wandb.enable=false \
    --save_checkpoint=true \
2>&1 | tee "${LOG_DIR}/train.log"
