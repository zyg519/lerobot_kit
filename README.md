<div align="center">
  <h1>基于 Lerobot 和 SO-ARM101 机械臂学习 VLA</h1>
  <!-- <p><strong></strong></p> -->
  <!-- <p>基于 Lerobot 和 SO-ARM101 机械臂学习 VLA</p> -->

  <a href="https://github.com/yourname/explain_module"><img src="https://img.shields.io/badge/Lerobot-0.6.2-2ea45f" alt="Lerobot-verison"></a>
  <a href="https://github.com/yourname/explain_module"><img src="https://img.shields.io/badge/Pi0-=white" alt="Manifest V3"></a>
  <br>
  <a href="README_EN.md">English</a>
</div>

## 硬件需求

### 机器人
淘宝京东可买，价格 2000 左右，可以自行搜索。建议自己买四根 USB 延长线(follower arm，leader arm，front camera，hand-eye camera)
- SO‑101 Follower arm ×1 (Feetech servo motors)
- SO‑101 Leader teleop arm ×1
- 2 × USB cameras (front view + hand‑eye view)
- 4 x USB extension cables($\leq 2\text{m}$)

---

### 相机规格
只是为了测试学习算法，相机也无需买特别好的，满足下述配置即可
- Resolution recommendation: 640×480, ≥30fps

---

### 主机配置

笔者使用 Lora 微调，训练模型所使用的远程服务器配置如下：<br>

| Type | Specifications |
|---|--|
|CPU| Intel(R) Xeon(R) Platinum 8347C CPU @ 2.10GHz |
|RAM| 64 G |
|GPU| 2 x 4090@24G
|||

笔者采集数据与模型推理所使用的本地设备配置如下：<br>
| Type | Specifications |
|---|--|
|CPU| Intel i914900kf |
|RAM| 32 G |
|GPU| 1 x 4080ti@16G
|||

## 安装环境
使用 conda 或者 uv 配置环境都可以，二者选一, 不建议使用 wsl，推荐纯 windows 环境或者纯 Linux 环境。笔者的远程服务器是 ubuntu22.04，本地设备因为要玩游戏所以是 windows。
### conda 
```
conda create -y -n lerobot python=3.12
conda activate lerobot

git clone 
```

