# -*- coding: utf-8 -*-
"""
模型家族横评 P3 隔离轨 · lib_image_qc_enh —— 客观图像指标增强库（纯像素统计）。

定位
    只做**像素统计**，不做任何画面内容识别、不调用视觉模型、不加载分类器、
    不做人/物/场景判断，因此与内容分级无关，可安全用于任意题材的出图横评。
    输出是一张「数值表」，供 analyze_family.py / 人工读图做**辅助参考**
    （README：亮度 / 对比度σ / 锐度 LapVar / 色彩度不参与主观评分，不能替代读图）。

继承的 4 个老指标（逐字沿用，口径不变，保证与 04_结果分析/metrics.json 可比）
    brightness / contrast_std / sharpness_lapvar / colorfulness
    来源：04_结果分析/metrics.py 的 `laplacian_var()` 与 `colorfulness()`
          （Hasler & Süsstrunk 彩色度公式），主程序 `run.py fanalyze` 消费。

新增的客观项（全部项目无关，无阈值依赖内容）
    影调尾部   highlight_clip_ratio  / shadow_crush_ratio / dynamic_range_p99_p01
               midtone_share / luma_p05·p50·p95
    对比度     rms_contrast（全局 REC.709 亮度 RMS） / local_contrast_ratio（局部）
    锐度细分   sharpness_lapvar_norm（除以均值，跨曝光可比）
               edge_density / edge_energy（Sobel 梯度幅值占比与均值）
    噪点       noise_sigma（Immerkær 快速噪声估计）/ noise_snr_db
    颜色       color_temp_k（CCT，McCamy 近似）/ saturation_mean / warm_cool_index
    构图重心   centroid_x·y / centroid_offset_center / thirds_offset
               mass_spread（亮度质量分布，**主体在不在画面里**的代理量）
    有效内容   flat_area_ratio（低方差网格占比，抓「糊成一片 / 空图」）

来源与取舍说明（重要，避免误引）
    1. Picture/tools/modules/quality_control.py 经全库 grep（`from PIL` / `import numpy`）
       确认**不含任何图像侧代码**——它是纯文本 QC（标点/字数/词频/模板句残留）。
       所以「quality_control 里的非限制级图像函数」实际为 **0 个**，本模块没有从它搬任何函数。
    2. Picture 整棵 tools/ 树里唯一的图像侧量化检查是
       `Picture/tools/batch7_render.py` 的 `png_stats()`：
           g = im.convert("L").resize((64,64)); mean_luma; non_black = mean_luma > 8
       即「转 L 通道 + 降采样 + 亮度阈值」三点思路，且与题材完全无关。
       本模块保留这三点思路并**双向泛化**：阈值比（不是单张图一个均值）→
       highlight_clip_ratio（≥250）与 shadow_crush_ratio（≤5），
       降采样上限从 64×64 放宽到 `max_side`（默认 2048，噪点估计需要真实分辨率）。
    3. 色温项的**命名域**参考 Picture 词库的「色温效果 / 光线方向 / 色彩体系.色温」
       这类纯光色类目（项目无关），但**实现是客观 CCT 计算**（RGB→CIE xy→McCamy），
       一个词条都没搬。
    4. 构图项刻意**只算亮度质量分布**，不算显著性网络、不做人物检测：
       主体是谁与本库无关，权重要不要按内容加权由调用方决定。

API
    analyze(png_path, cfg=None)      -> dict     单张图全指标（含 flags / verdict）
    analyze_dir(root, cfg=None)      -> dict     目录批量：rows + aggregate + flags 统计
    load_cfg(overrides=None)         -> dict     默认参数 + 覆盖
    flag_report(rows)                -> dict     只汇总 flags 计数（不看图即可分诊）
    METRICS / LEGACY_METRICS / SOURCES / THRESHOLDS   —— 自解释常量，便于文档与表格生成

退出码：0 正常 / 1 用法或 IO 错。

用法（必须用 ComfyUI 自带 python，因为要 numpy + Pillow）：
    python -X utf8 lib_image_qc_enh.py
    python -X utf8 lib_image_qc_enh.py --root "%USERPROFILE%/APP/ComfyUI-aki-v3/ComfyUI/output/model_benchmark" --limit 24
    python -X utf8 lib_image_qc_enh.py --root output/model_benchmark --json _qc.json
    python -X utf8 lib_image_qc_enh.py --file a.png --json
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(os.environ.get("USERPROFILE", ""), "APP", "ComfyUI-aki-v3",
                            "ComfyUI", "output", "model_benchmark")

# ── 指标登记表：(key, 中文名, 来源标签, 单位) ───────────────────────────────────
LEGACY_METRICS = ("brightness", "contrast_std", "sharpness_lapvar", "colorfulness")

METRICS = (
    # key,                 名称,              来源标签,                    单位
    ("brightness",        "亮度均值",          "legacy:04_结果分析",         "0-255"),
    ("contrast_std",      "对比度σ",          "legacy:04_结果分析",         "0-255"),
    ("sharpness_lapvar",  "锐度 LapVar",      "legacy:04_结果分析",         "灰度²"),
    ("colorfulness",      "彩色度",           "legacy:04_结果分析",         "-"),
    ("luma_p05",          "亮度 P05",         "enh:png_stats 亮度分布泛化",  "0-255"),
    ("luma_p50",          "亮度 P50",         "enh:png_stats 亮度分布泛化",  "0-255"),
    ("luma_p95",          "亮度 P95",         "enh:png_stats 亮度分布泛化",  "0-255"),
    ("highlight_clip_ratio", "高光过曝占比",  "enh:png_stats 单端阈值→双端", "0-1"),
    ("shadow_crush_ratio",   "暗部死黑占比",  "enh:png_stats 单端阈值→双端", "0-1"),
    ("dynamic_range_p99_p01", "动态范围 P99-P01", "enh:直方图跨度",          "0-255"),
    ("midtone_share",     "中间调占比",        "enh:直方图跨度",              "0-1"),
    ("rms_contrast",      "全局 RMS 对比度",   "enh:REC.709 亮度 RMS",        "-"),
    ("local_contrast_ratio", "局部/全局对比度", "enh:3x3 局部标准差",         "-"),
    ("sharpness_lapvar_norm", "锐度 LapVar(归一)", "enh:除以亮度均值",        "灰度"),
    ("edge_density",      "边缘密度",          "enh:Sobel 梯度阈值占比",      "0-1"),
    ("edge_energy",       "边缘能量",          "enh:Sobel 梯度均值",          "0-1"),
    ("noise_sigma",       "噪点 σ",            "enh:Immerkær 快速估计",       "0-255"),
    ("noise_snr_db",      "噪点信噪比",        "enh:亮度/σ",                  "dB"),
    ("color_temp_k",      "色温 CCT",          "enh:McCamy 近似",             "K"),
    ("saturation_mean",   "平均饱和度",        "enh:HSV 的 S 通道",           "0-1"),
    ("warm_cool_index",   "冷暖偏移",          "enh:mean(R-B)",               "-1..1"),
    ("centroid_x",        "亮度重心 X",        "enh:亮度加权质心",            "0-1"),
    ("centroid_y",        "亮度重心 Y",        "enh:亮度加权质心",            "0-1"),
    ("centroid_offset_center", "重心偏心距",   "enh:到画面中心距离",          "0-1"),
    ("thirds_offset",     "三分点最近距离",     "enh:到四交点最短距离",        "0-1"),
    ("mass_spread",       "亮度质量离散度",     "enh:亮度质量分布",            "0-1"),
    ("flat_area_ratio",   "平坦区占比",        "enh:低方差网格占比",          "0-1"),
)

# ── 每个指标的来源（文档与表格生成的唯一出处，禁止在此写任何分级词条）──────────
SOURCES = {
    "legacy:04_结果分析":
        "04_结果分析/metrics.py :: laplacian_var() / colorfulness() + 主循环统计字段",
    "enh:png_stats 亮度分布泛化":
        "Picture/tools/batch7_render.py :: png_stats()（convert('L')+resize+亮度均值）"
        " → 泛化为 P05/P50/P95 分位",
    "enh:png_stats 单端阈值→双端":
        "Picture/tools/batch7_render.py :: png_stats() 的 non_black(mean_luma>8) "
        " → 泛化为像素级双端阈值比（≥250 / ≤5）",
    "enh:直方图跨度":
        "png_stats 的直方图思路延伸：P99-P01 有效动态范围 + 中间调占比",
    "enh:REC.709 亮度 RMS":
        "04_结果分析 metrics.py 的 g=a.mean(axis=2) 灰度口径 → 改 REC.709 加权亮度",
    "enh:3x3 局部标准差":
        "全局 σ 的局部对照，区分「整体平淡」与「主体有层次」",
    "enh:除以亮度均值":
        "laplacian_var() 的归一化版本，消除暗图天然低 LapVar 的偏差",
    "enh:Sobel 梯度阈值占比":
        "laplacian_var() 的互补锐度估计（十邻域梯度 vs 四邻域二阶差分）",
    "enh:Sobel 梯度均值":
        "同上，取均值而非阈值占比，保留强度信息",
    "enh:Immerkær 快速估计":
        "Immerkær (1996) 快速噪声 σ：卷积 [[1,-2,1],[-2,4,-2],[1,-2,1]] 求和，"
        "与题材无关的纯数值估计",
    "enh:亮度/σ":
        "噪点 σ 与亮度均值之比的 dB 表示，便于跨曝光排序",
    "enh:McCamy 近似":
        "RGB→CIE xy→McCamy(1992) CCT 公式；命名域参考 Picture 词库纯光色类目，"
        "未搬任何词条",
    "enh:HSV 的 S 通道":
        "补 colorfulness 之外的饱和度维度（colorfulness 对大色块敏感、对淡色不敏感）",
    "enh:mean(R-B)":
        "冷暖方向的极简量，与 color_temp_k 互为印证",
    "enh:亮度加权质心":
        "构图重心代理量：只用亮度质量分布，不做显著性网络 / 人物检测",
    "enh:到画面中心距离":
        "同上，中心构图偏离度",
    "enh:到四交点最短距离":
        "三分法落点代理量（越小越贴近三分交点）",
    "enh:亮度质量分布":
        "质量离散度 = 主体是否集中在小面积（≈0）或铺满全画面（≈大）",
    "enh:低方差网格占比":
        "抓「输出没渲染出东西 / 大面积糊平」，纯方差统计",
}

# ── 参考阈值（工程经验值，非 Picture 规则；只用于分诊，不用于评分）─────────────
THRESHOLDS = {
    "highlight_clip_ratio": (0.02, 0.08, "high"),   # (warn, bad, 方向)
    "shadow_crush_ratio":   (0.05, 0.15, "high"),
    "dynamic_range_p99_p01": (140.0, 90.0, "low"),
    "midtone_share":        (0.25, 0.15, "low"),
    "rms_contrast":         (0.30, 0.18, "low"),
    "local_contrast_ratio": (0.12, 0.07, "low"),
    "noise_snr_db":         (32.0, 26.0, "low"),
    "saturation_mean":      (0.15, 0.08, "low"),
    "flat_area_ratio":      (0.60, 0.80, "high"),
    # mass_spread / thirds_offset / color_temp_k 设为 (None, None, "none")：
    # 它们是**对比轴**不是缺陷轴（例如重心偏中心可能正是该提示词要的），故不参与分诊。
    "mass_spread":          (None, None, "none"),
    "thirds_offset":        (None, None, "none"),
    "color_temp_k":         (None, None, "none"),
}

DEFAULTS = {
    "max_side": 2048,        # 分析分辨率上限（噪点/锐度需要真实像素，太大则降采样）
    "high_clip": 250,        # 高光过曝阈值（0-255）
    "shadow_clip": 5,        # 暗部死黑阈值（0-255）
    "edge_thr": 0.06,        # Sobel 归一化幅值阈值，算 edge_density
    "flat_var_thr": 2.0,     # 网格内标准差阈值（灰度），低于此值算「平坦区」
    "grid": 32,              # 平坦区/局部对比度的网格边长（像素）
    "rec709": (0.2126, 0.7152, 0.0722),
}

_LAP4 = np.array([[0.0, 1.0, 0.0],
                  [1.0, -4.0, 1.0],
                  [0.0, 1.0, 0.0]], dtype=np.float32)
_SOBEL_X = np.array([[-1.0, 0.0, 1.0],
                     [-2.0, 0.0, 2.0],
                     [-1.0, 0.0, 1.0]], dtype=np.float32)
_SOBEL_Y = _SOBEL_X.T.copy()
_IMMERK = np.array([[1.0, -2.0, 1.0],
                    [-2.0, 4.0, -2.0],
                    [1.0, -2.0, 1.0]], dtype=np.float32)
_THIRDS = ((1 / 3, 1 / 3), (2 / 3, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 2 / 3))


def load_cfg(overrides=None):
    cfg = dict(DEFAULTS)
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if k in DEFAULTS})
    return cfg


def _convolve(a, k):
    """3x3 相关卷积（边界不补零，直接裁掉一圈，统计上更干净）。"""
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(a, (3, 3))
    return np.einsum("ijkl,kl->ij", w, k, optimize=True)


def _laplacian_var(g):
    """4 邻域 Laplacian 方差 —— 口径与 04_结果分析/metrics.py::laplacian_var 逐字一致。"""
    return float(_convolve(g, _LAP4).var())


def _colorfulness(rgb):
    """Hasler & Süsstrunk 彩色度 —— 口径与 04_结果分析/metrics.py::colorfulness 一致。"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2)
                 + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))


def _cct_kelvin(r, g, b):
    """McCamy 近似色温：RGB(线性化前的 sRGB 均值即可，够用) → CIE xy → CCT。"""
    r, g, b = float(r), float(g), float(b)
    if r < 1e-6 or g < 1e-6 or b < 1e-6:
        return None
    X = 0.4124 * r + 0.3576 * g + 0.1805 * b
    Y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    Z = 0.0193 * r + 0.1192 * g + 0.9505 * b
    s = X + Y + Z
    if s < 1e-9:
        return None
    x, y = X / s, Y / s
    denom = 0.1858 - y
    if abs(denom) < 1e-9:
        return None
    n = (x - 0.3320) / denom
    cct = 449.0 * n ** 3 + 3525.0 * n ** 2 + 6823.3 * n + 5520.33
    if not math.isfinite(cct) or cct <= 0:
        return None
    return float(min(max(cct, 1500.0), 15000.0))


def _local_stats(g, grid):
    h, w = g.shape
    gh, gw = max(1, h // grid), max(1, w // grid)
    blocks = g[:gh * grid, :gw * grid].reshape(gh, grid, gw, grid)
    return blocks.std(axis=(1, 3))


def analyze(png_path, cfg=None):
    """单张 PNG 的全指标。只读文件、只算像素统计，不做任何内容判断。"""
    cfg = cfg or DEFAULTS
    row = {"file": os.path.basename(png_path),
           "path": os.path.abspath(png_path),
           "ok": False}
    try:
        row["file_kb"] = round(os.path.getsize(png_path) / 1024, 1)
    except OSError:
        row["file_kb"] = None
    try:
        with Image.open(png_path) as im:
            src_mode = im.mode
            src_size = im.size
            if src_mode in ("RGBA", "LA", "P"):
                # 带 alpha 的图合成到中灰，避免透明区被当成死黑/过曝
                rgba = im.convert("RGBA")
                base = Image.new("RGBA", rgba.size, (128, 128, 128, 255))
                work = Image.alpha_composite(base, rgba).convert("RGB")
            else:
                work = im.convert("RGB")
            work.load()
    except Exception as e:                                  # noqa: BLE001
        row["error"] = "%s: %s" % (type(e).__name__, e)
        return row

    aw, ah = work.size
    scale = 1.0
    if max(aw, ah) > cfg["max_side"]:
        scale = cfg["max_side"] / float(max(aw, ah))
        work = work.resize((max(1, int(aw * scale)), max(1, int(ah * scale))),
                           Image.LANCZOS)
    a = np.asarray(work, dtype=np.float32)
    if a.ndim == 2:
        a = np.dstack([a, a, a])
    h, w = a.shape[:2]

    kr, kg, kb = cfg["rec709"]
    g = kr * a[..., 0] + kg * a[..., 1] + kb * a[..., 2]          # REC.709 亮度
    lum_legacy = a.mean(axis=2)                                    # 老指标口径（等权 RGB）

    p05, p50, p95 = (float(np.percentile(g, p)) for p in (5, 50, 95))
    gmean = float(g.mean())
    gstd = float(g.std())
    p99, p01 = float(np.percentile(g, 99)), float(np.percentile(g, 1))
    sigma = math.sqrt(max(float((g * g).mean()), 1e-9))

    gx = _convolve(g, _SOBEL_X)
    gy = _convolve(g, _SOBEL_Y)
    mag = np.sqrt(gx * gx + gy * gy) / (255.0 * 4.0)              # 归一化到 ~0-1
    edge_density = float((mag > cfg["edge_thr"]).mean())
    edge_energy = float(mag.mean())

    lapvar = _laplacian_var(lum_legacy)
    imm = _convolve(g, _IMMERK)
    npix = float((w - 2) * (h - 2))
    noise_sigma = float(math.sqrt(math.pi / 2) / 6.0 * float(np.abs(imm).sum()) / max(npix, 1.0))

    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)

    # 亮度加权质心：w = 归一化亮度^2，凸显亮部质量（主体通常在亮部或强反差处）
    wgt = np.clip(g / 255.0, 0.0, 1.0) ** 2
    tot = float(wgt.sum())
    if tot > 1e-9:
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        cx = float((wgt * xs).sum() / tot) / max(w - 1, 1)
        cy = float((wgt * ys).sum() / tot) / max(h - 1, 1)
    else:
        cx = cy = 0.5
    diag = math.hypot(max(w - 1, 1), max(h - 1, 1))
    off_center = math.hypot(cx - 0.5, cy - 0.5) / (0.5 * math.sqrt(2.0) * 1.0)
    thirds = min(math.hypot(cx - tx, cy - ty) for tx, ty in _THIRDS) / 0.5
    colw = wgt.sum(axis=0)
    roww = wgt.sum(axis=1)
    def _norm_dist(v):
        s = float(v.sum())
        if s < 1e-9:
            return 0.0
        idx = np.arange(len(v), dtype=np.float32)
        mu = float((v * idx).sum() / s)
        sd = math.sqrt(max(float((v * (idx - mu) ** 2).sum() / s), 0.0))
        return float(sd / max(len(v) - 1, 1))
    mass_spread = float((_norm_dist(colw) + _norm_dist(roww)) / 2.0)

    flat_ratio = float((_local_stats(g, cfg["grid"]) < cfg["flat_var_thr"]).mean())

    cct = _cct_kelvin(a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean())

    row.update({
        "ok": True,
        "src_mode": src_mode,
        "src_size": "%dx%d" % (src_size[0], src_size[1]),
        "analysis_size": "%dx%d" % (w, h),
        "analysis_scale": round(scale, 4),
        # ── 老 4 项（口径不变） ──
        "brightness": round(float(lum_legacy.mean()), 2),
        "contrast_std": round(gstd, 3),
        "sharpness_lapvar": round(lapvar, 2),
        "colorfulness": round(_colorfulness(a), 3),
        # ── 影调尾部 ──
        "luma_p05": round(p05, 2),
        "luma_p50": round(p50, 2),
        "luma_p95": round(p95, 2),
        "highlight_clip_ratio": round(float((g >= cfg["high_clip"]).mean()), 5),
        "shadow_crush_ratio": round(float((g <= cfg["shadow_clip"]).mean()), 5),
        "dynamic_range_p99_p01": round(p99 - p01, 2),
        "midtone_share": round(float(((g > 63) & (g < 191)).mean()), 4),
        # ── 对比度 ──
        "rms_contrast": round(sigma / max(gmean, 1e-6), 4),
        "local_contrast_ratio": round(float(_local_stats(g, cfg["grid"]).mean())
                                       / max(gstd, 1e-6), 4),
        # ── 锐度细分 ──
        "sharpness_lapvar_norm": round(float(lapvar / max(float(lum_legacy.mean()), 1e-6)), 3),
        "edge_density": round(edge_density, 4),
        "edge_energy": round(edge_energy, 4),
        # ── 噪点 ──
        "noise_sigma": round(noise_sigma, 3),
        "noise_snr_db": round(20.0 * math.log10(max(gmean, 1e-6) / max(noise_sigma, 1e-6)), 2),
        # ── 颜色 ──
        "color_temp_k": (round(cct, 1) if cct else None),
        "saturation_mean": round(float(sat.mean()), 4),
        "warm_cool_index": round(float((a[..., 0].mean() - a[..., 2].mean()) / 255.0), 4),
        # ── 构图重心 ──
        "centroid_x": round(cx, 4),
        "centroid_y": round(cy, 4),
        "centroid_offset_center": round(off_center, 4),
        "thirds_offset": round(thirds, 4),
        "mass_spread": round(mass_spread, 4),
        "flat_area_ratio": round(flat_ratio, 4),
    })
    row["flags"] = _flags(row)
    row["verdict"] = "bad" if any(f.startswith("bad:") for f in row["flags"]) else (
        "warn" if row["flags"] else "ok")
    return row


def _flags(row):
    out = []
    for key, (warn, bad, direction) in THRESHOLDS.items():
        if key not in row or row[key] is None or warn is None:
            continue
        v = row[key]
        if direction == "high":
            if v >= bad:
                out.append("bad:%s" % key)
            elif v >= warn:
                out.append("warn:%s" % key)
        else:
            if v <= bad:
                out.append("bad:%s" % key)
            elif v <= warn:
                out.append("warn:%s" % key)
    return out


def _iter_pngs(root, pattern, recursive, limit):
    if os.path.isfile(root):
        return [root]
    pat = os.path.join(root, "**", pattern) if recursive else os.path.join(root, pattern)
    files = sorted(glob.glob(pat, recursive=recursive))
    return files[:limit] if limit else files


def _agg(values):
    v = [x for x in values if isinstance(x, (int, float))]
    if not v:
        return {}
    arr = np.asarray(v, dtype=np.float64)
    return {"n": int(arr.size), "mean": round(float(arr.mean()), 4),
            "p05": round(float(np.percentile(arr, 5)), 4),
            "p50": round(float(np.percentile(arr, 50)), 4),
            "p95": round(float(np.percentile(arr, 95)), 4),
            "min": round(float(arr.min()), 4), "max": round(float(arr.max()), 4)}


def analyze_dir(root=None, cfg=None, pattern="*.png", recursive=True, limit=0, keep_rows=True):
    """目录批量：逐图指标 + 全体分布汇总 + flags 计数。默认递归。"""
    root = root or DEFAULT_ROOT
    cfg = cfg or DEFAULTS
    if not os.path.exists(root):
        return {"ok": False, "root": os.path.abspath(root), "error": "路径不存在"}
    files = _iter_pngs(root, pattern, recursive, limit)
    rows = []
    for f in files:
        r = analyze(f, cfg)
        if r.get("ok"):
            rows.append(r)
        elif keep_rows:
            rows.append(r)
    num_keys = [k for k, _, _, _ in METRICS]
    agg = {}
    for k in num_keys:
        agg[k] = _agg([r.get(k) for r in rows if r.get("ok")])
    flag_count = {}
    for r in rows:
        for f in r.get("flags", []):
            flag_count[f] = flag_count.get(f, 0) + 1
    verdict = {"ok": 0, "warn": 0, "bad": 0, "failed": 0}
    for r in rows:
        if not r.get("ok"):
            verdict["failed"] += 1
        else:
            verdict[r["verdict"]] += 1
    return {
        "ok": True,
        "root": os.path.abspath(root),
        "pattern": pattern,
        "scanned": len(files),
        "analyzed": sum(1 for r in rows if r.get("ok")),
        "verdict": verdict,
        "flag_count": dict(sorted(flag_count.items(), key=lambda kv: -kv[1])),
        "aggregate": agg,
        "rows": rows if keep_rows else [],
    }


def flag_report(rows):
    """只汇总 flags / verdict，用于「不读图先分诊」。"""
    out = {"n": len(rows), "verdict": {"ok": 0, "warn": 0, "bad": 0, "failed": 0},
           "flag_count": {}}
    for r in rows:
        if not r.get("ok"):
            out["verdict"]["failed"] += 1
            continue
        out["verdict"][r["verdict"]] += 1
        for f in r.get("flags", []):
            out["flag_count"][f] = out["flag_count"].get(f, 0) + 1
    out["flag_count"] = dict(sorted(out["flag_count"].items(), key=lambda kv: -kv[1]))
    return out


def _jsonable(o):
    """numpy 标量兜底转 Python 原生类型，保证 analyze()/analyze_dir() 结果可直接 json.dump。"""
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if hasattr(o, "item") and getattr(o, "ndim", None) == 0:
        return o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def _fmt_table(rep, keys=None):
    keys = keys or [k for k, _, _, _ in METRICS]
    lines = []
    hdr = "%-26s%8s%10s%10s%10s%10s" % ("metric", "mean", "p05", "p50", "p95", "max")
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for k in keys:
        s = rep["aggregate"].get(k) or {}
        if not s:
            continue
        lines.append("%-26s%8.4g%10.4g%10.4g%10.4g%10.4g"
                     % (k, s["mean"], s["p05"], s["p50"], s["p95"], s["max"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="客观图像指标增强库（纯像素统计，无内容判断）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="PNG 目录（默认 output/model_benchmark）")
    ap.add_argument("--file", default=None, help="只分析单个文件")
    ap.add_argument("--pattern", default="*.png")
    ap.add_argument("--limit", type=int, default=12, help="抽样张数，0=全量")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--json", default=None, help="结果写到此 JSON")
    ap.add_argument("--max-side", type=int, default=None)
    ap.add_argument("--metrics", default=None, help="逗号分隔，只打印这些指标")
    a = ap.parse_args(argv)

    cfg = load_cfg({"max_side": a.max_side} if a.max_side else None)
    try:
        if a.file:
            row = analyze(a.file, cfg)
            rep = {"ok": True, "root": os.path.abspath(a.file), "scanned": 1,
                   "analyzed": 1 if row.get("ok") else 0,
                   "verdict": {"ok": 0, "warn": 0, "bad": 0, "failed": 0},
                   "flag_count": {}, "aggregate": {}, "rows": [row]}
            if not row.get("ok"):
                rep["ok"] = False
                rep["error"] = row.get("error")
            else:
                rep["verdict"][row["verdict"]] = 1
                for f in row.get("flags", []):
                    rep["flag_count"][f] = 1
                rep["aggregate"] = {k: _agg([row.get(k)]) for k, _, _, _ in METRICS}
            keys = [k.strip() for k in a.metrics.split(",")] if a.metrics else None
            print("file:", row["file"], "| size:", row.get("src_size"),
                  "| mode:", row.get("src_mode"))
            print(_fmt_table(rep, keys))
            print("verdict:", rep["verdict"], "flags:", rep["flag_count"])
        else:
            rep = analyze_dir(a.root, cfg, a.pattern, not a.no_recursive, a.limit)
            if not rep.get("ok"):
                print("[ERR]", rep.get("error"), rep.get("root"))
                return 1
            print("root      :", rep["root"])
            print("scanned   : %d  analyzed: %d" % (rep["scanned"], rep["analyzed"]))
            print("verdict   :", rep["verdict"])
            keys = [k.strip() for k in a.metrics.split(",")] if a.metrics else None
            print(_fmt_table(rep, keys))
            if rep["flag_count"]:
                print("flags     :", rep["flag_count"])
            else:
                print("flags     : 无")
    except Exception as e:                                      # noqa: BLE001
        print("[ERR] %s: %s" % (type(e).__name__, e))
        return 1

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(_jsonable(rep), fh, ensure_ascii=False, indent=1)
        print("json ->", os.path.abspath(a.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
