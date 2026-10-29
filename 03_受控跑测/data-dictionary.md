# 数据字典（data-dictionary）

> 本仓数据治理登记（2026-10-11，数据管理治理评估 R2 P1）：把散落在脚本 docstring / README 表格里的字段约定
> 统一登记为一处权威字典，并记录 schema 版本。改字段（新增/改名/删字段）时必须同步更新本表并 bump 对应 `schema_version`。
> 覆盖范围：03 跑测日志（JSONL + 合并视图）、07 样例数据 json、05 工作流溯源清单。10 横评指标字段见
> `10_模型家族横评/lib_image_qc_enh.py` 的 `METRIC_SOURCES`（含 legacy 来源标注）。

## 1. 03 受控跑测日志（append-only JSONL，唯一事实源）

- 协议版本：`schema_version` 字段；当前 `SCHEMA_VERSION = 2`（v2 协议，2026-10-11 起显式打标）。
- 旧记录（v2 上线前落盘）无 `schema_version` 字段，读取方一律 `.get("schema_version")` 容错。
- 合并视图 `<log>.json` 由 jsonl 重建，同 key 取最新一条（见 `logutil.py`）。

| 字段 | 类型 | 含义 | 来源/写入方 | 引入版本 |
|---|---|---|---|---|
| `schema_version` | int | 记录 schema 版本（缺失=旧记录） | `logutil.append_record`（setdefault） | 2 |
| `ts` | str | 本地时间 `%Y-%m-%d %H:%M:%S` | run_models / run_combos 落盘处 | 2 |
| `seed` | int | 实际种子：run_combos=build_prompt.SEED(1111119)；run_models=扁平化 KSampler 运行时值 | 同上 | 2 |
| `steps` | int\|null | run_combos 固定 25；run_models 取运行时值（custom 链路读不到→null） | 同上 | 2 |
| `cfg` | float\|null | 同上（run_combos 固定 1） | 同上 | 2 |
| `py` | str | 解释器版本 `platform.python_version()` | 同上 | 2 |
| `comfy` | str\|null | ComfyUI 版本（/system_stats；服务未启动→null） | 同上 | 2 |
| `label` | str | 组合标签（`<序号>_<sampler>_<scheduler>` 等） | 同上 | 1（旧） |
| `model` | str | 模型标签（跨模型跑测） | run_models | 1（旧） |
| `combo` | str | 组合名（run_combos） | run_combos | 1（旧） |
| `sampler` / `scheduler` | str | 采样器 / 调度器名 | 同上 | 1（旧） |
| `ok` | bool | 是否成功（false=异常数据标记） | 同上 | 1（旧） |
| `sec` | number | 耗时（秒） | 同上 | 1（旧） |
| `files` | list[str] | 产物文件名清单 | 同上 | 1（旧） |
| `error` | str\|null | 失败原因（成功为 null） | 同上 | 1（旧） |
| `note` | str | 备注（如官方推荐来源） | 同上 | 1（旧） |
| `prompt_id` | str\|缺失 | 提交 `/prompt` 返回的号，用于事后与服务端 `history/<pid>` 及节点级执行对齐；扁平化失败与提交失败的记录没有该字段，2026-10-29 之前的历史记录也没有，读取方一律 `.get("prompt_id")` 容错 | run_models / run_combos 出图记录 | 2（补字段，不升 schema 版本） |

## 2. 07 样例输出与数据（审计链副本 json）

| 文件 | 字段 | 含义 | 来源 |
|---|---|---|---|
| `result_log.json` | label/sampler/scheduler/note/ok/sec/files/error | 09-22 十七组逐组日志 | 03 run_combos（旧版覆写日志，v2 起由 jsonl 重建） |
| `model_test_log.json` | 同 result_log + model 字段 | 跨模型跑测日志（历史曾被覆写只剩失败记录，v2 已修复） | 03 run_models |
| `cfg_probe_log.json` | label/cfg/neg/note/ok/sec/files | cfg×负向探针逐组耗时 | 03 cfg_probe |
| `metrics.json` | label/size/brightness/contrast_std/sharpness_lapvar/colorfulness/file_kb | 单模型客观指标 | 04 metrics.py |
| `model_metrics.json` | 模型/组合/亮度/对比度/锐度/色彩度/与基线相似度/相对变化% | 跨模型指标表 | 04 analyze_models.py |
| `similarity.json` | 组合间相似度 + 最近邻 | 「多组合等价」量化证据 | 04 focus_sheet.py |

> 07 各 json 均可能被 04/06/10 引用为证据；改动 04 脚本输出字段时须同步本表与 06/07 README。

## 3. 05 工作流溯源清单（workflows_manifest.json）

| 路径 | 字段 | 含义 |
|---|---|---|
| `meta` | `generator` / `generated_at` / `root` / `templates_dir` / `note` | 生成器、生成时间、外部原件根目录、模板目录、说明 |
| `workflows[]` | `category` / `file` / `path` | 类别（Image/Edit）、文件名、外部绝对路径 |
| | `md5` / `size` / `mtime` | 当前原件指纹（改造前后 diff 校验用） |
| | `source_template` / `source_md5` | 来源官方模板名及其指纹（模板缺失时 null 并告警） |
| | `backups` | 同名备份清单（`*.bak*` + `Image\新建文件夹\` 下条目） |

> 结构说明与再生成命令见 `05_结构改造脚本/README.md` 第八节；清单由 `gen_workflows_manifest.py` 手动生成（外部原件变更后需重跑，见该节「漂移检测与再生成」）。

## 4. 变更纪律

1. 新增/改名/删除字段：同步更新本表 + bump 对应 `schema_version`（03 日志）；07/05 数据按文件说明同步 README。
2. 破坏性变更（删字段/改类型）：先评估旧记录读取方（`.get` 容错或迁移），留痕于本表「引入版本」列。
3. 本表为唯一权威字典；发现字段口径不一致（如历史 Krea2 cfg 打架）时在此登记处置结论。
