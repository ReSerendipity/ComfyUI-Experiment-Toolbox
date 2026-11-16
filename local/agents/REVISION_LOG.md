# REVISION_LOG（自进化修订记录）

> 本文件由自进化协议维护：每次更新根 `AGENTS.md` 后追加一行，不删不改历史行。
> 路径优先 `local/agents/REVISION_LOG.md`；存量 `docs/agents/REVISION_LOG.md` 视为历史分片。
> 顶部「自进化版本」必须与最后一行版本对应；有 `scripts/check_revision_log.py` 的仓继续用机械闸。

| 自进化版本 | 日期 | 触发原因 | 更新内容摘要 | 对应项目版本 | 已校验 |
| :---: | ---------- | --- | --- | :---: | :-: |
| v1.0 | YYYY-MM-DD | 初始化台账 | 建立 GOTCHAS / REVISION_LOG 标准表头 | 当前版本 | — |
| v1.1 | 2026-10-31 | 新增第三轨 `11_版式化文生图`（提示词结构维度），需在根 `AGENTS.md` 登记定位、红线与入口 | §0 定位补「第三轨」；§3 红线改为「两轨 + 第三轨 11，编号 01~11 勿重排」；§4 补 `lay/layrun/laygal` 入口；§5 目录补 `11_版式化文生图`；GOTCHAS 追加 #10~#14 | 未发版 | 是 |
| v1.2 | 2026-11-01 | 同步治理 §17 自主收口条款（ADR-0015） | 根 AGENTS.md §6 增「提交 / 推送 / 合并 / CI 监控在任务结尾自主完成，不询问用户」一行 | — | ✅ |
| v1.3 | 2026-11-03 | 第三轨 `11` 从「单模型 8 页实例」扩到「12 部短篇集 88 页 + 跨模型对照 + 格数上限实测」，需在根 `AGENTS.md` 同步定位、入口与目录 | §0 定位补「主线 MOSS + `model_ab.py` 跨模型对照 + `panel_test.py` 格数上限」；§4 补 `build_series` / `model_ab` / `panel_test` 三个入口；§5 目录行同步；CHANGELOG 补 5 条 Added + 2 条 Fixed；GOTCHAS 追加 #15~#31 | 未发版 | 是 |
| v1.4 | 2026-11-16 | ComfyUI 两份技能（headless-ab-test / workflow-diff）自 Agent-Knowledge 收编迁移，原 WorkBuddy 原件与存档删除，06 文档升为真源并在根 AGENTS.md 更新指路 | 06/skill_comfyui-headless-ab-test.md 升全量版真源 + 新增 skill_comfyui-workflow-diff.md；06/README.md 更新登记两行；§3 指路行改双文档真源口径；CHANGELOG Changed 补 1 条；本次无踩坑、GOTCHAS 无追加 | 未发版 | ✅ |
