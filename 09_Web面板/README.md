# 09 Web 面板（参数轨 · 人类用户入口）

> 面向**人类用户**的浏览器界面，把工具箱参数轨（01~04）的 headless 脚本能力包了一层 Web 壳。
> 纯 Python 标准库实现（`http.server`），**零第三方依赖**，直接用 ComfyUI 自带 python 运行。

## 启动（两条命令）

```bash
cd "%USERPROFILE%/Desktop/ComfyUI-实验与改造工具箱/09_Web面板"
%USERPROFILE%/APP/ComfyUI-aki-v3/python/python.exe panel.py
```

然后浏览器打开 **http://127.0.0.1:8189**。

- 面板端口 `8189`；跑测仍提交给 ComfyUI（`8188`）。**02 页不需要服务**，③④ 页需要 ComfyUI 已启动。
- 建议用绘世启动器先把 ComfyUI 起好，再开面板。
- 关闭：在面板窗口按 Ctrl+C（或直接关窗口）。

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
3. 确认提示词与种子，点「开始跑测」，进度条走完、日志全绿；
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
