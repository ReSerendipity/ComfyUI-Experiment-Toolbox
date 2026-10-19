# -*- coding: utf-8 -*-
"""色彩网格文本投影：把任意图变成字符网格 + 客观统计，供纯文本会话"读图"兜底。

背景：多模态读图不可用（会话被路由为纯文本模型）时，需要一种确定性的
"以文本方式看图"手段。本工具把图缩成 N×M 色块网格，每格按主色映射为
单字符（W 白 / w 浅 / D 灰 / K 黑 / R 红 / O 橙 / Y 黄 / G 绿 / C 青 /
B 蓝 / P 紫），并输出亮度/深色占比/红蓝占比等统计。构图、颜色分区、
文字带位置都可读；纹理细节读不出（边界要如实声明）。

实测用法（model-eval-to-publish 流程）：
  - 冒烟/套件产物的版式结构核验（标题带/印章/照片区/线条位置）
  - 客观断言 FAIL 时的"冤案复核"（暗蓝面 S/V 双低会被色相判定漏掉，
    网格能直接看到蓝色块存在——先看网格再调阈值，不许盲调）
  - 封面"阴森感"定位（K 占比一眼可见：黑板照片占了半幅）

用法：
    python text_grid.py img.png                # 40 列网格
    python text_grid.py img.png --cols 60      # 更细
    python text_grid.py img1.png img2.png      # 多图依次输出

依赖：Pillow + numpy（与 04_结果分析 其余脚本一致）。
"""
import argparse
import numpy as np
from PIL import Image


def grid_of(path, cols=40):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    H, W = a.shape[:2]
    rows = max(1, round(cols * H / W / 2))          # 字符高约为宽的一半
    ch, cw = H / rows, W / cols
    lines, stats = [], []
    for r in range(rows):
        line = []
        for c in range(cols):
            cell = a[int(r*ch):int((r+1)*ch), int(c*cw):int((c+1)*cw)]
            R, G, B = cell[..., 0].mean(), cell[..., 1].mean(), cell[..., 2].mean()
            L = 0.299*R + 0.587*G + 0.114*B
            mx, mn = max(R, G, B), min(R, G, B)
            if L > 0.92 and mx-mn < 0.06: ch_ = "W"
            elif L > 0.80: ch_ = "w"
            elif L < 0.12: ch_ = "K"
            elif mx-mn < 0.10: ch_ = "D"
            elif R >= G and R >= B and R-G > 0.12 and R-B > 0.12:
                ch_ = "R" if L < 0.5 else "O"
            elif G >= R and G >= B: ch_ = "G"
            elif B >= R and B >= G and B-R > 0.08: ch_ = "B" if L < 0.55 else "C"
            elif R > B and G > B and L > 0.6: ch_ = "Y"
            else: ch_ = "P" if B > G else "D"
            line.append(ch_)
            stats.append((R, G, B, L))
        lines.append("|" + "".join(line) + "|")
    s = np.array(stats)
    lum = 0.299*s[:, 0] + 0.587*s[:, 1] + 0.114*s[:, 2]
    red = ((s[:, 0] > 0.43) & (s[:, 0] > s[:, 1]*1.45) & (s[:, 0] > s[:, 2]*1.45)).mean()
    blue = ((s[:, 2] > 0.35) & (s[:, 2] > s[:, 0]*1.3) & (s[:, 2] > s[:, 1]*1.15)).mean()
    dark = (lum < 0.15).mean()
    paper = ((s[:, 0] > 0.85) & (s[:, 1] > 0.82) & (s[:, 2] > 0.75)).mean()
    return lines, dict(lum=float(lum.mean()), dark=float(dark), paper=float(paper),
                       red=float(red), blue=float(blue))


def main():
    ap = argparse.ArgumentParser(description="色彩网格文本投影（纯文本会话读图兜底）")
    ap.add_argument("images", nargs="+", help="图片路径（可多张）")
    ap.add_argument("--cols", type=int, default=40, help="网格列数（默认 40）")
    a = ap.parse_args()
    print("legend: R=red O=orange Y=yellow G=green C=cyan B=blue P=purple K=black D=gray W=white w=lightgray")
    for p in a.images:
        lines, st = grid_of(p, a.cols)
        print(f"===== {p} =====")
        print("\n".join(lines))
        print(f"stats: 亮度 {st['lum']:.3f} | 深色 {st['dark']:.1%} | 纸底 {st['paper']:.1%} | "
              f"红系 {st['red']:.1%} | 蓝系 {st['blue']:.1%}")


if __name__ == "__main__":
    main()
