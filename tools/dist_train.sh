#!/bin/bash

export PYTHONPATH="${PWD}:${PYTHONPATH}"
export HF_ENDPOINT="https://hf-mirror.com"

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
    --dataset.root="/data/chenzhen/tmp/lerobot/data/grap_ball_20260815_175420" \
    --job_name="pi0_training" \
    --output_dir="./outputs/pi0_training_20260815_1" \
    --peft.method_type="LORA" \
    --peft.r=8 \
    --peft.lora_alpha=16 \
    --steps=30000 \
    --batch_size=8 \
    --num_workers=8 \
    --wandb.enable=false \
    --save_checkpoint=true
