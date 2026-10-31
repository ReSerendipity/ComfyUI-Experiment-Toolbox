# 10 · 模型家族横评

测**「同一个家族文件夹内，换主模型权重」**这一个维度：家族内 text encoder / VAE /
latent / 采样器 / 调度器 / 步数 / cfg / shift 全部钉死，**唯一变量是 UNet 权重**。

## 与 03_受控跑测 的分工（互补，不替代）

| 模块 | 变量维度 | 典型问题 |
|---|---|---|
| `03_受控跑测` | **采样器 / 调度器**（模型不动） | 「euler+karras 会不会炸」「哪个调度器最稳」 |
| **`10_模型家族横评`** | **主模型权重**（采样参数不动） | 「同一文件夹里这三个 checkpoint 谁强」「量化格式差多少」「AIO 包 vs 底模差多少」 |

两者可以串联：先用 10 选出候选权重，再用 03 在候选上扫采样器。

## 三条命令

必须用 **ComfyUI 自带 python**（`%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\python.exe`），
因为要 numpy / Pillow，`--arch-probe comfy` 还要 import `comfy.*`。

```powershell
# ① 发现候选家族：扫 models/unet 子文件夹 → SHA256 去重 → 判定 eligible / skipped
python run.py fdiscover
python run.py fdiscover --min-unique 2 --arch-probe fingerprint

# ② 配置驱动跑测：先看计划（0 提交），再按家族分批
python run.py fbench --dry-run
python run.py fbench --calibration          # 每条链路 1 张，批量前置闸门
python run.py fbench --families FLUX-1-dev
python run.py fbench --all

# ③ 结果分析：指标 + 跨种子稳定性 + 家族拼版 + 评分表 + 报告骨架
python run.py fanalyze --out "%USERPROFILE%/model_benchmark/toolbox_acceptance/"
```

也可以直接跑本目录的脚本（`run.py` 只是转发 + 补 PYTHONPATH）：
`python 10_模型家族横评/bench_family.py --config 10_模型家族横评/family_config.json --dry-run`

## 配置编写法

复制 `family_config.example.json` → `family_config.json`，改这三处：

1. `comfy.comfy_root` —— ComfyUI 目录（含 `user/` 与 `models/`）。
2. `families.<文件夹名>` —— **键名必须等于 `models/unet` 下的子文件夹名**。
3. `families.<文件夹名>.weights` —— **留空 `[]` 即由 ① 自动填入**（已按 SHA256 去重）。

### 字段

| 字段 | 含义 |
|---|---|
| `workflow` | 相对 `comfy_root` 的路径，本模块只读打开，绝不写回 |
| `unet_folder` | `models/unet` 下的子文件夹名 |
| `weights` | 权重文件名数组；`[]` = 自动发现 |
| `chain` | 链路标签，仅用于报告分层与分组显示 |
| `clip_loaders` | 1 个条目 = `CLIPLoader`（用 `clip_name`）；2 个条目 = `DualCLIPLoader`（用 `clip_name1/clip_name2`） |
| `vae` / `latent_class` | VAE 文件名 / latent 节点类名 |
| `sampler` / `scheduler` / `steps` / `cfg` | 采样四要素，**家族内钉死** |
| `model_sampling` | `{"node":"ModelSamplingFlux","max_shift":…,"base_shift":…}` 或 `{"node":"ModelSamplingAuraFlow","shift":…}`；无则 `null` |
| `guidance` | `{"node":"FluxGuidance","value":4.0}`；无则 `null` |
| `negative_mode` | `zeroout` = `ConditioningZeroOut`；`real` = 注入 `negative.real_text` |
| `sample_chain` | `ksampler` / `custom_basic_guider` / `custom_cfg_guider`（仅报告用，实际由工作流里的节点决定） |
| `_container_edits` | 覆盖工作流子图容器的 positional 值，键是容器输入下标 |
| `weight_overrides` | **模型级例外**，见下 |

### W06 例外怎么写（真实案例）

`FLUX-2-klein-9b/Flux.2 Klein 9B fp8 darkBeast.safetensors` 被 ComfyUI 判为
`ZImage/Lumina2`（dim 3840、cap_feat_dim 2560），**不是 FLUX.2**。用 Klein 链路实测硬失败：

```
RuntimeError: Given normalized_shape=[2560], expected input with shape [*, 2560],
but got input of size[1, 512, 12288]
  traceback: comfy/ldm/lumina/model.py:660 embed_cap -> cap_embedder -> rms_norm
```

所以 `weight_overrides` 把它**整条链替换成 zimage**，并打 `declared_exception`：

```json
"weight_overrides": {
  "Flux.2 Klein 9B fp8 darkBeast.safetensors": {
    "_why": "架构实测为 ZImage/Lumina2，Klein 链路维度不兼容，故整条链替换为 zimage",
    "declared_exception": true,
    "chain": "zimage",
    "workflow": "user/default/workflows/Image/Z_image.json",
    "clip_loaders": [{"clip_name": "Z-image-turbo/qwen_3_4b_fp8_mixed.safetensors",
                      "type": "lumina2", "device": "default"}],
    "vae": "FLUX-1-dev + Z-image-turbo/ae.safetensors",
    "latent_class": "EmptySD3LatentImage",
    "sampler": "res_multistep", "scheduler": "simple", "steps": 25, "cfg": 4.0,
    "model_sampling": {"node": "ModelSamplingAuraFlow", "shift": 3.0},
    "negative_mode": "zeroout", "sample_chain": "ksampler"
  }
}
```

`declared_exception: true` 的权重会被 `analyze_family.py` 标为 **Stratum B**：
家族内统计**必须同时给「含例外 / 不含例外」两版**，且报告顶部挂例外横幅。
**不得**把例外权重与同族其他权重的差异表述成「同链路权重差异」。

## 输出结构

```
<out>/                                  默认 <comfy>/output/model_benchmark
├─ ledger.json                          断点续跑台账，实时落盘；已完成自动 SKIP
├─ <family>/<model>/<prompt>/s<seed>.png
│                          s<seed>.workflow.json   提交给 /prompt 的 API 图（原样）
│                          s<seed>.params.json     全部解析后参数 + prompt sha256
│                          s<seed>.result.json     prompt_id / 耗时 / cache_hit / error
```

## 评分口径

100 分制（`scoresheet.csv` 列名已固定）：

| 维度 | 分值 |
|---|---|
| A 提示词还原 | 30 |
| B 解剖 / 结构 | 20 |
| C 光影与材质 | 15 |
| D 细节与文字 | 15 |
| E 跨种子稳定性 | 10 |
| F 构图与审美 | 10 |

`metrics.json` 的亮度 / 对比度σ / 锐度 LapVar / 色彩度是**辅助参考**，不参与主观评分，
不能替代读图。`similarity.json` 的口径是**同模型同 prompt 跨种子**，
**禁止**把它的数字拿去跨架构 / 跨家族比像素。

## 重要陷阱（都是本机踩过的）

1. **「模型能否加载」必须在 ComfyUI 服务器进程语义下判定。**
   裸 `import comfy` 的独立进程里 `comfy.memory_management.aimdo_enabled` 停在 `False`，
   `load_torch_file` 会走严格的 `safetensors.safe_open`；而服务器在 `main.py` 里置 `True`，
   走容错的 `comfy_aimdo` ModelMMAP。同一文件前者报 `file not fully covered`、后者正常。
   → 判断可用性请走 `/prompt` 真实工作流，或在裸进程里复刻 `init_devices` 并置位该开关。
2. **每个家族的工作流都可能自带提示词改写器与批量读取器。**
   本模块 `prompt_enhance_off=true` 时会剪掉 `TextGenerate` / `ComfySwitchNode` 选路 /
   `BatchPromptReaderWithClip`（后者替换成空提示词编码，因为它输出 CONDITIONING，
   类型上接不到它的 CLIP 输入）。剪完会打印是否还有残留节点。
3. **只取原始 VAEDecode 输出。** 本模块会删掉 `PreviewImage` 分支，避免 SeedVR2
   2K 放大混进对比。
4. **同种子跨架构像素不可比。** 噪声生成器、调度器、latent 打包、VAE 全都不同，
   同 seed 产生的噪声张量逐元素无关。种子只用来固定方差、测同模型稳定性。

## 依赖

`numpy` + `Pillow`（ComfyUI 自带 python 已含）+ 标准库。
拼版标签用 `%WINDIR%\Fonts\msyh.ttc`（与 04 各脚本 `os.path.expandvars` 写法一致），缺失时自动退回 PIL 默认字体。

## 增补（2026-10-19）：十二类通用套件 + 增益对照纪律

- `prompts/suite_12_generic.json`：十二类通用能力面套件（写实/动漫/英文文字/中文竖排/产品/风景/计数/长提示词/国风/中英混排/抽象/建筑），每条带可验证断言（文字逐字引号锚定、计数写明数量、长提示词列 N 项约束）。与 `prompts/S1-S9`（风格×机位矩阵）互补：S 系管风格向横评，本套件管**新模型上手速查**——一轮 12 张即可定位强项与短板（文字渲染/计数/长提示词是多数新模型的分水岭项）。
- `docs/gain-ab-steady-state.md`：增益件 A/B 对照（唯一变量）、多种子复核阈值（~5% 级差异须 ≥3 种子）、稳态计时（批次首跑预热不进基准）、分辨率档位（同种子跨分辨率构图重排，比图必须重跑）、封面明度纪律（照片贴纸必须限定明度与内容）。
- 配套分析工具在 `04_结果分析/`：`text_grid.py`（色彩网格文本投影）、`light_audit.py`（明度审计）。
- 流程级 SOP：Agent-Knowledge 仓 `skills/model-eval-to-publish/`。

## 增补（2026-10-31）：四语文字渲染套件（覆盖矩阵第 16 条落地）

- `prompts/suite_text_4lang.json`：中/日/英/韩四语**同版式**海报，唯一变量是语言本身。每条 10 项逐字断言，跨 6 个字号层级（主标→副标→菜单品名/价格→印章→页脚），同时考字号区分、左右对齐、数字混排、标点处理。四语文案字符量级刻意对齐（中/日 4 字、英 17 字母、韩 6 音节），避免"某语言字多所以更难"的偏差。
- `docs/文字渲染四语横评.md`：九模型 × 四语 × 四种子（144 张）的实证与判读纪律——**种子必检**（比像素不比 MD5，`max=0` 说明参数被静默忽略）、**逐字核对用全宽裁切**（窄带会切掉草字头与韩文收音，实测制造 3 次误判）、**核心项加权评分**（错核心字扣 2、边角扣 1，等权会把两者抹平）、**稳定性三档**。
- 与 `suite_12_generic.json` 的分工：后者是"新模型上手速查"（一轮 12 张看强项短板），本套件是"字形先验的压力测试"（四语同版式，测在哪一档字号/哪一种文字系统上先崩）。`m03/m04/m10` 三条单点断言仍保留，互不替代。
- 落地口径：原矩阵第 16 条只写"非拉丁 + 多行"，实测发现单语单条测不出语言间差异，故扩成四语同版式；原表不改，仅在 `docs/覆盖矩阵设计.md` §4.1 表下加注记。
