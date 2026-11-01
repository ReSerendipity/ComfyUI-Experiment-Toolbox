# -*- coding: utf-8 -*-
"""《猫与台风夜》· 全 8 页生成（厚涂电影感）

按 `story_data.PAGES` 逐页生成，经 `/view` 取回产物压成 jpg，落到 `pages/`，
再写 `story.json` 供阅读器渲染。

用法：
  python gen_story2.py            # 全 8 页
  python gen_story2.py 1 2 3      # 只跑指定页
  python gen_story2.py --plan     # 只看分镜与提示词长度
  python gen_story2.py --index    # 只重建 story.json，不出图
"""
import io
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_data as SD
from layout_runner import SERVER, run

PAGES_DIR = os.path.join(HERE, "pages")
W, H = 800, 1200
STEPS, CFG, SAMPLER, SCHED = 30, 4.0, "euler", "simple"
NEG_BASE = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"

STYLE = SD.STYLE_BY_KEY[SD.CHOSEN]


def fetch(image):
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(SERVER + "/view" + q, timeout=120) as r:
        return r.read()


def save_jpg(raw, dst, quality=90):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def write_index():
    """按 PAGES 全量重建 story.json（部分重跑也不会丢页）。"""
    pages = []
    for p in SD.PAGES:
        pages.append(dict(no=p["no"], caption=p["name"], line=p["line"],
                          image="pages/%02d.jpg" % p["no"], seed=p["seed"],
                          prompt=SD.page(p["body"], p["tone"], STYLE["block"], p["cast"])))
    json.dump(dict(title=SD.TITLE, subtitle=SD.SUBTITLE, genre=SD.GENRE,
                   logline=SD.LOGLINE,
                   size="%dx%d" % (W, H), style=STYLE["label"],
                   note="单种子单次生成，未修图。角色卡按页取子集，空镜格不出现人物。",
                   pages=pages),
              open(os.path.join(HERE, "story.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return pages


def main(argv):
    if "--plan" in argv:
        print("画风：%s（%s）" % (STYLE["label"], STYLE["key"]))
        for p in SD.PAGES:
            full = SD.page(p["body"], p["tone"], STYLE["block"], p["cast"])
            print("P%-2d %-10s seed=%d  角色=%-8s %4d 字"
                  % (p["no"], p["name"], p["seed"], "+".join(p["cast"]), len(full)))
        print("共 %d 页，画幅 %dx%d，euler / %d 步 / CFG %.1f"
              % (len(SD.PAGES), W, H, STEPS, CFG))
        return 0
    if "--index" in argv:
        n = len(write_index())
        print("[index] story.json 已全量重建（%d 页）" % n)
        return 0

    want = {int(a) for a in argv if a.isdigit()} or {p["no"] for p in SD.PAGES}
    os.makedirs(PAGES_DIR, exist_ok=True)

    ok = 0
    for p in SD.PAGES:
        if p["no"] not in want:
            continue
        neg = ", ".join(x for x in [NEG_BASE, STYLE.get("neg", "")] if x)
        rec = dict(name="neko_p%02d" % p["no"],
                   prompt=SD.page(p["body"], p["tone"], STYLE["block"], p["cast"]),
                   negative=neg, width=W, height=H, steps=STEPS, cfg=CFG,
                   sampler=SAMPLER, scheduler=SCHED, seed=p["seed"])
        imgs = run(rec)
        rel = "pages/%02d.jpg" % p["no"]
        if imgs:
            size = save_jpg(fetch(imgs[0]), os.path.join(HERE, rel))
            ok += 1
            print("[saved]  %-14s %6.1fKB" % (rel, size / 1024), flush=True)

    meta = write_index()
    print("[summary] %d/%d 页成功；story.json 已全量重建（%d 页）"
          % (ok, len(want), len(meta)))
    return 0 if ok == len(want) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
