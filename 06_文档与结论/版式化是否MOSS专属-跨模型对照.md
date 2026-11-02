# 版式化是不是 MOSS-Image 专属？跨模型对照

> 2026-11-02 · 同一段版式化提示词、同一个 seed，换模型跑
> 工具：`11_版式化文生图/model_ab.py`；产物：`11_版式化文生图/samples_ab/`

## 结论先说

**不是专属。** 至少 Qwen-Image-2.1-turbo 在「标签级」和「段落级」两类版式上，
用**完全相同的提示词与 seed**，拿到了同等结构的成品，且快约 2.4 倍。

差异在**画面质感**，不在**版式与文字**。

## 对照口径

| 项 | MOSS-Image | Qwen-Image-2.1-turbo |
|---|---|---|
| UNET | `moss_image_sft_int8_convrot` | `qwen-image-2.1-turbo-int8-convrot` |
| 文本编码器 | `qwen3.5_9b_int8_convrot`（type=`moss_image`） | `qwen3-vl-8b-heretic-1.3.0_fp8`（type=`qwen_image`） |
| VAE | `flux2-vae` | `qwen_image_2.1_vae_bf16` |
| 潜空间节点 | `EmptyFlux2LatentImage` | `EmptySD3LatentImage` |
| 采样 | euler / 30 步 / CFG 4 / simple | euler / 8 步 / CFG 1.0 / simple + `ModelSamplingAuraFlow` shift 3.1 |
| 负向词 | 同一串（含「文字模糊，文字扭曲，伪汉字」） | 同左 |
| 提示词 | 逐字相同 | 逐字相同 |
| seed | 20261111（塔罗）/ 20261112（信息图） | 同左 |

参数不是调出来的：三件套与采样口径分别按各自官方模板给
（`image_moss_image_t2i.json` / `image_qwen_Image_2512.json`），Qwen 的步数按 turbo 口径下调。

## 实测两例

### 塔罗牌（标签级，768×1344）

| | MOSS | Qwen |
|---|---|---|
| 耗时 | 54.2 s | 21.0 s |
| 双线外框 + 四角星饰 | 有 | 有 |
| 顶部罗马数字 `XVII` | 正确 | 正确 |
| 八枚小星 + 中央大星 | 有 | 有 |
| 倾倒双水罐的女人 | 有 | 有 |
| 底部「星辰」+ `THE STAR · XVII` | 正确 | 正确 |
| 质感 | 厚涂、装饰画风、细节多 | 平涂、干净、色块明确 |

### 中文信息图（段落级，1024×1536）

| | MOSS | Qwen |
|---|---|---|
| 耗时 | 51.1 s | 21.3 s |
| 标题带 + 副标 | 正确 | 正确 |
| 四个等高区块 + 虚线分隔 | 有 | 有 |
| 阶段名 `01 种植` … `04 烘焙` | 正确 | 正确 |
| 正文两行说明 | 正确 | 正确 |
| 关键数字 `1900 M` / `100% 手采` / `72 H` / `210 °C` | 正确 | 正确 |
| 底部数据来源 + 制图日期 | 正确 | 正确 |
| 排版差异 | 说明文字换行更松、脚注居中 | 行距更紧、脚注左右分栏 |

## 这说明什么

1. **「版式是模型先验」这条不是 MOSS 独有。** 现代 T2I 普遍有「这是一张卡牌 / 一张信息图」
   的结构先验，所以第一句「整张…完整展示 / 四边与画面边缘平行」就能把它带进排版模式。
2. **「文字必须逐字注入」这条同样通用。** 两个模型拿到的都是同一份逐块写死的文字，
   结果都对；提示词结构是可迁移的资产，不是某个模型的补丁。
3. **真正的差距在画风。** 同一段提示词，MOSS 出厚涂装饰感，Qwen 出平涂干净感。
   如果作品要「厚涂电影感」（12 部短篇就是），换模型等于换画风，需要重出。

## 边界（别外推）

- 只测了 **2 个类型 × 1 个 seed × 2 个模型**，不是横评。
- 没测：小字号「标注级」（建筑立面图的尺寸标注）、`app_ui` 的图标细节、
  生僻字与长段落正文（>50 字）。
- 没测其他家族：FLUX-3-klein、Z-image-turbo、Krea2-turbo、MiniMax-H3 本机都有权重，
  加进 `model_ab.py` 的 `FAMILIES` 即可跑。
- 换家族必须重新确认三件套与潜空间节点，否则会静默无图（`status=success` 但 `outputs={}`）。

## 复现

```powershell
python 11_版式化文生图/model_ab.py --list
python 11_版式化文生图/model_ab.py tarot --seed=20261111
python 11_版式化文生图/model_ab.py infographic --seed=20261112
python 11_版式化文生图/model_ab.py magazine --models=moss,qwen --seed=20261113
```
