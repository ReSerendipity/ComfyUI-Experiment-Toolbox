# -*- coding: utf-8 -*-
"""补充验证（不在 17 组矩阵内）：karras 异常到底是"调度器不兼容"还是"步数不足"。
仅这两组为了定位根因临时改动 steps，其余参数仍保持工作流原值。"""
import json, os, sys, time, shutil, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_prompt import build
from run_combos import post, wait, collect, OUT

PROBES = [
    ("P1_euler_karras_steps50", "euler", "karras", 50, "karras 提到 50 步是否恢复"),
    ("P2_euler_normal_steps25", "euler", "normal", 25, "标准线性调度对照（25 步）"),
]

def main():
    for label, samp, sched, steps, note in PROBES:
        prefix = f"ss_test/{label}"
        p = build(samp, sched, prefix)
        p["1458"]["inputs"]["steps"] = steps          # 仅此一处临时改动
        t0 = time.time()
        print(f"[probe] {label}  steps={steps} ...", flush=True)
        res, err = post("/prompt", {"prompt": p})
        if err:
            print("  提交失败:", err[:600], flush=True); continue
        ok, outs, werr = wait(res["prompt_id"])
        dt = round(time.time() - t0, 1)
        files = collect(prefix)
        for f in files:
            shutil.copy2(f, os.path.join(OUT, f"{label}__{os.path.basename(f)}"))
        print(f"  -> {'OK' if ok else 'FAIL'} {dt}s  {len(files)} 张", flush=True)
        if not ok:
            print("  错误:", str(werr)[:400], flush=True)

if __name__ == "__main__":
    main()
