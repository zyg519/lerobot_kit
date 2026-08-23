#!/bin/bash

# ============================================================
# LeRobot 分布式 Lora 微调 GR00T
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 或者激活 conda 环境
# conda activate lerobot

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

# LoRA 模式下基座参数全部冻结，下方 tune_* 开关不生效（no-op）；
# 如需对某模块（如 projector）做全量微调，改用 --peft.full_training_modules。
OUTPUT_DIR="./outputs/gr00t_lora_training_20260823_1"
LOG_DIR="${OUTPUT_DIR}_log"
mkdir -p "${LOG_DIR}"

torchrun \
    --nproc_per_node=2 \
    src/lerobot/scripts/lerobot_train.py \
    --policy.type="groot" \
    --policy.pretrained_path="/home/zyg/.cache/modelscope/models/nv-community--GR00T-N1.7-3B/snapshots/master" \
    --policy.base_model_path="/home/zyg/.cache/modelscope/models/nv-community--GR00T-N1.7-3B/snapshots/master" \
    --policy.push_to_hub=false \
    --policy.use_bf16=true \
    --policy.model_params_fp32=false \
    --dataset.repo_id="" \
    --dataset.root="/data/chenzhen/tmp/lerobot/data/grap_ball_20260815_175420_trim" \
    --job_name="gr00t_lora_training" \
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
