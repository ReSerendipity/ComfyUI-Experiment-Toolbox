# 05 结构改造脚本

> 本目录来自 2026-09-24 合并前的 `ComfyUI-工作流改造经验/01_可复用脚本`（旧 README 存于 `99_归档/README-旧-工作流改造经验-20260923.md`）。
> 2026-09 于 ComfyUI-aki-v3 完成 Image 类 8 个 + Edit 类 3 个工作流的「取长补短」融合改造，此处是当时沉淀的脚本与经验。
> 采样器/调度器参数结论见 `../06_文档与结论/`（两轨共享的结论内核）。

---

## 脚本分类速查（24 个随包改造脚本，另有 1 个 `gen_workflows_manifest.py` 只读审计脚本见第八节、与 1 个 dry-run 共享助手 `dryrun.py` 见第九节；2026-10-14 按文件计数核实）

### 官方模板对齐类
| 脚本 | 作用 |
|---|---|
| `apply_official.py` | 按官方模板对齐采样参数 |
| `apply_sampler_prefs.py` | 应用采样器/调度器偏好 |
| `fix_zimage_native.py` | Z_image 原生 bf16 参数修正 |
| `fix_z_format.py` | Z_image JSON 序列化格式修复（separators 坑） |
| `diff_edit.py` | 当前工作流 vs 官方模板 diff（v2：Image 8 + Edit 3 全 11 对；`--export-dir` 批量导出快照到 `../08_官方模板对齐/`） |

### 融合/升级类
| 脚本 | 作用 |
|---|---|
| `upgrade_workflows.py` | 批量升级工作流（6 份对齐 Qwen 2.1 基准：接口补齐/SaveImageAdvanced 替换/RS 链接冲突修复） |
| `fuse_21_features.py` | 融合 2.1 特性（超分 SeedVR2/批量提示词/显存控制/6 个 LoRA 插槽） |
| `fuse_krea2_layout.py` | 融合 Krea2 布局 |
| `apply_resolution_selector.py` | 分辨率选择器节点构造应用 |

### 清理类
| 脚本 | 作用 |
|---|---|
| `clean_edit.py` / `clean_edit2.py` | 编辑工作流基础清理（删注释/ImageCompare/模型名对正） |
| `clear_prompts.py` | 清空所有 prompt |
| `rebuild_flux2_edit.py` | Flux.2 编辑重建（保留 2 张 LoadImage） |
| ~~`del_flux2_sg2.py`~~ | 删 Flux.2 残留第二子图 —— ⚠️ **未随包**：旧 README 引用了它，但原文件夹中实际不存在（一次性脚本未归档） |

### 参考图槽位类
| 脚本 | 作用 |
|---|---|
| `count_ref_images.py` | 统计官方模板/工作流参考图数量 |
| `add_ref_images.py` | Qwen 2.1 加到 10 张 / 2511 补满 3 张 |
| `add_flux2_8.py` | Flux.2 加 6 条参考图链（凑满 8 张） |

### 检查/验证类
| 脚本 | 作用 |
|---|---|
| `verify_workflows.py` / `verify_upgrade.py` / `verify_clear.py` | 各阶段整体验证（`verify_upgrade.py` 另支持仓内样本模式，见第九节） |
| `final_check.py` / `final_confirm.py` | 最终交付检查 |
| `check_fmts.py` / `check_layouts.py` / `check_modes.py` | 格式/布局/静止模式检查 |

⚠️ **可移植性警告**：这些脚本的 `D`/`CONFIG` 表里写死了本机工作流的节点指纹（`main_id`、`unet_link_id`、`iface_order` 等）。对这 11 份工作流精确有效；**换工作流时把它们当操作说明书读、重写 CONFIG，不要直接跑**。

---

## 关键路径速查

| 用途 | 路径 |
|---|---|
| 官方工作流模板 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates\` |
| Image 类工作流 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image\` |
| Edit 类工作流 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Edit\` |
| 节点源码（权威） | `comfy_extras\nodes_qwen.py`、`comfy_extras\nodes_edit_model.py`、`comfy_api_nodes\nodes_bfl.py` |
| 模型目录 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\models\unet\` |

---

## 一、最高优先级经验：官方模板 > 联网搜索

**这是本次改造最深刻的教训。**

- 曾按社区博客/搜索把 Qwen 系 scheduler 改成 beta、Z_image 改成 8 步/turbo；
- 后经**本机官方模板**纠正：Qwen 系应为 `euler + simple`，Z_image 原生 bf16 版为 `25 步 / cfg 4 / res_multistep`；
- 结论：**本机官方模板是最权威依据**，联网搜索的社区资料仅作参考，冲突时以官方模板为准。

### 采样参数权威值（来自官方模板）

| 模型 | 步数 | CFG | 采样器 | 调度器 |
|---|---|---|---|---|
| Qwen-Image-2.1 | 25 | 1 | euler | simple |
| Qwen-Image-Edit-2511 | 40 | 3 | euler | simple |
| Qwen-image-2512 | 25 | 4 | euler | simple |
| FLUX-2-klein-9b（base） | 20+ | 1 | euler | 官方专用 |
| FLUX-2-klein-9b（distilled） | 4 | 1 | euler | Flux2Scheduler 官方调度 |
| Z-image | 25 | 4 | euler | res_multistep |
| Krea2-turbo | 8 | 1 | euler | simple |

> **2026-10-11 复核（数据治理 R2 P0）**：`Krea2-turbo` 的 CFG 曾误记为 4，经官方模板 `image_krea2_turbo_t2i.json` 的 KSampler `widgets_values` 实测为 `[…, 8, 1, 'euler', 'simple', 1]` → **CFG=1**（8 步 / euler / simple），与 `06_文档与结论/采样器和调度器的组合推荐.md`（§第一/二节 cfg=1 官方原值）及 `10_模型家族横评`（`family_config.json` krea2 cfg=1.0、`docs/参数基线与验证流程.md` cfg 1.0）口径一致。此前 05 表 cfg=4 为错误口径，已修正。
>
> 详细清单与证据链见 `../06_文档与结论/采样器和调度器的组合推荐.md`。

---

## 二、节点参考图槽位权威结论（读源码确认）

| 模型 | 节点类型 | 参考图上限 | 加槽方法 |
|---|---|---|---|
| Qwen-Image-2.1 | `TextEncodeQwenImage21` | 官方博客 ≤10 张；节点 Autogrow 槽 image_1~image_16 | ✅ 可加（Autogrow） |
| Qwen-Image-Edit-2511 | `TextEncodeQwenImageEditPlus` | **固定 3 张**（image1/2/3，源码硬编码） | ❌ 不能加，只能补满 3 张 |
| Flux.2 Klein | `ReferenceLatent` 链 | 无硬上限（官方模板 2 张，社区 4~8 张，官方节点文档说 8 张） | ✅ 复制整条链 |

**参考图链结构（Flux.2）**：
```
LoadImage → ImageScaleToTotalPixels(缩放图像像素) → VAEEncode(VAE编码) → ReferenceLatent×2(正/负条件串联)
```

---

## 三、JSON 结构关键知识点

1. **子图节点 type 是 UUID**，真实节点定义在 `definitions.subgraphs`；顶层「节点」是子图接口的封装。
2. **子图 links 是 dict 格式**（`{"id":..,"origin_id":..,...}`），顶层 links 是数组格式（`[id, origin_id, origin_slot, target_id, target_slot, type]`）——改子图链接时别搞混。
3. **JSON 序列化格式坑**：Z_image.json / krea2_turbo.json 写回必须用 `separators=(', ', ': ')`；其余用 compact。用错会导致前端报错或节点丢失。
4. **`widgets_values` 为 `[]` vs `None`**：只是序列化差异，不影响功能（diff 时注意）。
5. 子图接口 `inputs` 数组元素含 `id`(uuid)、`name`、`type`、`linkIds`、`label`、`pos`；顶层主节点 inputs 含 `name/type/widget/link`。
6. **加子图参考图槽位的完整操作**（Qwen Autogrow 类）：子图 `inputs` 尾部追加接口 → 子图内 `-10 → ImageScale/VAEEncode` 连线 → 顶层加 LoadImage + 顶层 link → 主节点 inputs 追加条目并把 `link` 指向新 link id。
7. **加 Flux.2 参考图链**：每张图复制 `ImageScaleToTotalPixels → VAEEncode → ReferenceLatent×2`，conditioning 正/负各串一条链，最后一张的输出接到 CFGGuider 的 positive/negative；同时更新前一张输出 `links` 数组。
8. **子图容器取值可能三处冲突**（positional / named / 内部节点自身 widgets），positional 是运行时真值——详见 `../06_文档与结论/采样器和调度器的组合推荐.md` §6.5。

---

## 四、本次改造的完整操作清单（可复现流程）

### Image 类（8 个，已完成）
1. **选基准**：以 `Qwen_image_2_1_t2i.json` 的分辨率选择器构造为参考；
2. **补全 Text to Image 节点**：补上解码器、采样器、种子、模型选项；
3. **删冗余**：删「保存图像 + 对比图像」，只留 1 个 SaveImageAdvanced；
4. **融合功能**：超分辨率（SeedVR2，mode=4 静止）、批量提示词、显存控制、6 个 LoRA 插槽；
5. **官方模板对齐**：采样器/调度器/步数/CFG 按官方模板；
6. **统一布局**：主节点 [0,0]、LoadImage 左 [-380]、SaveImageAdvanced 右 [330,-10]、size [850,610]；
7. **清空所有 prompt**；
8. **备份**：原版备份进 `Image\新建文件夹\`（*.init.bak / *.official.bak / *.sampler.bak）。

### Edit 类（3 个，已完成）
1. 从官方模板复制：`image_qwen_image_2_1_image_edit.json`、`image_qwen_image_edit_2511.json`（选非 int8，因模型是 nvfp4）、`image_flux2_klein_image_edit_9b_distilled.json`（因模型是 9B fp8 蒸馏版 DarkBeast）；
2. 清理：删 MarkdownNote 注释、ImageCompare、SaveImage→SaveImageAdvanced、清空 prompt、模型文件名对正；
3. 参考图槽位：Qwen 2.1 加到 10 张、Qwen 2511 补满 3 张、Flux.2 加到 8 张（子图1 复制 6 条参考图链）；
4. 编辑类不加批量提示词（编辑是图生图，不需要）。

---

## 五、模型编辑能力结论（本机 unet 目录 8 模型）

**具备编辑功能的 3 个**：
- `Qwen-Image-2.1`（qwen_image_2.1_int8_convrot）— 文生图 + 编辑共用，参考图 ≤10 张
- `Qwen-Image-Edit-2511`（qwen_image_edit_2511_nvfp4）— 专用编辑模型，参考图 ≤3 张
- `Flux.2 Klein 9B`（DarkBeast-Klein9b-V2-BFS-FP8）— 文生图 + 编辑共用，参考图 4~8 张

**纯文生图（无编辑）**：Krea2-turbo、Qwen-image-2512、Z-image-turbo、FLUX-1-dev（仅基础图生图/重绘，编辑需 Kontext 模型未下载）、Z-image（空目录）。

---

## 六、后续维护注意事项

1. 任何工作流改动前先备份进对应 `新建文件夹\`，不跟修改后的混放同目录；
2. 模型文件名必须和子图 UNETLoader 实际加载一致（顶层接口显示不能误导）；
3. 占位模型名（未下载的）不用管，但真实使用的模型必须对正；
4. 默认全量模式；步数/CFG 取官方值最低标准；
5. 改多图槽位时：Qwen 2.1 用 Autogrow（前端加槽最稳），Flux.2 在前端复制参考图链比改 JSON 安全；
6. 官方模板变更时，用 `diff_edit.py` 复查对齐状态；
7. 改完结构后想验证参数是否正确，走 `../02_调度器sigma分析/`（离线）与 `../03_受控跑测/`（实拍）。

---

## 七、幂等与备份四步模板（2026-10-11 起，评估 P2-3）

所有**写工作流文件**的改造脚本统一按四步执行，防止重复改写与误改：

1. **备份**：改动前 `shutil.copy2` 到 `Image\新建文件夹\*.xxx.bak-<时间戳>`（`apply_official.py` 为 `*.official.bak`）；
2. **检测已应用**：用「脚本自身写入的特征」做幂等守卫（`upgrade_workflows.py` 判子图接口含 `scheduler_1` 且顶层已有 `SaveImageAdvanced`；`apply_official.py` 判 `widgets_values` 已与目标一致）；
3. **跳过**：已应用则打印 `[跳过]` 并 continue，不重复写入；
4. **应用 → verify**：应用后必须跑对应 `verify_*` 脚本复核（`verify_upgrade.py` / `verify_workflows.py` 等）。

> 已落地的脚本：`upgrade_workflows.py`（v3：备份 + 守卫）、`apply_official.py`（v2：守卫）。
> 新写结构轨脚本时请沿用本模板；本目录脚本是「当操作说明书读」的一次性手术脚本，换工作流仍需重写 `CONFIG`。
>
> 2026-10-14 补充：本节描述的备份仍照常发生，dry-run 只控制写入时机；具体开关与恢复步骤见第九节 / 第十节。

---

## 八、工作流溯源清单（2026-10-11，评估 P2-4）

`workflows_manifest.json` 是 11 份工作流原件（Image 8 + Edit 3）的仓库内审计记录，由 `gen_workflows_manifest.py` 生成（**只读外部原件，绝不写入 ComfyUI 目录**）：

| 字段 | 含义 |
|---|---|
| `md5` / `size` / `mtime` | 当前原件指纹（改造前后可 diff 校验） |
| `source_template` / `source_md5` | 来源官方模板名及其指纹（模板缺失时为 `null` 并告警） |
| `backups` | 同名备份清单（类别目录下 `*.bak*` + `Image\新建文件夹\` 下同名条目） |

再生成命令（本机实际根为 aki-v3.2，README 约定为 aki-v3，二者均可）：

```bat
python gen_workflows_manifest.py --root "%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows" ^
  --templates "%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates"
```

#### 漂移检测与再生成（2026-10-11 数据治理 R2 P2 补充）

清单由脚本**手动生成**（未接入 CI/钩子），外部原件变更后不会自动更新 → 存在快照漂移风险。维护纪律：

1. **触发再生成的时机**：更新/新增外部工作流原件（`ComfyUI\user\default\workflows\`）后；官方模板目录升级后（`source_template`/`source_md5` 可能变化）。
2. **漂移检测命令**（先备份 → 重跑 → fc 对比，产出为 0 即无漂移）：
   ```bat
   copy workflows_manifest.json workflows_manifest.prev.json
   python gen_workflows_manifest.py --root ... --templates ...
   fc /B workflows_manifest.prev.json workflows_manifest.json
   del workflows_manifest.prev.json
   ```
3. **审查要点**：`mtime`/`md5` 变化说明原件被改动；`source_md5` 变化说明官方模板升级；`backups` 新增说明出现新备份。确认无异常后覆盖 `workflows_manifest.json` 并提交。
4. **只读纪律**：本脚本只读外部原件与模板，绝不写入 ComfyUI 目录（见上）。

---

## 九、dry-run 开关与样本演练（2026-10-14）

所有**写工作流文件**的改造脚本（`apply_official.py` / `apply_sampler_prefs.py` / `upgrade_workflows.py` / `fuse_21_features.py` / `fuse_krea2_layout.py` / `apply_resolution_selector.py` / `fix_zimage_native.py` / `fix_z_format.py` / `clean_edit.py` / `clean_edit2.py` / `clear_prompts.py` / `rebuild_flux2_edit.py` / `add_ref_images.py` / `add_flux2_8.py`）统一接入共享助手 [`dryrun.py`](dryrun.py)，默认关闭。**幂等守卫与备份纪律不变**——dry-run 只影响写入。两个开关：

| 开关 | 作用 |
|---|---|
| `--dry-run` | 不落盘：跳过备份 `copy2` 与 `makedirs`；只打印将修改的文件 + 将写入的结构 diff（以磁盘当前内容为基线，`indent=2` pretty 后的 unified diff）；读取与 `[跳过]` 幂等判定照常执行。 |
| `--target-dir DIR` | 把脚本写死的 `Image` / `Edit` 工作流目录重定向到样本目录 `DIR`；备份自动落入 `DIR\新建文件夹\`，不会污染仓库外的真实 ComfyUI 目录。 |

典型用法（先拿样本目录试一遍，确认 diff 后再对真机执行）：

```bat
:: 0) 先拷一份样本到临时目录（包含同名工作流文件）
xcopy "%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image" "%TEMP%\wf_sample\" /I /Y

:: 1) dry-run 看计划（不写入、不备份）
python apply_official.py --dry-run --target-dir "%TEMP%\wf_sample"
python upgrade_workflows.py --dry-run --target-dir "%TEMP%\wf_sample"

:: 2) 确认无误后，对真机目录正常跑（不带开关 = 老行为）
python apply_official.py
```

> 不带任何参数时，以上所有脚本对工作流文件的**写入内容与备份时机/位置**与接入 dry-run 之前逐字节一致；开关只在显式传入时生效。（控制台日志已统一为 `[备份]/[已写入]/[无变化]` 前缀，不影响落盘内容。）

---

## 十、最小恢复说明（按已有备份将工作流回到改动前）

本目录脚本在改动前都会先拷一份 `*.bak`（`upgrade_workflows.py` 额外附时间戳 `-YYYYMMDD_HHMMSS`）。恢复 = **把备份文件拷回工作流同名路径**，不依赖 Git、不重新手写 JSON。步骤：

1. **定位备份**：`%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image\新建文件夹\` 下按命名取对应一份（同名多个时选时间戳最新）：
   - `Z_image.official.bak` → `apply_official.py` 创建
   - `Z_image.sampler.bak` → `apply_sampler_prefs.py`
   - `Z_image.upgrade.bak-<时间戳>` → `upgrade_workflows.py`
   - `Z_image.pre_fusion.bak` / `Z_image.step3.bak` / `Z_image.layout.bak` → `fuse_*` / `apply_resolution_selector.py`
   - `Z_image.prompt_clear.bak` → `clear_prompts.py`
   - `<name>.init.bak` → `clean_edit.py`（Edit 工作流）
   - `<name>.json.bak` → `apply_resolution_selector.py`（同名旁文件）
   - 无时间戳同名备份多次运行会被覆盖——**想保留多个中间态**，手动拷到带时间戳名字即可（与 `upgrade_workflows.py` 命名一致）。
2. **拷回原位置**（以 `Z_image.json` 为实，PowerShell）：
   ```powershell
   $wf  = "$env:USERPROFILE\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image\Z_image.json"
   $bak = "$env:USERPROFILE\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image\新建文件夹\Z_image.upgrade.bak-20261011_153012"
   Copy-Item -LiteralPath $bak -Destination $wf -Force
   ```
3. **逐字节验证**（与备份前的原件字节一致）：
   ```powershell
   (Get-FileHash -LiteralPath $wf  -Algorithm SHA256).Hash
   (Get-FileHash -LiteralPath $bak -Algorithm SHA256).Hash
   ```
   两行输出相同 → 恢复完成。若之前跑过 `gen_workflows_manifest.py`，也可对照 `workflows_manifest.json` 中记录的 `md5` / `size` / `mtime`。
4. **Edit 类同构**：将上面 `Image` 换为 `Edit`；`clean_edit.py` 将备份统一写入 `Image\新建文件夹\`，因此 Edit 工作流的 `.init.bak` 也从同一目录取回。

> 安全垫：恢复前先拷一份当前态作 `.pre-restore.bak-<时间戳>`，防止“恢复错了”后无法回到更新后的状态。dry-run 不产生备份，也不需要恢复。

---

## 九、仓内可复现验收路径（2026-10-14，verify_upgrade 样本模式）

参照 `10_模型家族横评` 三个门禁在 CI 里以 selftest/合成样本运行的做法，`verify_upgrade.py` 新增只作用于**仓内脱敏样本**的验收路径，保持本轨「不在真实原件上盲跑」定位：

- **样本**：`sample_workflow_minimal.json` —— 按升级后布局（主节点 + ResolutionSelector + SaveImageAdvanced + 单子图）手工构造的最小工作流，无任何本机路径/真实模型名/真实 UUID。
- **不变量标签**：每条违背以 `[INV:名称]` 前缀输出（如 `iface-slot`、`toplink-unique`、`counters`、`layout-rs` 等），失败信息可直接定位不变量。
- **命令**（纯标准库，CI 可直接跑）：
  ```bat
  python verify_upgrade.py --sample      :: 样本全部不变量通过 → exit 0
  python verify_upgrade.py --selftest    :: 样本通过 + 逐类内存破坏必须 FAIL 且指明不变量
  python verify_upgrade.py --sample --break iface-slot   :: 演示单类失败（不落盘，不碰样本文件）
  ```
- **CI 接入**：`.github/workflows/ci.yml` 的 Gate ④ 以 `--selftest` 运行；破坏样本任一处结构不变量会使该步骤失败并在日志指明具体 `[INV:…]`。
- **退出码**：0 通过 / 1 存在失败项 / 2 用法或 IO 错；无参数仍为本机原件模式（需本机 ComfyUI 目录，缺目录时明确报环境缺失）。
