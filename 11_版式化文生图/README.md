# 11 · 版式化文生图

把「一张图」当**版面**来生成：一张图 = 一个完整信息载体（卡牌 / 海报 / 封面 / 界面 / 图纸）
或 N 个叙事画格（分镜页 / 四格 / 故事板）。核心不是画得好，是**版式与文字同时可控**。

本轨只做 MOSS-Image 一个模型，变量维度是**提示词结构**，不是采样参数也不是权重。

## 与前三条轨的分工

| 模块 | 变量维度 | 典型问题 |
|---|---|---|
| `03_受控跑测` | 采样器 / 调度器 | 「euler+karras 会不会炸」 |
| `10_模型家族横评` | 主模型权重 | 「同一文件夹三个 checkpoint 谁强」 |
| `05` + `08` | 工作流结构 | 「子图扁平化后喂 /prompt 还等不等价」 |
| **`11_版式化文生图`** | **提示词结构** | **「怎么让模型把 9 个格子和 8 段台词都画对」** |

结论内核在 `06_文档与结论/MOSS-Image-版式化文生图实测结论.md`；本目录只放工具与类型库。

## 三条命令

必须用 **ComfyUI 自带 python**，并且 ComfyUI 已在 `127.0.0.1:8188`。

```powershell
# ① 契约自检：三件套在 /object_info 里是否合法（避免静默无图）
python run.py lay --probe

# ② 出样张：列类型 / 跑全部 / 跑指定类型
python run.py lay --list
python run.py lay
python run.py lay tarot dossier

# ③ 自定义：写 recipe.json 交给驱动
python run.py layrun recipe.json
```

也可以直接跑本目录脚本（`run.py` 只是转发）：

```powershell
python 11_版式化文生图/gen_types.py --list
python 11_版式化文生图/layout_runner.py recipe.json
```

## 目录

| 文件 | 管什么 |
|---|---|
| `layout_types.py` | **类型库**：10 类版式骨架 + 完整中文提示词 + 推荐分辨率 |
| `layout_runner.py` | API 直连驱动：摊平子图 → 提交 `/prompt` → 轮询 `/history` |
| `gen_types.py` | 按类型库批量出样张 |
| `gen_variant.py` | 骨架复用演示：同骨架换主体与属性槽位 |
| `build_gallery.py` | 由类型库直接生成 `gallery.html`（提示词与实跑一致，不手抄） |
| `docs/版式化提示词七要素.md` | 方法论：什么样的提示词能让版式与文字同时成立 |
| `docs/类型库手册.md` | 10 类骨架速查表 |
| `docs/漫画分镜实战.md` | 用本轨做连贯短篇漫画的 SOP（角色一致性、分页、收尾） |
| `story/` | 实例短篇《末班车开往海见》：`story_data.py`（分镜与提示词）→ `gen_story.py`（生成落盘）→ `reader.html`（一页一屏阅读器） |
| `samples/` | 10 类样张（压缩 jpg，见下方入库策略） |
| `gallery.html` | 由类型库直接生成的画廊（含短篇漫画阅读区），`python run.py laygal` 重建 |

## 口径（2026-10-29 实测）

| 项 | 值 | 说明 |
|---|---|---|
| UNet | `MOSS-Image\moss_image_sft_int8_convrot.safetensors` | 组合框合法值必须带子目录前缀 |
| TE | `MOSS-Image\qwen3.5_9b_int8_convrot.safetensors`（`type=moss_image`） | 模板用 `w4a8_gptq`，本机 int8_convrot 可用 |
| VAE | `MOSS-Image\flux2-vae.safetensors` | 模板用 `_small`，完整版 latent 同空间 |
| 分辨率 | 宽高均为 **16 的倍数**，总像素 **1M–2M** 最佳 | 越界直接 `ValueError`，不静默 |
| steps / cfg | 30 / 4.0 | 官方模板默认 25 / 2.5；两者都能复刻成功 |
| sampler / scheduler | `euler` / `simple` | 模板默认 `er_sde` |
| 负向词 | `nsfw, worst quality, bad anatomy, watermark, jpeg artifact` | OpenMOSS 官方推荐 |
| SLG | 关（`slg=False`） | 开启时跳过层 22；动漫风格可能过曝 |

耗时参考（RTX 5070 Ti Laptop 12G，30 步）：1024×1536 ≈ 42s，800×1200 ≈ 30s，720×1280 ≈ 27s。

## 样张入库策略

`samples/` 只放**本轨原创**的 10 类样张，压缩为 jpg（quality 86，长边 ≤1200，合计约 1.9MB）。

复刻验证用的参考图与复刻图**不入库**：原图是 ModelScope AIGC 专区他人作品，
复刻图是他人作品的派生。口径与 `06_文档与结论/MOSS-Image-书法与诗画合一实测结论.md`
一致——只记结论与可复现口径，样张留在实验工作区。

## 已知边界

- **文字密度上限**：单图 8–12 个文字块可控；超过后小字号块开始出现笔画粘连。
- **跨格一致性**：同一页内多格的人物脸型会漂移；跨页一致性靠逐页复用同一段角色设定卡维持，
  不保证逐帧一致（T2I，无参考图输入）。
- **精确图形**：环形进度弧、条形码条纹这类「规则几何」容易被画成近似形。
- **开窗数 / 阵列数**：模型会按构图美观自行增减，必须用「数量固定为 N」这类硬约束压住。
