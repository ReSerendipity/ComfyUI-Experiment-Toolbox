# -*- coding: utf-8 -*-
"""封面生成 · 四比例

读 `cover_data.py`，逐张提交，经 `/view` 取回并压成 jpg，落到 `covers/`。

用法：
  python gen_covers.py            # 全部
  python gen_covers.py comic_3x4  # 指定
  python gen_covers.py --plan     # 只看比例与提示词长度
"""
import io
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import cover_data as CV
from layout_runner import SERVER, run

OUT = os.path.join(HERE, "covers")
STEPS, CFG, SAMPLER, SCHED = 30, 4.0, "euler", "simple"


def fetch(image):
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(SERVER + "/view" + q, timeout=120) as r:
        return r.read()


def save_jpg(raw, dst, long_edge=1600, quality=90):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    if max(w, h) > long_edge:
        k = long_edge / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def main(argv):
    want = [a for a in argv if not a.startswith("--")] or [c["key"] for c in CV.COVERS]
    if "--plan" in argv:
        for c in CV.COVERS:
            print("%-12s %-5s %4d×%-4d %4d 字  %s"
                  % (c["key"], c["ratio"], c["size"][0], c["size"][1],
                     len(c["prompt"]), c["for_"]))
        return 0

    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for c in CV.COVERS:
        if c["key"] not in want:
            continue
        w, h = c["size"]
        rec = dict(name="cover_" + c["key"], prompt=c["prompt"], negative=CV.NEGATIVE,
                   width=w, height=h, steps=STEPS, cfg=CFG,
                   sampler=SAMPLER, scheduler=SCHED, seed=c["seed"])
        imgs = run(rec)
        if imgs:
            dst = os.path.join(OUT, "%s.jpg" % c["key"])
            size = save_jpg(fetch(imgs[0]), dst)
            ok += 1
            print("[saved]  covers/%s.jpg  %6.1fKB" % (c["key"], size / 1024), flush=True)

    print("[summary] %d/%d 张" % (ok, len(want)))
    return 0 if ok == len(want) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
