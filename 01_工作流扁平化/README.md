# 01 工作流扁平化

**解决什么问题**：新版 ComfyUI 工作流（顶层是 `definitions.subgraphs` 子图容器）**不能直接提交给 `/prompt`** —— 后端不展开子图，必须先把子图"压平"成 API prompt 格式。

| 文件 | 功能 | 使用方式 | 适用场景 | 依赖 |
|---|---|---|---|---|
| **`flatten.py`** ★ | 通用扁平化器：子图容器 → API prompt。支持容器 `-10`/`-20` 虚拟槽映射、`mode:4` bypass 递归透传、可达性裁剪（丢掉用不到的分支，如挂着的 SeedVR2）、容器取值类型守卫 | 作为模块用：<br>`import flatten`<br>`api, applied = flatten.flatten(工作流路径, {"KSampler": {"sampler_name":"euler","scheduler":"simple"}})`<br>命令行自测：`python flatten.py <工作流.json>` | 任何子图格式工作流的 headless 跑图前置步骤 | 仅标准库 |
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

## 使用注意
- 提交前先做**单组校验**：`POST /prompt` 的响应里 `node_errors` 为空才算通。
- 常见报错对照：
  - `required_input_missing: model` → bypass 链断线（规则 4）
  - `Failed to convert an input value to a INT value` → widget 位置错位或容器取值损坏（规则 5/6）
  - `Return type mismatch`（如 `received_type(CLIP) mismatch input_type(CONDITIONING)`）→ 旁路某个节点时接错了它的输出语义
- 若某工作流扁平化后校验不通过，**别硬猜**：把扁平化结果打印出来逐个节点核对参数值是否落在合法范围（对比 `../07_样例输出与数据/` 里的正确样例）。
