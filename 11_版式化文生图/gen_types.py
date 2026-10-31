# -*- coding: utf-8 -*-
"""版式化文生图 · 批量出样张

按类型库逐类生成，一类型一张，结果写 gen_result.json。

用法：
  python gen_types.py                 # 全部 10 类
  python gen_types.py tarot dossier   # 指定类型
  python gen_types.py --list          # 只列类型，不出图
  python gen_types.py --steps 25 --cfg 2.5 --sampler er_sde   # 换采样口径

需要 ComfyUI 已在 8188 且装好 MOSS-Image 三件套；先 `python layout_runner.py --probe` 自检。
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import layout_types as LT
from layout_runner import run

DEFAULTS = dict(steps=30, cfg=4.0, sampler="euler", scheduler="simple")


def parse(argv):
    opts = dict(DEFAULTS)
    keys = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--list", "--probe"):
            opts[a[2:]] = True
        elif a.startswith("--"):
            k = a[2:]
            if k in ("steps", "cfg", "sampler", "scheduler", "seed"):
                opts[k] = argv[i + 1]
                i += 1
            else:
                raise SystemExit("未知参数：%s" % a)
        else:
            keys.append(a)
        i += 1
    return opts, keys


def main(argv):
    opts, keys = parse(argv)
    if opts.get("probe"):
        from layout_runner import SERVER, probe
        print("[probe] %s" % SERVER)
        bad = probe()
        print("[probe] %s" % ("全部通过" if not bad else "缺失：%s" % ", ".join(bad)))
        return 0 if not bad else 1
    if opts.get("list"):
        print("%-14s%-12s%-14s%-8s分辨率" % ("key", "类型", "主线", "文字密度"))
        for r in LT.summary():
            print("%-14s%-12s%-14s%-8s%s" % r)
        return 0

    keys = keys or list(LT.TYPES.keys())
    out = []
    for k in keys:
        t = LT.get(k)
        w, h = t["size"]
        rec = dict(name="type_%s" % k, prompt=t["prompt"], width=w, height=h,
                   steps=int(opts["steps"]), cfg=float(opts["cfg"]),
                   sampler=opts["sampler"], scheduler=opts["scheduler"],
                   seed=int(opts.get("seed") or random.randint(1, 2 ** 48)))
        imgs = run(rec)
        out.append({"key": k, "label": t["label"], "seed": rec["seed"], "images": imgs})

    json.dump(out, open(os.path.join(HERE, "gen_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = sum(1 for x in out if x["images"])
    print("[summary] %d/%d 成功" % (ok, len(out)))
    return 0 if ok == len(out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
