# -*- coding: utf-8 -*-
"""
ComfyUI 实验与改造工具箱 · Web 面板（参数轨）
纯标准库实现（http.server），零第三方依赖 —— 必须用 ComfyUI 自带 python 运行
（因为 σ 计算要 import comfy.*，结果分析要 numpy/Pillow，只有它这套环境齐）。

启动：
    cd "%USERPROFILE%/Desktop/ComfyUI-实验与改造工具箱/09_Web面板"
    %USERPROFILE%/APP/ComfyUI-aki-v3/python/python.exe panel.py
浏览器打开 http://127.0.0.1:8189

页面（全部复用工具箱 01~04 的脚本逻辑）：
  ① 工作流真值 —— flatten.py 读运行时参数（positional 容器值为准）
  ② σ 风险矩阵 —— sigma_matrix.py 离线计算，不跑图
  ③ 受控跑测   —— flatten + /prompt 提交，固定提示词与种子
  ④ 结果分析   —— metrics.py 指标 + 拼版 + 相似度
"""
import json, os, re, sys, time, threading, shutil, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------- 路径配置（复用到别处时改这里） ----------------
PANEL_DIR   = os.path.dirname(os.path.abspath(__file__))
TOOLBOX     = os.path.dirname(PANEL_DIR)
sys.path.insert(0, os.path.join(TOOLBOX, "01_工作流扁平化"))
import flatten as flatten_mod          # noqa: E402

COMFY_ROOT = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI"
COMFY_URL  = "http://127.0.0.1:8188"
WF_DIR     = os.path.join(COMFY_ROOT, "user", "default", "workflows", "Image")
CF_OUT     = os.path.join(COMFY_ROOT, "output")
OUT_ROOT   = os.path.join(PANEL_DIR, "output")
PORT       = 8189

DEFAULT_SEED = 1111119
FALLBACK_SAMPLERS = ["euler", "euler_ancestral", "euler_cfg_pp", "heun", "dpmpp_2m", "dpmpp_2m_sde_gpu",
                     "dpmpp_3m_sde_gpu", "dpmpp_2s_ancestral", "res_multistep", "res_multistep_ancestral",
                     "uni_pc", "uni_pc_bh2", "er_sde", "lcm", "ddim"]
FALLBACK_SCHEDS = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform",
                   "beta", "linear_quadratic", "kl_optimal"]

os.makedirs(OUT_ROOT, exist_ok=True)
PRINT_LOCK = threading.Lock()


def log(*a):
    with PRINT_LOCK:
        print(time.strftime("[%H:%M:%S]"), *a, flush=True)


# 本机面板 → ComfyUI 全部走 127.0.0.1，强制绕过系统代理（HTTP_PROXY 等环境变量会劫持 localhost）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(url, payload=None, timeout=20, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            return None, e.read().decode()
        except Exception:
            return None, str(e)
    except Exception as e:
        return None, str(e)


def comfy_status():
    st, err = http_json(COMFY_URL + "/system_stats", timeout=3)
    return {"running": st is not None, "stats": st, "error": None if st is not None else (err or "未启动")}


def comfy_lists():
    """从 /object_info/KSampler 拿采样器/调度器合法值全集；服务未启动则用回退表。"""
    d, err = http_json(COMFY_URL + "/object_info/KSampler", timeout=5)
    if d and "KSampler" in d:
        req = d["KSampler"]["input"].get("required", {})
        try:
            return {"samplers": list(req["sampler_name"][0]), "schedulers": list(req["scheduler"][0]),
                    "source": "object_info"}
        except Exception:
            pass
    return {"samplers": FALLBACK_SAMPLERS, "schedulers": FALLBACK_SCHEDS, "source": "fallback"}


# ---------------- ① 工作流真值（复用 flatten.py） ----------------
VALUE_KEYS = {
    "KSampler": ["sampler_name", "scheduler", "steps", "cfg", "seed", "denoise"],
    "KSamplerAdvanced": ["sampler_name", "scheduler", "steps", "cfg", "seed", "denoise", "add_noise"],
    "KSamplerSelect": ["sampler_name"],
    "BasicScheduler": ["scheduler", "steps"],
    "Flux2Scheduler": ["steps"],
    "FluxGuidance": ["guidance"],
    "UNETLoader": ["unet_name"],
    "CLIPLoader": ["clip_name"],
    "DualCLIPLoader": ["clip_name"],
    "VAELoader": ["vae_name"],
}
PROMPT_SOURCE_CLASSES = ("KSampler", "KSamplerAdvanced", "CFGGuider", "BasicGuider")


def read_workflow_truth(path):
    try:
        api, _ = flatten_mod.flatten(path)
    except Exception as e:
        return {"file": os.path.basename(path), "error": "扁平化失败: %s" % e}
    vals, route, sampler_node = {}, "custom", None
    for k, nd in api.items():
        ct = nd["class_type"]
        for key in VALUE_KEYS.get(ct, []):
            if key in nd["inputs"] and not isinstance(nd["inputs"][key], list):
                vals.setdefault(key, nd["inputs"][key])
        if ct in ("KSampler", "KSamplerAdvanced"):
            route, sampler_node = "ksampler", (k, nd)
    positive_src = None
    for k, nd in api.items():
        if nd["class_type"] in PROMPT_SOURCE_CLASSES and isinstance(nd["inputs"].get("positive"), list):
            positive_src = str(nd["inputs"]["positive"][0])
            break
    prompt_text = None
    if positive_src and positive_src in api and isinstance(api[positive_src]["inputs"].get("text"), str):
        prompt_text = api[positive_src]["inputs"]["text"]
    return {"file": os.path.basename(path), "route": route, "values": vals,
            "prompt_chars": len(prompt_text) if prompt_text else 0}


def list_workflows():
    rows = []
    if not os.path.isdir(WF_DIR):
        return {"wf_dir": WF_DIR, "exists": False, "rows": rows}
    for f in sorted(os.listdir(WF_DIR)):
        if f.lower().endswith(".json") and ".bak" not in f:
            rows.append(read_workflow_truth(os.path.join(WF_DIR, f)))
    return {"wf_dir": WF_DIR, "exists": True, "rows": rows}


def read_default_prompt():
    """从 2.1 工作流容器读上次统一的 818 字符提示词，作为面板默认值。"""
    src = os.path.join(WF_DIR, "Qwen_image_2_1_t2i.json")
    try:
        w = json.load(open(src, encoding="utf-8"))
        c = [n for n in w["nodes"] if isinstance(n.get("type"), str) and "-" in n["type"] and len(n["type"]) > 30][0]
        return c["widgets_values_named"].get("prompt", "")
    except Exception:
        return ""


# ---------------- ② σ 风险矩阵（复用 sigma_matrix.py，懒加载缓存） ----------------
SIGMA = {"status": "idle", "data": None, "error": None}
SIGMA_LOCK = threading.Lock()


def _compute_sigma():
    SIGMA["status"], SIGMA["error"] = "computing", None
    try:
        sys.path.insert(0, COMFY_ROOT)
        sys.path.insert(0, os.path.join(TOOLBOX, "02_调度器sigma分析"))
        import comfy.samplers as S                       # noqa: E402
        import sigma_matrix as SM                        # noqa: E402
        out = {}
        for name, cls_name, mtype, steps, official in SM.MODELS:
            ms, _ = SM.build_ms(cls_name, mtype)
            scheds = {}
            for sc in S.SCHEDULER_NAMES:
                sig = S.calculate_sigmas(ms, sc, steps)
                m = SM.metrics(sig, steps)
                scheds[sc] = {"first_d_pct": round(m["first_d_pct"], 2), "hi_steps": m["hi_steps"],
                              "lo_steps": m["lo_steps"], "last_sigma": round(m["last_sigma"], 6),
                              "risk": SM.verdict(m, steps)}
            out[name] = {"steps": steps, "official": official, "scheds": scheds}
        SIGMA["data"], SIGMA["status"] = out, "ready"
        log("σ 风险矩阵计算完成（%d 个模型）" % len(out))
    except Exception as e:
        SIGMA["status"], SIGMA["error"] = "error", "%s: %s" % (type(e).__name__, e)
        log("σ 计算失败:", SIGMA["error"])


def sigma_route():
    with SIGMA_LOCK:
        if SIGMA["status"] == "idle":
            threading.Thread(target=_compute_sigma, daemon=True).start()
    if SIGMA["status"] == "computing":
        return 202, {"status": "computing"}
    if SIGMA["status"] == "error":
        return 500, {"status": "error", "error": SIGMA["error"]}
    return 200, {"status": "ready", "models": SIGMA["data"]}


# ---------------- ③ 受控跑测（复用 flatten.py + /prompt） ----------------
DROP_TYPES = {"TextGenerate", "PrimitiveStringMultiline", "PreviewAny", "PrimitiveBoolean"}
DROP_ALWAYS = {"BatchPromptReaderWithClip"}


def prune_llm(api):
    for k in [k for k, v in api.items() if v["class_type"] == "ComfySwitchNode"]:
        cands = [x for x in api[k]["inputs"].values()
                 if isinstance(x, list) and str(x[0]) in api
                 and api[str(x[0])]["class_type"] not in (DROP_TYPES | DROP_ALWAYS)]
        if cands:
            rep = list(cands[0])
            for v2 in api.values():
                for kk, vv in list(v2["inputs"].items()):
                    if isinstance(vv, list) and str(vv[0]) == k:
                        v2["inputs"][kk] = list(rep)
        api.pop(k, None)
    for k in [k for k, v in api.items() if v["class_type"] in DROP_TYPES]:
        api.pop(k, None)
    for v in api.values():
        for kk, vv in list(v["inputs"].items()):
            if isinstance(vv, list) and str(vv[0]) not in api:
                v["inputs"].pop(kk)
    return api


def replace_batch_reader(api):
    """把 BatchPromptReaderWithClip 换成等语义的空提示词 CLIPTextEncode（控制变量要求）。"""
    for k in [k for k, v in api.items() if v["class_type"] in DROP_ALWAYS]:
        clip_link = None
        for vv in api[k]["inputs"].values():
            if isinstance(vv, list) and str(vv[0]) in api:
                src_ct = api[str(vv[0])]["class_type"]
                if src_ct == "DualCLIPLoader" or clip_link is None:
                    clip_link = list(vv)
                if src_ct == "DualCLIPLoader":
                    break
        newk, rep = "gen_neg_" + k, None
        if clip_link:
            api[newk] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip_link, "text": ""},
                         "_meta": {"title": "Web面板生成的空提示词编码"}}
            rep = [newk, 0]
        for v2 in api.values():
            for kk, vv in list(v2["inputs"].items()):
                if isinstance(vv, list) and str(vv[0]) == k:
                    if rep:
                        v2["inputs"][kk] = list(rep)
                    else:
                        v2["inputs"].pop(kk)
        api.pop(k, None)
    for v in api.values():
        for kk, vv in list(v["inputs"].items()):
            if isinstance(vv, list) and str(vv[0]) not in api:
                v["inputs"].pop(kk)
    return api


def build_api(wf_path, combo, prompt, seed):
    """扁平化 + 按组合后处理（post-flatten 直接改 api，避开 overrides 机制）。"""
    api, _ = flatten_mod.flatten(wf_path)
    if any(v["class_type"] == "TextGenerate" for v in api.values()):
        api = prune_llm(api)
    if any(v["class_type"] in DROP_ALWAYS for v in api.values()):
        api = replace_batch_reader(api)
    ov = {k: v for k, v in combo.items() if k != "name" and v not in (None, "")}
    touched = []
    for k, nd in api.items():
        ct = nd["class_type"]
        if ct in ("KSampler", "KSamplerAdvanced"):
            for pk in ("sampler_name", "scheduler", "steps", "cfg", "seed"):
                if pk in ov and pk in nd["inputs"]:
                    if pk in ("seed", "steps"):
                        nd["inputs"][pk] = int(ov[pk])
                    elif pk == "cfg":
                        nd["inputs"][pk] = float(ov[pk])
                    else:
                        nd["inputs"][pk] = ov[pk]
                    touched.append(pk)
        elif ct == "KSamplerSelect" and "sampler_name" in ov and "sampler_name" in nd["inputs"]:
            nd["inputs"]["sampler_name"] = ov["sampler_name"]; touched.append("sampler_name")
        elif ct == "BasicScheduler":
            if "scheduler" in ov and "scheduler" in nd["inputs"]:
                nd["inputs"]["scheduler"] = ov["scheduler"]; touched.append("scheduler")
            if "steps" in ov and "steps" in nd["inputs"]:
                nd["inputs"]["steps"] = int(ov["steps"]); touched.append("steps")
        elif ct == "FluxGuidance" and "cfg" in ov and "guidance" in nd["inputs"]:
            nd["inputs"]["guidance"] = float(ov["cfg"]); touched.append("guidance(cfg)")
        elif ct == "Flux2Scheduler" and "steps" in ov and "steps" in nd["inputs"]:
            nd["inputs"]["steps"] = int(ov["steps"]); touched.append("steps")
        if "seed" in ov and ct in ("KSampler", "KSamplerAdvanced") and "seed" in nd["inputs"]:
            nd["inputs"]["seed"] = int(ov["seed"])
    pos_src = None
    for v in api.values():
        if v["class_type"] in PROMPT_SOURCE_CLASSES and isinstance(v["inputs"].get("positive"), list):
            pos_src = str(v["inputs"]["positive"][0]); break
    if pos_src and pos_src in api and isinstance(api[pos_src]["inputs"].get("text"), str):
        api[pos_src]["inputs"]["text"] = prompt
    else:
        raise RuntimeError("未找到正向提示词注入点")
    return api, sorted(set(touched))


def collect(prefix):
    d = os.path.join(CF_OUT, os.path.dirname(prefix))
    b = os.path.basename(prefix)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(b) and f.lower().endswith(".png"))


JOB = {"status": "idle", "log": [], "done": 0, "total": 0, "started": None, "finished": None, "out_subdir": None}
JOB_LOCK = threading.Lock()


def _runner(tasks, prompt, seed, out_subdir):
    outdir = os.path.join(OUT_ROOT, out_subdir)
    os.makedirs(outdir, exist_ok=True)
    ok = fail = 0
    for label, wf_file, cname, combo in tasks:
        prefix = "%s/%s__%s" % (out_subdir, label, cname)
        JOB["log"].append({"label": label, "combo": cname, "status": "running", "msg": ""})
        idx = len(JOB["log"]) - 1
        try:
            api, touched = build_api(os.path.join(WF_DIR, wf_file), combo, prompt, seed)
            for v in api.values():
                if v["class_type"] in ("SaveImage", "SaveImageAdvanced") and "filename_prefix" in v["inputs"]:
                    v["inputs"]["filename_prefix"] = prefix
            before = set(collect(prefix))
            res, err = http_json(COMFY_URL + "/prompt", {"prompt": api}, timeout=90)
            if err:
                raise RuntimeError("提交失败: %s" % err[:400])
            t0 = time.time()
            while time.time() - t0 < 1800:
                h, _ = http_json(COMFY_URL + "/history/" + res["prompt_id"], timeout=15)
                if h and res["prompt_id"] in h:
                    st = h[res["prompt_id"]].get("status", {})
                    if st.get("completed"):
                        break
                    if st.get("status_str") == "error":
                        msgs = [x for x in st.get("messages", []) if x[0] in ("execution_error", "execution_interrupted")]
                        raise RuntimeError(json.dumps(msgs, ensure_ascii=False)[:500])
                time.sleep(3)
            else:
                raise RuntimeError("等待超时(1800s)")
            dt = round(time.time() - t0, 1)
            files = [f for f in collect(prefix) if f not in before] or collect(prefix)
            dest = []
            for f in files:
                d2 = os.path.join(outdir, "%s__%s__%s" % (label, cname, os.path.basename(f)))
                shutil.copy2(f, d2); dest.append(os.path.basename(d2))
            if not dest:
                raise RuntimeError("完成但未收集到输出图")
            ok += 1
            JOB["log"][idx] = {"label": label, "combo": cname, "status": "ok", "msg": "%.1fs, %d 张" % (dt, len(dest))}
        except Exception as e:
            fail += 1
            JOB["log"][idx] = {"label": label, "combo": cname, "status": "error", "msg": str(e)[:400]}
        JOB["done"] += 1
    JOB["status"], JOB["finished"] = "done", time.strftime("%H:%M:%S")
    JOB["log"].append({"label": "_summary", "combo": "", "status": "done",
                       "msg": "成功 %d / 失败 %d，产物在 output/%s/" % (ok, fail, out_subdir)})
    log("跑测结束：成功 %d / 失败 %d" % (ok, fail))


def start_run(body):
    with JOB_LOCK:
        if JOB["status"] == "running":
            return 409, {"error": "已有跑测在进行中"}
        wfs = body.get("workflows") or []
        combos = body.get("combos") or []
        # 键名归一化：容忍前端旧键 sampler → sampler_name
        for c in combos:
            if isinstance(c, dict) and "sampler_name" not in c and c.get("sampler"):
                c["sampler_name"] = c.pop("sampler")
        prompt = (body.get("prompt") or "").strip()
        seed = int(body.get("seed") or DEFAULT_SEED)
        out_subdir = re.sub(r"[^\w\-]+", "_", body.get("out_subdir") or "web_test")
        if not wfs or not combos or not prompt:
            return 400, {"error": "workflows / combos / prompt 均不能为空"}
        # 合法值校验（仅当能从 ComfyUI 拿到权威列表时才校验，避免回退表误杀）
        lists = comfy_lists()
        if lists["source"] == "object_info":
            bad = []
            for c in combos:
                cn = c.get("name") or "?"
                if c.get("sampler_name") and c["sampler_name"] not in lists["samplers"]:
                    bad.append("组合 %r: 采样器 %r 非法" % (cn, c["sampler_name"]))
                if c.get("scheduler") and c["scheduler"] not in lists["schedulers"]:
                    bad.append("组合 %r: 调度器 %r 非法" % (cn, c["scheduler"]))
                for pk in ("steps", "cfg"):
                    v = c.get(pk)
                    if v not in (None, ""):
                        try:
                            (int(v) if pk == "steps" else float(v))
                        except (TypeError, ValueError):
                            bad.append("组合 %r: %s=%r 不是数字" % (cn, pk, v))
            if bad:
                return 400, {"error": "参数校验失败（合法值见面板下拉框）：" + "；".join(bad)}
        tasks = []
        for wf in wfs:
            label = re.sub(r"\.json$", "", os.path.basename(wf))
            for c in combos:
                cname = re.sub(r"[^\w\-]+", "_", c.get("name") or "combo")
                tasks.append((label, os.path.basename(wf), cname, dict(c)))
        JOB.update({"status": "running", "log": [], "done": 0, "total": len(tasks),
                    "started": time.strftime("%H:%M:%S"), "finished": None, "out_subdir": out_subdir})
        threading.Thread(target=_runner, args=(tasks, prompt, seed, out_subdir), daemon=True).start()
        log("跑测启动：%d 个任务 → output/%s/" % (len(tasks), out_subdir))
        return 200, {"ok": True, "total": len(tasks), "out_subdir": out_subdir}


# ---------------- ④ 结果分析（复用 metrics.py 口径） ----------------
def _metrics(a):  # a: float ndarray RGB
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view
    g = a.mean(axis=2)
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    w = sliding_window_view(g, (3, 3))
    lap = float((w * k).sum(axis=(-1, -2)).var())
    r, gg, b = a[..., 0], a[..., 1], a[..., 2]
    rg, yb = np.abs(r - gg), np.abs(0.5 * (r + gg) - b)
    colorful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    return {"brightness": round(float(g.mean()), 1), "contrast_std": round(float(g.std()), 2),
            "sharpness_lapvar": round(lap, 1), "colorfulness": round(colorful, 2)}


def analyze(subdir):
    from PIL import Image
    d = os.path.join(OUT_ROOT, re.sub(r"[^\w\-]+", "_", subdir or "web_test"))
    if not os.path.isdir(d):
        return 404, {"error": "目录不存在: %s" % d}
    groups = {}
    for f in sorted(g for g in os.listdir(d) if g.lower().endswith(".png")):
        parts = f.split("__")
        if len(parts) < 3:
            continue
        key = (parts[0], parts[1])
        p = os.path.join(d, f)
        groups.setdefault(key, []).append((os.path.getmtime(p), p))
    rows = []
    for (wf, combo), lst in sorted(groups.items()):
        lst.sort()
        rows.append({"wf": wf, "combo": combo, "path": lst[-1][1], "n_files": len(lst)})
    baselines = {}
    for r in rows:
        baselines.setdefault(r["wf"], []).append(r["combo"])
    # 基线：优先 base 组合，否则字母序第一个
    small, big = 128, 128
    def gray128(p):
        im = Image.open(p).convert("L").resize((small, big))
        return list(im.getdata())
    out_rows = []
    for r in rows:
        base_combo = "base" if "base" in baselines[r["wf"]] else sorted(baselines[r["wf"]])[0]
        im = Image.open(r["path"]).convert("RGB")
        row = {"wf": r["wf"], "combo": r["combo"], "path": r["path"], "size": "%dx%d" % im.size,
               "n_files": r["n_files"], "is_baseline": r["combo"] == base_combo}
        row.update(_metrics(__import__("numpy").asarray(im).astype("float32")))
        if r["combo"] != base_combo:
            bp = next(x["path"] for x in rows if x["wf"] == r["wf"] and x["combo"] == base_combo)
            a, b = gray128(r["path"]), gray128(bp)
            mse = sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)
            row["similarity"] = round(1 - mse / (255 * 255), 4)
        else:
            row["similarity"] = 1.0
        out_rows.append(row)
    # 拼版（4 列带标签）
    try:
        from PIL import ImageDraw, ImageFont
        thumbs = []
        for r in out_rows:
            im = Image.open(r["path"]).convert("RGB"); im.thumbnail((340, 340))
            thumbs.append(("%s__%s" % (r["wf"], r["combo"]), im))
        cols, cw, ch, pad, cap = 4, 350, 380, 10, 26
        rn = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (cw + pad) + pad, max(1, rn) * (ch + pad) + pad), (255, 255, 255))
        dr = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        except Exception:
            font = ImageFont.load_default()
        for i, (name, t) in enumerate(thumbs):
            cx, cy = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + pad)
            dr.text((cx + 4, cy + 2), name[:34], fill=(0, 0, 0), font=font)
            sheet.paste(t, (cx + (cw - t.width) // 2, cy + cap))
        mp = os.path.join(d, "_montage.png"); sheet.save(mp)
        montage = "/api/image?subdir=%s&name=_montage.png" % os.path.basename(d)
    except Exception as e:
        montage = None
        log("拼版失败:", e)
    return 200, {"rows": out_rows, "montage": montage, "dir": d}


# ---------------- HTTP 服务 ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _img(self, subdir, name):
        root = os.path.realpath(OUT_ROOT)
        p = os.path.realpath(os.path.join(OUT_ROOT, subdir, name))
        if not p.startswith(root) or not os.path.isfile(p):
            return self._send(404, {"error": "图片不存在"})
        ext = os.path.splitext(p)[1].lower()
        ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
        with open(p, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        path, _, qs = self.path.partition("?")
        q = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
        try:
            if path == "/" or path == "/index.html":
                with open(os.path.join(PANEL_DIR, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if path == "/api/health":
                return self._send(200, {"ok": True, "toolbox": TOOLBOX, "wf_dir": WF_DIR,
                                        "out_root": OUT_ROOT, "comfy": comfy_status()})
            if path == "/api/workflows":
                return self._send(200, list_workflows())
            if path == "/api/default_prompt":
                return self._send(200, {"prompt": read_default_prompt(), "seed": DEFAULT_SEED})
            if path == "/api/sigma":
                code, data = sigma_route()
                return self._send(code, data)
            if path == "/api/comfy_lists":
                return self._send(200, comfy_lists())
            if path == "/api/run_status":
                return self._send(200, {k: JOB[k] for k in ("status", "log", "done", "total", "started", "finished", "out_subdir")})
            if path == "/api/image" and "subdir" in q and "name" in q:
                return self._img(q["subdir"], q["name"])
            return self._send(404, {"error": "no route: " + path})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode()) if n else {}
            if self.path == "/api/run":
                code, data = start_run(body)
                return self._send(code, data)
            if self.path == "/api/analyze":
                code, data = analyze(body.get("subdir") or "")
                return self._send(code, data)
            return self._send(404, {"error": "no route"})
        except Exception as e:
            return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log("Web 面板启动 → http://127.0.0.1:%d  （Ctrl+C 停止）" % PORT)
    log("工具箱根目录:", TOOLBOX)
    log("工作流目录:", WF_DIR)
    log("产物目录:", OUT_ROOT)
    srv.serve_forever()
