# Changelog

本仓所有值得注意的变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
发布与回滚口径见 [`docs/release-governance.md`](docs/release-governance.md)。

> 归类口径：本文件条目直接取自 `git log` 的提交标题（未二次改写），映射为
> `feat→Added`、`fix→Fixed`、`perf/ci/chore/docs/test→Changed`。

## [Unreleased]

**现状（2026-10-18 实测）**：本仓**尚无远端 tag 与 GitHub Release**——`git ls-remote --tags origin` 为空，
`GET /repos/ReSerendipity/ComfyUI-Experiment-Toolbox/tags` 与 `/releases` 均返回 0 条。
本仓唯一权威版本位即 Git tag `vMAJOR.MINOR.PATCH`（见 `docs/release-governance.md` §1），
因此当前**没有可回填的 `[VERSION] - YYYY-MM-DD` 段落**；下面列出的是建仓至 2026-10-18 之间尚未发布的变更，
首个正式 `v*` tag 推送时，本段整体改名为 `[X.Y.Z] - YYYY-MM-DD`。

### Added

- `feat(e3)`: 一键全链 run full + E1~E8 入口注册（2026-10-16）
- `feat(e8)`: 提示词变体闭环 —— 矩阵生成 → 文本质检 → 跑测配置 → 淘汰判定（2026-10-16）
- `feat(e7)`: Web 面板「⑤ 视频档位」区 —— 跑测器上屏（2026-10-16）
- `feat(e6)`: fgate 名册审计扩展 —— 同底座双量化 + 孤儿文件两维度（2026-10-16）
- `feat(e5)`: 跨快照趋势回归 ftrend —— 检出跨时间的硬回归（2026-10-16）
- `feat(e1)`: 视频质检 vqc —— 容器层 + 抽帧层 + 时序层三层只读检查（2026-10-16）
- `feat(e2+e4)`: 显存自适应档位 + 适配器驱动视频跑测器（2026-10-16）
- `feat(受控跑测)`: MiniMax H3 t2v 时长档位跑测器（run.py h3dur 入口）（2026-10-15）

### Changed

- `perf(gate)`: 名册基线改 256MB 哈希上限，check 292s → ~6s（2026-10-16）
- `ci`: 门禁扩至 ⑪ —— E1/E2/E5/E8 四个新 selftest 接入（2026-10-16）
- `ci(gates)`: 11 道门禁逐步失败隔离，一道红不再遮住其余（2026-10-17）
- `ci(arch)`: Gate ⑥ 模块依赖方向门禁（架构 P1-1）（2026-10-15）
- `chore(merge)`: 集成 origin/main 孪生分叉（重写历史遗留）（2026-10-17）
- `chore(identity)`: .mailmap 归一个人邮箱显示（红线 #4 补正）（2026-10-18）
- `chore(gitignore)`: AGENTS.md 仅本地保留（治理规范 §7）（2026-10-13）
- `chore(gitignore)`: 忽略 .qoder/ 本地评估产物（2026-10-13）
- `chore(readme)`: 建立 README 双版本制度（内部版 docs/README.internal.md 仅本地保留）（2026-10-13）
- `chore`: 修正 run.bat 的 ComfyUI python 路径笔误（aki-v3 -> aki-v3.2）（2026-10-15）
- `test`: 新增 tests/ 标准库单测并接入 CI Gate ⑦（2026-10-15）
- `docs(release)`: 新建 docs/release-governance.md 并最小修正发布链（D-03）（2026-10-18）
- `docs(governance)`: CONTRIBUTING.md 随仓治理规范 + PR 自审模板（2026-10-15）
- `docs(readme)`: 补全官方模板包的真实位置（2026-10-17）
- `docs(readme)`: 合并沿革与映射表迁内部版，根 README 留对外内容（2026-10-13）
- `docs(agents)`: 修正三条不可解析的仓外路径指针（2026-10-16）
- `docs(06)`: 停止把技能快照伪装成本仓可装载技能，并补人工指路（2026-10-17）
- `docs(contributing)`: 补上本地凭据防线的安装与自检口径（2026-10-17）
- `docs(contributing)`: 给强制备份产物定现役检索口径（2026-10-17）
- `docs`: 功能扩展方案（2026-10-15，E1~E8 全部落地）（2026-10-16）

### Fixed

- `fix(10)`: Gate ③ 同长改写断言去除时钟依赖（2026-10-17）
- `fix(gate)`: 修正 Gate ⑤ 的 NUL 分隔符并补空集失败闸（2026-10-16）
- `fix(privacy)`: 本机字面路径脱敏为 %USERPROFILE%/占位符形态，Gate ⑤ 扩面至 .json/.md（架构 P1-3）（2026-10-15）
- `fix(paths)`: ComfyUI 根路径口径全仓收敛为 aki-v3.2（架构 P1-2/DX P1-3）（2026-10-15）
- `fix`: 全仓 aki-v3 硬编码清零 + bench_family loader 规范化 + gate 默认落盘（2026-10-15）
- `fix(run)`: build_env 注入 ComfyUI 根至 PYTHONPATH；family_config 对齐本机实存模型（2026-10-15）
- `fix(flatten)`: _link 类型归一 —— 子图 links 混用 int/str id 导致 str-vs-int 崩溃（2026-10-15）
- `fix(flatten)`: __main__ 默认工作流路径笔误（aki-v3 -> aki-v3.2）（2026-10-15）
- `fix(flatten)`: 容器输入注入按 widget 占位对齐；可达性裁剪纳入视频输出节点（2026-10-15）

> `Deprecated` / `Removed` / `Security` 三类：建仓至本记录日（2026-10-18）无对应提交标题，故不设小节。
