# -*- coding: utf-8 -*-
"""短篇漫画通用引擎

给定一个「故事数据模块」，逐页生成、压图落盘、写索引。数据模块只需暴露：

    TITLE / SUBTITLE / GENRE / LOGLINE / SIZE
    PAGES          每页 dict：no, name, seed, cast, tone, body, line
    STYLES         画风列表，每项 dict：key, label, note, block, neg
    STYLE_BY_KEY   由 STYLES 派生的字典
    CHOSEN         本次制作使用的画风 key
    page(body, tone, style_block, cast) -> str   拼完整提示词

输出目录 = 数据模块所在目录，产物落 `<dir>/pages/NN.jpg`，索引 `<dir>/story.json`。

用法：
  python story_kit.py ../story3/story_data.py --plan
  python story_kit.py ../story3/story_data.py
  python story_kit.py ../story3/story_data.py 3 5      # 只跑指定页
  python story_kit.py ../story3/story_data.py --index  # 只重建索引
"""
import importlib.util
import io
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from layout_runner import SERVER, run

W, H = 800, 1200
STEPS, CFG, SAMPLER, SCHED = 30, 4.0, "euler", "simple"
NEG_BASE = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"


def load(path):
    """按文件路径加载故事数据模块。"""
    path = os.path.abspath(path)
    name = "storydata_" + os.path.basename(os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._DIR = os.path.dirname(path)
    return mod


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


def write_index(D, style):
    """按 PAGES 全量重建 story.json——部分重跑也不会丢页。"""
    pages = []
    for p in D.PAGES:
        pages.append(dict(no=p["no"], caption=p["name"], line=p["line"],
                          image="pages/%02d.jpg" % p["no"], seed=p["seed"],
                          prompt=D.page(p["body"], p["tone"], style["block"], p["cast"])))
    json.dump(dict(title=D.TITLE, subtitle=D.SUBTITLE, genre=D.GENRE,
                   logline=getattr(D, "LOGLINE", ""), size="%dx%d" % (W, H),
                   style=style["label"],
                   note="单种子单次生成，未修图。角色卡按页取子集，空镜格不出现人物。",
                   pages=pages),
              open(os.path.join(D._DIR, "story.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return pages


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    D = load(argv[0])
    style = D.STYLE_BY_KEY[D.CHOSEN]
    rest = argv[1:]

    if "--plan" in rest:
        print("%s · 画风：%s（%s）" % (D.TITLE, style["label"], style["key"]))
        for p in D.PAGES:
            full = D.page(p["body"], p["tone"], style["block"], p["cast"])
            print("P%-2d %-12s seed=%d  角色=%-12s %4d 字"
                  % (p["no"], p["name"], p["seed"], "+".join(p["cast"]), len(full)))
        print("共 %d 页，画幅 %dx%d，euler / %d 步 / CFG %.1f"
              % (len(D.PAGES), W, H, STEPS, CFG))
        return 0

    if "--index" in rest:
        n = len(write_index(D, style))
        print("[index] story.json 已全量重建（%d 页）" % n)
        return 0

    want = {int(a) for a in rest if a.isdigit()} or {p["no"] for p in D.PAGES}
    os.makedirs(os.path.join(D._DIR, "pages"), exist_ok=True)

    ok = 0
    for p in D.PAGES:
        if p["no"] not in want:
            continue
        neg = ", ".join(x for x in [NEG_BASE, style.get("neg", "")] if x)
        rec = dict(name="%s_p%02d" % (D.SLUG, p["no"]),
                   prompt=D.page(p["body"], p["tone"], style["block"], p["cast"]),
                   negative=neg, width=W, height=H, steps=STEPS, cfg=CFG,
                   sampler=SAMPLER, scheduler=SCHED, seed=p["seed"])
        imgs = run(rec)
        rel = "pages/%02d.jpg" % p["no"]
        if imgs:
            size = save_jpg(fetch(imgs[0]), os.path.join(D._DIR, rel))
            ok += 1
            print("[saved]  %-14s %6.1fKB" % (rel, size / 1024), flush=True)

    meta = write_index(D, style)
    print("[summary] %d/%d 页成功；story.json 已全量重建（%d 页）"
          % (ok, len(want), len(meta)))
    return 0 if ok == len(want) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
