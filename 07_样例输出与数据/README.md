# 07 样例输出与数据

用途：**让你知道"正常结果"和"异常结果"各长什么样**，以及拿到原始数据自己复算/画图。

| 文件 | 是什么 | 怎么用 |
|---|---|---|
| `跨模型对比拼版.png` | **最有参考价值**：6 个模型 × 20 组（基线 / karras / exponential / kl_optimal）的带标签拼版 | 一眼看清"karras 与 exponential 组整体糊掉"的对比 |
| `对比拼版_19组.png` | Qwen-Image 2.1 的 17 组矩阵 + 2 组补充验证拼版 | 单模型组合矩阵的全景 |
| `聚焦对照_4组.png` | 4 张大图并排：基线 / 最优 / 异常(karras@25) / 修复(karras@50) | 写报告时的头图；也能直观理解"步数补足 → 重影消失" |
| `model_metrics.json` | **跨模型指标表**：模型 / 组合 / 亮度 / 对比度 / 锐度 / 色彩度 / 与基线相似度 / 相对变化% | 直接读；或据此重画图表 |
| `metrics.json` | Qwen-Image 2.1 的单模型指标表 | 同上 |
| `similarity.json` | 组合间相似度与最近邻（证明"多组合实际等价"） | 查"哪两个组合几乎一样" |
| `result_log.json` | 09-22 十七组的逐组日志（组合、耗时、产物、错误） | 查单组耗时/成败 |
| `model_test_log.json` | 跨模型跑测的日志（**注意：曾被单模型补跑覆盖，只剩 3 条失败记录**） | 失败原因参考用；完整清单请看 `model_metrics.json` 或直接看图片目录 |
| `cfg_probe_log.json` | cfg × 负向提示词 探针的逐组耗时 | 参考用（该组耗时噪声大，未用于结论） |

## 图片目录不在本包内

跑测产生的**逐张原图**没有拷进来（体积大且是一次性产物），仍在工作区：

- 单模型矩阵：`%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\output\`
- 跨模型跑测：`%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\output_models\`
- ComfyUI 侧原始落盘：`%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\output\`

**命名规则**：`<模型标签>__<组合名>__<原始文件名>.png` —— 用 `模型__组合` 就能定位，`analyze_models.py` 也是靠这个规则从目录重建清单的。

## 从数据里能直接读到的结论

| 现象 | 数据位置 |
|---|---|
| karras 劣化幅度随步数增加而下降 | `model_metrics.json`：50 步 −25% ＜ 8 步 −55~63% ＜ 20 步 −93% ＜ 25 步 −97% |
| exponential 比同模型 karras 更狠 | Qwen_2512：−64% vs −25% |
| kl_optimal 只在 ≤8 步模型上明显发糊 | Z_image_turbo 对比度 −44%、krea2_turbo 锐度 −33% |
| 基线组彼此高度一致（说明固定提示词与种子生效） | `similarity.json` / 拼版图 |
| Flux.2 Klein 换采样器几乎无差别且都干净 | 拼版图最上方三张 |
