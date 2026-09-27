# -*- coding: utf-8 -*-
"""
CFG 探针：验证「没有负向提示词时，把 CFG 调大于 1 有没有意义」。
3 个 cfg × 2 种负向提示词（空 / 实际内容），其余参数全部保持工作流原值
（euler+simple / steps 25 / seed 1111119 / 1024²），仅 cfg 与 negative_prompt 变化。
同时记录耗时，用于验证 cfg>1 会启用 uncond 分支（每步多一次前向）。
"""
import json, os, sys, time, shutil, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_prompt import build
from run_combos import post, wait, collect, OUT

NEG_REAL = "低质量，模糊，变形，畸变，多余的手指，错误的手部，水印，签名，文字，噪点，过曝"
NODE_ENCODE = "1452"   # TextEncodeQwenImage21

CASES = [
    ("C1_cfg1_neg_empty",  1.0, "",       "基线：cfg=1 + 空负向"),
    ("C2_cfg2_neg_empty",  2.0, "",       "cfg=2 + 空负向"),
    ("C3_cfg4_neg_empty",  4.0, "",       "cfg=4 + 空负向"),
    ("C4_cfg2_neg_real",   2.0, NEG_REAL, "cfg=2 + 实际负向提示词"),
    ("C5_cfg4_neg_real",   4.0, NEG_REAL, "cfg=4 + 实际负向提示词"),
]


def main():
    log = []
    for label, cfg, neg, note in CASES:
        prefix = f"ss_test/{label}"
        p = build("euler", "simple", prefix)
        p["1458"]["inputs"]["cfg"] = cfg
        p[NODE_ENCODE]["inputs"]["negative_prompt"] = neg
        t0 = time.time()
        print(f"[cfg probe] {label}  cfg={cfg} neg={'空' if not neg else '有'} ...", flush=True)
        res, err = post("/prompt", {"prompt": p})
        if err:
            print("   提交失败:", err[:500], flush=True); continue
        ok, outs, werr = wait(res["prompt_id"])
        dt = round(time.time() - t0, 1)
        files = collect(prefix)
        for f in files:
            shutil.copy2(f, os.path.join(OUT, f"{label}__{os.path.basename(f)}"))
        print(f"   -> {'OK' if ok else 'FAIL'} {dt}s  {len(files)} 张", flush=True)
        log.append({"label": label, "cfg": cfg, "neg": "有" if neg else "空", "note": note,
                    "ok": ok, "sec": dt, "files": [os.path.basename(x) for x in files]})
    json.dump(log, open(r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\cfg_probe_log.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n完成:", sum(1 for x in log if x["ok"]), "/", len(CASES))


if __name__ == "__main__":
    main()
