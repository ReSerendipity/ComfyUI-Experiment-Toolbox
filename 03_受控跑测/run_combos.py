# -*- coding: utf-8 -*-
"""
Qwen_image_2_1_t2i 采样器 × 调度器组合对比测试
固定：seed=1111119 / steps=25 / cfg=1 / 1024x1024 / 提示词（全部取自工作流原值，不修改）
仅切换 KSampler 的 sampler_name 与 scheduler。
"""
import json, os, time, shutil, sys, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_prompt import build, PROMPT, SEED, STEPS, CFG, W, H

COMFY = "http://127.0.0.1:8188"
OUT = r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\output"
CF_OUT = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\output"
os.makedirs(OUT, exist_ok=True)

COMBOS = [
    ("01_euler_simple",              "euler",               "simple",          "官方原值基线（Qwen-Image 2.1 官方模板）"),
    ("02_euler_beta",                "euler",               "beta",            "Qwen-Image 官方教程推荐调度器"),
    ("03_euler_sgm_uniform",         "euler",               "sgm_uniform",     "新一代 DiT 通用均匀调度"),
    ("04_euler_karras",              "euler",               "karras",          "通用最优非线性调度"),
    ("05_res_multistep_simple",      "res_multistep",       "simple",          "新一代蒸馏模型官方配套"),
    ("06_res_multistep_beta",        "res_multistep",       "beta",            "重启多步 + beta"),
    ("07_dpmpp_2m_karras",           "dpmpp_2m",            "karras",          "主流首选：二阶多步"),
    ("08_dpmpp_2m_sde_gpu_karras",   "dpmpp_2m_sde_gpu",    "karras",          "写实向 SDE"),
    ("09_dpmpp_3m_sde_gpu_karras",   "dpmpp_3m_sde_gpu",    "karras",          "三阶多步 SDE"),
    ("10_dpmpp_2s_ancestral_karras", "dpmpp_2s_ancestral",  "karras",          "二阶单步祖先（创意型）"),
    ("11_euler_ancestral_simple",    "euler_ancestral",     "simple",          "一阶祖先（随机型）"),
    ("12_heun_karras",               "heun",                "karras",          "二阶梯形法"),
    ("13_uni_pc_bh2_karras",         "uni_pc_bh2",          "karras",          "统一预测-校正二阶"),
    ("14_euler_cfg_pp_simple",       "euler_cfg_pp",        "simple",          "CFG++ 引导变体（cfg=1 对照组）"),
    ("15_er_sde_simple",             "er_sde",              "simple",          "扩展反向时间 SDE"),
    ("16_euler_kl_optimal",          "euler",               "kl_optimal",      "训练分布最优调度"),
    ("17_euler_linear_quadratic",    "euler",               "linear_quadratic", "线性-二次混合调度"),
]


def post(path, payload):
    req = urllib.request.Request(COMFY + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode()
    except Exception as e:
        return None, str(e)


def wait(pid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=15) as r:
                h = json.loads(r.read().decode())
        except Exception:
            time.sleep(2); continue
        if pid in h:
            e = h[pid]
            st = e.get("status", {})
            if st.get("completed"):
                return True, e.get("outputs", {}), None
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] in ("execution_error", "execution_interrupted")]
                return False, None, json.dumps(msgs, ensure_ascii=False)[:1200]
            if st.get("status_str") == "success":
                return True, e.get("outputs", {}), None
        time.sleep(2)
    return False, None, "timeout"


def collect(prefix):
    """返回本次生成落盘的图片路径（按 ComfyUI 输出目录查前缀）。"""
    d = os.path.join(CF_OUT, os.path.dirname(prefix))
    base = os.path.basename(prefix)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.startswith(base) and f.lower().endswith(".png"))


def main():
    combos = COMBOS
    frm = os.environ.get("FROM")
    if frm:
        combos = [c for c in COMBOS if c[0] >= frm]
    log = json.load(open(r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\result_log.json", encoding="utf-8")) \
        if os.path.exists(r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\result_log.json") else []
    total = len(combos)
    for i, (label, samp, sched, note) in enumerate(combos, 1):
        prefix = f"ss_test/{label}"
        before = set(collect(prefix))
        t0 = time.time()
        print(f"[{i}/{total}] {label}  ({samp} + {sched}) ...", flush=True)
        p = build(samp, sched, prefix)
        res, err = post("/prompt", {"prompt": p})
        if err:
            print("   提交失败:", err[:500], flush=True)
            log.append({"label": label, "sampler": samp, "scheduler": sched, "note": note,
                        "ok": False, "error": err[:800], "sec": 0, "files": []})
            continue
        pid = res["prompt_id"]
        ok, outs, werr = wait(pid)
        dt = round(time.time() - t0, 1)
        files = [f for f in collect(prefix) if f not in before]
        if not files:
            files = collect(prefix)
        dest = []
        for f in files:
            dst = os.path.join(OUT, f"{label}__{os.path.basename(f)}")
            try:
                shutil.copy2(f, dst); dest.append(dst)
            except Exception as e:
                print("   复制失败:", e, flush=True)
        print(f"   -> {'OK' if ok else 'FAIL'} {dt}s, 图片 {len(dest)} 张", flush=True)
        if not ok:
            print("   错误:", str(werr)[:500], flush=True)
        log.append({"label": label, "sampler": samp, "scheduler": sched, "note": note,
                    "ok": bool(ok) and bool(dest), "sec": dt, "files": [os.path.basename(x) for x in dest],
                    "error": None if ok else str(werr)[:800]})
        json.dump(log, open(r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test\result_log.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("\n完成：成功 %d / 共 %d" % (sum(1 for x in log if x["ok"]), total))


if __name__ == "__main__":
    s = os.environ.get("ONLY")
    if s:
        COMBOS = [c for c in COMBOS if c[0] == s]
    main()
