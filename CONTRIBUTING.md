# 贡献指南（CONTRIBUTING）

> 本文件是随仓分发的贡献与质量规范（2026-10-15 建立；对应「质量工程效率 P1-3 / 开发者体验 P1-1」）。
> 维护者本地另有一份更详细的 AI 辅助开发指南（不入库）；本文件是其「公开仓红线 + 变更纪律」的公开子集。

## 仓库定位

ComfyUI 采样器/调度器受控实验（参数轨 01~04+07）与工作流结构改造（结构轨 05+08）的两轨工具箱，共享结论内核 `06_文档与结论/`。**目录编号即架构边界**，脚本依赖方向见根 README 第四节；跨轨依赖由 CI Gate ⑥ 强制（违规即红）。

## 公开仓红线（任何改动前先读）

1. **不含本机字面绝对路径**：`.py` 一律 `os.path.expandvars(r"%USERPROFILE%\...")` 形态；配置/文档用 `%USERPROFILE%` / `%WINDIR%` 变量形态。CI Gate ⑤ 扫描全部跟踪的 `.py/.json/.md`（`99_归档/` 历史原件除外），命中即红。
2. **不含密钥与凭据形状**：gitleaks 三层防线（pre-commit / CI push+PR / 每周全量历史）。误报在 `gitleaks.toml` 追加 allowlist 并写明理由，不放宽规则本身。
3. **运行产物不入库**：`__pycache__/`、`*.bak*`、`09_Web面板/output/`、运行日志等已被 `.gitignore` 排除。

## 变更纪律

- **归位**：新脚本/新文档放进对应编号轨；不动 `06_文档与结论/` 共享结论内核（参考文档原件在工作流目录 `%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\`，更新以原件为准；原件不可达时退到仓内 `08_官方模板对齐/` 的对照快照——2026-10-11 生成的「当前工作流 vs 官方模板」diff，是对照物、非现役原件）。
- **备份**：任何写盘类脚本改文件前必须先 `.bak-<时间戳>` 备份（统一走 `05_结构改造脚本/dryrun.py` 的备份纪律）。
- **幂等四步**：备份 → 已应用检测 → 跳过 → 应用后跑对应 `verify_*`（见 05 README 第七节）。
- **dry-run 优先**：结构轨脚本先 `--dry-run --target-dir` 演练，确认 diff 再实跑。
- **路径常量**：集中在文件顶部，改常量不改逻辑；当前 ComfyUI 根统一为 `%USERPROFILE%\APP\ComfyUI-aki-v3.2`，换机只改 `run.bat` 顶部 `PY=` 与各脚本顶部常量。

## 验证要求（提交前本地最少跑这些）

```bat
python -m compileall -q .
python -X utf8 -m unittest discover -s tests
python "05_结构改造脚本/verify_upgrade.py" --selftest
python "10_模型家族横评/lib_ledger_verify.py" --selftest
```

改动 `09_Web面板/index.html` 前端逻辑后另跑 `09_Web面板/test_dom.js`（jsdom，本地环境）。CI 会复跑以上检查（语法编译 / 锁文件 / 门禁自检×3 / 结构样本验收 / 路径红线 Gate ⑤ / 依赖方向 Gate ⑥ / 单测 Gate ⑦）。

## 提交与评审规范

- 提交信息 `type(scope): 中文描述`（fix/feat/docs/test/ci/chore/refactor），正文写明「对应报告哪条建议 + 变更内容」。
- `git add` 用显式路径，不用 `add -A` / `add .`。
- **workflow / 门禁 / CI 配置类变更走 PR**，按 `.github/PULL_REQUEST_TEMPLATE.md` 完成自审清单后再请求合并。
- push 由维护者执行；贡献者发 PR 前请确保本地验证全绿。

## 依赖治理

第三方依赖锁定在 `requirements-lock.txt`（当前仅 numpy/Pillow）。新增第三方依赖前先在 PR 说明用途与替代方案；纯标准库能实现的不引依赖（CI 与 Web 面板均为零第三方依赖设计）。
