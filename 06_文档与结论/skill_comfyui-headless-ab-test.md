---
name: comfyui-headless-ab-test
description: 在无人值守（headless）模式下启动本机 ComfyUI，做**控制变量对照实验**（固定提示词与种子，每轮只变一个维度：采样器 × 调度器、steps、cfg、LoRA 强度等），产出逐组输出图 + 客观指标 + 结论并记录到 Markdown。也支持把工作流当参数矩阵跑。适用于 ComfyUI-aki-v3 的新版 `definitions.subgraphs` 子图格式工作流——这类工作流无法直接喂给 `/prompt`，必须先扁平化为 API prompt。触发词：批量出图、参数对比、控制变量、对照实验、采样器对比、调度器对比、A/B、矩阵测试、headless、API 提交、subgraph 扁平化、ComfyUI 自动化。
agent_created: true
---

# ComfyUI Headless 参数矩阵 A/B 测试

用于「固定大部分参数、只扫一两个变量、逐组出图并总结差异」这类任务。已在 Qwen-Image 2.1 / ComfyUI 0.37.0 / Windows 上验证。

## 0. 先分清路线：控制变量对照实验 ≠ 批量生成

**默认走控制变量路线**（提示词与种子固定成常量，每轮只变一个维度），只有在需要"一次跑很多不同提示词"时才走批量路线。两者不可混用：

| | 控制变量对照（默认） | 批量生成 |
|---|---|---|
| 提示词 | **固定单一常量**（写进工作流容器控件） | 一次多个，来自 `input/Picture/*.txt` |
| 种子 | **固定** | 常随机 |
| 变化项 | 每轮只变一个维度（采样器／调度器／steps…） | 提示词是变量 |
| 对照方式 | 同模型自身配置为基线，比相似度 + 相对指标变化 | 无对照 |
| 适用 | 参数 A/B、模型横向对比 | 出素材、跑提示词集合 |

**控制变量路线的硬性要求**：工作流子图里的 `BatchPromptReaderWithClip`（批量提示词读取器，从 `input/Picture/*.txt` 取文本）**必须旁路**，改为注入受控的单一提示词。原因：① 留着它提示词就不受控，实验失效；② 目录为空时直接报错，任务跑不起来。

> 处理方式：该节点的输出是 **`CONDITIONING`**（它自己拿 `clip` 去编码文件里的文本），通常接给 `ConditioningZeroOut → CFGGuider.negative`。因此**不能**把它的下游接到它的 `clip` 输入（类型不符：CLIP ≠ CONDITIONING）。正确做法是**删掉它，并新建一个 `CLIPTextEncode`（`clip` 取自它原来的 clip 来源、`text=""`）接到原下游**。

## 0. 铁律

- **不修改用户的工作流文件**。所有改动只发生在内存里的 API prompt 副本上；产物写到独立输出目录。
- **改前必备份**（若确实要改磁盘文件）：`shutil.copy2(src, src + ".bak-<时间戳>")`。
- 输出文件名要能反查组合，例如 `filename_prefix = "ab_test/06_res_multistep_beta"`。
- 结论必须「实测现象 + 客观指标 + 人眼核对」三者对齐，禁止只凭指标或只凭印象下结论。

## 1. 启动服务

```bash
cd "%USERPROFILE%/APP/ComfyUI-aki-v3"
python/python.exe -s ComfyUI/main.py --port 8188 --disable-auto-launch --disable-comfy-compiler \
  > "<输出目录>/comfyui_server.log" 2>&1
```

- 用 `run_in_background=true` 启动；启动约 15~30 秒，轮询 `curl -s http://127.0.0.1:8188/system_stats` 直到返回 JSON。
- `--disable-comfy-compiler` 是用户既有安全配置（规避 comfy-aimdo malloc graph 崩溃），批量跑测时保留。
- 先探测是否已在运行，避免重复起进程抢显存。

## 2. 校验（务必做，几分钟省下几十分钟）

```bash
curl -s http://127.0.0.1:8188/object_info/KSampler
```

从 `/object_info/<节点名>` 拿到**权威**信息：
- `input.required.<key>[0]` 若是 list → 该参数的合法取值全集（采样器 45 个 / 调度器 9 个，别照抄文档，以服务端为准）。
- 节点入参名与是否 required / optional（缺 required 会在提交时返回 `node_errors`）。
- 顺手校验 `unet_name` / `clip_name` / `vae_name` 的合法值里**确实包含**工作流写的那串路径（含子目录反斜杠形式）。

## 3. 子图工作流扁平化（关键步骤）

`/prompt` 只吃 API 格式。新版工作流是 `{nodes, links, definitions.subgraphs}`，**backend 不会自己展开子图**，必须自己扁平化：

1. 顶层找 `type` 为 UUID（含 `-` 且长度 > 30）的节点 → 子图容器；在 `definitions.subgraphs` 里按 `id` 找同名定义。
2. **容器 output 映射**：子图定义里的 `-20` 是虚拟输出槽。`sg.outputs[i].linkIds` → 找到 `target_id == -20 && target_slot == i` 的 link，其 `origin_id` 就是「容器第 i 个输出真正来自哪个内部节点」。**顶层只连了 output 0 时，其他分支（如挂着的放大/后处理）可以直接丢弃**，不必执行。
3. **容器 input 映射**：`-10` 是虚拟输入槽。`sg.inputs[i].linkIds` → 找到 `origin_id == -10 && origin_slot == i` 的 link，`target_id / target_slot` 即「容器第 i 个 widget 注入到哪个内部节点的第几个入参」。
   - ⚠️ **容器 widget 名与内部语义可能错位**：实测 Qwen 2.1 模板里容器 input 叫 `scheduler` 的其实是 sampler_name，`scheduler_1` 才是 scheduler。**一律以 `target_slot` 对齐目标节点的真实入参顺序**（KSampler 顺序：model, positive, negative, latent_image, seed, steps, cfg, sampler_name, scheduler, denoise）。
4. **`mode: 4` = bypass**：删除该节点并保留下游连线。**必须递归解析**——bypass 节点会成链（本例 UNETLoader → 6 个 bypass LoRA → KSampler），若按顺序边删边改，链上第二个节点会指向已删节点而断线。正确做法：先定义 `resolve(v)` 沿 bypass 链回溯到非 bypass 源，**全部重写完再删节点**；若链首本身未连线（如 bypass 的 LoRA 输入空着），兜底把 `model` 直接接到 UNETLoader。
5. 内部节点 ID 统一加偏移（如 +1000，多子图再 +1000）防止与顶层 ID 撞号。
6. 顶层还需补上真正落盘的节点（如 `SaveImageAdvanced` / `SaveImage`），其 `images` 入参指向映射后的内部节点。

**两个必踩的坑（已实测）**：

- ⚠️ **「既是 widget 又被连线」的输入仍占一个位置值。** 只要输入的 `inputs[i].widget` 存在，就要从 `widgets_values` 里消耗一个位置值（即使它同时带 `link`）——ComfyUI 把已连线的 widget 值也照常序列化作为回退值。正确流程是「先按 widget 顺序填满，再用 links 覆盖」。若按 `link is not None` 跳过，会导致**整条 widget 序列整体错位**（如 `denoise` 拿到 `'euler'`、`cfg` 丢失）。
- ⚠️ **容器经 `-10` 注入的输入也带 link**，同理必须计入 widget 位置，不能当普通连线跳过。

**提示词增强开关（新版官方模板常见）**：Krea2 等模板内有 `TextGenerate`（LLM 扩写提示词）+ `ComfySwitchNode` 选路，容器把它暴露成 `prompt_enhance`。做单一变量对比时**必须关掉**（容器 positional 里那个布尔值），否则提示词被 LLM 改写，变量不唯一。并且——**不能直接把 `ComfySwitchNode` 删掉**，因为它同时承担 model / prompt 的选路（如 `enable_lora` 开关），删掉会断 `model` 链。正确做法：先把开关解析成「某个非 LLM 上游直连下游」，再删开关与 LLM 链，最后清理悬空连线。

**run 之前先做单组提交校验**：`POST /prompt` 的响应里 `node_errors` 为空才算通。常见报错 `required_input_missing: model` 基本就是 bypass 链断线。

参考实现（可直接复用）：`ss_test\flatten.py`（通用扁平化器）+ `ss_test\run_models.py`（多模型跑测）。

**提交前先单跑一组验证**，看 `/prompt` 返回的 `node_errors` 是否为空：

```python
# POST /prompt  {"prompt": <api_prompt>}
# 期望: {"prompt_id": "...", "number": 0, "node_errors": {}}
```

## 4. 批量跑测

- 逐组构造 prompt → `POST /prompt` → 轮询 `GET /history/<prompt_id>` 直到 `status.completed`。
- 直接**连续提交**即可，ComfyUI 自带队列；不必等前一组结束再提交下一组。
- 跑测脚本支持 `FROM=<组合名>` 环境变量断点续跑，避免中途重启后重跑已完成组合。
- 记录项：组合名、采样器、调度器、墙钟耗时、产物文件名、错误信息。写成 JSON 便于后续汇总。
- 单组 1024² / 25 步 / Qwen int8 约 18~22 秒（5070 Ti Laptop）；首个任务含模型加载 +5~10 秒。**采样器耗时差异可达 2 倍**（heun / euler_cfg_pp / dpmpp_2s_ancestral 约 34~36s，euler / uni_pc_bh2 / er_sde 约 18s）——二阶及以上每步多次模型评估。

## 5. 结果汇总

1. 把 ComfyUI `output/<prefix>/` 下的图复制到独立目录，命名 `<组合名>__<原名>.png`。
2. **客观指标**（用 ComfyUI 的 python，有 numpy/Pillow）：亮度（灰度均值）、对比度（灰度 σ）、锐度（Laplacian 方差）、色彩度（Hasler-Süsstrunk）。
3. **两两相似度**：灰度缩到 128px → `1 - MSE/255²`。用于证明「哪些组合实际等价」——指标接近 1.0 即肉眼难分。
4. **带标签拼版图**（4 列网格）供人眼整体扫读；再挑 3~4 张关键结果做**大图并排聚焦对照**。
5. 报告用中文，含：测试约束表（明确写出「哪些参数固定未动」）→ 逐组结果总表（含耗时与指标）→ 按"干净可用 / 异常 / 换构图"分组的效果差异 → 含补充验证证据链的结论 → 产物清单。

## 6. 离线验证调度器（不跑图，先算 σ 曲线）

**在花时间跑图之前，先用纯计算筛掉注定要坏的调度器。** 尤其对 flow matching 模型（Qwen-Image / Z-Image / FLUX 系），σ 范围只有 [0,1]，社区里为 DDPM 设计的调度器套上去形状会完全变味。

```python
import sys; sys.path.insert(0, r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI")
import comfy.model_sampling as msmod, comfy.samplers as S

class Cfg:  # ← 取自 comfy/supported_models.py 里对应模型的 sampling_settings
    sampling_settings = {"multiplier": 1.0, "shift": 0.69}   # QwenImage21 @1024²
ms = msmod.ModelSamplingDiscreteFlow(Cfg())          # DDPM 系模型改用 ModelSamplingDiscrete
for sched in S.SCHEDULER_NAMES:
    sig = [float(x) for x in S.calculate_sigmas(ms, sched, 25)]
```

必看的三个量：

| 指标 | 判据 |
|---|---|
| **高噪声区步数**（σ > 0.5σ_max） | ≥10 步才安全；≤4 步基本判死（这是定大结构的阶段） |
| **首步 Δσ** | > 0.15σ_max 基本判死；一阶采样器误差 ~O(Δσ²)，首步大 3 倍 → 误差约 9 倍 |
| **末步前 σ → 0 的跳变** | **与画质无关，不要看这个**。flow 采样器在 `sigmas[i+1]==0` 时直接取 denoised 不做积分（`comfy/k_diffusion/sampling.py`），所以末步跳变再大也不产生误差 |

同时记住 `timestep(σ) = σ * multiplier`：**flow 模型（multiplier=1.0）的时间轴就是 σ**，所以 Δσ 就是模型感受到的步长。

**调度器的两种实现（`comfy/samplers.py` `SCHEDULER_HANDLERS`）**：
- `use_ms=True`（simple / sgm_uniform / beta / normal / ddim_uniform / linear_quadratic）→ σ 取自**模型自身的 training σ 表** → 一般安全；
- `use_ms=False`（karras / exponential / kl_optimal）→ 只用 σ 的两个端点套通用公式（karras 来自 EDM，rho=7）→ **在 flow 模型上要单独验算**。

已实测案例（Qwen-Image 2.1，σ∈[0.00069,1.0]，shift=0.69，25 步）：`karras` σ>0.5 仅 4 步、首步 Δσ=0.174（simple 的 3.1 倍）→ 严重重影；`exponential` 3 步 / 0.262 → 更激进。50 步时 karras 首步 Δσ 减半到 0.089 → 重影基本消失。

## 7. 常见坑

- **不同 `ModelType` 的 σ 曲线要各算各的**：`QwenImage`/`Krea2`/`Flux`/`Flux2` 在源码里传的都是 **`ModelType.FLUX` → `ModelSamplingFlux`（σ 表 10000 点）**；只有 `ModelType.FLOW`（Z-Image / Lumina2）走 `ModelSamplingDiscreteFlow`（σ 表 1000 点）；MiniMax H3 是 `FLOW_AV` → `ModelSamplingAV`。**混用会把 σ_min 算错 3 倍多。**
- **工作流里的 `ModelSampling*` 节点会覆盖类的默认 shift**：如 Z_image_turbo 有 `ModelSamplingAuraFlow(shift=3)`、flux.1-dev 有 `ModelSamplingFlux(1.15/0.5)`。算 σ 前先确认工作流里有没有这类节点。
- **结论方向别猜，去算**：本例 09-22 凭实测现象推断 karras「低噪声区步数不足」，09-23 离线算 σ 曲线发现**恰好相反**（karras 把 14/25 步给了低噪声区，是全场最多；真正的问题是高噪声区只有 4 步、首步跨度过大）。**能离线算的量绝不要靠推断下结论。**
- **超参冲突要三处对齐**：子图容器的 positional `widgets_values` / `widgets_values_named` / 子图内部节点自身 widgets 可能三份各不相同。生效规则取决于前端设置 `Comfy.Workflow.NamedValuesRestore`（默认 false → positional 生效）。**读运行时真值只读容器 positional。**
- **给多份工作流做「单一变量」对比时，要先统一提示词与种子**，并逐个检查是否藏有 LLM 提示词增强（会改写提示词）或批量提示词读取器（提示词不受控）。统一时 positional 与 named 两处都要写。
- **容器 positional 可能是损坏的，注入前要类型守卫**：本例 `flux.1-dev.json` 的容器 `height` 位置被塞进了一个 UNET 文件名（`widgets_values_named` 从 `cfg` 起整体错位一格），导致该工作流在 UI 里也跑不起来。做法：注入前比较「目标输入原有值」与「容器给的值」类型，若原本是数值而容器给了非数值字符串，就不注入、保留原值，并打印警告。**这类损坏值得报给用户并（备份后）修复文件**，因为它是全局性故障、不只是本次实验的问题。

- **`node_errors` 里报缺 required 入参**：如 `TextEncodeQwenImage21` 的 `images`（COMFY_AUTOGROW_V3）在 API 里可以不给；但若报错就补空值。
- **`COMFY_DYNAMICCOMBO_V3`（如 SaveImageAdvanced 的 format）**：按 `widgets_values_named` 的扁平键名给，即 `format` + `format.bit_depth` + `format.input_color_space`。
- **指标异常必须回头看图**：本例 karras 组对比度只有基线一半，看图后确认是「双重曝光鬼影」这种结构性缺陷，而不是简单的"对比度低"。
- **异常若整组复现 → 变量是调度器/采样器整体行为，不是个例**；此时加一组「改变另一个维度（如 steps）」的补充验证来定位根因，而不是猜。
- 跑测结束后 ComfyUI 仍在运行，要在报告里说明，由用户决定是否关闭。
