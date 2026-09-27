# -*- coding: utf-8 -*-
"""聚焦对照图（4 张关键结果并排）+ 组合间相似度矩阵（量化"是否几乎相同"）。"""
import os, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test"
OUT = os.path.join(BASE, "output")


def load(name, size=256):
    f = glob.glob(os.path.join(OUT, name + "__*.png"))[0]
    return Image.open(f).convert("RGB")


# ---------- 1. 聚焦对照图 ----------
focus = [
    ("01_euler_simple", "基线 euler+simple"),
    ("06_res_multistep_beta", "最优 res_multistep+beta"),
    ("04_euler_karras", "异常 euler+karras(25步)"),
    ("P1_euler_karras_steps50", "修复 euler+karras(50步)"),
]
cw, ch, pad, cap = 480, 500, 12, 34
W = len(focus) * (cw + pad) + pad
H = ch + pad * 2 + cap
sheet = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(sheet)
try:
    f18 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
except Exception:
    f18 = ImageFont.load_default()
for i, (name, label) in enumerate(focus):
    t = load(name).copy(); t.thumbnail((cw, ch))
    x = pad + i * (cw + pad)
    d.text((x + 6, pad), label, fill=(0, 0, 0), font=f18)
    sheet.paste(t, (x + (cw - t.width) // 2, pad + cap))
sheet.save(os.path.join(BASE, "聚焦对照_4组.png"))

# ---------- 2. 相似度矩阵（1 - 归一化 MSE，下采样 128px 灰度） ----------
labels = [os.path.basename(f).split("__")[0] for f in sorted(glob.glob(os.path.join(OUT, "*.png")))]
M = []
for lb in labels:
    im = load(lb, 128).convert("L").resize((128, 128))
    M.append(np.asarray(im).astype(np.float32))
M = np.stack(M)
n = len(labels)
sim = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        mse = float(((M[i] - M[j]) ** 2).mean())
        sim[i, j] = 1.0 - mse / (255.0 ** 2)

# 每个组合最相近的三个
res = []
for i in range(n):
    order = np.argsort(-sim[i])
    near = [(labels[k], round(float(sim[i, k]), 3)) for k in order if k != i][:3]
    res.append({"label": labels[i], "nearest": near, "max_sim": near[0][1]})

json.dump(res, open(os.path.join(BASE, "similarity.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("相似度（1-归一化MSE，越接近1越像）")
print("=" * 72)
for r in res:
    print(f"{r['label']:30s} 最相近: " + ", ".join(f"{a}({b})" for a, b in r["nearest"]))
print("\n聚焦对照图:", os.path.join(BASE, "聚焦对照_4组.png"), sheet.size)
