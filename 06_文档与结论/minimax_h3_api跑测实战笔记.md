# MiniMax H3 API 跑测实战笔记（2026-10-14/15 实测）

> 本文为 06_文档与结论 的**新增**篇目，不改动既有共享内核文件。
> 对应工具：`run.py h3dur`（= `03_受控跑测/run_h3_durations.py`）。
> 全部结论来自本机 ComfyUI-aki-v3.2 + `Video/video_minimax_h3_t2v.json` 实跑，非文档推测。

## 1. 工作流结构（新版子图格式）

`video_minimax_h3_t2v.json` = 顶层 6 节点 + `definitions.subgraphs[0]`（22 节点）：

- **容器节点 [105]**（type=子图 UUID）：widgets 注入 prompt/width/height/duration/noise_seed/unet_name/clip_name/vae_name×2
- **duration → 帧数链**：容器 `value_1`(秒, FLOAT) → [111] PrimitiveFloat → [107] ComfyMathExpression → [104] length(INT)
  ```
  frames = max(5, round(sec*24)) + (5 - (max(5, round(sec*24)) % 17)) % 17   # 17k+5 网格，24fps
  5s→124  8s→192  10s→243  11s→277  15s→362
  ```
  ⚠️ 手算 17k+5 极易错（如 10s 是 **243** 不是 244），以脚本 `frames_for()` 为准。
- **模型链**：UNETLoader → Lora(fl2v_turbo_4step, 1.0) → Lora(realism, 0.6) → SolAttentionPatch → FusedModulation → ChunkFeedForward → SpectrumPatch → BasicGuider；条件来自 [104] MiniMaxH3ImageToVideo(clip/vae/prompt/w/h/length) → CONDITIONING+LATENT
- **输出链**：SamplerCustomAdvanced → VAEDecode(视频) + VAEDecodeAudio(音频) → RTXVideoSuperResolution(2× ULTRA) → CreateVideo(fps=24) → SaveVideo

## 2. API 跑测方法（控制变量）

用 `01_工作流扁平化/flatten.py` 把 UI 工作流转 API prompt，`overrides` 按**原始数字 ID**覆盖：

```python
overrides = {
    104: {"length": 192, "width": 1344, "height": 768},   # MiniMaxH3ImageToVideo
    13:  {"clip_name": "<TE 文件名>"},                     # CLIPLoader 换 TE
    6:   {"unet_name": "<DiT 文件名>"},                    # UNETLoader 换 DiT
}
api, applied = flatten(workflow_path, overrides)
```

固定量（取自工作流原值）：DiT/TE/VAE/LoRA/patch 链/steps=8/res_multistep+simple/seed/prompt/2× ULTRA 超分。**换任何单一变量只改 overrides 一处**。

## 3. 踩坑记录（按严重度排序）

### P0-1 loader 文件名必须带子目录前缀
ComfyUI 0.39 的 UNETLoader/CLIPLoader/VAELoader/LoraLoader 的候选值是**相对 models/ 的路径**，扁平名直接 400 `value_not_in_list`：
```
unet_name = "MiniMax-H3\\10Eros_Max_h3_TURBO-hybrid_beta5_int8.safetensors"   # ✅
unet_name = "10Eros_Max_h3_TURBO-hybrid_beta5_int8.safetensors"               # ❌ 400
```

### P0-2 RTXVideoSuperResolution 的隐藏 required 参数
`strength`(FLOAT, 默认 1.0) 与 `image_encoding`(COMBO, 默认 "8-bit RGB") 在 UI 条件隐藏，但 API 提交是 **required**，缺一个 400 `required_input_missing`。

### P0-3 容器 positional 数组只含「有 widget 的输入」（flatten.py 已修复）
T2V 工作流的 first_frame/last_frame 是 IMAGE 口、**无 widget 标记、不占 positional 位**；flatten.py 原实现直接 `enumerate(sg["inputs"])` 对齐 pos，导致后续整体错位 2 位——症状：DiT 名被注入 VAE 输入、TE 名被注入 audio VAE 输入（仅类型守卫拦住两个数值位）。2026-10-15 修复：按顶层容器 inputs 的 widget 名集合过滤后再对齐。备份 `flatten.py.bak-20261015-121500`。

### P1-4 容器空 prompt 的语义
容器 `prompt=''` 时，前端语义是**不覆盖**内部链路值（子图 [104] 的详细 prompt 照常生效）；flatten 按链路注入空串。`run_h3_durations.py` 的做法：检测到容器空 prompt 时，从子图 [104] 的 named widgets 取原值 override（对齐前端）。

### P1-5 ComfyUI API 不注册子图 UUID
`/object_info` 查不到子图 UUID 节点类型，必须 flatten 成普通节点再提交（本仓 `flatten.py` 的职责）。

## 4. 显存边界表（RTX 5070 Ti Laptop，可用上限 11.91GB）

| 时长 | 帧数 | 可跑分辨率 | 超分后 | 实测耗时 |
|---|---|---|---|---|
| 5s | 124 | 1344×768 | 2688×1536 | 5.2 min |
| 8s | 192 | 1344×768 | 2688×1536 | 6.9 min |
| 10s | 243 | 1152×640 | 2304×1280 | 6.2 min |
| 11s | 277 | 960×544 | 1920×1088 | 4.9 min |
| 15s | 362 | 960×544 | 1920×1088 | 6.7 min |

- 失败样例：10s/11s/15s @1344×768（峰值 12.15-12.24GB > 11.91GB）；11s @1152×640（理论 11.85GB 可装，但碎片致 CUDA free=0）。
- **经验：理论余量 <0.1GB 时实际不可用，需预留 ≥0.3GB。**
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 对真实容量不足无帮助（仅缓解碎片）。
- 更长时长的解法只有降分辨率（latent 与 帧数×分辨率 成正比）或牺牲超分。

## 5. 模型选型结论（H3）

- **10Eros-Max**（HF `TenStrip/10Eros-Max`）：作者模型卡明确 **beta5 是唯一功能正常版**（beta3/4 损坏、beta6 测试中）；`TURBO-hybrid` = ref+fl 双 turbo delta 融合，一个文件覆盖 T2V/首尾帧 I2V/多参考 I2V。
- TE 解限三选一（显存占用仅在条件编码阶段）：abliterated_nvfp4（17.9GB）/ Ultra-Heretic int8_convrot（26.4GB，实测 5 档全过）/ 官方 nvfp4_awq（不解限）。
- DiT 无 fp4 档：10Eros 只有 int8/bf16/w4a8_14gb；官方 DiT 量化只有 int8_convrot。

## 6. 工具用法

```
python run.py h3dur --dry-run                    # 只出计划与 payload，0 提交
python run.py h3dur --only 8s_1344x768           # 单档
python run.py h3dur --te "MiniMax-H3\\qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors"
python run.py h3dur --dit "MiniMax-H3\\<unet_name>.safetensors"
python run.py h3dur --workflow <wf.json>
```
日志：`03_受控跑测/h3_duration_logs/result_log.jsonl`（append-only 唯一事实源）+ `result_log.json`（合并视图，由 jsonl 重建）。
