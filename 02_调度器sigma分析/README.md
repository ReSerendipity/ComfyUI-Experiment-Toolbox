# 02 调度器 sigma 分析（离线，不跑图）

**解决什么问题**：换了个模型，想知道哪些调度器能用、哪些会翻车 —— **不用跑图**，直接算 σ 曲线就能判。这是本包最高性价比的一块。

| 文件 | 功能 | 使用方式 | 适用场景 | 依赖 |
|---|---|---|---|---|
| **`sigma_matrix.py`** ★ | 多模型风险矩阵：对预设的每个模型 × 9 个调度器，算出「首步 Δσ」「首步 Δσ%」「高噪声区步数」「末步前 σ」，并按判据标出 `高危 / 注意 / 安全` | `python sigma_matrix.py`<br>改顶部 `MODELS` 增删模型 | 新模型/新工作流上线前先跑一遍，得到「该避开哪些调度器」 | 需 `import comfy.*` → 用 ComfyUI 的 python |
| `sigma_report.py` | 单模型的 9 个调度器 σ 曲线详情 + 逐步 σ 打印（诊断用） | `python sigma_report.py` | 想深挖"某个调度器到底怎么分配步数" | 同上 |
| `sigma_model_matrix.json` | **参考数据**：7 个模型 × 9 调度器的离线判定结果 | 直接读 | 查历史结论、做对照 | — |
| `sigma_schedules.json` | **参考数据**：Qwen-Image 2.1 在 25/50 步下 9 个调度器的 σ 序列 | 直接读 | 想拿具体 σ 数值做图或复算 | — |

## 要改的常量
- `COMFY` = 你的 ComfyUI 根目录（用于 `sys.path.insert` 以便 `import comfy.*`）。
- `sigma_matrix.py` 的 `MODELS`：每条为 `(显示名, supported_models 类名, model_type, 官方steps, 官方采样器+调度器)`。

## 怎么加一个新模型

```python
# ① 在 comfy/supported_models.py 里找到该模型的类，读出它的 sampling_settings
#    例：class QwenImage21 → {"multiplier": 1.0, "shift": 0.69}
# ② 在 comfy/model_base.py 里找到对应类，看它传给 BaseModel 的 model_type
#    FLUX → ModelSamplingFlux；FLOW → ModelSamplingDiscreteFlow；FLOW_AV → ModelSamplingAV
# ③ 把条目加进 MODELS
("新模型名", "SupportedModels里的类名", ModelType.FLUX, 25, "euler + simple"),
```

> ⚠️ **别搞错 model_sampling 类**：`QwenImage` / `Krea2` / `Flux` / `Flux2` 在源码里传的都是 `ModelType.FLUX` → **`ModelSamplingFlux`（σ 表 10000 点）**；只有 `ModelType.FLOW`（Z-Image / Lumina2 系）才走 `ModelSamplingDiscreteFlow`（σ 表 1000 点）。混用会把 σ_min 算错 3 倍多。
> ⚠️ **工作流里可能还有 `ModelSampling*` 节点覆盖默认 shift**（实测：`Z_image_turbo` 有 `ModelSamplingAuraFlow(shift=3)`、`flux.1-dev` 有 `ModelSamplingFlux(1.15/0.5)`）。算 σ 前先确认。

## 判据（本包使用的阈值）

| 指标 | 含义 | 阈值 |
|---|---|---|
| **首步 Δσ%** | 第一步跨过的噪声幅度占 σ_max 的百分比。flow 模型里 `timestep(σ) = σ`，所以 Δσ 就是模型感受到的步长；一阶采样器误差 ≈ O(Δσ²) | **> 15% → 高危**；> 9% → 注意 |
| **高噪声区步数** | σ > 0.5σ_max 的步数 —— 这个区间决定整体构图/大结构 | **≤ max(1, 15%×steps) → 高危** |
| 末步前 σ → 0 的跳变 | **与画质无关，不要看这个**。flow 采样器在 `sigmas[i+1]==0` 时直接取模型的 denoised 输出、不做积分 | — |

## 关键结论（已验证，可直接引用）
- `karras` / `exponential`：**7/7 个 flow 模型全部高危**（首步 Δσ 从 9.4%@50步 到 81.5%@4步）；`exponential` 每个模型都比 `karras` 更激进。
- `kl_optimal`：**≤8 步的蒸馏模型上高危**，≥20 步可接受。
- 根因：`karras` 曲线出自 EDM 论文（rho=7），只用 σ 两个端点套通用公式，是为 DDPM 那种 σ_max≈14.6 的大动态范围设计的；套到 flow 模型（σ∈[0,1]）上会把步数错堆到低噪声区，高噪声区只剩几步。
- **调度器分两类实现**（`comfy/samplers.py` 的 `SCHEDULER_HANDLERS`）：`use_ms=True`（simple/sgm_uniform/beta/normal/ddim_uniform/linear_quadratic）= σ 取自**模型自身训练表**，一般安全；`use_ms=False`（karras/exponential/kl_optimal）= 只用端点套通用公式，**必须单独验算**。

## 2026-11-07 实拍复核（离线判据第一次落地成真实像素）

此前 `karras` / `exponential` 的「高危」全部来自离线 σ 计算，没跑过图 —— 这次补上实拍，两类架构各一组，**同种子、同步数、同 CFG、同分辨率，唯一变量是 scheduler**，判据先定后跑（均值 < 8 判黑屏、> 247 判白屏、标准差 < 6 判纯色；另外看相对基线的对比度衰减）。

| 模型（架构） | scheduler | steps/cfg | 耗时 | 均值亮度 | 标准差 | 结果 |
|---|---|---:|---:|---:|---:|---|
| `waiIllustriousSDXL_v160`（**epsilon，非 flow**） | simple（基线） | 25 / 6.0 | 36.2s（含首次载入） | 138.7 | 64.8 | 正常 |
| 同上 | **exponential** | 25 / 6.0 | 10.1s | 139.3 | 64.5 | **正常**（与基线几乎同分布） |
| 同上 | karras | 25 / 6.0 | 10.0s | 139.3 | 64.7 | 正常 |
| `moss_image_sft_int8_convrot`（**flow**） | simple（基线） | 28 / 4.0 | 30.4s（含首次载入） | 220.8 | 47.1 | 正常，版式与主图都成形 |
| 同上 | **exponential** | 28 / 4.0 | 21.2s | 245.8 | **11.3** | **崩** —— 接近白屏，只剩淡绿块与残缺标题骨架，主体消失 |
| 同上 | karras | 28 / 4.0 | 21.1s | 244.2 | 16.2 | **崩** —— 同款褪色，标题/正文全糊 |

**读法（这次的增量结论）**：
1. **离线判高危的落点是 flow 架构，不是「调度器有毒」**。同一个 `exponential` 在 SDXL 上把图正常跑出来（均值/标准差与 simple 基线差 0.6 / 0.3），在 MOSS-Image 上直接褪成一片白 —— 差别就在 `use_ms`：SDXL 自带训练 σ 表，`simple` 与 `exponential` 拿到的 σ 序列接近；flow 模型的 σ∈[0,1]，`exponential` 把步数全堆到低噪声区，高噪声区只剩一两步，大结构根本没建立。
2. **`exponential` 确实比 `karras` 更激进**（离线结论成立）：同模型同种子下对比度 11.3 vs 16.2，`exponential` 更淡。
3. **实拍不是用来「确认崩」，是用来定「在哪崩」**。所以本包的判据表照旧有效，但引用时必须带架构限定：**flow 模型 + `karras`/`exponential` = 别用**；epsilon 模型（SDXL 系）上没有这条限制。
4. 复现路径：`03_受控跑测/run_combos.py` 本身就支持「采样器 × 调度器」矩阵，把 seed/steps/cfg/分辨率钉死后只切 `scheduler` 即可；本次对照的完整参数是 `euler` 采样器、SDXL 组 `832×1216 / 25 步 / cfg 6.0`、MOSS 组 `1024×1024 / 28 步 / cfg 4.0`、种子 `20261107`。
