# 05 结构改造脚本 · USAGE（怎么跑）

> 本页是**操作手册**：入口命令、输入、输出、最小示例、坏了怎么查。
> 为什么改、改了什么、参数权威值从哪来——见同目录 [`README.md`](README.md)（结论与经验内核）；
> 采样器/调度器权威值见 [`../06_文档与结论/采样器和调度器的组合推荐.md`](../06_文档与结论/采样器和调度器的组合推荐.md)。

---

## 一、这个目录是干什么的

把 ComfyUI 工作流 JSON 当**结构化文本**做外科手术：官方模板参数对齐、参考图槽位补齐、分辨率选择器接入、批量升级与清理，每步改完配套校验。
11 份工作流（Image 8 + Edit 3）就是 2026-09 那次「取长补短」改造的作业对象，脚本里写死了它们的节点指纹（`main_id`、`unet_link_id`、`iface_order` 等）。

**定位：一次性的手术脚本，不是通用工具。** 换工作流 = 当操作说明书读、重写脚本里的 `CONFIG`/`EDITS` 常量，别指望直接跑通。

---

## 二、前置条件

| 项 | 要求 | 2026-11-10 本机核对 |
|---|---|---|
| Python | 3.8+，**纯标准库**（`json`/`os`/`shutil`/`uuid`/`difflib`），不 import `comfy`/`torch`/`numpy` | ✅ 任意 python3 可跑，无需 ComfyUI 自带 python |
| 工作流目录 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image`（8 份）与 `\Edit`（3 份） | ✅ 存在 |
| 官方模板目录 | `%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates` | ✅ 存在 |
| 运行位置 | **必须 cd 到本目录**：所有改造脚本 `import dryrun`（同目录模块，无包结构） | — |

> 路径里的 `aki-v3.2` 是脚本常量写死的版本号；README 早期正文写作 `aki-v3`，本机实际为 `aki-v3.2`。装在别的版本目录时见第五节「路径不存在」。

---

## 三、入口命令

26 个 `.py` = 24 个改造/核查脚本 + 1 个只读清单生成器（`gen_workflows_manifest.py`）+ 1 个共享助手（`dryrun.py`，不单独运行）。按「能不能带参数」分三类：

### 3.1 改造类——会写工作流文件（14 个，统一带两个开关）

命令形态（不带开关 = 老行为，写入内容与备份时机和接入 dry-run 之前逐字节一致）：

```powershell
python <脚本>.py                       # 直接改真机工作流（自带幂等守卫 + 备份）
python <脚本>.py --dry-run             # 只打印将改的文件 + 结构 diff，不备份、不落盘
python <脚本>.py --dry-run --target-dir "<样本目录>"    # 拿样本目录演练
```

| 脚本 | 作用 | 写入目标 | 自动备份文件名（落在 `新建文件夹\`） |
|---|---|---|---|
| `apply_official.py` | 按官方模板对齐采样参数（含 flux.1-dev 的 FluxGuidance→4） | Image | `*.official.bak` |
| `apply_sampler_prefs.py` | 应用采样器/调度器偏好 | Image | `*.sampler.bak` |
| `upgrade_workflows.py` | 批量升级（接口补齐 / SaveImageAdvanced 替换 / RS 链接冲突修复） | Image | `*.upgrade.bak-<YYYYMMDD_HHMMSS>` |
| `fuse_21_features.py` | 融合 2.1 特性（超分 / 批量提示词 / 显存控制 / 6 个 LoRA 槽） | Image | `*.pre_fusion.bak` + `*.step3.bak` |
| `fuse_krea2_layout.py` | 融合 Krea2 布局 | Image | `*.pre_fusion.bak` + `*.layout.bak` |
| `apply_resolution_selector.py` | 构造并接入分辨率选择器节点 | Image | `<name>.json.bak`（写在原件旁，仅当尚不存在时创建） |
| `clean_edit.py` | Edit 工作流基础清理（删注释 / ImageCompare / 模型名对正） | Edit | `*.init.bak` |
| `clear_prompts.py` | 清空所有 prompt | Image | `*.prompt_clear.bak` |
| `clean_edit2.py` | Edit 工作流二次清理 | Edit | **无**（改前手动复制） |
| `rebuild_flux2_edit.py` | Flux.2 编辑重建（保留 2 张 LoadImage） | Edit | **无**（改前手动复制） |
| `add_ref_images.py` | Qwen 2.1 加到 10 张 / 2511 补满 3 张 | Image/Edit | **无**（改前手动复制） |
| `add_flux2_8.py` | Flux.2 加 6 条参考图链（凑满 8 张） | Edit | **无**（改前手动复制） |
| `fix_zimage_native.py` | Z_image 原生 bf16 参数修正 | Image | **无**（改前手动复制） |
| `fix_z_format.py` | Z_image JSON 序列化格式修复（`separators` 坑，从 `Z_image.step3.bak` 嗅探原格式） | Image | **无**（改前手动复制） |

> ⚠️ 表里标「无」的 6 个脚本**确实不调 `guard_backup`**（源码核对，2026-11-10）：它们**不会**自动备份，跑之前先 `Copy-Item` 一份。README §九把 14 个脚本都写作「统一接入 dry-run」，接入的是**开关**，不等于自动备份。

### 3.2 只读类——自带参数（3 个）

| 脚本 | 参数 | 作用 |
|---|---|---|
| `gen_workflows_manifest.py` | `--root <路径>`（默认 `...\workflows`）、`--templates <路径>` | 生成 `workflows_manifest.json`（11 份原件的 md5 / 大小 / mtime / 来源模板 / 备份清单）。**只读外部原件，绝不写 ComfyUI 目录** |
| `diff_edit.py` | `--templates`、`--edit`、`--image`、`--export-dir <目录>` | 当前工作流 vs 官方模板逐对照；带 `--export-dir` 时导出 `../08_官方模板对齐/<名>.diff.md` |
| `verify_upgrade.py` | `--sample [PATH]`、`--break <不变量>`、`--selftest` | 结构不变量校验。三种模式：原件模式（无参）/ 仓内样本 / 自测演练 |

`verify_upgrade.py` 的不变量标签可直接定位失败点：`toplink-dup` `toplink-refs` `toplink-types` `sublink-refs` `top-sub-idconflict` `iface-slot` `main-widgets` `save-single` `layout-rs` `counters` `wiring-rs`。

### 3.3 只读类——无参数（8 个，路径写死）

`verify_workflows.py` · `verify_clear.py` · `final_check.py` · `final_confirm.py` · `check_fmts.py` · `check_layouts.py` · `check_modes.py` · `count_ref_images.py`

直接 `python <脚本>.py`，**不接受任何参数**，读的目录写死在源码顶部（`Image` 目录，或 `Image\新建文件夹` 里的 `.bak`）。换机/换目录只能改常量。

---

## 四、输入与输出

| | 内容 |
|---|---|
| **输入** | ① 外部工作流 JSON：`...\workflows\Image\` 8 份 + `\Edit\` 3 份（不在本仓、不入库）；② 官方模板目录（仅 `diff_edit.py` / `gen_workflows_manifest.py` 读）；③ 已有备份 `*.bak`（`fix_z_format.py` 与只读校验读，用于格式嗅探和差异对比） |
| **输出（写盘）** | 覆盖写回**原路径**的同一份 JSON；序列化格式按原文件嗅探（有 `\n  ` 用 `indent=2`，有 `", "` 用带空格分隔符），不擅自统一 |
| **输出（备份）** | 见 3.1 表；目标为工作流目录下的 `新建文件夹\`（无备份脚本除外） |
| **输出（控制台）** | 每文件一行状态：`[备份]` / `[已写入]` / `[无变化]`（内容与将写入一致，跳过）/ `[跳过]`（幂等守卫命中）/ `[dry-run]`（计划 + unified diff，默认最多 40 行，超出截断并提示总行数） |
| **退出码** | `verify_upgrade.py`：0 通过 / 1 有失败项 / 2 用法或 IO 错；其余改造脚本无约定退出码，靠日志判断 |

---

## 五、最小示例（零风险，不碰真机文件）

先跑仓内脱敏样本，确认 python 环境与脚本本身没问题：

```powershell
cd "$env:USERPROFILE\APP\repository\ComfyUI-Experiment-Toolbox\05_结构改造脚本"

python verify_upgrade.py --sample                     # 期望：总体 全部通过 → exit 0
python verify_upgrade.py --sample --break iface-slot # 期望：exit 1，且报 [INV:iface-slot]
```

实测输出（2026-11-10）：

```
sample_workflow_minimal.json
  接口: ['width', 'height', 'scheduler', 'scheduler_1', 'seed', 'unet_name']
  [OK] 全部检查通过
总体: 全部通过
```

`--break` 演示失败信号，破坏只发生在**内存副本**上，样本文件不被改动：

```
- [INV:iface-slot] 接口 scheduler(索引 2) 链接 202 origin_slot=0 不一致
总体: 存在失败项
```

再看一次「真机改造会长什么样」（不写入、不备份）：

```powershell
# 先把真机 Image 目录拷成样本，再对着样本 dry-run
Copy-Item -LiteralPath "$env:USERPROFILE\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image" `
          -Destination "$env:TEMP\wf_sample" -Recurse -Force
python apply_official.py --dry-run --target-dir "$env:TEMP\wf_sample"
```

`--target-dir` 的落点规则：目录 basename 与被替换目录同名、或原名含 `Image`/`Edit` 时直接替换；原名目录已不存在时也替换（保证样本演练可用）；否则保持原路径。

---

## 六、失败时怎么查

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'dryrun'` | 没在本目录运行（从仓根 `python 05_结构改造脚本\xxx.py`） | `cd` 进本目录再跑 |
| `FileNotFoundError: ...\workflows\Image\Z_image.json` | 脚本常量写死 `aki-v3.2`，实际装在别的版本/别的盘 | 改造类加 `--target-dir` 指向真实目录；只读类（3.3）只能改源码顶部 `D` 常量 |
| `FileNotFoundError: ...\Z_image.step3.bak` | `fix_z_format.py` 依赖前序步骤留下的 `step3.bak` | 先补出该备份（或改脚本里的 `bak` 路径）；无备份时**不要**让它直接写 |
| `[环境缺失] 本机工作流目录不存在` + exit 2 | `verify_upgrade.py` 无参进了原件模式 | CI / 无本机环境改用 `--sample` 或 `--selftest` |
| `JSONDecodeError: Expecting ...` | 上一次写入被中断，或人手动改坏了 JSON | 工作流目录 `新建文件夹\` 取最近 `.bak` 拷回同名路径（README §10 有逐字节校验步骤） |
| `UnicodeEncodeError: 'gbk' codec can't encode` | 控制台代码页不是 UTF-8（`>` 重定向时尤其明显） | 先 `chcp 65001`；或用根目录 `run.py`（它强制 UTF-8 且以子进程调用，行为等同） |
| 跑完一行 `[跳过]`，文件没动 | 幂等守卫命中：`widgets_values` 已等于目标值 | 正常。想看「为什么跳过」用 `--dry-run`，或 `diff_edit.py` 对照官方模板 |
| `[dry-run] ... （无行级差异，仅序列化格式/键序变化）` | 内容等价，只是键序/缩进不同 | 正常，不是故障 |
| 改完前端打不开 / 节点丢失 | 序列化格式写错（Z_image、krea2_turbo 必须 `separators=(', ', ': ')`） | 用 `fix_z_format.py --dry-run` 确认格式，再回拷 `.bak` 重来 |
| 想整体回退 | — | 备份拷回同名路径，`Get-FileHash -Algorithm SHA256` 两行相同即恢复完成（README §10 给了完整命令） |
