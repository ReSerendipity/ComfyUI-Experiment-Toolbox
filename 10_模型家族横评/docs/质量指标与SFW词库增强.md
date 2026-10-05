# 质量指标与 SFW 词库增强

> 定位：**项目无关**的两块增强能力，供 `10_模型家族横评` 串行集成（入口由指挥方接，本轨不做）。
>
> | 文件 | 一句话 | 方向 |
> |---|---|---|
> | `lib_image_qc_enh.py` | 客观图像指标（纯像素统计，不读图内容） | 出图后**测量** |
> | `lib_sfw_prompts_kit.py` | SFW/中性提示词素材包（正向供词） | 写词时**加料** |
>
> **隔离铁律**：Picture 是成人向分级提示词库（`词库.json` 34,289 条 / 128 类）。
> 本轨只抽【项目无关、非限制级】的部分；凡涉及分级、身体部位、暴露度、年龄分档的
> 词与规则**一律不迁移**，只在本文件与两个 lib 里留**计数**（§五）。
> 两个 lib 里**没有任何限制级词条正文**，也**没有敏感词黑名单**。

---

## 一、`lib_image_qc_enh.py` —— 客观图像指标

### 1.1 它做什么 / 不做什么

| 做 | 不做 |
|---|---|
| 只算像素统计（亮度、对比度、锐度、噪点、色温、亮度质心…） | 不识画面内容、不做主体检测、不加载任何模型 |
| 输出数值表 + `flags` 分诊标签 | 不给主观分、不参与 `scoresheet.csv` 六维评分 |
| 只读 PNG，不写回、不裁剪、不展示画面 | 不改 ComfyUI、不连 API、不出图 |

> 与 README「评分口径」一致：这 27 项是**辅助参考**，不能替代读图，
> 也不能把 `similarity.json` 的跨架构数字和这里的像素统计混着比。

### 1.2 API

```python
analyze(png_path, cfg=None) -> dict          # 单张图全指标 + flags + verdict
analyze_dir(root, cfg=None, pattern="*.png", recursive=True, limit=0) -> dict
    # -> {"ok","root","scanned","analyzed","verdict":{ok/warn/bad/failed},
    #     "flag_count":{...},"aggregate":{指标:{n,mean,p05,p50,p95,min,max}},"rows":[...]}
load_cfg(overrides=None) -> dict             # 默认参数 + 覆盖
flag_report(rows) -> dict                    # 只汇总 flags/verdict，用于「不读图先分诊」
METRICS / LEGACY_METRICS / SOURCES / THRESHOLDS   # 自解释常量（文档/表格生成用）
```

```powershell
# 必须用 ComfyUI 自带 python（要 numpy + Pillow）
python -X utf8 lib_image_qc_enh.py
python -X utf8 lib_image_qc_enh.py --root "%USERPROFILE%/APP/ComfyUI-aki-v3/ComfyUI/output/model_benchmark" --limit 24
python -X utf8 lib_image_qc_enh.py --root output/model_benchmark --limit 0 --json _qc.json
python -X utf8 lib_image_qc_enh.py --file a.png --metrics brightness,noise_snr_db,color_temp_k
```

`cfg` 可调项：`max_side`（分析分辨率上限，默认 2048）、`high_clip`（250）、
`shadow_clip`（5）、`edge_thr`（0.06）、`grid`（32）、`flat_var_thr`（2.0）。

### 1.3 指标清单（27 个 key / 29 个标量值）

来源列的三个前缀含义：
`legacy:`＝直接继承工具箱 `04_结果分析/metrics.py` 口径（**逐字一致，可与旧 metrics.json 直接对比**）；
`enh:png_stats`＝来自 Picture `tools/batch7_render.py::png_stats()` 的思路并泛化；
`enh:` 其他＝标准 CV/色彩学做法，项目无关。

#### 影调

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `brightness` | 等权 RGB 灰度均值 | 0-255 | 无（记录用） | legacy:04_结果分析 |
| `luma_p05/p50/p95` | REC.709 亮度分位 | 0-255 | 无（分布形状） | enh:png_stats 亮度分布泛化 |
| `contrast_std` | 亮度标准差 | 0-255 | 无（记录用） | legacy:04_结果分析 |
| `highlight_clip_ratio` | 亮度 ≥250 的像素占比 | 0-1 | warn ≥0.02 / bad ≥0.08 | enh:png_stats 单端阈值→双端 |
| `shadow_crush_ratio` | 亮度 ≤5 的像素占比 | 0-1 | warn ≥0.05 / bad ≥0.15 | enh:png_stats 单端阈值→双端 |
| `dynamic_range_p99_p01` | P99−P01 有效动态范围 | 0-255 | warn ≤140 / bad ≤90 | enh:直方图跨度 |
| `midtone_share` | 亮度落在 64-190 的像素占比 | 0-1 | warn ≤0.25 / bad ≤0.15 | enh:直方图跨度 |
| `rms_contrast` | 亮度 RMS / 均值（REC.709 亮度） | ~0.3-1.7 | warn ≤0.30 / bad ≤0.18 | enh:REC.709 亮度 RMS |

#### 对比度

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `local_contrast_ratio` | 32px 网格局部标准差均值 / 全局标准差 | 0-1 | warn ≤0.12 / bad ≤0.07 | enh:3x3→32px 局部标准差 |
| `colorfulness` | Hasler-Süsstrunk 彩色度 | 0-100+ | 无（记录用） | legacy:04_结果分析 |

#### 锐度与边缘

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `sharpness_lapvar` | 4 邻域 Laplacian 方差 | 30-3600（本机样本） | 无（记录用） | legacy:04_结果分析 |
| `sharpness_lapvar_norm` | 上式 ÷ 亮度均值（跨曝光可比） | 0.30-36（本机样本） | 无（排序用） | enh:除以亮度均值 |
| `edge_density` | 归一化 Sobel 幅值 >0.06 的像素占比 | 0-1 | 无（记录用） | enh:Sobel 梯度阈值占比 |
| `edge_energy` | 归一化 Sobel 幅值均值 | 0-1 | 无（记录用） | enh:Sobel 梯度均值 |

> 为什么 LapVar 要配 Sobel：LapVar 是四邻域二阶差分，对「斜向条纹」和「压缩糊块」
> 都可能给低分；Sobel 十邻域一阶梯度给的排序经常不同。两个一起看才不至于被单一指标骗。

#### 噪点

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `noise_sigma` | Immerkær 快速噪声 σ（卷积 `[[1,-2,1],[-2,4,-2],[1,-2,1]]`） | 0.3-6（本机样本） | 无（记录用） | enh:Immerkær 快速估计 |
| `noise_snr_db` | `20·log10(亮度均值 / noise_sigma)` | 26-59 dB | warn ≤32 / bad ≤26 | enh:亮度/σ |

> **可比性警告**：`noise_sigma` 对**分析分辨率**敏感（σ 随下采样变小）。
> 跨权重比噪点必须保证 `analysis_size` 一致；`noise_snr_db` 把分辨率影响吸收掉一部分，更耐比。

#### 颜色

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `color_temp_k` | CCT 色温（RGB→CIE xy→McCamy 近似），钳在 1500-15000K | 5300-11000（本机样本） | 对比轴，不分诊 | enh:McCamy 近似 |
| `saturation_mean` | HSV 的 S 通道均值 | 0-1 | warn ≤0.15 / bad ≤0.08 | enh:HSV 的 S 通道 |
| `warm_cool_index` | `mean(R−B)/255`，正=偏暖 | -0.05..0.19 | 对比轴，不分诊 | enh:mean(R-B) |

> `colorfulness` 对大色块极敏感、对淡色几乎无反应，所以补 `saturation_mean`；
> CCT 是绝对标尺，`warm_cool_index` 是相对方向，两者互相印证。

#### 构图重心（亮度质量代理量）

| 指标 | 定义 | 取值 | 参考阈值 | 来源 |
|---|---|---|---|---|
| `centroid_x/y` | 亮度归一化后平方加权的质心（归一到 0-1） | 0-1 | 对比轴，不分诊 | enh:亮度加权质心 |
| `centroid_offset_center` | 质心到画面中心的归一化距离 | 0-1 | 对比轴，不分诊 | enh:到画面中心距离 |
| `thirds_offset` | 质心到最近三分交点的归一化距离 | 0.15-0.47 | 对比轴，不分诊 | enh:到四交点最短距离 |
| `mass_spread` | 亮度质量的横/纵标准离散度均值 | 0-0.29（均匀分布≈0.289） | 对比轴，不分诊 | enh:亮度质量分布 |
| `flat_area_ratio` | 32px 网格内标准差 <2 灰度的网格占比 | 0-0.79 | warn ≥0.60 / bad ≥0.80 | enh:低方差网格占比 |

> 构图四项**只算亮度质量分布**，不算显著性网络、不做人物检测：
> 「主体是谁」与本库无关。`mass_spread` 越小说明亮部质量越集中
> （大特写／主体占满），越大说明亮部铺满（风景／高调场景），全白图取到理论上限 0.289。
> `flat_area_ratio` 是抓「输出没渲染出东西 / 大面积糊平」的兜底闸。

### 1.4 来源勘误（重要，避免误引）

任务书里写的是「读 `quality_control.py` 里与限制级无关的图像侧量化检查思路」。
实测结论必须写清楚，否则后面的人会一直按错误前提引用：

1. **`Picture/tools/modules/quality_control.py` 里没有任何图像/像素代码。**
   对 Picture 整棵树 grep `from PIL` / `import numpy`，只有
   `tools/batch7_render.py` 命中（`_archive/` 下的历史副本除外）；
   `quality_control.py` 是纯文本 QC（标点、字数、词频、模板句残留、注入/清洗类函数）。
   → 「quality_control 里的非限制级图像函数」实际为 **0 个**，本模块没从它搬任何函数。
2. **Picture 唯一的图像侧量化检查是 `tools/batch7_render.py::png_stats()`**：
   `im.convert("L").resize((64,64))` → `mean_luma` → `non_black = mean_luma > 8`。
   本模块保留它的三点思路（转 L 亮度通道 / 降采样 / 亮度阈值判定）并双向泛化：
   - 单张图一个均值 → **像素级双端阈值比**（`highlight_clip_ratio` / `shadow_crush_ratio`）
   - 降采样上限 64×64 → `max_side`（默认 2048）。噪点估计必须在真实分辨率上做，
     64×64 会把噪点抹平，所以这条不能照抄。
3. **老 4 项（brightness / contrast_std / sharpness_lapvar / colorfulness）来自工具箱自己的
   `04_结果分析/metrics.py`**（`laplacian_var()` / `colorfulness()`），口径逐字保留，
   保证与既有 `metrics.json` 可直接对比——这是**继承**，不是从 Picture 搬的。
4. `color_temp_k` 的**命名域**参考了 Picture 词库里「色温效果 / 光线方向 / 色彩体系.色温」
   这类纯光色类目（项目无关），但**实现是客观 CCT 计算，一个词条都没搬**。

### 1.5 本机实测（只读，不展示画面）

`<comfy>/output/model_benchmark` 全量 216 张 PNG（`--limit 0`）：

| 指标 | mean | p05 | p50 | p95 | max |
|---|---|---|---|---|---|
| brightness | 124.7 | 52.4 | 125.7 | 185.2 | 201.5 |
| contrast_std | 62.2 | 43.8 | 61.6 | 80.7 | 93.7 |
| sharpness_lapvar | 473.2 | 34.5 | 241.2 | 1887 | 3560 |
| colorfulness | 31.6 | 17.5 | 28.8 | 50.8 | 65.1 |
| highlight_clip_ratio | 0.019 | 0.000 | 0.001 | 0.101 | 0.463 |
| shadow_crush_ratio | 0.031 | 0.000 | 0.009 | 0.182 | 0.290 |
| dynamic_range_p99_p01 | 225.7 | 191.0 | 229.6 | 252.4 | 254.6 |
| midtone_share | 0.441 | 0.174 | 0.435 | 0.754 | 0.938 |
| rms_contrast | 1.170 | 1.033 | 1.130 | 1.497 | 1.678 |
| local_contrast_ratio | 0.284 | 0.141 | 0.264 | 0.505 | 0.612 |
| sharpness_lapvar_norm | 4.438 | 0.304 | 1.896 | 18.89 | 36.4 |
| edge_density | 0.124 | 0.027 | 0.104 | 0.285 | 0.424 |
| edge_energy | 0.0325 | 0.0102 | 0.0283 | 0.0726 | 0.1177 |
| noise_sigma | 1.302 | 0.345 | 0.866 | 3.264 | 5.994 |
| noise_snr_db | 41.3 | 26.1 | 42.5 | 52.7 | 59.1 |
| color_temp_k | 6107 | 5295 | 5893 | 7868 | 11000 |
| saturation_mean | 0.274 | 0.087 | 0.261 | 0.532 | 0.764 |
| warm_cool_index | 0.071 | -0.042 | 0.075 | 0.155 | 0.189 |
| centroid_offset_center | 0.120 | 0.016 | 0.096 | 0.299 | 0.393 |
| thirds_offset | 0.339 | 0.156 | 0.353 | 0.454 | 0.465 |
| mass_spread | 0.275 | 0.224 | 0.275 | 0.323 | 0.337 |
| flat_area_ratio | 0.224 | 0.000 | 0.139 | 0.660 | 0.792 |

分诊结果：`ok 69 / warn 97 / bad 50 / failed 0`；触发最多的三条是
`warn:saturation_mean`(37)、`warn:midtone_share`(32)、`warn:shadow_crush_ratio`(29)。
这套阈值是**分诊带**不是评分线：它的用途是把 216 张图按「疑似有问题」排序，
让读图人先看 flag 最密的那几张，而不是给每个权重打分。

合成图自测（全黑/全白/纯噪声/线性渐变/单点）五张都符合解析预期，
例如纯噪声图 `noise_sigma=55.8 / snr=7.2dB / edge_density=0.954`，
全黑图 `shadow_crush_ratio=1.0 / flat_area_ratio=1.0`。

### 1.6 已知限制

1. `noise_sigma` 依赖 `analysis_size`；跨权重比必须同分辨率，或改用 `noise_snr_db`。
2. 所有指标**分母是画面本身**：画风差异（插画 vs 写实）会让 LapVar/edge_density
   系统性偏科。跨题材比像素前先确认两条提示词的题材档位可比。
3. 构图四项是亮度代理量，**不能替代读图判断构图好坏**；高调/逆光图会系统性把质心推偏。
4. 不做跨图配准，不给相似度；`similarity.json` 的口径（同模型同提示词跨种子）仍然只归它自己。

---

## 二、`lib_sfw_prompts_kit.py` —— SFW/中性提示词素材包

### 2.1 API

```python
list_categories() -> [str]                    # 19 个内置类目（按组稿顺序）
category_counts() -> {类目: 条数}
get(category, n=1, seed=None, exclude=()) -> [str]     # 确定性轮转（同 seed 同结果）
compose(dims=None, n_each=1, sep="，", seed=None) -> str
load_external(path, limit_per_cat=200, deny_terms=(), include_route_only=False)
        -> {"pool": {类目: [条目]}, "report": {...}}     # 可选，默认不读任何文件
audit_external(path) -> 报表                  # 只报类目名与计数，**不含词条正文**
EXTERNAL_ALLOW / SKIP_TABLE / SUBBUCKET_KEEP / PARTIAL_SKIP / ROUTE_TABLE / AUDIT_NOTE   # 审计常量
```

```powershell
python -X utf8 lib_sfw_prompts_kit.py                        # 纳入/跳过台账
python -X utf8 lib_sfw_prompts_kit.py --sample 2              # 每类抽 2 条示例
python -X utf8 lib_sfw_prompts_kit.py --compose light_quality,composition,camera_angle --n-each 2 --seed FLUX-1-dev
python -X utf8 lib_sfw_prompts_kit.py --audit "D:/some/通用词库.json"
```

`get()` 的确定性来自 `md5(seed)` 命名空间（对齐 Picture 词库的「seed=md5(文件名)」
可复现口径），**没有随机数、没有全局状态**，同 seed 永远同结果，可进台账。

### 2.2 内置类目（19 类 / 234 条，全部自写）

| # | 类目 | 条数 | 覆盖内容 |
|---|---|---|---|
| 1 | `light_direction` | 14 | 光位：侧光/逆光/顶光/窗口光/分割光/轮廓光/环形柔光… |
| 2 | `light_quality` | 14 | 光质：硬光/柔光/柔箱/散射/烛光/霓虹/舞台聚光… |
| 3 | `color_temperature` | 10 | 2700K~8500K + 双色温对比 + 白平衡偏移 |
| 4 | `time_of_day` | 10 | 清晨/正午/黄金时段/日落/蓝调时刻/夜晚/凌晨 |
| 5 | `weather` | 13 | 晴/薄云/阴/雨/雾/雪/风/闷热/雨后初霁 |
| 6 | `weather_effect` | 10 | 逆光光晕/湿反射/雪地高反照/丁达尔/镜头雨滴 |
| 7 | `composition` | 14 | 三分法/对称/引导线/框中框/对角线/留白/黄金分割 |
| 8 | `shot_size` | 12 | 极特写→大远景 + 俯瞰/仰视全景 |
| 9 | `camera_angle` | 11 | 平视/俯拍/仰拍/顶视/贴地低角度/荷兰角/过肩 |
| 10 | `depth_of_field` | 10 | 极浅→全景深合成/移轴微缩/背景压缩 |
| 11 | `lens_kit` | 12 | 24/35/50/85/100/135mm + 16-35/70-200 + 移轴/鱼眼 |
| 12 | `camera_settings` | 11 | f/1.2~f/11、快门、ISO、曝光补偿、包围曝光 |
| 13 | `color_scheme` | 12 | 冷暖对比/单色/邻近/互补/莫兰迪/高调低调/青橙 |
| 14 | `material_surface` | 15 | 陶瓷/拉丝金属/铜绿/磨砂玻璃/石面/大理石/亚麻/水磨石 |
| 15 | `texture_detail` | 12 | 颗粒/划痕/经纬/涟漪/年轮/凿痕/拉丝纹/龟裂 |
| 16 | `scene_generic` | 16 | 工作室/天台/雨后街角/晨雾湖面/仓库/放映厅/市集… |
| 17 | `background_props` | 14 | 旧墙/折叠椅/陶罐/长桌/垂帘/吊灯/书架/隔断 |
| 18 | `ambience_mood` | 12 | 安静/慵懒/清冷/明快/庄重/神秘/怀旧/寂寥 |
| 19 | `post_fx` | 12 | 暗角/胶片颗粒/高光溢出/高光去饱和/色调分离 |

维度顺序＝组稿顺序：光 → 时/天 → 构图 → 机位 → 镜头 → 色彩 → 材质 → 场景 → 氛围 → 后期。
`compose()` 缺省取 6 维（光质/构图/机位/配色/材质/氛围），加料时优先扩光与构图两维。

### 2.3 外部通用词库的对接（可选，默认不读文件）

`load_external(path)` 走**类目白名单**，三道闸：

1. `EXTERNAL_ALLOW` 白名单（81 类）——不在白名单的类目整类拒绝，不看内容；
   键名带分级标记位（`_L<数字>`）的类目由 `_LEVEL_CAT_RE` 统一识别并整类拒绝，
   **其原名刻意不复现**（否则受限词面会跟着代码走）。
2. `SUBBUCKET_KEEP` 子桶白名单（6 个父类目 / 438 条被拒）——**默认全拒、白名单放行**，
   只在第一层按子桶名过滤，白名单子桶内部结构不受限制。
   用白名单而不是黑名单，受限子桶的原名就不必出现在本文件里。
3. `_gate()` 结构闸门——只判**结构与分级标记位**，不做内容审查：
   空条 / >40 字 / 首尾元数据残留 / 分级后缀标记位 / 「数字+单位」测量式 /
   调用方自传 `deny_terms`。不通过的条目丢弃并计入 `report.gate_rejected`。

实测（`--audit` Picture 词库，只读）：

| 桶 | 类目 | 条数 |
|---|---|---|
| 白名单（毛） | 81 | 20,805 |
| 子桶拒绝 | 6 父类目 | −438 |
| **白名单（净纳入）** | **81** | **20,367** |
| 整类拒绝（具名域 / 分级标记位 / 白名单外未登记） | 46 | 11,481 / 858 / 254 = **12,593** |
| 项目专属路由分桶 | 1 | 891 |
| 对账 | 128 | 34,289 ✓ |

`load_external(limit_per_cat=50)` 实跑：81 类入库 3,979 条（与 `EXTERNAL_ALLOW` 的类目集合完全一致）；
整类拒绝 47 个（44 个白名单外 + 2 个分级标记位 + 1 个路由分桶）；
结构闸门再拒 109 条（测量式 7 / 元数据残留 3 / 超长 3，分布在 11 个类目，
逐条原因见 `report.gate_rejected`，不含条目正文）。

> 打印口径：`--audit` 默认**不打印**「白名单外未登记」类目的原名（外部库的受限类目名
> 可能含限制级词面）。确实要看清单时加 `--audit-names`，此时你已确认信任该库。

---

## 三、三个 lib 的分工（别互相替代）

| 库 | 方向 | 输入 | 输出 | 什么时候用 |
|---|---|---|---|---|
| `lib_prompt_qc` | **减法 · 拦截** | 提示词文本 | `finding`（rule/severity/match） | 提交前闸门：否定式、叠标点、模板废句、质量后缀、字数窗 |
| `lib_prompt_robust` | **减法 · 对照** | 完整提示词 | 精简版 + 逐项改动计划 + 锚点保留判定 | 做「砍修饰从句后排序会不会变」的鲁棒性实验 |
| `lib_sfw_prompts_kit` | **加法 · 供词** | 维度名 / 类目名 | 正向素材片段 | 扩写提示词、加新维度、给弱权重补可控抓手 |

一句话记法：**qc 管「不能写什么」，robust 管「写多少」，kit 管「还能写什么」。**
三者互不覆盖：qc 不提供素材、robust 不判断违规、kit 不含任何规则与黑名单。

> 用法建议：kit 取的片段本身就是**正向短描述**，天然符合 qc 的「纯正向、否定式交给
> negative_mode」口径；所以 kit 产出的片段可以直接拼进 S1..S9 的加长变体，
> 再用 robust 砍一遍看排序是否稳定——但**这属于控制变量变更**，
> 按 README「提示词套件逐字节一致」的要求，必须走新一组 ID（不能改 S1..S9 本体）。

---

## 四、隔离声明（限制级专属部分刻意不迁移）

从 Picture 只取【项目无关、非限制级】的部分。以下**刻意不迁移**，只留计数：

| 不迁移的东西 | 规模（计数） | 处置 |
|---|---|---|
| 词库分级内容专属类目 | 3 类 / 1,112 条 | 整类拒绝（**原键名不复现**，只留中性占位与条数） |
| 词库身体与体型域类目 | 8 类 / 1,687 条 | 整类拒绝 |
| 词库外貌与妆造域类目 | 5 类 / 2,895 条 | 整类拒绝 |
| 词库服饰与配件域类目 | 10 类 / 2,028 条 | 整类拒绝 |
| 词库年龄与人物设定域类目 | 8 类 / 2,738 条 | 整类拒绝 |
| 词库多人关系与叙事域类目 | 11 类 / 1,149 条 | 整类拒绝 |
| 词库题材锚点域类目 | 1 类 / 984 条 | 整类拒绝 |
| 白名单类目内的受限子桶 | 6 个父类目 / 438 条 | 子桶白名单默认拒（原名不复现） |
| 外部库的项目专属路由分桶 | 1 类 / 891 条 | 既不纳入也不拒绝，需显式开关 |
| 引擎侧分级合规门（`compliance()` 标签） | 16 处 error + 8 处 warning | 全部不迁移 |
| 引擎侧分级专属函数（命名含分级/视线/场景路由） | 5 个模块共 21 个函数 | 全部不迁移 |
| 图像侧分级专属检查 | **0 个** | 无可迁移项（见 §1.4 实测） |

合计：**46 类 / 12,593 条**整类拒绝 + **438 条**子桶拒绝 = **13,031 条**未迁移。

三条设计上的理由：

1. **内置素材 100% 自写。** `BUILTIN` 的 234 条是本轨自己写的通用摄影/场景词汇，
   没有复制词库任何一条原文——所以两个 lib 不含词条正文，自带素材也不依赖
   Picture 词库文件存在（删掉那个 1.47MB 的 JSON，本库照常工作）。
2. **不用敏感词黑名单。** 黑名单要靠穷举维护、必然漏、还会天天误伤。
   这里的安全保证是**类目白名单（封闭集）＋结构闸门**：`EXTERNAL_ALLOW` 之外的
   类目连内容都不看就拒掉；`SKIP_TABLE` 只有类目名与条数，没有词。
3. **图侧只算像素。** `lib_image_qc_enh` 不识内容、不加载模型，天然与分级无关；
   所以它对任何题材的出图都可用，不存在「换个题材就失效」的问题。

---

## 五、验证记录（2026-10-05）

| 项 | 结果 |
|---|---|
| 改前哈希基线 | `C:/Users/Doro/model_benchmark/p3_parallel/baseline_C_before.json`（30 文件 / 其中非 `__pycache__` 26） |
| 改后复核 | 见 §5.3，**除本轨 3 个新文件外零变化**（`__pycache__` 无新增/改动） |
| `py_compile` | `lib_image_qc_enh.py`、`lib_sfw_prompts_kit.py` 均通过（`-B`，`cfile` 落临时目录，不污染 `__pycache__`） |
| 图像库实算 | `output/model_benchmark` 216/216 张全量统计成功，`failed=0`（§1.5） |
| 素材包台账 | 19 类 / 234 条内置 + 81 类 / 20,367 条白名单净纳入 + 46 类 / 12,593 条整类拒绝 + 6 父类目 / 438 条子桶拒绝（§二） |
| 限制级词条自检 | 严格标记词组 grep **0 命中**；需判读的单字命中 7 处全为误报（详见 §5.2） |

### 5.2 限制级词条自检（可复跑）

```powershell
# A) 严格标记词组：限制级词条 / 分级标记位 / 英文对应词
rg -n -e '裸体|裸露|全裸|乳沟|乳尖|乳晕|乳房|乳头|胸部|胸围|臀|下体|私处|阴蒂|阴道|阴唇|阴茎|肉棒|自慰|口交|抽插|潮吹|爱液|淫水|精液|情趣|色情|情欲|罩杯|三围|围度|萝莉|御姐|熟女|少女|未成年|幼女|偷拍|窥视|偷窥|扶他|丁字裤|深V领|\bNTR\b|NSFW|_L[0-9]|\bL[1-5]\b|\bnude\b|\bnaked\b|\berotic\b|\bporn\b|\bsex\b|\bbreasts?\b|\bboobs\b|\bnipples?\b|\bvagina\b|\bpussy\b|\bpenis\b|\bcum\b|\bhorny\b|\bhandjob\b|\borgasm\b' -- lib_image_qc_enh.py lib_sfw_prompts_kit.py docs/质量指标与SFW词库增强.md
# 结果：exit=1，3 个文件 0 命中。

# B) 需人工判读的单字（阴/乳/胸/臀/裸/淫）
rg -n -o -e '阴|乳|胸|臀|裸|淫' -- <同上三文件>
# 结果：7 处，逐条判读如下，无一处是限制级词面。
```

B 组 7 处判读：

| 位置 | 命中字 | 实际上下文 | 判定 |
|---|---|---|---|
| `lib_sfw_prompts_kit.py:22` | 裸 | 「半角逗号**裸**测量」（结构闸门说明，指「无单位修饰的裸测量」） | 误报 |
| `lib_sfw_prompts_kit.py:62` | 阴 | 「**阴**天散射光」 | 误报（天气） |
| `lib_sfw_prompts_kit.py:68` ×2 | 阴 | 「6500K **阴**天冷白」「8500K **阴**影冷调」 | 误报（天气/光影） |
| `lib_sfw_prompts_kit.py:76` | 阴 | 「**阴**天」 | 误报（天气） |
| `lib_sfw_prompts_kit.py:157` | 阴 | 「**阴**影类型」（外部类目名，通用光影维度，计数 90） | 误报（光影） |
| `docs/质量指标与SFW词库增强.md:231` | 阴 | 内置类目表 `weather` 行的「**阴**/雨/雾/雪」 | 误报（天气） |

`乳` / `胸` / `臀` / `淫` 四个单字在三个文件中**完全 0 出现**。

补充：受限类目的**原键名**也不在文件里——分级内容专属的 3 个类目在 `SKIP_TABLE`
里写作 `<分级行为句类>` / `<分级幻想扩展类>` / `<分级深度阶类>`，靠 `_LEVEL_CAT_RE`
（任何 `_L<数字>` 键）在运行时识别；子桶同理，改用 `SUBBUCKET_KEEP` 白名单默认全拒。

### 5.3 边界遵守

* 新建文件仅 3 个：`lib_image_qc_enh.py`、`lib_sfw_prompts_kit.py`、`docs/质量指标与SFW词库增强.md`。
* 未改 `01-09`、未改 `10` 现有任何文件（含另两轨的 `lib_inventory_gate` /
  `lib_prompt_qc` / `lib_prompt_robust` / `discover*` / `bench*` / `analyze*` / `run.py` /
  `prompts` / `docs` 已有 5 份）。
* Picture 全程**只读**；未 git、未下载、未出图、未提交 ComfyUI 任务。
* 入口集成（`run.py` 子命令接线）**未做**，按指挥方要求串行进行。
* 遗留清理：`py_compile` 曾在 `__pycache__` 落下 1 个 `.pyc`，已删除；
  后续编译一律 `-B` + 临时 `cfile`。
