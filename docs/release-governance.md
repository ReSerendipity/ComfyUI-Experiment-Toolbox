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
- 每次合并 `main` 在 `[Unreleased]` 追加；type 映射 `feat→Added`、`fix→Fixed`、`perf/ci/chore/docs/test/refactor→Changed`（以根 `CHANGELOG.md` 顶部「归类口径」为准）。
- 发版时 `[Unreleased]` → `[VERSION] - YYYY-MM-DD`。
- **现状（2026-10-18 更新）**：根级 `CHANGELOG.md` 已建立（Keep a Changelog，骨架 + 按提交回填的 `[Unreleased]`）；`check-release-standard.sh` 不再据此报 FAIL。

## 3. 发布流程（远端）

1. 确认 CHANGELOG `[Unreleased]` 条目完整（见 §2）。
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
- **回滚后验证**：重跑 `python -m compileall -q .` 与 `python -X utf8 -m unittest discover -s tests -v`（CI 的编译步与 Gate ⑦；完整 11 道门禁见 `.github/workflows/ci.yml`）；对新 Release 归档执行 `sha256sum -c SHA256SUMS.txt` 通过。

## 6. SLA / 错误预算

- 本仓是**实验工具包**，无面向公众的在线服务 / 部署端点，不适用可用性 SLA 与错误预算。
- 若未来发布面向终端用户的可安装产物或常驻服务，再定目标可用性与错误预算阈值——**待定（负责人 + 触发条件：出现首个面向终端用户的可安装/常驻产物时）**。

## 7. 发布前检查清单

- [ ] 版本位即 tag（`vMAJOR.MINOR.PATCH`），无其它版本位需同步（见 §1）
- [ ] CHANGELOG `[Unreleased]` 已改版本 + 日期
- [ ] `python -m compileall -q .` 通过
- [ ] `python -X utf8 -m unittest discover -s tests -v` 全绿（Gate ⑦）；CI 11 道门禁全绿（见 `.github/workflows/ci.yml`）
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
| **`CHANGELOG.md`** | 原缺，**已由本单建立** | ✅ 已对齐 | 无 |
| **draft → 人工 published** | 现为 tag 推送即自动 published | ⚠️ 差异 | 本单不改发布形态（避免重构发布行为）；在 §3.5 登记为待定项 |

> 本仓校准的判定依据：`ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10.1（远端优先 / tag 驱动 / 产物附 SHA256SUMS）、§10.2、§10.6，以及 `.github/scripts/check-release-standard.sh` 的可机器判定条款。

### 8.1 发布链本地实跑记录（2026-11-06，整改单 rem_ComfyUI_Experiment_Toolbox_20261105 条目 2）

按 §7 清单做了一轮**本地实跑**。本轮整改单硬约束禁止 `git tag` / `git push`，因此触发 `release.yml` 的远端半程未能执行；本地可跑部分全部实跑并留档：

| 实跑项 | 命令 / 方法 | 结果（2026-11-06 实测） |
|---|---|---|
| 版本位唯一性（§7 第 1 项） | `ls pyproject.toml setup.py setup.cfg package.json config.yaml` | 全部不存在，版本位即 tag（§1 口径成立） |
| compileall（§7 第 3 项） | `python -m compileall -q .` | exit 0，零输出 |
| CI 门禁（§7 第 4 项） | Gate ①–⑪ 逐条按 `.github/workflows/ci.yml` 原命令本地执行 | 11/11 全绿：Gate ⑤ 扫 202 个 tracked 文件 0 命中；Gate ⑥ 扫 106 个 .py 0 违规；Gate ⑦ unittest 30 用例 OK |
| tag 正则校验（release.yml validate 步等价） | 对候选串 `v1.0.0` / `v1.0.0-beta.1` 复算 `^v[0-9]+\.[0-9]+\.[0-9]+$` | 正例通过、负例拒绝。**顺带实测**：`-beta.1` 等预发布后缀会被该正则拒绝，与 §1 预发布口径存在潜在冲突——本轮不改，留属主裁决 |
| 归档 + 完整性（§4 / §7 第 6 项） | `git archive --format=tar.gz --prefix="ComfyUI-Experiment-Toolbox-v1.0.0/" -o …` → `sha256sum` → `sha256sum -c` | 归档 27,626,908 字节，408 个文件与 `git ls-files`（408）全等、文件名集合一致；未跟踪文件与 `__pycache__` 均未混入；SHA256 `c2b8a85896bc12e6…` 校验 OK。产物在仓外临时目录，未入库 |

**阻塞点（发布链未能走到 Release 的原因）与解阻条件**：

1. **tag 推送被禁**：本轮整改单硬约束禁止 `git tag` / `git push` → `release.yml`（`on: push: tags`）无法触发。解阻：属主单独授权打 `vX.Y.Z` tag（版本号由属主定）并推送。
2. **§3.5 待定项未决**：首个正式 Release 的 draft vs published 形态、负责人、触发条件仍待属主裁决（§3 第 5 条）。解阻：属主填定后，按裁决形态走首发。
3. **SCA 首扫为红**：ci.yml 新增 pip-audit 步骤对锁文件首扫，Pillow==12.1.0 命中 58 个唯一漏洞通告（76 行）——接入后 §7「CI 门禁全绿」将含一项红，直到属主裁决升级位（12.1.1 / 12.2.0 / 12.3.0 / 13.0.0，须与 ComfyUI 自带 python 环境实测对齐后回填锁文件）或登记豁免。numpy==2.3.5 零命中。

## 禁止事项

- 不得重写 §10 的公共条款（远端优先、tag 驱动、版本位一致、不可变标签、扫描阻断、无 GPG）。
- 不得引入 `latest` 作发布基线；不得保留或新建 GPG 签名流程。
- 不得留空占位符，不得编造阈值。