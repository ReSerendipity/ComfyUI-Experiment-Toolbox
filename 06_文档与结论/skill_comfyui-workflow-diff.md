> **技能真源（2026-11-16 收编）**
> 本文档是本机技能 `comfyui-workflow-diff` 的全量沉淀与**唯一活跃真源**（2026-11-16 技能治理迁移：原 `%USERPROFILE%/.workbuddy/skills/comfyui-workflow-diff/` 原件与 Agent-Knowledge 存档副本已删除，本文件内容为删除前原件全量版）。仓内没有项目技能根，本文件不注册为可装载 skill，由根 `AGENTS.md` §3 指路。
> 何时该读这份：对比 / 同步 / 审计 ComfyUI 工作流 JSON——死节点判定（连线可达性，不靠 mode 猜）、采样参数对齐官方模板、latent 通道校验（4ch vs 16ch）、MarkdownNote 注释复制、画布去重叠、运行中实例实载验证。

# ComfyUI 工作流对比 / 同步 / 审计

## 何时使用
- 对比用户工作流文件与官方模板的差异（节点级 + 连接级）。
- 把 sampler / steps / cfg / scheduler 等参数对齐到官方。
- 判定注入节点（SeedVR2 / LoraLoader / 自定义采样链等）是否真的在出图主链上执行。
- 校验 latent 通道（4ch vs 16ch）是否匹配模型家族。
- 把官方 `MarkdownNote` 注释节点复制到用户文件。

## 关键路径（ComfyUI-aki-v3.2，按需替换）
- 官方模板：`ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates`
- 用户文件：`ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image`
- 节点定义：`ComfyUI\comfy_extras\nodes_*.py`（SaveImageAdvanced=nodes_images.py，EmptySD3LatentImage=nodes_sd3.py，ResolutionSelector=nodes_resolution.py）、`ComfyUI\nodes.py`（EmptyLatentImage, SaveImage, PreviewImage 等）

## 工作流 JSON 格式（新版，必须先搞清再写脚本）
- 顶层：`d["nodes"]`（顶层节点）+ `d["links"]`（顶层连线）。
- 子图：`d["definitions"]["subgraphs"][]` 内含各自的 `nodes` 与 `links`。
- 连线是 **dict**：`{id, origin_id, origin_slot, target_id, target_slot, type}`（不是旧版 list `[link_id, origin, origin_slot, target, target_slot, type]`）。脚本必须同时兼容两种。
- 子图输出：子图 `outputs[].linkIds` → 在 `links` 里找到该 link 的 `origin_id`/`target_slot`，即为"子图对外暴露的源节点/槽"。
- 节点 `inputs[]` 中每项含 `link`（=连线的 `id`），据此解析上游节点类型。

## 死节点判定（最重要，别靠 mode 猜）
- **权威判据 = 连线图逆向可达性（reverse-reachability BFS）**，不是节点 `mode` 字段。
- **根节点（roots）= 所有 `OUTPUT_NODE=True` 的节点**，不是只有 SaveImage！ComfyUI 执行器从"每个输出节点"反向遍历。常见 OUTPUT_NODE：`SaveImage`、`SaveImageAdvanced`、`PreviewImage`(继承 SaveImage)、`PreviewAny`、`BatchPromptReaderWithClip`、`ReservedVRAMSetter`（后两者是自定义但都设了 OUTPUT_NODE=True）。
  - 因此 `PreviewImage` **会执行**，并被其上游（如 `ImageScaleToTotalPixels`）一并拉入执行集。**别再误判 PreviewImage/ImageScale 为死节点。**
- 步骤：建全部节点+连线的扁平图；roots = (a) 容器内所有 OUTPUT_NODE 类型节点 ∪ (b) 被顶层 OUTPUT_NODE 消费的子图输出槽之内部源节点（子图 `outputs[].linkIds` → 对应 link 的 `origin_id`）；做反向 BFS（rev[target].append(origin)）→ 被访问者=会执行，否则死节点。
- 判 OUTPUT_NODE：`grep -nE "^class |OUTPUT_NODE" <node>.py`；core 的在 `comfy_extras/`、`nodes.py`，自定义的在 `custom_nodes/*/`。
- **验证事实**：本构建 `execution.py` 后端**无任何 `mode` 检查**，`mode` 字段不影响服务端是否执行（mute/bypass 是前端行为）。标准 mode 仅 0/1/2（1=NEVER 前端 bypass）。`mode=4` 等非标准值更不是执行判据。所以"死节点"= 不接任何输出根，与 mode 无关。
- 参考脚本：`reach3.py`（含 OUTPUT_NODE roots 的正确版）。

## 采样参数对齐
- 真实采样节点：`KSampler`(widgets=[seed, seed_mode, steps, cfg, sampler_name, scheduler, denoise])、`KSamplerSelect`(=[sampler_name])、`Flux2Scheduler`(=[steps, w, h])、`BasicScheduler`(=[scheduler, steps, denoise])、`FluxGuidance`(=[guidance])。
- 直接读取这些节点的 `widgets_values` 比对，不要启发式猜整数（旧脚本曾误把非 steps 整数当 steps）。
- FLUX 家族常用"自定义采样链"（KSamplerSelect+BasicScheduler+BasicGuider+RandomNoise+SamplerCustomAdvanced+ModelSamplingFlux）替代官方单 `KSampler`；CFG 在 FLUX 上常表现为 `guidance`（FluxGuidance 节点），不是 KSampler 的 cfg。

## Latent 通道校验（真实缺陷高发区）
- `EmptyLatentImage`（`nodes.py`）= **4 通道**（`torch.zeros([b,4,h//8,w//8])`）→ SD1.5/SDXL。
- `EmptySD3LatentImage`（`nodes_sd3.py`）= **16 通道**（`torch.zeros([b,16,h//8,w//8])`）→ SD3/FLUX/Qwen 系。
- 这**不是纯命名差异**，通道数不匹配会导致模型 `conv_in` 维度报错。对比时务必逐文件统计两类节点数量（我们 vs 官方）；官方用 16ch 而我们误用 4ch 的文件需要改成 `EmptySD3LatentImage`。

## 节点功能速查（问答用）
- `SaveImageAdvanced`：新版 schema 节点，支持 png/exr/avif、bit_depth、input_color_space、%token% 前缀格式化；`SaveImage` 是老版仅 PNG 的节点。两者都写 output 目录。
- `PreviewImage`：仅画布预览，**不写盘**（临时查看）。
- `ResolutionSelector`：按 aspect_ratio + megapixels 算 width/height 喂给 Empty Latent Image 的辅助节点；**不是所有工作流都用它**（官方仅 Qwen2.1、Z-Image 用，其余硬编码分辨率）。
- `ComfySwitchNode`：运行时在多个输入间切换（如切预设/提示词变体）。
- `PrimitiveInt/Float/Boolean`：常量值节点，驱动 widget 输入。
- `ConditioningZeroOut`：把 conditioning 清零（喂"空负向"给 cfg≈1 的 FLUX/SD3）。
- `ReservedVRAMSetter`：预留显存副作用节点；在出图主链上即执行。
- `LoraLoaderModelOnly`：仅加载 LoRA 到模型（不产出图），在出图主链上即生效。

## 复制官方 MarkdownNote（保留字段、重分配 id）
1. 提取官方模板全部 `MarkdownNote`（顶层 + 子图都搜）。
2. 备份用户当前文件到 `*.bak_mdnote`。
3. 取文件内所有节点（含子图）的最大**数字** id，新节点 id 设为 `max+1, +2...`（避免与子图 uuid 字符串冲突）。
4. `copy.deepcopy(note)`，改 `id`，强制 `mode=0`，`append` 到顶层 `nodes`（MarkdownNote 无连接，放顶层即可，子图内的注释也放顶层不影响功能）。
5. 用 `json.dump(d, f, ensure_ascii=False, separators=(",",":"))` 写回（保持紧凑，兼容 ComfyUI 读取）。
6. 写后重新 `json.load` 校验。

## 在运行中的 ComfyUI 里验证工作流（浏览器内）
改完后强烈建议对着用户正在跑的 ComfyUI 实例实证：
1. **静态**：`curl -s -o object_info.json http://127.0.0.1:8188/object_info` → 取所有节点类型集合；把待验工作流里每个 `type` 与其比对，缺的即会报红线。注意 `MarkdownNote`、`Fast Groups Bypasser (rgthree)` 等**前端专属节点不在 object_info**，属正常。
2. **读取工作流 JSON 的正确 API**：`GET http://127.0.0.1:8188/userdata/workflows%2FImage%2F<file>.json` —— **子目录斜杠必须 URL 编码成 `%2F`**，否则 404。（列表用 `?dir=workflows/Image` 正常。）
3. **在 UI 里加载**：agent-browser（`agent-browser open http://127.0.0.1:8188/` 后）用其 `eval` 执行：
   ```js
   (async()=>{const n='<file>.json';const r=await fetch('/userdata/workflows%2FImage%2F'+n);
   const d=await r.json();await window.app.loadGraphData(d,true,true,n);return 'ok';})()
   ```
   ComfyUI 前端暴露 `window.app.loadGraphData(graphData,true,true,name)` 可编程加载工作流；加载成功即证结构有效，再 `screenshot` 目视。
- **agent-browser 在 Windows 的坑**：`eval` 若**单独调用**常漂到 `about:blank`（relative fetch 会 "Failed to parse URL"）——必须把 `open`+`eval`+`screenshot` **串在同一条 bash 命令链**里；`snapshot -i` 在 ComfyUI 这种重 SPA 上会卡死，别用；首次 `open` 冷启动约 10~30s，前台 120s 超时易误杀，建议 `run_in_background` + 轮询。
- 结束务必 `agent-browser close --all`。

## 画布布局去重叠（观感）
用户常反馈"节点互相挡住"。做法：
1. 对每个容器（顶层 + 每个子图）取 `node.pos` + `node.size`（缺省 [210,100]）做 AABB 相交检测，报告重叠对与重叠面积。
2. 顶层**注释节点**统一归入最左一列（x = 非笔记节点最小 x − 最大笔记宽 − 80；y 从最小 y 起按 `高度+40` 堆叠）——保证零重叠且整齐。
3. 子图里被压到的节点用"环形空闲位搜索"移到最近空位：从 preferred 位置按 step≈45 向外扩环，取第一个与所有其他节点都不相交的位置。注意：环形搜索的方向顺序会影响落点，改完**务必再跑检测 + 实载目视**。
4. 一般优先移动**你新增的/工具类**节点（MarkdownNote/PreviewImage/ConditioningZeroOut/开关块），尽量不动用户原有核心节点；若用户明确要求"全部检查"，也把既有重叠一并nudge。
- 备份用 `.bak_layout`。

## 启动 ComfyUI + 实跑验证（无 GUI 交互）
- **启动**（aki 便携版）：GUI 启动器是 `绘世启动器.exe`，参数存 `.launcher/preference.json`；直接跑内置 python 即可：
  `%USERPROFILE%/APP/ComfyUI-aki-v3.2/python/python.exe -s ComfyUI/main.py --windows-standalone-build --disable-auto-launch`（cwd=安装根），后台跑约 40s，之后 `curl 127.0.0.1:8188/` 应 200。
- **投递并验证某个工作流**（浏览器内 eval，**必须与 `open` 同链**）：
  ```js
  const d = await (await fetch('/userdata/workflows%2FImage%2F'+name)).json();
  await window.app.loadGraphData(d,true,true,name);
  const p = await window.app.graphToPrompt();               // UI→API 提示词
  const j = await (await fetch('/prompt',{method:'POST',headers:{'Content-Type':'application/json'},
                 body:JSON.stringify({prompt:p.output,client_id:'agent'})})).json();
  // j.prompt_id 或 j.error / j.node_errors
  ```
  然后 `GET /history` 轮询 `prompt_id`，看 `status.status_str`（success/error）与 `status.messages` 里的 `execution_error`（含 exception_message/node_type/node_id）。
- **子图工作流的提示词入口**：顶层子图节点第 0 个 widget 常是 `positive_prompt`（`node.widgets[0].value` 可设）；但**很多 aki 用户的"批量"工作流实际用 `BatchPromptReaderWithClip` 从 `ComfyUI/input/<folder_path>/*.txt` 读提示词**，此时代入 widget 无效。
  - 常见报错：`[BatchPromptLoader] No matching files in folder: … Search pattern: *.txt` → 该 folder 无 txt（或 `current_number` 超过文件数）。查 `custom_nodes/BatchPromptLoader/batch_prompt_loader.py`。
  - 排查时可用 Python 遍历 `ComfyUI/input/` 统计各目录 txt 数，与各节点的 `folder_path`（`widgets_values[0]`）比对。
  - **把正面提示词改回文本节点**：把采样器/guider 的 `positive`（或 `FluxGuidance.conditioning`）改接 `CLIPTextEncode.slot0`（若该编码器无 clip 输入要补 `clip<-CLIPLoader/DualCLIPLoader`）；Qwen2.1 用 `TextEncodeQwenImage21.slot0`。批量节点 `folder_path` 要设成有 txt 的目录且 **recursive=true**（根目录无 txt 时 false 仍报错）。
  - **子图 widget↔input 顺序错位陷阱**：子图顶层节点 `widgets_values` 与 `inputs` **未必按序对应**（例：flux.1-dev 因该子图 **没有 `negative_prompt` 输入**，`["",20,1024,1024,…]` 被按 `[positive_prompt,cfg,steps,width,…]` 解析 → `guidance` 吃到 20、`steps` 吃到 1024）。核对实际生效值要看 `POST /prompt` 后 `/queue`（running 项）里对应节点的 `inputs`，别只看文件里的 widget。
  - **修复**：把子图节点 `widgets_values` 中映射到目标 input 的那一位改成正确值（保持参数化），或断开该 `-10→节点` 链接让节点 widget 生效；改后**必须**再 `POST /prompt` + 查 `/queue` 复核实际值，再跑一次确认变快/正常。
- 注意：`/prompt` 返回 200 且带 `prompt_id` 也可能同时带 `node_errors`（非致命校验）；真正成败以 `/history` 的 status 为准。

## 收尾/卫生
- 改工作流前把备份写成**独立后缀**（如 `X.json.bak_latent`/`.bak_options`），但注意：**ComfyUI 的 Workflows 列表会扫到这些 `.bak*` 文件**，列表会很乱。收尾时把 `*.bak*` 统一移进 `workflows/<分类>/_backups/`（或移到 `workflows/` 目录之外，彻底不显示）。
- 接入"备用"开关到采样器时的注意点：Qwen 类工作流的 `steps/cfg` 往往**已作为子图节点参数暴露**（顶层子图节点 widget 经 `-10` 代理进 KSampler）；把开关接到 `KSampler.steps/cfg` 会**覆盖该参数控制**，需先与用户确认。改后旧 `-10->KSampler` 链接会变孤儿——可保留（前端通常容忍）并**实载验证**。
- FLUX 工作流里子图暴露的 "cfg" 参数常实际驱动 **`FluxGuidance.guidance`**（不是 CFG）；给 `CFGGuider` 设 cfg 时别误接到它。

## 铁律
- 改前先 `cp -p` 备份（每次编辑留独立 `.bak*`）。
- 用户若说"不删死节点，后续连接即可" → 只保留、不删除。
- 所有判定以**读实际 JSON + 跑脚本验证**为准，不凭记忆下结论。
