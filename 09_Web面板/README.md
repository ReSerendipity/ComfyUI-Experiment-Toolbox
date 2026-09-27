# 09 Web 面板（参数轨 · 人类用户入口）

> 面向**人类用户**的浏览器界面，把工具箱参数轨（01~04）的 headless 脚本能力包了一层 Web 壳。
> 纯 Python 标准库实现（`http.server`），**零第三方依赖**，直接用 ComfyUI 自带 python 运行。

## 启动（一条命令）

在工具箱根目录**双击 `start.bat`** 即可。等价命令：

```bash
cd "%USERPROFILE%/Desktop/ComfyUI-实验与改造工具箱"
run.bat panel                                    # Windows
# 或任意终端：
"%USERPROFILE%/APP/ComfyUI-aki-v3/python/python.exe" run.py panel
```

**启动后会自动打开浏览器**，无需手动输地址 → http://127.0.0.1:8189

- 不想自动开浏览器：加 `--no-browser`（例：`run.bat panel --no-browser`）。
- 面板端口 `8189`；跑测提交给 ComfyUI（`8188`）。**①② 页不需要 ComfyUI**，③④ 页需要。
- **端口被占时不再静默抢绑**：若已有一个面板在跑，新实例会直接报错并告诉你怎么处理（Windows 的 `SO_REUSEADDR` 会让两个进程绑同一端口、请求随机落到旧代码上，极难排查，故已关闭）。
- 关闭：在面板窗口按 Ctrl+C（或直接关窗口）。

## ComfyUI 不用你手动开

③ 页点「开始跑测」时，**若 ComfyUI 没启动，面板会自动帮你拉起它**，并在页面上显示「ComfyUI 加载中… 已等 Ns」，就绪后自动继续跑测。

- 顶栏也有独立的 **「启动 ComfyUI」** 按钮（未启动时才出现），可先单独把服务起好。
- 拉起命令与根 README 第三节完全一致，跑在**独立控制台窗口**里——方便你看模型加载日志、按 Ctrl+C 停止。
- 幂等：已在运行 / 正在启动时不会重复拉起。
- 启动后立刻退出（比如显存不足、依赖报错）会在页面上直接提示 `exit=N`，让你去看那个控制台窗口，而不是干等超时。
- 等就绪的上限 5 分钟（首次加载模型较慢）。

## 四个页面

| 页面 | 复用 | 功能 | 需 ComfyUI？ |
|---|---|---|---|
| ① 工作流真值 | `01_工作流扁平化/flatten.py` | 列出每份工作流的运行时参数（positional 容器值为准：采样器/调度器/steps/cfg/seed/模型），并标出提示词是否为空 | 否 |
| ② σ 风险矩阵 | `02_调度器sigma分析/` | 7 模型 × 9 调度器离线判定（高危/注意/安全），不跑图 | 否（首次计算约 20~60s，之后走缓存） |
| ③ 受控跑测 | `03_受控跑测/` 逻辑 | 勾选工作流 + 组合（采样器/调度器/steps/cfg，留空=不改；base=当前值），固定提示词与种子，逐组提交 + 进度条 + 日志 | 是 |
| ④ 结果分析 | `04_结果分析/` 口径 | 客观指标（亮度/对比度σ/锐度/色彩度）+ 与 base 基线的相似度 + 带标签拼版图 | 否（分析已落盘的产物） |

## 跑测流程（③→④）

1. ① 页确认工作流真值没问题（提示词非空、参数合理）；
2. ③ 页勾工作流、加组合。**组合行交互约定**：
   - **采样器 / 调度器 = 下拉框**，选项来自 ComfyUI `/object_info/KSampler` 的合法值全集（ComfyUI 离线时用内置回退表，下拉框始终可用）；
   - **steps / CFG = 数字输入**，**留空 = 用各工作流当前值**（当前值见①页）；base 组合 = 全部留空 = 完全按当前值；
   - 后端提交前还有一道校验：非法采样器/调度器、非数字 steps/CFG 会被直接 400 拦截（合法值与下拉框同源），不会浪费队列时间；
   - 缺项会**点名**（如「未勾选任何工作流」「未添加任何组合」），不再是一句笼统的「均不能为空」；
3. 确认提示词与种子，点「开始跑测」——**ComfyUI 没开的话面板会先自动拉起它**，再自动开始跑测；进度条走完、日志全绿；
4. ④ 页点「分析」，看拼版图与指标表——相似度接近 1 的组合实际等价，对比度/锐度骤降的组合有异常，**最终以人眼看图为准**。

> 想让相似度对比有意义，跑测里要**包含 base 组合**（面板默认已加）——④ 页以 base 为各工作流的基线。

产物在 `09_Web面板/output/<子目录>/`（拼版为 `_montage.png`）。

## 结构改造（05）不在本面板

加参考图槽位、模板对齐等结构手术**刻意不 Web 化**：低频、高风险、强依赖节点指纹，请在 ComfyUI 前端（Autogrow 加槽最稳）或用 agent 跑 `05_结构改造脚本/`。

## 复用到别处

`panel.py` 顶部的常量：`COMFY_ROOT` / `WF_DIR` / `CF_OUT`（ComfyUI 侧）、`OUT_ROOT`（产物根）、`PORT`。工作流目录里的 `.bak` 文件自动跳过。

## 已知边界

- ③ 页的组合参数只覆盖 KSampler / KSamplerSelect+BasicScheduler / FluxGuidance / Flux2Scheduler 四类链路；MiniMax H3（Spectrum 链路）不适用——与工具箱 README 第七节的「不适用」口径一致。
- ② 页首次打开需等 torch 导入（面板日志可见），完成后常驻缓存直到面板重启。
- 面板绑定 `127.0.0.1`，不对外网开放。

## 回归测试（test_dom.js）

改动 `index.html` 的前端逻辑后，可跑一次真实 DOM 回归（jsdom 执行页面真实 JS，检查下拉框选项数与收集键名）：

```bash
cd "%USERPROFILE%/.workbuddy/binaries/node/workspace"
NODE_PATH="$(pwd)/node_modules" node "%USERPROFILE%/Desktop/ComfyUI-实验与改造工具箱/09_Web面板/test_dom.js"
```

通过标准：`sampOpts>20`、`schdOpts>=9`、收集产物 `combos[0].sampler_name` 与所选一致。前置：managed node 工作区已 `npm install jsdom`（2026-09-24 已装）。

> 教训备注（2026-09-24）：本次曾因列头行误用 `class="combo-row"` 导致 `refreshComboSelects` 对无 `.csamp` 的行抛错、被 catch 吞掉，下拉框永远只有占位项——纯 grep 源码的"验证"发现不了，必须 DOM 级验证。`.combo-head` 与 `.combo-row` 已分离，且 `startRun` 会跳过无 `.cname` 的行。
