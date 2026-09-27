# -*- coding: utf-8 -*-
"""分析跨模型跑测结果：客观指标 + 与各模型基线的相似度，检验 σ 预测。"""
import os, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test"
OUT = os.path.join(BASE, "output_models")
log = json.load(open(os.path.join(BASE, "model_test_log.json"), encoding="utf-8")) if \
    os.path.exists(os.path.join(BASE, "model_test_log.json")) else []
# 直接以输出目录为准重建清单（日志可能被后续单模型补跑覆盖）
ok = []
for p in sorted(glob.glob(os.path.join(OUT, "*.png"))):
    b = os.path.basename(p)
    if b.count("__") < 2:
        continue
    m, cname = b.split("__")[0], b.split("__")[1]
    seen = (m, cname)
    if seen in [ (x["model"], x["combo"]) for x in ok ]:
        continue                      # 同组合只取第一张，避免重跑产生的副本重复计数
    ok.append({"model": m, "combo": cname, "files": [b], "sec": 0})
print("从输出目录重建：%d 组" % len(ok))


def load(f):
    return Image.open(os.path.join(OUT, f)).convert("RGB")


def laplacian_var(g):
    from numpy.lib.stride_tricks import sliding_window_view
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    return float((sliding_window_view(g, (3, 3)) * k).sum(axis=(-1, -2)).var())


def metrics(im):
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    g = a.mean(axis=2)
    r, gg, b = a[..., 0], a[..., 1], a[..., 2]
    rg = np.abs(r - gg); yb = np.abs(0.5 * (r + gg) - b)
    col = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    return dict(bright=round(float(g.mean()), 1), contrast=round(float(g.std()), 2),
                sharp=round(laplacian_var(g), 1), color=round(col, 2))


def thumb_gray(f, n=128):
    return np.asarray(load(f).convert("L").resize((n, n))).astype(np.float32)


# 按模型分组
models = {}
for x in ok:
    models.setdefault(x["model"], []).append(x)

rows = []
for m, items in models.items():
    base = next((i for i in items if i["combo"].startswith("base")), None)
    bg = thumb_gray(base["files"][0]) if base else None
    bm = metrics(load(base["files"][0])) if base else None
    for it in items:
        f = it["files"][0]
        mm = metrics(load(f))
        sim = None
        if bg is not None:
            gg = thumb_gray(f)
            sim = round(1 - float(((bg - gg) ** 2).mean()) / (255.0 ** 2), 4)
        rel = ""
        if bm:
            rel = "锐度%+.0f%% 对比度%+.0f%%" % ((mm["sharp"] / bm["sharp"] - 1) * 100,
                                                (mm["contrast"] / bm["contrast"] - 1) * 100)
        rows.append(dict(model=m, combo=it["combo"], sim=sim, sec=it["sec"], **mm, rel=rel))

hdr = f"{'模型':26s}{'组合':30s}{'亮度':>7s}{'对比度':>8s}{'锐度':>8s}{'相似度':>9s}  {'相对基线':<22s}{'耗时':>7s}"
print(hdr); print("-" * len(hdr))
for r in rows:
    print(f"{r['model']:26s}{r['combo']:30s}{r['bright']:>7.1f}{r['contrast']:>8.2f}{r['sharp']:>8.1f}"
          f"{(r['sim'] if r['sim'] is not None else 0):>9.4f}  {r['rel']:<22s}{r['sec']:>7.1f}")

json.dump(rows, open(os.path.join(BASE, "model_metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 拼版：按模型分组，4 列
files = [(f"{x['model']} / {x['combo']}", x["files"][0]) for x in ok]
cols = 4
cw, ch, pad, cap = 350, 380, 10, 28
rowsn = (len(files) + cols - 1) // cols
W, H = cols * (cw + pad) + pad, rowsn * (ch + pad) + pad
sheet = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
except Exception:
    font = ImageFont.load_default()
for i, (name, f) in enumerate(files):
    t = load(f).copy(); t.thumbnail((cw, ch))
    cx = pad + (i % cols) * (cw + pad); cy = pad + (i // cols) * (ch + pad)
    d.text((cx + 4, cy + 2), name[:34], fill=(0, 0, 0), font=font)
    sheet.paste(t, (cx + (cw - t.width) // 2, cy + cap))
sheet.save(os.path.join(BASE, "跨模型对比拼版.png"))
print("\n拼版:", sheet.size, "->", os.path.join(BASE, "跨模型对比拼版.png"))
print("成功组合:", len(ok), "/ 记录", len(log))
