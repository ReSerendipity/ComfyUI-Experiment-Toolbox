# -*- coding: utf-8 -*-
"""明度审计（light audit）：对单图或目录批量输出"亮不亮、干净不干净"的客观指标。

场景（model-eval-to-publish 流程实测沉淀）：
  - 封面/海报类产物的"阴森感"验收：AI 生成的排版封面若让模型自选照片主体，
    深色照片可能占半幅压垮整体色调（实测：黑板照片致深色占比 26.5%，换
    亮色主体 + 明度约束后 1.7%–4.7%）。
  - 与"纸底 + 墨字 + 朱红点缀"的既定视觉语言对齐验收：纸底占比、深色占比
    是两个一票否决级指标。

指标（与 04_结果分析/README 指标口径互补，本表为"版面明度"口径）：
  lum          平均亮度（0.299/0.587/0.114 加权）
  dark%        深色占比：亮度 < 0.15 的像素（阴森探测器，封面建议 < 8%）
  paper%       纸底占比：R>0.85 & G>0.82 & B>0.75（暖白纸底）
  clip_hi%     高光截断：亮度 > 0.985（过曝；排版封面建议 < 5%）
  clip_lo%     暗部死黑：亮度 < 0.02
  sat          平均饱和度（HSV 近似）
  top_text%    顶部 --top-band 区域内亮度 < 0.4 的像素占比（标题/模型名
               大字带的"醒目度"量化；实测 23%–35% 为醒目区间）

用法：
    python light_audit.py img.png [img2.png ...]
    python light_audit.py some_dir/ --fail-dark 0.10
    python light_audit.py cover.png --top-band 0.25

--fail-dark N：任意图 dark% > N 时退出码 2（可接 CI / 批量闸门）。
依赖：Pillow + numpy。
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image


def audit(path, top_band=0.25):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    L = 0.299*a[..., 0] + 0.587*a[..., 1] + 0.114*a[..., 2]
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx-mn)/(mx+1e-6), 0)
    paper = ((a[..., 0] > 0.85) & (a[..., 1] > 0.82) & (a[..., 2] > 0.75)).mean()
    top = L[:max(1, int(L.shape[0]*top_band))]
    return {
        "file": str(path),
        "lum": round(float(L.mean()), 3),
        "dark%": round(float((L < 0.15).mean())*100, 1),
        "paper%": round(float(paper)*100, 1),
        "clip_hi%": round(float((L > 0.985).mean())*100, 2),
        "clip_lo%": round(float((L < 0.02).mean())*100, 2),
        "sat": round(float(sat.mean()), 3),
        "top_text%": round(float((top < 0.4).mean())*100, 1),
    }


def main():
    ap = argparse.ArgumentParser(description="明度审计：亮度/深色/纸底/高光截断/顶部文字像素")
    ap.add_argument("paths", nargs="+", help="图片文件或目录")
    ap.add_argument("--top-band", type=float, default=0.25, help="顶部区域高度占比（默认 0.25）")
    ap.add_argument("--fail-dark", type=float, default=None,
                    help="任意图 dark%% 超过该值则退出码 2（如 0.10 表示 10%%）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 数组（供脚本消费）")
    a = ap.parse_args()
    files = []
    for p in a.paths:
        pp = Path(p)
        if pp.is_dir():
            files += sorted(list(pp.glob("*.png")) + list(pp.glob("*.jpg")) + list(pp.glob("*.jpeg")))
        else:
            files.append(pp)
    if not files:
        print("no images found"); sys.exit(1)
    rows = [audit(f, a.top_band) for f in files]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        head = ["file", "lum", "dark%", "paper%", "clip_hi%", "clip_lo%", "sat", "top_text%"]
        print("\t".join(head))
        for r in rows:
            print("\t".join(str(r[k]) for k in head))
    if a.fail_dark is not None:
        bad = [r for r in rows if r["dark%"] > a.fail_dark*100]
        if bad:
            print(f"FAIL dark% > {a.fail_dark:.0%}: " + ", ".join(r["file"] for r in bad), file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
