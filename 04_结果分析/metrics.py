# -*- coding: utf-8 -*-
"""对 17 组结果做客观指标统计 + 生成带标签的拼版对照图。"""
import os, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test"
OUT = os.path.join(BASE, "output")
files = sorted(glob.glob(os.path.join(OUT, "*.png")))

def laplacian_var(g):
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(g, (3, 3))
    return float((w * k).sum(axis=(-1, -2)).var())

def colorfulness(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = np.abs(r - g); yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))

rows = []
thumbs = []
for f in files:
    im = Image.open(f).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    g = a.mean(axis=2)
    name = os.path.basename(f).split("__")[0]
    rows.append({
        "label": name,
        "size": "%dx%d" % im.size,
        "brightness": round(float(g.mean()), 1),
        "contrast_std": round(float(g.std()), 2),
        "sharpness_lapvar": round(laplacian_var(g), 1),
        "colorfulness": round(colorfulness(a), 2),
        "file_kb": round(os.path.getsize(f) / 1024),
    })
    t = im.copy(); t.thumbnail((340, 340))
    thumbs.append((name, t))

# 拼版 4 列
cols = 4
cell_w, cell_h, pad, cap = 350, 380, 10, 26
rows_n = (len(thumbs) + cols - 1) // cols
W, H = cols * (cell_w + pad) + pad, rows_n * (cell_h + pad) + pad
sheet = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
except Exception:
    font = ImageFont.load_default()
for i, (name, t) in enumerate(thumbs):
    cx = pad + (i % cols) * (cell_w + pad)
    cy = pad + (i // cols) * (cell_h + pad)
    d.text((cx + 4, cy + 2), name, fill=(0, 0, 0), font=font)
    sheet.paste(t, (cx + (cell_w - t.width) // 2, cy + cap))
sheet.save(os.path.join(BASE, "对比拼版_17组.png"))

json.dump(rows, open(os.path.join(BASE, "metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

hdr = f"{'组合':32s}{'亮度':>8s}{'对比度σ':>10s}{'锐度(LapVar)':>14s}{'色彩度':>9s}{'文件KB':>8s}"
print(hdr); print("-" * len(hdr))
for r in rows:
    print(f"{r['label']:32s}{r['brightness']:>8.1f}{r['contrast_std']:>10.2f}{r['sharpness_lapvar']:>14.1f}{r['colorfulness']:>9.2f}{r['file_kb']:>8d}")
print("\n拼版已保存:", os.path.join(BASE, "对比拼版_17组.png"), sheet.size)
