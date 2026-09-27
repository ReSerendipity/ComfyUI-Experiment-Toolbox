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
