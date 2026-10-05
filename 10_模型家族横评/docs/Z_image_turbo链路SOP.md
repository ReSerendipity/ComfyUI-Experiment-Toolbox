# Z-Image 链路 SOP（UI 工作流 → 扁平化 → API 注入 → 出图）

> 定位：**项目无关**的 Z-Image 系（`ZImage`/`Lumina2` 架构）链路操作手册。
> 覆盖：工作流文件怎么选、为什么要扁平化、注入点在哪、六步流水、常见报错与排障。
>
> 思路来源：`Picture/docs/流程文档/Z_image_turbo渲染全流程_20260923.md`（UI JSON →
> flatten → POST 的完整流水）。该文是项目内文档，此处只保留**与提示词库内容无关**的
> 链路操作知识**，并与工具箱 `10_模型家族横评` 的 W06 实测（`Z_image.json` 链路）
> 做交叉对照——两边用的是**不同的工作流文件、不同步数**，这是最容易踩的坑，放在 §二。

---

## 一、三条铁律

1. **不改工作流文件**。UI 工作流放 `ComfyUI/user/default/workflows/Image/`，
   只读打开、只读内存副本注入，绝不写回。
2. **改前备份**；本流程只调用，不落盘改 JSON。
3. **UI 格式不能直接 `POST /prompt`**。UI 导出的 JSON 是
   `nodes` + `links` + `definitions.subgraphs`（带 UUID 类型的子图容器），
   API 要的是扁平 `{node_id: {"class_type", "inputs"}}` 图。**必须先扁平化**。

---

## 二、两个工作流文件的区别（先搞清再跑）

同一架构家族有两个常用工作流，参数完全不同，**混用会得到"参数没生效"的错觉**：

| 项 | `Z_image_turbo.json` | `Z_image.json` |
|---|---|---|
| 定位 | 蒸馏/Turbo，**少步数快出图** | 基础步数档，通用 |
| 步数 | **8** | **25** |
| cfg | **1.0** | **4.0** |
| sampler / scheduler | `res_multistep` / `simple` | `res_multistep` / `simple` |
| 负向 | 空文本 / 零条件 | `ConditioningZeroOut` |
| shift | 文件自带 | 文件自带；实测 `Z_image.json` 的 shift 3.0 由 ZImage 模型配置 `sampling_settings.shift=3.0` 内建，**工作流里没有另加 `ModelSamplingAuraFlow`** |
| 实测耗时 | 约 16–38 s/张（多数 28–32 s） | **86.5 s**（25 步 + 5.37 GB TE 冷载入；全热时应显著更低） |
| 典型用途 | 批量预览、回归烟测 | 正式评分、出成品 |

> **实测对照（工具箱横评 W06）**：W06 `Flux.2 Klein 9B fp8 darkBeast` 被 ComfyUI
> 架构判定为 `ZImage`/`Lumina2`，用 `Z_image.json` 链路跑，**86.5 s**，
> `ModelSamplingAuraFlow(shift=3)`、`res_multistep`/`simple`、steps 25、cfg 4.0、
> TE `qwen_3_4b_fp8_mixed`（`type=lumina2`）、VAE `ae.safetensors`、
> latent `EmptySD3LatentImage`。同 seed 的 Krea2 8 步全热约 38 s。
> **两个数字不能直接相减**：缓存状态不同。要算每步成本必须同一缓存状态下测
> （#7 扣约 30 s 载入 → ≈2.3 s/步；Krea2 → ≈4.5 s/步）。

**选哪个**：要快、要回归覆盖、要每天跑几十张 → turbo（8 步）；
要评分、要出成品、要给读图人看 → `Z_image.json`（25 步）。
**同一轮对比里绝不能混用**，否则"哪个权重更强"会被"8 步还是 25 步"污染。

---

## 三、工作流结构（扁平化前）

`Z_image_turbo.json` 典型形态：顶层 4 个节点。

| 节点 id | type | 角色 |
|---|---|---|
| 82 | UUID 子图容器 | `Text to Image (Z-Image-Turbo)`；`widgets_values[0]`＝正向提示词、seed、分辨率 |
| 107 | `ResolutionSelector` | width / height → 子图 |
| 108 | `SaveImageAdvanced` | 落盘；prefix 为工作流内默认值 |
| 109 | `MarkdownNote` | 说明便签（渲染链路不可达，扁平化时被裁掉） |

子图内部（`definitions.subgraphs`）：模型 UNETLoader + `CLIPLoader(type=lumina2)`
+ `CLIPTextEncode`（正向）/ 负向空文本 → `KSampler` → `VAEDecode` → 子图 output。

> **参数以扁平化结果为准，不以任何文档手抄为准**。改过工作流后只须重跑一次扁平化，
> 重新读节点输入。

---

## 四、扁平化：五个必须遵守的规则

UI 版子图格式的展开规则（工具箱 `01_工作流扁平化/flatten.py` 的实现要点）：

1. **容器识别**：顶层节点的 `type` 是 UUID 字符串（对应 `definitions.subgraphs[].id`）。
   实用判据：`type` 含 `-` 且长度 > 30。
2. **容器输入（虚拟槽 `-10`）**：`sg.inputs[i]` → 找 `origin_id == -10 且 origin_slot == i`
   的那条 link，其 `(target_id, target_slot)` 指明"注入到子图内部第 `target_slot` 个输入"，
   值取容器的 `widgets_values[i]`。
   ⚠️ **必须按 `target_slot` 对齐，绝对不能按输入名匹配**——容器 input 名与内部语义会错位。
3. **容器输出（虚拟槽 `-20`）**：`sg.outputs[j].linkIds` → 找 `target_id == -20 且
   target_slot == j` 的 link，其 `(origin_id, origin_slot)` 是容器第 j 个输出的来源。
4. **`mode == 4` = bypass**：删掉该节点，下游接到它的上游。
   **必须递归解析**（bypass 节点会成链），且要设递归上限防环。
   解析完成后再删除 bypass 节点本身。
5. **可达性裁剪**：只保留从 `SaveImage` / `SaveImageAdvanced` / `SaveImagetoPath` /
   `PreviewImage` **反向可达**的节点。`MarkdownNote` 这类不可达节点自动消失。

### 4.1 widget 占位语义（最容易踩的坑）

- ComfyUI 会把**已连线**的 widget 值也照常序列化，作为回退值。
  所以扁平化要**先把 widget 值按位置填好，再用 links 覆盖**——顺序反了语义就不对。
- 判定"占一个位置值"的依据是输入带 `widget` 标记，**即使它同时被连线也要占位**。
- `seed` 后面可能跟一个控制模式字符串（`fixed` / `randomize` / `increment` /
  `decrement`），占位时要跳过，否则后续所有 widget 值整体错位。

### 4.2 类型守卫（防脏数据）

工作流的 positional 数组可能损坏（例如 height 位置被塞了一个模型文件名）。
守卫规则：**若目标输入原本是数值、而容器给的是非数值字符串，则不注入，保留节点自身值**，
并打一条警告。不要硬塞——`EmptySD3LatentImage` 收到字符串会在服务端炸。

### 4.3 ID 重编号

子图内节点 id 与顶层 id 会撞车。做法：子图节点按容器序号偏移（`id + 1000*i`），
顶层非容器节点用 `t{id}` 前缀。**注入时一律用 `class_type` 定位，不要用原始 id**
（id 已被重映射）。

---

## 五、六步流水

```text
[1] 读 UI JSON（只读）
      Z_image_turbo.json
         │
[2] flatten(path, overrides=None)
      → (api_prompt, applied)
      · 容器按 -10/-20 虚拟槽展开、idmap 重编号
      · mode==4 bypass 递归透传
      · 从 Save*/Preview* 反向可达性裁剪（Note 等死支自动去掉）
      → 节点数与工作流相关（turbo 约 12 个）
         │
[3] deepcopy + 注入（每次一条，不回写源文件）
      · 找 class_type == "KSampler"
      · positive 链到 CLIPTextEncode → inputs.text = 正文
      · KSampler.inputs.seed = SEED_BASE + idx
      · 含 "SaveImage" 的节点 → filename_prefix = 本次唯一前缀
         │
[4] POST /prompt   {"prompt": graph, "client_id": "..."}
      · resp.node_errors 非空 → 打印并记 ok=false，不轮询
         │
[5] GET /history/{prompt_id} 轮询
      · status success/error，或 outputs 出现 images 即停（超时 300 s）
         │
[6] 本地拷贝/归档
      ComfyUI\output\{subfolder}\{filename} → 目标目录
```

**HTTP 封装**：标准库 `urllib.request` 即可，无第三方依赖。
**缓存**：模块级缓存"只 flatten 一次"的 base 图，每条 `copy.deepcopy` 再改，
避免串 seed / 串 text。

---

## 六、注入点速查

| 注入项 | 定位方式 | 字段 |
|---|---|---|
| 正向提示词 | `KSampler.inputs.positive` → `[node_id, slot]` | 该节点 `inputs.text` |
| seed | `class_type == "KSampler"` | `inputs.seed` |
| 文件名前缀 | `class_type` 含 `SaveImage` | `inputs.filename_prefix` |
| UNet 权重 | `class_type == "UNETLoader"` | `inputs.unet_name` |
| TE 权重 / 类型 | `class_type == "CLIPLoader"` | `inputs.clip_name` / `inputs.type`（lumina2） |
| VAE | `class_type == "VAELoader"` | `inputs.vae_name` |
| 分辨率 | 工作流 ResolutionSelector 链 | **默认不注入**；改画幅改 UI 工作流或扁平化后对应节点 |

**独立复用伪代码**：

```python
import copy
from flatten import flatten
base, _ = flatten(r"...\Z_image_turbo.json")
graph = copy.deepcopy(base)
# 按上表注入 text / seed / filename_prefix，再 POST /prompt
```

---

## 七、常见报错与排障

### 7.1 架构不匹配（本链路最典型的一类）

```
RuntimeError: Given normalized_shape=[2560], expected input with shape [*, 2560],
but got input of size[1, 512, 12288]
  comfy/ldm/lumina/model.py:660 embed_cap -> cap_embedder -> rms_norm
```

**判读方法**（这张 traceback 本身就是架构证据）：

| traceback 落点 | 含义 |
|---|---|
| `comfy/ldm/lumina/model.py` | **Z-Image / Lumina2** 的 DiT 实现 |
| `comfy/ldm/flux/` | FLUX 系 |

再看两个数字：`cap_embedder.normalized_shape = [2560]` = Z-Image 的 `cap_feat_dim`；
实际喂入 `[1, 512, 12288]` = FLUX.2 Klein 的 `context_in_dim`（`qwen_3_8b` +
`type=flux2` 的多层 tap）。**两者维度不可通约 → 架构级不兼容**。

**关键细节**：`UNETLoader` 那一步**执行成功**了。所以失败点在**条件链**，
不是权重坏了。排查时先看"哪些节点已成功执行"，能省掉整轮猜测。

**处置**：换链路（把这条权重的 `chain` 整条替换成 `zimage`），并打
`declared_exception` 标记，报告里单列一个分层——**不许**把它的差异表述成
"同链路权重差异"，因为差异同时来自权重 / TE（Qwen3-8B vs Qwen3-4B）/ 步数（20 vs 25）/
cfg（5.0 vs 4.0）/ latent 打包 / 采样器，共 6 个变量同时变了。

### 7.2 排障速查表

| 症状 | 处理 |
|---|---|
| `urllib` 连接拒绝 | ComfyUI 没起；先 `GET /system_stats` 探活拿 200 |
| 扁平化后节点异常 / 注入打空 | 用 `class_type` 定位，勿用原始 id；用工作流分析脚本打印节点表对照 |
| 参数名错位 / widget 整体偏移 | 检查 `seed` 后面的控制模式字符串是否被跳过；检查是否按 `target_slot` 对齐（不是按名字） |
| `node_errors` | 打印 JSON；最常见是模型路径与当前机不一致 → 在 UI 打开工作流确认能加载，**不要把绝对路径写死进脚本** |
| 有 graph 无图 | 查 `history` 的 `outputs.images`；确认 Save 链在可达性裁剪后仍然保留 |
| 预览被覆盖 | 文件名前缀必须带本次运行的唯一标记；多后端/多 prompt 勿共用 prefix |
| 两后端抢队列 | 串行 `POST /prompt`，不要并发 |
| 数值输入收到字符串 | 触发类型守卫；修工作流而不是绕过守卫 |
| bypass 链把 `model` 断开 | 兜底：若采样节点的 `model` 既无 widget 值也无连线，直接接回 `UNETLoader`（bypass 的 LoRA 本身是 no-op，与前端语义一致） |

### 7.3 两条通用纪律

1. **"模型能否加载"必须在 ComfyUI 服务器进程语义下判定。**
   裸 `import comfy` 的独立进程里内存管理开关停在 `False`，权重读取走严格路径，
   可能报 `file not fully covered`；服务器进程里走容错读取器，同一文件正常。
   → 判断可用性请走 `/prompt` 真实工作流，不要用裸进程加载结论。
2. **同一个文件夹里的权重不一定是同一架构。** 文件夹名、文件名、甚至量化标称
   都可能与真实架构不符。跑测前先做**零出图的架构探针**（只读权重头部的
   JSON + meta 张量），把架构判定结果记进台账，再决定链路。

---

## 八、与工具箱横评的接线位置

| 本 SOP 环节 | 工具箱现状 |
|---|---|
| flatten | `01_工作流扁平化/flatten.py`，`10_模型家族横评/bench_family.py` 直接 `import flatten`（sys.path 注入，不拷代码） |
| 链路参数钉死 | `10_模型家族横评/family_config.json` 的 `families.<文件夹>` + `weight_overrides` |
| 架构例外声明 | `weight_overrides.<权重名>.declared_exception = true` → 分析阶段归 Stratum B |
| 注入点 | `bench_family.py` 的提交段（按 `class_type` 定位，不按 id） |
| LLM 改写链剪枝 | `prune.prompt_enhance_off=true` → 剪掉 `TextGenerate` 等节点；`BatchPromptReaderWithClip` 旁路成空提示词编码 |
| 出图后处理剪枝 | 只取原始 `VAEDecode` 输出，删掉 `PreviewImage` 分支，避免放大器混进对比 |
| 镜像 / flatten 能力差异 | 见 `flatten版本对照.md` |

> 版本对照结论摘要：工具箱 `01` 版与 `Picture/tools` 版的 `flatten()` **核心算法
> AST 完全一致**（6 个函数逐一比对全等），唯一差异是 `__main__` 的默认工作流路径
> 解析方式。详见 `flatten版本对照.md`。