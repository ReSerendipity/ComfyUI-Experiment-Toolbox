# -*- coding: utf-8 -*-
r"""
模型家族横评 ③：结果分析。

产出四件：
  a) metrics.json      客观指标（亮度 / 对比度 / LapVar 锐度 / 色彩度）
  b) similarity.json   同模型同 prompt 跨种子稳定性（128px 灰度相似度矩阵 + 均值）
  c) 家族拼版 PNG      行 = 模型，列 = S1..S9，每格缩略图 + 模型名 + seed，白底，标签 msyh
  d) scoresheet.csv    评分表模板（100 分制）
     report_skeleton.md 读图排名汇总骨架（含家族内「含/不含例外」双口径表位）

指标算法抄自 04_结果分析/metrics.py 与 analyze_models.py（laplacian_var /
colorfulness / thumb_gray+1-归一化MSE）。不 import 那两个文件：它们在模块级
就读写硬编码的 %USERPROFILE%\WorkBuddy\... 路径，import 即产生副作用。

相似度口径（重要）
    只在「同模型 + 同 prompt + 不同 seed」之间计算，衡量的是**同模型跨种子稳定性**。
    跨架构/跨家族的像素相似度无意义（噪声张量、latent 打包、VAE 全都不同），
    本脚本因此不输出任何跨模型相似度数字。

用法（必须用 ComfyUI 自带 python）：
    python analyze_family.py --out C:/Users/Doro/model_benchmark/toolbox_acceptance/
    python analyze_family.py --out <dir> --root <跑测输出根> --thumb 300
"""
import argparse
import csv
import json
import os
import sys
from collections import OrderedDict, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"

# ---- 指标算法：抄自 04_结果分析/metrics.py 第 11-20 行 / analyze_models.py 第 29-46 行 ----
def laplacian_var(g):
    from numpy.lib.stride_tricks import sliding_window_view
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    return float((sliding_window_view(g, (3, 3)) * k).sum(axis=(-1, -2)).var())


def colorfulness(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2)
                 + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
# ---------------------------------------------------------------------------------


def load_rgb(p):
    return Image.open(p).convert("RGB")


def metrics_of(im):
    a = np.asarray(im).astype(np.float32)
    g = a.mean(axis=2)
    return OrderedDict([
        ("size", "%dx%d" % im.size),
        ("brightness", round(float(g.mean()), 1)),
        ("contrast_std", round(float(g.std()), 2)),
        ("sharpness_lapvar", round(laplacian_var(g), 1)),
        ("colorfulness", round(colorfulness(a), 2)),
    ])


def thumb_gray(im, n=128):
    return np.asarray(im.convert("L").resize((n, n))).astype(np.float32)


def sim_matrix(ims):
    """1 - 归一化 MSE（抄自 04_结果分析/focus_sheet.py 第 39-51 行）"""
    M = np.stack([thumb_gray(i) for i in ims])
    n = len(ims)
    S = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            S[i, j] = 1.0 - float(((M[i] - M[j]) ** 2).mean()) / (255.0 ** 2)
    return S


def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def scan(root):
    """扫描输出目录里的 PNG。

    支持两种布局（按相对 root 的深度自动判定）：
      规范四层   family/model/prompt/seed.png
      扁平/历史  group/*.png            （探针、冒烟图等；family=group，
                                          model=文件名去后缀，prompt/seed 记为 "?"）
    两种布局都会顺带读取同名的 .params.json / .result.json。
    """
    recs = []
    if not os.path.isdir(root):
        return recs
    for dp, dns, fns in os.walk(root):
        pngs = sorted(f for f in fns if f.lower().endswith(".png"))
        if not pngs:
            continue
        rel = os.path.relpath(dp, root).replace("\\", "/")
        parts = [] if rel == "." else rel.split("/")
        for fn in pngs:
            stem_full = os.path.join(dp, fn)
            stem = stem_full[:-4]
            params, result = {}, {}
            if os.path.isfile(stem + ".params.json"):
                try:
                    params = json.load(open(stem + ".params.json", encoding="utf-8"))
                except Exception:
                    params = {}
            if os.path.isfile(stem + ".result.json"):
                try:
                    result = json.load(open(stem + ".result.json", encoding="utf-8"))
                except Exception:
                    result = {}
            if len(parts) >= 3:
                family, model, prompt, seed = parts[0], parts[1], parts[2], fn[:-4]
                layout = "quad"
            else:
                family = parts[0] if parts else "(root)"
                model = fn[:-4]
                prompt = params.get("prompt_id") or "?"
                seed = str(params.get("seed", "?"))
                layout = "flat"
            recs.append(OrderedDict([
                ("layout", layout),
                ("family", family), ("model", model), ("prompt", prompt), ("seed", seed),
                ("png", stem_full),
                ("png_rel", os.path.relpath(stem_full, root).replace("\\", "/")),
                ("chain", params.get("chain", "")),
                ("declared_exception", bool(params.get("declared_exception"))),
                ("elapsed_s", result.get("elapsed_s")),
                ("prompt_sha256", params.get("prompt_sha256")),
                ("steps", params.get("steps")), ("cfg", params.get("cfg")),
                ("sampler", params.get("sampler")), ("scheduler", params.get("scheduler")),
            ]))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="跑测输出根（含 family 层）")
    ap.add_argument("--out", required=True, help="分析产物输出目录")
    ap.add_argument("--thumb", type=int, default=300)
    ap.add_argument("--grid-seed", default=None,
                    help="拼版用哪个 seed（默认取每个 (family,model,prompt) 的第一个）")
    a = ap.parse_args()

    out = a.out
    os.makedirs(out, exist_ok=True)
    if not a.root:
        # 默认：模块自带 prompts 的同级没有输出时，回退到 ComfyUI 常见位置
        cands = [r"C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI/output/model_benchmark",
                 os.path.join(HERE, "output")]
        a.root = next((c for c in cands if os.path.isdir(c)), cands[0])
    root = a.root
    print("扫描输出根 : %s" % root)
    recs = scan(root)
    print("发现图像   : %d 张" % len(recs))
    if not recs:
        print("[!] 没有找到任何 .png；请用 --root 指定跑测输出根")
        return 2

    # ---------- a) 客观指标 ----------
    metrics = []
    for r in recs:
        try:
            im = load_rgb(r["png"])
        except Exception as e:
            print("  跳过(读图失败) %s: %s" % (r["png_rel"], e))
            continue
        m = metrics_of(im)
        m.update({"family": r["family"], "model": r["model"], "prompt": r["prompt"],
                  "seed": r["seed"], "chain": r["chain"],
                  "declared_exception": r["declared_exception"],
                  "file_kb": round(os.path.getsize(r["png"]) / 1024, 1),
                  "png": r["png_rel"]})
        metrics.append(m)
    json.dump(metrics, open(os.path.join(out, "metrics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    hdr = "%-18s %-40s %-4s %8s %9s %10s %9s" % ("family", "model", "prompt", "亮度", "对比度σ",
                                                "锐度LapVar", "色彩度")
    print("\n" + hdr)
    print("-" * len(hdr))
    for m in sorted(metrics, key=lambda x: (x["family"], x["model"], x["prompt"], x["seed"])):
        print("%-18s %-40s %-4s %8.1f %9.2f %10.1f %9.2f"
              % (m["family"], m["model"][:40], m["prompt"], m["brightness"],
                 m["contrast_std"], m["sharpness_lapvar"], m["colorfulness"]))

    # ---------- b) 同模型同 prompt 跨种子稳定性 ----------
    by = defaultdict(list)
    for m in metrics:
        by[(m["family"], m["model"], m["prompt"])].append(m)
    stab = []
    for (fam, model, pid), items in sorted(by.items()):
        items.sort(key=lambda x: x["seed"])
        if len(items) < 2:
            stab.append(OrderedDict([("family", fam), ("model", model), ("prompt", pid),
                                     ("n_seeds", len(items)),
                                     ("mean_sim", None), ("matrix", None),
                                     ("note", "种子数 < 2，无法计算稳定性")]))
            continue
        ims = [load_rgb(root + os.sep + i["png"].replace("/", os.sep)) for i in items]
        S = sim_matrix(ims)
        seeds = [i["seed"] for i in items]
        off = S[~np.eye(len(S), dtype=bool)]
        stab.append(OrderedDict([
            ("family", fam), ("model", model), ("prompt", pid), ("n_seeds", len(items)),
            ("seeds", seeds),
            ("matrix", [[round(float(S[i, j]), 4) for j in range(len(S))] for i in range(len(S))]),
            ("mean_sim", round(float(off.mean()), 4)),
            ("min_sim", round(float(off.min()), 4)),
            ("note", "同模型同prompt跨种子专用；禁止跨架构/跨家族比像素"),
        ]))
    json.dump(stab, open(os.path.join(out, "similarity.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    got = [s for s in stab if s["mean_sim"] is not None]
    print("\n跨种子稳定性（同模型同prompt，%d/%d 组可算）" % (len(got), len(stab)))
    for s in sorted(got, key=lambda x: -x["mean_sim"])[:12]:
        print("  %-18s %-38s %-4s n=%d  mean_sim=%.4f min=%.4f"
              % (s["family"], s["model"][:38], s["prompt"], s["n_seeds"],
                 s["mean_sim"], s["min_sim"]))

    # ---------- c) 家族拼版：行=模型，列=prompt ----------
    fams = sorted({m["family"] for m in metrics})
    models = sorted({(m["family"], m["model"]) for m in metrics})
    pids = sorted({m["prompt"] for m in metrics})
    cw, chh, pad, cap, hdr_h = a.thumb, a.thumb, 12, 30, 34
    lab_w = 190
    W = lab_w + len(pids) * (cw + pad) + pad
    H = hdr_h + len(models) * (chh + pad) + pad
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_cell = get_font(14)
    f_head = get_font(18)
    f_note = get_font(13)
    for j, pid in enumerate(pids):
        d.text((lab_w + pad + j * (cw + pad) + 4, 8), pid, fill=(0, 0, 0), font=f_head)
    d.text((8, 8), "family / model  \\  prompt", fill=(90, 90, 90), font=f_note)
    for i, (fam, model) in enumerate(models):
        y = hdr_h + i * (chh + pad)
        d.text((8, y + 6), fam, fill=(0, 0, 0), font=f_cell)
        d.text((8, y + 24), model[:26], fill=(70, 70, 70), font=f_note)
        for j, pid in enumerate(pids):
            cands = [m for m in metrics if m["family"] == fam and m["model"] == model
                     and m["prompt"] == pid]
            if not cands:
                continue
            if a.grid_seed:
                pick = next((c for c in cands if c["seed"] == a.grid_seed), cands[0])
            else:
                pick = sorted(cands, key=lambda x: x["seed"])[0]
            x = lab_w + pad + j * (cw + pad)
            d.text((x + 2, y - 12), "seed " + str(pick["seed"]), fill=(120, 120, 120), font=f_note)
            t = load_rgb(root + os.sep + pick["png"].replace("/", os.sep)).copy()
            t.thumbnail((cw, chh))
            sheet.paste(t, (x + (cw - t.width) // 2, y + 6))
    sheet_path = os.path.join(out, "family_montage.png")
    sheet.save(sheet_path)
    print("\n拼版: %s  %s  (行=%d 模型, 列=%d prompt)" % (sheet_path, sheet.size, len(models), len(pids)))

    # ---------- d) 评分表模板 + 报告骨架 ----------
    cols = ["family", "model", "stratum", "prompt", "seed", "A还原30", "B解剖20", "C光影15",
            "D细节文字15", "E稳定性10", "F审美10", "总分100", "硬门结果", "证据描述", "读图人"]
    with open(os.path.join(out, "scoresheet.csv"), "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for m in sorted(metrics, key=lambda x: (x["family"], x["model"], x["prompt"], x["seed"])):
            stratum = "B(例外链路)" if m["declared_exception"] else "A"
            wr.writerow([m["family"], m["model"], stratum, m["prompt"], m["seed"],
                         "", "", "", "", "", "", "", "", "", ""])
    print("评分表: %s  (%d 行待填)" % (os.path.join(out, "scoresheet.csv"), len(metrics)))

    sk = os.path.join(out, "report_skeleton.md")
    with open(sk, "w", encoding="utf-8") as f:
        f.write("# 模型家族横评 · 读图报告骨架\n\n")
        f.write("> 评分表 100 分制：A 提示词还原 30 / B 解剖结构 20 / C 光影材质 15 / "
                "D 细节与文字 15 / E 跨种子稳定性 10 / F 构图审美 10。\n")
        f.write("> 每一项必须写可观察证据，禁止以模型名气/参数量/文件名加权。\n\n")
        f.write("## 0. 家族清单与链路\n\n")
        f.write("| family | model | chain | declared_exception | 说明 |\n|---|---|---|---|---|\n")
        seen = set()
        for m in sorted(metrics, key=lambda x: (x["family"], x["model"])):
            k = (m["family"], m["model"])
            if k in seen:
                continue
            seen.add(k)
            f.write("| %s | %s | %s | %s | |\n" % (m["family"], m["model"], m["chain"],
                                                "是" if m["declared_exception"] else "否"))
        f.write("\n## 1. 家族内排名 · 双口径（必须同时给出）\n\n")
        for fam in fams:
            ws = [mm for fm, mm in models if fm == fam]
            exc = [mm for fm, mm in models if fm == fam
                   and any(m["model"] == mm and m["declared_exception"] for m in metrics)]
            f.write("### %s\n\n" % fam)
            f.write("**口径 A（含例外权重，共 %d 个）**\n\n" % len(ws))
            f.write("| model | 总分 | A | B | C | D | E | F | 硬门 |\n|---|---|---|---|---|---|---|---|---|\n")
            for mm in ws:
                f.write("| %s |  |  |  |  |  |  |  |  |\n" % mm)
            f.write("\n**口径 B（不含例外权重，共 %d 个）**\n\n" % (len(ws) - len(exc)))
            f.write("| model | 总分 | A | B | C | D | E | F | 硬门 |\n|---|---|---|---|---|---|---|---|---|\n")
            for mm in ws:
                if mm in exc:
                    continue
                f.write("| %s |  |  |  |  |  |  |  |  |\n" % mm)
            if exc:
                f.write("\n> 例外权重 %s 使用不同链路，**不得**把其与同族其他权重的差异表述为"
                        "「同链路权重差异」；其分数单列 Stratum B。\n\n" % "、".join(exc))
        f.write("\n## 2. 逐 prompt 跨模型排名\n\n")
        for pid in pids:
            f.write("### %s\n\n| family | model | 总分 | 硬门 | 证据 |\n|---|---|---|---|---|\n" % pid)
            for m in metrics:
                if m["prompt"] == pid:
                    break
            f.write("\n")
        f.write("\n## 3. 六维雷达（每模型一张）\n\n")
        for fm, mm in models:
            f.write("- %s / %s\n" % (fm, mm))
        f.write("\n## 4. 客观指标附录\n\n")
        f.write("见 metrics.json（亮度/对比度σ/锐度LapVar/色彩度）。\n")
        f.write("注意：这些是**辅助参考**，不参与主观评分，不能替代读图。\n")
        f.write("\n## 5. 跨种子稳定性附录\n\n")
        f.write("见 similarity.json。口径：**同模型同 prompt 跨种子专用**；"
                "跨架构/跨家族像素不可比，本报告不给出任何跨模型相似度数字。\n")
        f.write("\n## 6. 选型建议\n\n")
        f.write("- 综合首选：\n- 速度首选：\n- 文字渲染首选：\n- 多人物首选：\n"
                "- 成人内容首选：\n- 显存最省：\n")
    print("报告骨架: %s" % sk)
    print("\n产物目录: %s" % out)
    for fn in sorted(os.listdir(out)):
        print("  %-24s %8.1f KB" % (fn, os.path.getsize(os.path.join(out, fn)) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
