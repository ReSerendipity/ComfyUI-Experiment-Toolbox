# 模型家族横评 · 读图报告骨架

> 评分表 100 分制：A 提示词还原 30 / B 解剖结构 20 / C 光影材质 15 / D 细节与文字 15 / E 跨种子稳定性 10 / F 构图审美 10。
> 每一项必须写可观察证据，禁止以模型名气/参数量/文件名加权。

## 0. 家族清单与链路

| family | model | chain | declared_exception | 说明 |
|---|---|---|---|---|
| FLUX-1-dev | Flux-Capacity-NSFW-V2-fp8 | flux1 | 否 | |
| FLUX-1-dev | fluxNSFWUNLOCKED | flux1 | 否 | |
| FLUX-1-dev | pornworks-nude-people-photo-realistic-nsfw-flux-1d-checkpoint | flux1 | 否 | |
| FLUX-2-klein-9b | BigLoveKlein2_fp8 | flux2klein | 否 | |
| FLUX-2-klein-9b | DarkBeast-Klein9b-V2-BFS-FP8 | flux2klein | 否 | |
| FLUX-2-klein-9b | Flux.2 Klein 9B fp8 darkBeast | zimage | 是 | |
| Krea2-turbo | krea2TurboNSFWAIO_v10 | krea2 | 否 | |
| Krea2-turbo | krea2_turbo_fp8_scaled | krea2 | 否 | |

## 1. 家族内排名 · 双口径（必须同时给出）

### FLUX-1-dev

**口径 A（含例外权重，共 3 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| Flux-Capacity-NSFW-V2-fp8 |  |  |  |  |  |  |  |  |
| fluxNSFWUNLOCKED |  |  |  |  |  |  |  |  |
| pornworks-nude-people-photo-realistic-nsfw-flux-1d-checkpoint |  |  |  |  |  |  |  |  |

**口径 B（不含例外权重，共 3 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| Flux-Capacity-NSFW-V2-fp8 |  |  |  |  |  |  |  |  |
| fluxNSFWUNLOCKED |  |  |  |  |  |  |  |  |
| pornworks-nude-people-photo-realistic-nsfw-flux-1d-checkpoint |  |  |  |  |  |  |  |  |
### FLUX-2-klein-9b

**口径 A（含例外权重，共 3 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| BigLoveKlein2_fp8 |  |  |  |  |  |  |  |  |
| DarkBeast-Klein9b-V2-BFS-FP8 |  |  |  |  |  |  |  |  |
| Flux.2 Klein 9B fp8 darkBeast |  |  |  |  |  |  |  |  |

**口径 B（不含例外权重，共 2 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| BigLoveKlein2_fp8 |  |  |  |  |  |  |  |  |
| DarkBeast-Klein9b-V2-BFS-FP8 |  |  |  |  |  |  |  |  |

> 例外权重 Flux.2 Klein 9B fp8 darkBeast 使用不同链路，**不得**把其与同族其他权重的差异表述为「同链路权重差异」；其分数单列 Stratum B。

### Krea2-turbo

**口径 A（含例外权重，共 2 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| krea2TurboNSFWAIO_v10 |  |  |  |  |  |  |  |  |
| krea2_turbo_fp8_scaled |  |  |  |  |  |  |  |  |

**口径 B（不含例外权重，共 2 个）**

| model | 总分 | A | B | C | D | E | F | 硬门 |
|---|---|---|---|---|---|---|---|---|
| krea2TurboNSFWAIO_v10 |  |  |  |  |  |  |  |  |
| krea2_turbo_fp8_scaled |  |  |  |  |  |  |  |  |

## 2. 逐 prompt 跨模型排名

### S1

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S2

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S3

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S4

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S5

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S6

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S7

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S8

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|

### S9

| family | model | 总分 | 硬门 | 证据 |
|---|---|---|---|---|


## 3. 六维雷达（每模型一张）

- FLUX-1-dev / Flux-Capacity-NSFW-V2-fp8
- FLUX-1-dev / fluxNSFWUNLOCKED
- FLUX-1-dev / pornworks-nude-people-photo-realistic-nsfw-flux-1d-checkpoint
- FLUX-2-klein-9b / BigLoveKlein2_fp8
- FLUX-2-klein-9b / DarkBeast-Klein9b-V2-BFS-FP8
- FLUX-2-klein-9b / Flux.2 Klein 9B fp8 darkBeast
- Krea2-turbo / krea2TurboNSFWAIO_v10
- Krea2-turbo / krea2_turbo_fp8_scaled

## 4. 客观指标附录

见 metrics.json（亮度/对比度σ/锐度LapVar/色彩度）。
注意：这些是**辅助参考**，不参与主观评分，不能替代读图。

## 5. 跨种子稳定性附录

见 similarity.json。口径：**同模型同 prompt 跨种子专用**；跨架构/跨家族像素不可比，本报告不给出任何跨模型相似度数字。

## 6. 选型建议

- 综合首选：
- 速度首选：
- 文字渲染首选：
- 多人物首选：
- 成人内容首选：
- 显存最省：
