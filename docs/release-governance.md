# 发布 / 回滚 规范（ComfyUI-Experiment-Toolbox）

> **来源与权威**：公共条款见 `ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10（发布 / 分发统一规范，2026-10-18）。
> 本文件由 `ReSerendipity/.github` 的 `RELEASE_GOVERNANCE_TEMPLATE.md` 本地化而来，只填本仓特有内容，不重写、不抵触 §10 的公共条款。
> 生成任务：D-03（阶段 D）。校准依据脚本：`ReSerendipity/.github` 的 `.github/scripts/check-release-standard.sh`。

---

## 0. 远端优先（根原则，不可改写）

发布链的构建、打包、扫描、上传、推送**全部在 GitHub Actions 远端完成**；本地只做三件事：改版本位、落 CHANGELOG、`git tag` + `git push`。本地不执行打包 / 镜像构建 / 发布上传。

本仓是 ComfyUI 实验脚本与工作流工具包，唯一可分发物是**源码归档**；该归档在 `ubuntu-latest` runner 上用 `git archive` 现场生成，本地不产出任何发布交付物。

## 1. 版本号规范

- 遵循 **SemVer** `MAJOR.MINOR.PATCH`；预发布用 `-alpha.N` / `-beta.N` / `-rc.N`。
- **唯一权威版本位**：**Git tag 本身**（`vMAJOR.MINOR.PATCH`）。本仓是脚本工具包，**无** `pyproject.toml` / `setup.py` / `package.json` / `config.yaml` 等仓内版本声明文件，也不发布 wheel / sdist。
- 当前已推送版本位：**尚无远端 tag**（`git ls-remote --tags origin` 为空，无 GitHub Release）。本地历史 tag（如 `v0.1.0`、`v29-*`）为实验期标记，未推送，不构成正式发布基线。
- 必须同步的其它版本位：**无**。
- 版本位漂移校验：本仓当前无仓内版本文件可漂移；若未来引入 `pyproject.toml` 等打包声明，须补 `tests/test_version_consistency.py` 钉住多点一致（漂一处即判红）——**待定（负责人 + 触发条件：引入首个打包/版本声明文件时）**。
- 自动化方式：**手动 tag（人工）**。本仓**未**使用 release-please，无自动版本位 PR。

## 2. CHANGELOG 管理

- 遵循 **Keep a Changelog**：`Added / Changed / Fixed / Deprecated / Removed / Security`。
- 每次合并 `main` 在 `[Unreleased]` 追加；type 映射 `feat→Added`、`fix→Fixed`、`refactor→Changed`。
- 发版时 `[Unreleased]` → `[VERSION] - YYYY-MM-DD`。
- **现状缺口**：本仓根目录尚无 `CHANGELOG.md`（`check-release-standard.sh` 对此报 FAIL）。首次打 `v*` tag 推送前须按 Keep a Changelog 初始化——**待定（负责人 + 触发条件：首个正式 `v*` tag 推送前）**。

## 3. 发布流程（远端）

1. 确认 CHANGELOG `[Unreleased]` 条目完整（首次发版前先建 `CHANGELOG.md`，见 §2）。
2. 同步版本位：本仓版本位即 tag，无其它位需同步。
3. 本地打 tag 并推送：`git tag v<X.Y.Z>` → `git push origin v<X.Y.Z>`。
4. 远端凭 tag 触发 `.github/workflows/release.yml`（`on: push: tags: v*`）：
   - checkout 被打 tag 的提交；
   - job 内校验 tag 匹配 `^v[0-9]+\.[0-9]+\.[0-9]+$`；
   - `git archive` 生成源码归档，`sha256sum` 生成 `SHA256SUMS.txt`；
   - `gh release create --generate-notes` 建 Release，并 `gh release upload` 挂归档与校验文件。
5. 发布形态：当前为 **tag 推送即自动 published**（非 draft）。§10.2 的「远端建 draft → 人工审核后 published」口径尚未启用——**待定（负责人 + 触发条件：首个正式 Release 发布前评审是否切 draft 模式）**。
6. 盯到终态：`gh run list` 确认绿；红了当场修或 revert 止损。

## 4. 分发产物与完整性

| 产物 | 构建位置 | 标签 / 命名 | 完整性手段 |
|---|---|---|---|
| 源码归档 `ComfyUI-Experiment-Toolbox-<TAG>.tar.gz` | **远端**（`release.yml`，ubuntu-latest） | 不可变 SemVer tag（`v<X.Y.Z>`）；**禁 floating `latest`** | 同 Release 资产 `SHA256SUMS.txt` |

- 本仓**无**容器镜像、**无**桌面安装包（Tauri / NSIS / APK）、**无** npm 包：ghcr 推送、Trivy `CRITICAL,HIGH` 阻断、`.trivyignore.yaml` 豁免登记、`provenance: true` / `sbom: true` **均不适用**。
- **不使用 GPG 分离签名**（2026-10-18 裁决）。本仓历史上从未存在 `gpg-signed-release.yml`（§10.6 已点名确认），完整性由 `SHA256SUMS.txt` 承担（防传输损坏）。
- 使用者校验方式：下载归档与 `SHA256SUMS.txt` 后执行 `sha256sum -c SHA256SUMS.txt`。

## 5. 回滚

- **判定**（满足任一即触发）：Release 归档无法解压、`sha256sum -c SHA256SUMS.txt` 不匹配、tag 发布后 `release.yml` / CI 门禁变红、或归档内容与预期提交不符。
- **执行**：`git revert <bad-commit>`（保历史、可再 forward）后打新的 `v<X.Y.Z+1>` patch tag；本仓无服务端配置 / 远端部署需回滚（运行态在本机 ComfyUI，见 §10.4 本地运行边界）。
- **破坏性动作**：重指向 / 删除 tag、移动任何远端 ref → **须仓库所有者单独授权**（`release.yml` 由 `push: tags` 触发，移动已发布 tag 会当场重跑发布链）。
- **回滚后验证**：重跑 `python -m compileall -q .` 与 `python -X utf8 -m unittest discover -s tests -v`（即 CI 11 道门禁）；对新 Release 归档执行 `sha256sum -c SHA256SUMS.txt` 通过。

## 6. SLA / 错误预算

- 本仓是**实验工具包**，无面向公众的在线服务 / 部署端点，不适用可用性 SLA 与错误预算。
- 若未来发布面向终端用户的可安装产物或常驻服务，再定目标可用性与错误预算阈值——**待定（负责人 + 触发条件：出现首个面向终端用户的可安装/常驻产物时）**。

## 7. 发布前检查清单

- [ ] 版本位即 tag（`vMAJOR.MINOR.PATCH`），无其它版本位需同步（见 §1）
- [ ] CHANGELOG `[Unreleased]` 已改版本 + 日期（首次发版前先建 `CHANGELOG.md`）
- [ ] `python -m compileall -q .` 通过
- [ ] `python -X utf8 -m unittest discover -s tests -v` 全绿（即 CI 11 道门禁全绿）
- [ ] 本仓无镜像：Trivy 阻断 / `.trivyignore.yaml` / `provenance+sbom` 项不适用
- [ ] **本地未产出任何发布交付物**（源码归档全部由远端 `release.yml` 构建）

---

## 8. 本仓校准记录（2026-10-18，任务 D-03）

按 §10 对本仓已有发布链逐项核对，结论如下：

| 核对项 | 现状（改动前） | 判定 | 处理 |
|---|---|---|---|
| **tag 驱动** | `.github/workflows/release.yml` 为 `on: push: tags: v*`，且 job 内校验 `^v[0-9]+\.[0-9]+\.[0-9]+$` | ✅ 已对齐 | 不改触发方式 |
| **产物附 SHA256SUMS** | 原 `release.yml` 仅 `gh release create --generate-notes`，**不挂任何资产**，无 `SHA256SUMS.txt` | ❌ 未对齐 | **最小修正**：补 checkout + `git archive` 源码归档 + `sha256sum > SHA256SUMS.txt` + `gh release upload`；未重构、未改 tag 触发、未引入 `latest`、未引入 GPG |
| **GPG 签名流程** | 本仓从未存在 `gpg-signed-release.yml`（§10.6 已确认） | ✅ 已对齐 | 不新建、不保留任何 GPG 流程 |
| **floating `latest`** | workflow 中无 `value=latest` | ✅ 已对齐 | 不改 |
| **Trivy 报告模式 / provenance / sbom** | 本仓无容器镜像、无 `docker/build-push-action` | ➖ 不适用 | 不改 |
| **`docs/release-governance.md`** | 原本缺失 | ❌ 未对齐 | 本文件即补齐（含「远端优先」标记） |
| **`CHANGELOG.md`** | 原本缺失（`check-release-standard.sh` 报 FAIL） | ❌ 未对齐 | **本单不新建**（超出 D-03 范围，见红线 7）；已在 §2 登记为待定项，首次发版前补建 |
| **draft → 人工 published** | 现为 tag 推送即自动 published | ⚠️ 差异 | 本单不改发布形态（避免重构发布行为）；在 §3.5 登记为待定项 |

> 本仓校准的判定依据：`ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10.1（远端优先 / tag 驱动 / 产物附 SHA256SUMS）、§10.2、§10.6，以及 `.github/scripts/check-release-standard.sh` 的可机器判定条款。

## 禁止事项

- 不得重写 §10 的公共条款（远端优先、tag 驱动、版本位一致、不可变标签、扫描阻断、无 GPG）。
- 不得引入 `latest` 作发布基线；不得保留或新建 GPG 签名流程。
- 不得留空占位符，不得编造阈值。
