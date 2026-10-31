# -*- coding: utf-8 -*-
"""短篇漫画《末班车开往海见》· 生成与落盘

读 `story_data.py`，逐页生成，经 `/view` 取回产物并压成 jpg，最后写 `story.json`
供 `build_gallery.py` 渲染阅读区。

用法：
  python gen_story.py              # 全 8 页
  python gen_story.py 1 2 3        # 只跑指定页
  python gen_story.py --plan       # 只看分镜与提示词长度，不提交

需要 ComfyUI 已在 8188 且 MOSS-Image 三件套可用；先 `python layout_runner.py --probe`。
"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_data as SD
from layout_runner import SERVER, run

PAGES_DIR = os.path.join(HERE, "pages")
W, H = 800, 1200
STEPS, CFG, SAMPLER, SCHED = 30, 4.0, "euler", "simple"


def fetch(image):
    """经 /view 取回产物字节，不依赖本机 ComfyUI 目录。"""
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(SERVER + "/view" + q, timeout=120) as r:
        return r.read()


def save_jpg(raw, dst, long_edge=1200, quality=86):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    if max(w, h) > long_edge:
        k = long_edge / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def write_index():
    """按 story_data 全量重建 story.json（不提交、不出图）。"""
    pages = []
    for p in SD.PAGES:
        pages.append(dict(no=p["no"], caption=p["caption"], line=p["line"],
                          image="pages/%02d.jpg" % p["no"], seed=p["seed"],
                          prompt=SD.page(p["body"], p["tone"])))
    json.dump(dict(title=SD.TITLE, subtitle=SD.SUBTITLE, logline=SD.LOGLINE,
                   genre=SD.GENRE, size="%dx%d" % (W, H), note=SD.NOTE, pages=pages),
              open(os.path.join(HERE, "story.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return pages


def main(argv):
    pages = SD.PAGES
    if "--plan" in argv:
        for p in pages:
            full = SD.page(p["body"], p["tone"])
            print("P%-2d %-10s %4d 字  seed=%d" % (p["no"], p["caption"], len(full), p["seed"]))
        print("共 %d 页，画幅 %dx%d，口径 %s/%d 步/CFG %.1f"
              % (len(pages), W, H, SAMPLER, STEPS, CFG))
        return 0
    if "--index" in argv:
        write_index()
        print("[index] story.json 已按 story_data 全量重建（%d 页）" % len(pages))
        return 0

    want = {int(a) for a in argv if a.isdigit()} or {p["no"] for p in pages}
    os.makedirs(PAGES_DIR, exist_ok=True)

    ok = 0
    for p in pages:
        if p["no"] not in want:
            continue
        full = SD.page(p["body"], p["tone"])
        rec = dict(name="umimi_p%02d" % p["no"], prompt=full, width=W, height=H,
                   steps=STEPS, cfg=CFG, sampler=SAMPLER, scheduler=SCHED, seed=p["seed"])
        imgs = run(rec)
        rel = "pages/%02d.jpg" % p["no"]
        if imgs:
            size = save_jpg(fetch(imgs[0]), os.path.join(HERE, rel))
            ok += 1
            print("[saved]  %-14s %6.1fKB" % (rel, size / 1024), flush=True)

    # 索引始终全量重建，避免只跑单页时把其它页从 story.json 里丢掉
    meta = write_index()
    print("[summary] %d/%d 页成功；story.json 已全量重建（%d 页）" % (ok, len(want), len(meta)))
    return 0 if ok == len(want) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
