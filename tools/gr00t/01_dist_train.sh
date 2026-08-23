#!/bin/bash

# ============================================================
# LeRobot 分布式微调 GR00T
# ============================================================

# 激活 .venv 环境
source .venv/bin/activate

# 或者激活 conda 环境
# conda activate lerobot

# 更新 Python 的模块搜索环境变量
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

OUTPUT_DIR="./outputs/gr00t_training_20260822_1"
LOG_DIR="${OUTPUT_DIR}_log"
mkdir -p "${LOG_DIR}"

torchrun \
    --nproc_per_node=2 \
    src/lerobot/scripts/lerobot_train.py \
    --policy.type="groot" \
    --policy.base_model_path="/home/zyg/.cache/modelscope/models/nv-community--GR00T-N1.7-3B/snapshots/master" \
    --policy.push_to_hub=false \
    --policy.tune_llm=false \
    --policy.tune_projector=true \
    --policy.tune_visual=true \
    --policy.tune_diffusion_model=false \
    --policy.tune_vlln=true \
    --policy.use_bf16=true \
    --policy.model_params_fp32=false \
    --dataset.repo_id="" \
    --dataset.root="/data/chenzhen/tmp/lerobot/data/grap_ball_20260815_175420_trim" \
    --job_name="gr00t_training" \
    --output_dir="${OUTPUT_DIR}" \
    --steps=30000 \
    --batch_size=2 \
    --num_workers=8 \
    --wandb.enable=false \
    --save_checkpoint=true \
2>&1 | tee "${LOG_DIR}/train.log"
