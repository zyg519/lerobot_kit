# GR00T LoRA（NVIDIA GR00T N1.7: Vision-Language-Action 基础模型）

> GR00T 论文: https://research.nvidia.com/labs/gear/gr00t/

<div align="center">

![Pi0](/tools/gr00t/assets/gr00t.png)

</div>

本目录提供 GR00T N1.7-3B 在 SO-101 机械臂上的 LoRA 微调与远程 rollout 工作流。与仓库内 pi0/smolvla 一致：
训练只保存 LoRA adapter（几 MB～几十 MB，基座全冻结），训练完成后用 `merge_lora_policy.py` 合并为完整 checkpoint 供部署使用。

## 01 数据采集

主从机械臂以及 front / hand_eye 相机连接本地主机后，复用 pi0 的采集与裁剪脚本：

```
bash tools/pi0/01_collect_data.sh
bash tools/pi0/02_idle_trim.sh
```

采集要求与 pi0 相同：动作流畅、删除失败 episode、删除 episode 开头的 idle 帧。

## 02 删除 leading idle frames
每个 episode 前的闲置静止的帧是有害的，需要删掉, 运行下述脚本删除
```
bash tools/pi0/02_idle_trim.sh
```

## 03 分布式 LoRA 训练

训练前下载 GR00T N1.7 基座权重，国内使用 ModelScope 较快：

```
pip install modelscope
modelscope download --model nv-community/GR00T-N1.7-3B

modelscope download --model nv-community/Cosmos-Reason2-2B
```

在 `01_dist_train.sh` 中把 `--policy.pretrained_path` 与 `--policy.base_model_path` 都配置为下载后的快照路径（默认配置了训练机上的 modelscope 缓存路径）。

在远程服务器（2×4090）上执行：

```
bash tools/gr00t/01_dist_train.sh
```

要点：

- LoRA 参数与 pi0/smolvla 一致：`--peft.method_type=LORA --peft.target_modules=all-linear --peft.r=8 --peft.lora_alpha=16`，
  即基座冻结、**全模型所有 Linear 层**（Qwen3-VL backbone + projector + DiT action head）挂 LoRA adapter。
- `--peft.target_modules` 可省略（GrootPolicy 已提供 all-linear 默认值），脚本中显式写出便于阅读。
- `--policy.tune_*` 系列开关在 LoRA 模式下不生效（no-op）；若希望某模块（如 projector）做全量微调，
  改用 `--peft.full_training_modules`（对应 PEFT 的 `modules_to_save`）。
- checkpoint 的 `pretrained_model/` 目录只含 `adapter_config.json` + `adapter_model.safetensors`，
  其中 `adapter_config.json` 记录了训练机上的基座路径（`base_model_name_or_path`）。

## 04 合并 LoRA 权重

远程服务器上的 `policy_server` 不加载 PEFT adapter，因此 rollout 前必须先合并：

```
python src/lerobot/scripts/merge_lora_policy.py \
    outputs/gr00t_lora_training_20260823_1/checkpoints/030000/pretrained_model \
    outputs/gr00t_lora_training_20260823_1/checkpoints/030000/merged_model \
    --policy-type groot
```

- 若在其他机器上合并，基座路径与训练机不一致时加 `--base-model <本机基座路径>`。
- 合并产物 `merged_model/` 含完整的 `model.safetensors`，且相机话题名保持训练配置（front/handeye）。

## 05 远程服务器和本地联动 rollout

在 `02_romote_rollout_server.sh` 配置好端口号、fps、inference_latency，在远程服务器上执行：

```
bash tools/gr00t/02_romote_rollout_server.sh
```

在 `03_remote_rollout_client.sh` 中确认 `--pretrained_name_or_path` 指向 **merged_model** 目录（见上一步），
在本地主机上执行：

```
bash tools/gr00t/03_remote_rollout_client.sh
```

## 备注

- 远程 rollout 服务端不支持直接加载 adapter 目录；如果 client 报 "找不到 model.safetensors"，请先执行第 04 步合并。
- 基座路径 `nv-community--GR00T-N1.7-3B` 为 ModelScope 镜像名，HuggingFace 原名为 `nvidia/GR00T-N1.7-3B`。
