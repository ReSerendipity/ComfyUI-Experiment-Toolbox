# 01 工作流扁平化

**解决什么问题**：新版 ComfyUI 工作流（顶层是 `definitions.subgraphs` 子图容器）**不能直接提交给 `/prompt`** —— 后端不展开子图，必须先把子图"压平"成 API prompt 格式。

| 文件 | 功能 | 使用方式 | 适用场景 | 依赖 |
|---|---|---|---|---|
| **`flatten.py`** ★ | 通用扁平化器：子图容器 → API prompt。支持容器 `-10`/`-20` 虚拟槽映射、`mode:4` bypass 递归透传、可达性裁剪（丢掉用不到的分支，如挂着的 SeedVR2）、容器取值类型守卫 | 作为模块用：<br>`import flatten`<br>`api, applied = flatten.flatten(工作流路径, {"KSampler": {"sampler_name":"euler","scheduler":"simple"}})`<br>命令行自测：`python flatten.py <工作流.json>` | 任何子图格式工作流的 headless 跑图前置步骤 | 仅标准库 |
| **`derive_api.py`** ★ | 模板派生层：① `resolve_switches` 把 `ComfySwitchNode` 折叠成直连并删除开关节点（惰性开关只跳过执行不跳过校验，未选分支会拖慢并可能改写提示词）；② `prune_unreachable` 重算可达性；③ `validate` 基于 `/object_info` 查未知输入/必填缺失/连线悬空/slot 越界；④ `resolve_models` 动态解析带子目录前缀的模型名 | `import derive_api as D`<br>`api = D.resolve_switches(api, {"1016": False})`<br>`api = D.prune_unreachable(api)`<br>`errs = D.validate(api)`<br>命令行自检：`python derive_api.py <模板.json>` | 从官方模板机械派生可提交 API 图；关闭 upsampler / SLG 等增益件 | 仅标准库 + 本地 ComfyUI 服务 |
| `build_prompt.py` | 单工作流**手写版**扁平化（Qwen-Image 2.1 t2i 专用）。功能上已被 `flatten.py` 覆盖 | `python build_prompt.py euler simple` 打印结果 | ① 想看清"某个具体工作流的子图映射长什么样"时的**范本**；② `01`/`02` 以外脚本（如 `cfg_probe.py`）沿用了它的 `PROMPT/SEED/STEPS/CFG` 常量 | `flatten` 无需；本文件依赖工作流固定路径 |

## 要改的常量
- `build_prompt.py` 顶部 `WF` = 目标工作流绝对路径，`ID_OFFSET` = 内部节点 ID 偏移。

## flatten.py 的核心规则（改动前务必先读）

1. **容器 = 顶层 `type` 是 UUID**（与 `definitions.subgraphs[].id` 对应）的节点。
2. **容器输入（`-10` 虚拟槽）**：`sg.inputs[i].linkIds` → 找 `origin_id == -10 && origin_slot == i` 的 link，其 `(target_id, target_slot)` 指明注入「内部节点第 `target_slot` 个输入」；容器 `widgets_values[i]` 就是该输入的值。
   ⚠️ **必须按 `target_slot` 对齐，不能用名字匹配** —— 容器 input 名与内部语义会错位（实测：容器里叫 `scheduler` 的其实是 `sampler_name`，`scheduler_1` 才是 `scheduler`）。
3. **容器输出（`-20` 虚拟槽）**：`sg.outputs[j].linkIds` → 找 `target_id == -20 && target_slot == j` 的 link，其 `(origin_id, origin_slot)` 即该输出的真实来源。
4. **`mode: 4` = bypass**：删掉该节点、把下游接到上游。**必须递归解析**（bypass 会成链），且要**先把所有连线重写完再删节点**，否则链上第二个节点会指向已删节点而断线（报 `required_input_missing: model`）。
5. **「既是 widget 又被连线」的输入仍占一个位置值** —— 只要输入带 `widget` 标记就要从 `widgets_values` 消耗一项（即使它同时有 `link`）。正确顺序是「先按 widget 顺序填满、再用 links 覆盖」；按 `link is not None` 跳过会导致**整条 widget 序列错位**（`denoise` 拿到 `'euler'`、`cfg` 丢失）。
6. **类型守卫**：注入前比较「目标输入原有值」与「容器给的值」类型；若原本是数值而容器给了非数值字符串，就不注入、保留原值并打印 `[flatten 警告]`。这条是为应对**损坏的工作流文件**（实测 `flux.1-dev.json` 的 `height` 位置被塞进过一个模型文件名）。
7. **容器 `widgets_values` 可能是 `sg.inputs` 全序**（2026-10-19 实测 MOSS-Image 官方模板）：容器 `inputs` 只列了 9 个提升项，而 `widgets_values` 是 14 项全序——`seed`/`steps`/`cfg`/`sampler_name`/`scheduler` 虽以 `-10` 连线提升，前端仍把回退值按 `sg.inputs` 顺序写进数组。旧逻辑按「只算带 widget 标记的输入」游标索引，从第一个非 widget 输入起整体错位，症状：`unet_name` 拿到 `steps=25`、`vae_name` 拿到 `sampler='er_sde'`、`ComfySwitchNode.switch` 拿到 `seed`。现按「长度相等且存在非 widget 输入 → 按 i 全序取」判据区分两种序列化形态。
8. **内部节点必填项补全**：模板导出的节点 `inputs` 只列被提升/被连线的口，未提升的 widget 值只存在于 `widgets_values_named`。仅遍历 `inputs` 会丢掉 `weight_dtype`/`type`/`device`/`batch_size`/`double_layers` 等必填项，提交时报 `required_input_missing`。现按命名表补全，并剔除 `control_after_generate`/`fixed` 这类前端辅助键（它们不是 API 输入）。

## 使用注意
- 提交前先做**单组校验**：`POST /prompt` 的响应里 `node_errors` 为空才算通。
- 常见报错对照：
  - `required_input_missing: model` → bypass 链断线（规则 4）
  - `Failed to convert an input value to a INT value` → widget 位置错位或容器取值损坏（规则 5/6）
  - `Return type mismatch`（如 `received_type(CLIP) mismatch input_type(CONDITIONING)`）→ 旁路某个节点时接错了它的输出语义
- 若某工作流扁平化后校验不通过，**别硬猜**：把扁平化结果打印出来逐个节点核对参数值是否落在合法范围（对比 `../07_样例输出与数据/` 里的正确样例）。

## 诊断：`status=success` 但 `outputs` 为空（静默无输出）

跑测最费时间的一种失败：服务端返回 success、耗时正常、**一张图都没有，日志里也没有 traceback**。
按下面顺序排，别从"模型坏了"开始猜——2026-10-11 用一整天（含把 4 个工作流的 unet 全换成已装版本）证明了**模型不是根因**。

### ① 先确认服务还活着

`GET /system_stats` 探不通就是进程没了。本机实测死因之一是 GPU 驱动复位（系统日志 `nvlddmkm` 事件 153）静默杀掉 ComfyUI 的 python——日志停在 `x/N` 步、无 traceback，客户端只见请求失败。
`03_受控跑测` 的 `wait()` 已内置「每 5 次失败探活一次」，探不通立即返回 `server_dead`。

### ② 再查模型名是否合法（最常见）

症状链：`unet_name` 不在服务端模型列表 → `Failed to validate prompt: ... value_not_in_list` → **该节点输出被忽略** → 下游全部剪枝 → `status=success` + `outputs={}`。

三个具体成因：

- **JSON 里是单反斜杠**：`FLUX-1-dev\fluxNSFW...`，JSON 把 `\f` 解析成换页符 `\x0c`，实际值变成 `FLUX-1-dev\x0cluxNSFW...`
- **用了正斜杠**：服务端列表是反斜杠，正斜杠不匹配
- **漏了子目录前缀**：模型放在 `models/*/子文件夹/` 时，合法值是 `子文件夹\文件名`，裸文件名被拒

做法：提交前用 `/object_info` 动态解析合法值（`derive_api.resolve_models`），不要硬编码文件名。

### ③ 查权重格式能不能被识别

`Qwen-Image-2.1-Turbo-FP8.safetensors` 报 `Could not detect model type`——它是 **torchao Float8Tensor** 格式（safetensors 头含 `_weight_scale` + `_tensor_data_names:["qdata","scale"]`），当前 ComfyUI 不认。
同模型换 `qwen-image-2.1-turbo-int8-convrot.safetensors` 直接可跑。

判据是**读 safetensors 头**，不是看文件名里的 `fp8`/`int8`——文件名标称与真实格式可能不一致（同目录同名不同架构的情况见 `10_模型家族横评/docs/Z_image_turbo链路SOP.md`）。

### ④ 查「你改的到底是不是生效的那份」

- **ComfyUI 按 UUID 缓存子图定义**：改磁盘上的 `definitions.subgraphs` 后 UI 里仍用旧定义，必须重载页面（`location.reload()`）或在 UI 内改。
- **ComfyUI 有自动保存**：手改的 JSON 会被覆盖。改工作流要在 UI 内做，然后**右键顶部工作流标签的「名称」→ 保存**（`Ctrl+S` 和点标签本身都不弹菜单）。
- **提交读容器值，不读内部节点值**：`/prompt` 取的是子图容器上被提升的 widget（`容器.widgets_values[]` / `widgets_values_named`），改子图内部 `UNETLoader` 的 widget 无效。
- **子图输入按输入顺序绑 slot，不按 `linkIds`**：改 `sg.inputs[].linkIds` 不生效；要么交换 link 目标，要么改容器 positional 值。
- **值来源分两类**：`unet_name` 是容器 widget → 改容器三处（`widgets[i].value` + `widgets_values[i]` + `widgets_values_named`）即持久化；是提升的 COMBO 输入（`link=null`、无 widget）→ 值在子图定义里，且真正被序列化的是 `app.graph.subgraphs`（按 UUID 键的 Map），只改 `c.subgraph.nodes` 运行生效但**不落盘**。

### ⑤ 还不行：换一个「已知能出图」的子图试

用前端 API 复制正常子图（`app.canvas.selectNode(sub,false)` + `copyToClipboard()`），切到问题工作流 `pasteFromClipboard()`，再把 SaveImage 的 `images` 输入接到新子图输出槽。

能出图 → 原工作流的子图结构本身坏了，不是参数问题。**注意此时跑的是复制来的管线，模型与工作流名不再对应**，别把结果当成该模型的结论。

### 回读真值：别猜参数，读出来

出图 PNG 的 tEXt `prompt` 元数据里存着**实际提交的完整 API 图**。注入是否生效、模型名是什么、seed/steps 取值，直接读它比对着代码猜快一个量级。

