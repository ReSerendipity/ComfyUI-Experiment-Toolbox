# -*- coding: utf-8 -*-
"""
跨模型统一变量跑测：验证第八节的 σ 预测。
固定：提示词（818 字符，已写入各工作流）+ 种子 1111119 + 各模型自身 steps / cfg / 分辨率。
变量：只切换采样器与调度器。
日志（v2，2026-10-11）：append-only JSONL（唯一事实源）+ 合并视图 JSON（由 jsonl 重建），
每条记录含 seed/steps/cfg/prompt_id/时间戳/解释器与 ComfyUI 版本，见 logutil.py。
"""
import json, os, platform, sys, time, shutil, urllib.request, urllib.error
import flatten
from logutil import append_record, migrate_legacy, rebuild_consolidated

COMFY = "http://127.0.0.1:8188"
BASE = os.path.expandvars(r"%USERPROFILE%\WorkBuddy\2026-09-22-23-53-24\ss_test")
OUT = os.path.join(BASE, "output_models")
WF = os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image")
CF_OUT = os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\output")
LOG_JSON = os.path.join(BASE, "model_test_log.json")    # 合并视图（由 jsonl 重建）
LOG_JSONL = os.path.join(BASE, "model_test_log.jsonl")  # 追加式原始日志（唯一事实源）
FIXED_SEED = 1111119
os.makedirs(OUT, exist_ok=True)

PROMPT = None  # 运行时从 2.1 工作流读

# (标签, 工作流文件, 节点类型, [(组合名, {参数:值}) ...])
# 节点类型 'KSampler' → 直接改 sampler_name/scheduler；'custom' → 改 KSamplerSelect / BasicScheduler
PLAN = [
    ("Z_image_turbo_8step", "Z_image_turbo.json", "KSampler", [
        ("base_resmultistep_simple", {"sampler_name": "res_multistep", "scheduler": "simple"}),
        ("euler_karras",             {"sampler_name": "euler", "scheduler": "karras"}),
        ("euler_exponential",        {"sampler_name": "euler", "scheduler": "exponential"}),
        ("euler_kl_optimal",         {"sampler_name": "euler", "scheduler": "kl_optimal"}),
    ]),
    ("krea2_turbo_8step", "krea2_turbo.json", "KSampler", [
        ("base_euler_simple", {"sampler_name": "euler", "scheduler": "simple"}),
        ("euler_karras",      {"sampler_name": "euler", "scheduler": "karras"}),
        ("euler_exponential", {"sampler_name": "euler", "scheduler": "exponential"}),
        ("euler_kl_optimal",  {"sampler_name": "euler", "scheduler": "kl_optimal"}),
    ]),
    ("Z_image_25step", "Z_image.json", "KSampler", [
        ("base_resmultistep_simple", {"sampler_name": "res_multistep", "scheduler": "simple"}),
        ("euler_karras",             {"sampler_name": "euler", "scheduler": "karras"}),
        ("euler_exponential",        {"sampler_name": "euler", "scheduler": "exponential"}),
    ]),
    ("Qwen_image_2512_50step", "Qwen_image_2512.json", "KSampler", [
        ("base_euler_simple", {"sampler_name": "euler", "scheduler": "simple"}),
        ("euler_karras",      {"sampler_name": "euler", "scheduler": "karras"}),
        ("euler_exponential", {"sampler_name": "euler", "scheduler": "exponential"}),
    ]),
]

# flux.1-dev / Flux.2 Klein 走 SamplerCustomAdvanced：另用参数名映射
PLAN_CUSTOM = [
    ("flux1dev_20step", "flux.1-dev.json", [
        ("base_euler_simple", {"KSamplerSelect": {"sampler_name": "euler"}, "BasicScheduler": {"scheduler": "simple"}}),
        ("euler_karras",      {"KSamplerSelect": {"sampler_name": "euler"}, "BasicScheduler": {"scheduler": "karras"}}),
        ("euler_exponential", {"KSamplerSelect": {"sampler_name": "euler"}, "BasicScheduler": {"scheduler": "exponential"}}),
    ]),
    ("Flux2Klein_4step_Flux2Sched", "Flux.2_Klein-9B-Distilled.json", [
        ("base_euler",         {"KSamplerSelect": {"sampler_name": "euler"}}),
        ("res_multistep",      {"KSamplerSelect": {"sampler_name": "res_multistep"}}),
        ("dpmpp_2m",           {"KSamplerSelect": {"sampler_name": "dpmpp_2m"}}),
    ]),
]


def post(path, payload):
    req = urllib.request.Request(COMFY + path, data=json.dumps(payload).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode()
    except Exception as e:
        return None, str(e)


def wait(pid, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=15) as r:
                h = json.loads(r.read().decode())
        except Exception:
            time.sleep(3); continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed"):
                return True, h[pid].get("outputs", {}), None
            if st.get("status_str") == "error":
                m = [x for x in st.get("messages", []) if x[0] in ("execution_error", "execution_interrupted")]
                return False, None, json.dumps(m, ensure_ascii=False)[:900]
        time.sleep(3)
    return False, None, "timeout"


def collect(prefix):
    d = os.path.join(CF_OUT, os.path.dirname(prefix))
    b = os.path.basename(prefix)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(b) and f.lower().endswith(".png"))


DROP_TYPES = {"TextGenerate", "PrimitiveStringMultiline", "PreviewAny", "PrimitiveBoolean"}
# 批量提示词读取器：从 input/Picture/ 读 txt 当提示词；做单一变量对比时它既不必要又会在目录为空时报错
DROP_ALWAYS = {"BatchPromptReaderWithClip"}


def prune_llm(api):
    """去掉 krea2 的 LLM 提示词增强链路。
    注意：ComfySwitchNode 也承担 model / prompt 的选路（如 enable_lora 开关），
    不能直接删——先把「非 LLM 上游」解析成直连，再删除开关与 LLM 链。"""
    # 1) 解析 ComfySwitchNode：挑一个不来自待删链路的上游，直连给下游
    for k in [k for k, v in api.items() if v["class_type"] == "ComfySwitchNode"]:
        node = api[k]
        cands = [x for x in node["inputs"].values()
                 if isinstance(x, list) and str(x[0]) in api
                 and api[str(x[0])]["class_type"] not in (DROP_TYPES | DROP_ALWAYS)]
        if cands:
            rep = list(cands[0])
            for v2 in api.values():
                for kk, vv in list(v2["inputs"].items()):
                    if isinstance(vv, list) and str(vv[0]) == k:
                        v2["inputs"][kk] = list(rep)
        api.pop(k, None)
    # 2) 删除 LLM 链节点
    for k in [k for k, v in api.items() if v["class_type"] in DROP_TYPES]:
        api.pop(k, None)
    # 3) 清理悬空连线
    for v in api.values():
        for kk, vv in list(v["inputs"].items()):
            if isinstance(vv, list) and str(vv[0]) not in api:
                v["inputs"].pop(kk)
    return api


def run_one(label, path, overrides, prefix):
    api, applied = flatten.flatten(path, overrides)
    if "TextGenerate" in [v["class_type"] for v in api.values()]:
        api = prune_llm(api)
    if any(v["class_type"] in DROP_ALWAYS for v in api.values()):
        for k in [k for k, v in api.items() if v["class_type"] in DROP_ALWAYS]:
            # BatchPromptReaderWithClip 的输出是 CONDITIONING（批量提示词机制的负向分支来源）。
            # 控制变量实验走「注入受控提示词」，因此把它替换成同等语义的「空提示词编码」，
            # 而不是把下游接到它的 clip 输入（那会类型不符：CLIP ≠ CONDITIONING）。
            clip_link = None
            for vv in api[k]["inputs"].values():
                if isinstance(vv, list) and str(vv[0]) in api and api[str(vv[0])]["class_type"] == "DualCLIPLoader":
                    clip_link = list(vv); break
            if clip_link is None:
                for vv in api[k]["inputs"].values():
                    if isinstance(vv, list) and str(vv[0]) in api:
                        clip_link = list(vv); break
            newk = "gen_neg_" + k
            if clip_link:
                api[newk] = {"class_type": "CLIPTextEncode",
                             "inputs": {"clip": clip_link, "text": ""},
                             "_meta": {"title": "生成的空提示词编码（替代批量提示词读取器）"}}
                rep = [newk, 0]
            else:
                rep = None
            for v2 in api.values():
                for kk, vv in list(v2["inputs"].items()):
                    if isinstance(vv, list) and str(vv[0]) == k:
                        if rep:
                            v2["inputs"][kk] = list(rep)
                        else:
                            v2["inputs"].pop(kk)
            api.pop(k, None)
    # 清掉指向已删节点的悬空连线
    for v in api.values():
        for k, val in list(v["inputs"].items()):
            if isinstance(val, list) and str(val[0]) not in api:
                v["inputs"].pop(k)
    # 正向提示词兜底：直接把「KSampler.positive（或 CFGGuider.positive）的上游文本节点」设为统一提示词
    pos_src = None
    for v in api.values():
        if v["class_type"] in ("KSampler", "KSamplerAdvanced", "CFGGuider", "BasicGuider"):
            p = v["inputs"].get("positive")
            if isinstance(p, list):
                pos_src = str(p[0])
                break
    if pos_src and pos_src in api:
        api[pos_src]["inputs"]["text"] = PROMPT
    for v in api.values():
        if v["class_type"] in ("SaveImage", "SaveImageAdvanced") and "filename_prefix" in v["inputs"]:
            v["inputs"]["filename_prefix"] = prefix
    return api


def _env_snapshot():
    """记录解释器版本与 ComfyUI 版本（服务不可达时 comfy=None，不阻塞跑测）。"""
    ver = None
    try:
        with urllib.request.urlopen(COMFY + "/system_stats", timeout=5) as r:
            ver = (json.loads(r.read().decode()).get("system") or {}).get("comfyui_version")
    except Exception:
        pass
    return {"py": platform.python_version(), "comfy": ver}


def _ksampler_params(api):
    """从扁平化结果读 KSampler 运行时 steps/cfg/seed；custom 链路读不到 → None。"""
    for v in api.values():
        if v.get("class_type") == "KSampler":
            inp = v.get("inputs", {})
            return {"steps": inp.get("steps"), "cfg": inp.get("cfg"), "seed": inp.get("seed")}
    return {"steps": None, "cfg": None, "seed": None}


def main():
    global PROMPT
    src = json.load(open(os.path.join(WF, "Qwen_image_2_1_t2i.json"), encoding="utf-8"))
    c = [n for n in src["nodes"] if isinstance(n.get("type"), str) and "-" in n["type"] and len(n["type"]) > 30][0]
    PROMPT = c["widgets_values_named"]["prompt"]
    print("统一提示词 %d 字符 / 种子 %s\n" % (len(PROMPT), FIXED_SEED))

    migrate_legacy(LOG_JSON, LOG_JSONL, key=lambda r: (r.get("model"), r.get("combo")))
    env = _env_snapshot()
    n_fail = 0
    tasks = [(l, f, "ks", combos) for l, f, _, combos in PLAN] + \
            [(l, f, "custom", combos) for l, f, combos in PLAN_CUSTOM]
    only = os.environ.get("ONLY")
    if only:
        tasks = [t for t in tasks if t[0] == only]
    for label, fname, kind, combos in tasks:
        for cname, ov in combos:
            prefix = f"mt/{label}__{cname}"
            before = set(collect(prefix))
            t0 = time.time()
            print(f"[{label}] {cname} ...", flush=True)
            try:
                ov = {"KSampler": ov} if kind == "ks" else ov
                api = run_one(label, os.path.join(WF, fname), ov, prefix)
            except Exception as e:
                print("   扁平化失败:", e, flush=True)
                n_fail += 1  # 本次跑测的失败计数（退出码用，不读合并视图——它含历史批次）
                append_record(LOG_JSONL, {"model": label, "combo": cname, "ok": False, "error": "flatten: %s" % e,
                            "sec": 0, "files": [], "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "seed": FIXED_SEED, "steps": None, "cfg": None,
                            "py": env["py"], "comfy": env["comfy"]})
                rebuild_consolidated(LOG_JSON, LOG_JSONL, key=lambda r: (r.get("model"), r.get("combo")))
                continue
            p = _ksampler_params(api)
            # ModelSamplingAuraFlow 的 shift 在部分工作流未序列化（UI 条件隐藏），API required——补默认 1.73（2026-10-15）
            for _nd in api.values():
                if _nd.get("class_type") == "ModelSamplingAuraFlow" and "shift" not in _nd.get("inputs", {}):
                    _nd["inputs"]["shift"] = 1.73
            res, err = post("/prompt", {"prompt": api})
            if err:
                print("   提交失败:", err[:400], flush=True)
                n_fail += 1
                append_record(LOG_JSONL, {"model": label, "combo": cname, "ok": False, "error": err[:600],
                            "sec": 0, "files": [], "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
                            "py": env["py"], "comfy": env["comfy"]})
                rebuild_consolidated(LOG_JSON, LOG_JSONL, key=lambda r: (r.get("model"), r.get("combo")))
                continue
            ok, outs, werr = wait(res["prompt_id"])
            dt = round(time.time() - t0, 1)
            files = [f for f in collect(prefix) if f not in before] or collect(prefix)
            dest = []
            for f in files:
                d = os.path.join(OUT, f"{label}__{cname}__{os.path.basename(f)}")
                shutil.copy2(f, d); dest.append(os.path.basename(d))
            print(f"   -> {'OK' if ok else 'FAIL'} {dt}s  {len(dest)} 张", flush=True)
            if not ok:
                print("   ", str(werr)[:300], flush=True)
            if not (ok and dest):
                n_fail += 1
            append_record(LOG_JSONL, {"model": label, "combo": cname, "prompt_id": res["prompt_id"], "ok": bool(ok) and bool(dest),
                        "sec": dt, "files": dest, "error": None if ok else str(werr)[:600],
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
                        "py": env["py"], "comfy": env["comfy"]})
            rebuild_consolidated(LOG_JSON, LOG_JSONL, key=lambda r: (r.get("model"), r.get("combo")))
    cons = rebuild_consolidated(LOG_JSON, LOG_JSONL, key=lambda r: (r.get("model"), r.get("combo")))
    print("\n完成：成功 %d / %d" % (sum(1 for x in cons if x["ok"]), len(cons)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
