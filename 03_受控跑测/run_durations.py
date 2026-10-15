# -*- coding: utf-8 -*-
"""
通用视频时长档位跑测器（E4 · 2026-10-16）
==========================================

把 `run_h3_durations.py` 里 MiniMax H3 特有的硬编码（帧数换算 / 档位矩阵 /
节点 ID / 隐藏参数补缺）抽成**适配器配置**，跑测器本体与模型无关：

  新增一个视频模型 = 在 adapters.json 加一条，本文件零改动。

适配器字段（见 adapters.json）：
  label / workflow / fps
  frames_rule  帧数换算：{"type":"grid","k":17,"offset":5,"min":5}
               base = max(min, round(sec*fps)); frames = base + (offset - base%k)%k
               17k+5@24fps（H3）与 8k+1@16fps 这类网格都能用它表达
  nodes        {"i2v": <时长节点ID>, "clip": <CLIPLoader ID>, "unet": <UNETLoader ID>}
  defaults     {"te": ..., "dit": ...}  可选，覆盖工作流里已失效的默认模型
  combos       [{"tag","duration","width","height","note"}, ...]
  fill_hidden  [{"class_type": "...", "inputs": {...}}]  UI 条件隐藏但 API required 的参数
  prompt_fallback  {"node_type": "...", "widget": "prompt"}  容器空 prompt 时回退子图原值
  log_dir      日志子目录名（默认 duration_logs/<adapter>）

E2 的显存自适应（lib_vram）在此复用：起始档按预算推荐，OOM 自动降档重跑。

用法（建议经 run.py dur 调用）：
  python run_durations.py --list
  python run_durations.py --adapter minimax_h3_t2v --dry-run
  python run_durations.py --adapter minimax_h3_t2v --only 8s_1344x768 [--te X] [--dit Y]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "01_工作流扁平化"))
from flatten import flatten  # noqa: E402
from logutil import append_record, rebuild_consolidated  # noqa: E402
import lib_vram  # noqa: E402

COMFY = "http://127.0.0.1:8188"
ADAPTERS_JSON = os.path.join(_HERE, "adapters.json")

# loader 类节点的文件输入（ComfyUI 0.39+ 候选值是相对 models/ 的路径）
LOADER_INPUTS = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name",
                 "VAELoader": "vae_name", "LoraLoaderModelOnly": "lora_name"}


# ---------------- 适配器 ----------------
def load_adapters(path=None):
    """读 adapters.json；跳过 `_` 开头的说明键（它们的值是字符串，不是适配器）。"""
    with open(path or ADAPTERS_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.items()
            if not k.startswith("_") and isinstance(v, dict)}


def frames_for(adapter, seconds):
    """时长(秒) → 帧数，按适配器的换算规则。"""
    rule = adapter.get("frames_rule") or {}
    fps = float(adapter.get("fps") or 24)
    if rule.get("type") == "grid":
        k = int(rule.get("k") or 1)
        off = int(rule.get("offset") or 0)
        lo = int(rule.get("min") or 1)
        base = max(lo, int(round(seconds * fps)))
        f = base + (off - base % k) % k
    else:                                   # 无规则：直接按 fps 取整
        f = max(1, int(round(seconds * fps)))
    hi = rule.get("max")
    return min(f, int(hi)) if hi else f


def log_paths(adapter, name=None):
    sub = adapter.get("log_dir") or os.path.join("duration_logs", name or "adapter")
    d = os.path.join(_HERE, sub)
    return d, os.path.join(d, "result_log.jsonl"), os.path.join(d, "result_log.json")


# ---------------- payload 构造 ----------------
def _subgraph_widget(workflow, node_type, widget):
    """取子图内某类型节点的 widget 原值（容器 widget 为空时前端不覆盖内部链路值）。"""
    try:
        wf = json.load(open(workflow, encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None
    for sg in wf.get("definitions", {}).get("subgraphs", []):
        for n in sg.get("nodes", []):
            if n.get("type") == node_type:
                named = (n.get("widgets_values_named") or {}).get(widget)
                if named:
                    return named
                vals = n.get("widgets_values") or []
                return vals[0] if vals else None
    return None


def build_api(adapter, workflow, combo, te=None, dit=None):
    """flatten 工作流并按档位覆盖 length/width/height（可选覆盖 TE/DiT）。"""
    tag, dur, w, h, _note = combo
    nodes = adapter.get("nodes") or {}
    frames = frames_for(adapter, dur)
    overrides = {}
    if nodes.get("i2v") is not None:
        overrides[nodes["i2v"]] = {"length": frames, "width": w, "height": h}
    pf = adapter.get("prompt_fallback")
    if pf and nodes.get("i2v") is not None:
        widget = pf.get("widget", "prompt")
        inner = _subgraph_widget(workflow, pf.get("node_type"), widget)
        if inner:
            overrides[nodes["i2v"]][widget] = inner
    te = te or (adapter.get("defaults") or {}).get("te")
    dit = dit or (adapter.get("defaults") or {}).get("dit")
    if te and nodes.get("clip") is not None:
        overrides[nodes["clip"]] = {"clip_name": te}
    if dit and nodes.get("unet") is not None:
        overrides[nodes["unet"]] = {"unet_name": dit}
    api, applied = flatten(workflow, overrides)
    return api, applied, frames


def fill_hidden_inputs(api, adapter):
    """补齐「UI 条件隐藏但 API required」的参数（flatten 的 overrides 补不进已有输入之外的键）。"""
    filled = []
    specs = adapter.get("fill_hidden") or []
    for k, nd in api.items():
        for spec in specs:
            if nd["class_type"] == spec.get("class_type"):
                for pk, pv in (spec.get("inputs") or {}).items():
                    if pk not in nd["inputs"]:
                        nd["inputs"][pk] = pv
                        filled.append((k, pk, pv))
    return filled


def normalize_loader_names(api):
    """扁平文件名 → ComfyUI 0.39+ 的相对 models/ 路径；缺的报给调用方拒绝提交。"""
    flat2full = {}
    for ct, key in LOADER_INPUTS.items():
        try:
            info = post("%s/object_info/%s" % (COMFY, ct))
            for v in info[ct]["input"]["required"][key][0]:
                base = str(v).replace("\\", "/").split("/")[-1]
                flat2full.setdefault(base, v)
        except Exception:                                    # noqa: BLE001
            pass
    fixed, missing = [], []
    for _k, nd in api.items():
        key = LOADER_INPUTS.get(nd["class_type"])
        if not key:
            continue
        cur = nd["inputs"].get(key)
        if isinstance(cur, str) and "\\" not in cur and "/" not in cur:
            full = flat2full.get(cur)
            if full:
                nd["inputs"][key] = full
                fixed.append((nd["class_type"], cur, full))
            else:
                missing.append((nd["class_type"], cur))
    return fixed, missing


def post(url, obj=None, timeout=120):
    data = json.dumps(obj).encode() if obj is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ---------------- 单档位执行 ----------------
def run_combo(adapter, workflow, combo, te=None, dit=None, dry=False, vctx=None,
              log_jsonl=None):
    """跑一个档位；返回**总是 dict**（失败也要带 error/detail 供 OOM 判定）。"""
    tag, dur, w, h, note = combo
    if vctx and vctx.get("tier") is not None:
        w, h = lib_vram.tier_wh(vctx["tier"])
        combo = (tag, dur, w, h, note)
    frames = frames_for(adapter, dur)
    vram_field = dict(vctx) if vctx else None
    api, applied, _ = build_api(adapter, workflow, combo, te, dit)
    print(f"[{tag}] {dur}s -> {frames}帧 | {w}x{h} | {note}")
    if applied:
        print("   overrides 应用 %d 项: %s" % (
            len(applied), "; ".join("%s#%s.%s: %r->%r" % a for a in applied)))
    if dry:
        print(f"   [dry-run] payload 节点数={len(api)}，未提交")
        return {"tag": tag, "duration": dur, "frames": frames, "width": w, "height": h,
                "ok": False, "error": "dry_run", "vram": vram_field}

    for k, pk, pv in fill_hidden_inputs(api, adapter):
        print(f"   [补缺] 节点{k} {pk}={pv}")
    fixed, missing = normalize_loader_names(api)
    for ct, old, new in fixed:
        print(f"   [规范化] {ct}: {old} -> {new}")
    if missing:
        print("   [ERROR] 以下模型文件在 ComfyUI 候选列表中不存在（已删/改名？），拒绝提交：")
        for ct, cur in missing:
            print(f"     {ct}: {cur!r}")
        rec = {"tag": tag, "duration": dur, "frames": frames, "width": w, "height": h,
               "ok": False, "error": "loader_missing", "detail": missing, "vram": vram_field}
        append_record(log_jsonl, rec)
        return rec

    t0 = time.time()
    try:
        resp = post(f"{COMFY}/prompt", {"prompt": api, "client_id": "durations"})
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"   提交失败 HTTP {e.code}: {body}")
        rec = {"tag": tag, "duration": dur, "frames": frames, "width": w, "height": h,
               "ok": False, "error": f"http_{e.code}", "detail": body, "vram": vram_field}
        append_record(log_jsonl, rec)
        return rec
    pid = resp.get("prompt_id")
    print(f"   prompt_id={pid} 等待执行...")
    last = -1
    while True:
        time.sleep(10)
        try:
            hist = post(f"{COMFY}/history/{pid}")
        except Exception:                                    # noqa: BLE001
            continue
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        outs = []
        for _nid, o in (entry.get("outputs") or {}).items():
            for key in ("videos", "gifs", "images"):
                for f in (o.get(key) or []):
                    outs.append(f.get("filename"))
        if status.get("completed") or outs:
            el = time.time() - t0
            rec = {"tag": tag, "duration": dur, "frames": frames, "width": w, "height": h,
                   "ok": True, "elapsed_sec": round(el, 1), "prompt_id": pid,
                   "outputs": outs, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "interpreter": sys.version.split()[0], "vram": vram_field}
            print(f"   完成 {el/60:.1f} 分钟 | 输出: {outs}")
            append_record(log_jsonl, rec)
            return rec
        if status.get("status_str") == "error":
            err = ""
            for m in status.get("messages", []):
                if m and m[0] == "execution_error":
                    err = str(m[1].get("exception_message", ""))[:300]
            print(f"   执行错误: {err}")
            rec = {"tag": tag, "duration": dur, "frames": frames, "width": w, "height": h,
                   "ok": False, "error": "exec_error", "detail": err,
                   "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "vram": vram_field}
            append_record(log_jsonl, rec)
            return rec
        mm = int((time.time() - t0) // 60)
        if mm != last:
            last = mm
            print(f"   ...{mm}m{int((time.time()-t0) % 60)}s")


# ---------------- CLI ----------------
def _combos(adapter):
    return [(c["tag"], float(c["duration"]), int(c["width"]), int(c["height"]),
             c.get("note", "")) for c in adapter.get("combos", [])]


def main(adapter=None, name=None, argv=None):
    """adapter 由调用方注入（run_h3_durations 的薄壳用法）；为 None 时从 adapters.json 取。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if adapter is None:
        if "--list" in args:
            data = load_adapters()
            for k, v in data.items():
                print("%-18s %s  combos=%d  fps=%s"
                      % (k, v.get("label", ""), len(v.get("combos", [])), v.get("fps")))
            return 0
        want = None
        for i, a in enumerate(args):
            if a == "--adapter" and i + 1 < len(args):
                want = args[i + 1]
        data = load_adapters()
        if want is None:
            print("[ERROR] 用 --adapter <名字> 指定；可选: %s" % list(data))
            return 2
        if want not in data:
            print("[ERROR] 未知适配器 %r；可选: %s" % (want, list(data)))
            return 2
        adapter, name = data[want], want

    # --log-path：只打印日志路径就退出。给 09 面板用，避免面板复制一份路径规则
    # （面板在 09 轨，不能 import 03 轨的 run_durations —— Gate ⑥ 依赖方向）。
    if "--log-path" in args:
        _d, _jl, _ = log_paths(adapter, name)
        os.makedirs(_d, exist_ok=True)
        print(_jl)
        return 0

    workflow = os.path.expandvars(adapter.get("workflow") or "")
    te = dit = only = None
    dry = auto = False
    auto, budget_arg, start_override, max_dg = True, None, None, 2
    vram_mode = "calibrated"     # calibrated=按标定表选档；live=按实时可用显存选档
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry = True
        elif a == "--only" and i + 1 < len(args):
            only = args[i + 1]; i += 1
        elif a == "--workflow" and i + 1 < len(args):
            workflow = os.path.expandvars(args[i + 1]); i += 1
        elif a == "--te" and i + 1 < len(args):
            te = args[i + 1]; i += 1
        elif a == "--dit" and i + 1 < len(args):
            dit = args[i + 1]; i += 1
        elif a == "--no-auto-vram":
            auto = False
        elif a == "--vram-budget" and i + 1 < len(args):
            budget_arg = float(args[i + 1]); i += 1
        elif a == "--start-tier" and i + 1 < len(args):
            start_override = int(args[i + 1]); i += 1
        elif a == "--max-downgrade" and i + 1 < len(args):
            max_dg = int(args[i + 1]); i += 1
        elif a == "--vram-mode" and i + 1 < len(args):
            vram_mode = args[i + 1]; i += 1
        i += 1

    if not workflow or not os.path.exists(workflow):
        print(f"[ERROR] 工作流不存在: {workflow!r}（用 --workflow 指定）")
        return 2
    log_dir, log_jsonl, log_json = log_paths(adapter, name)
    os.makedirs(log_dir, exist_ok=True)

    print(f"适配器: {name} — {adapter.get('label', '')}")
    print(f"工作流: {workflow}")
    print(f"ComfyUI: {COMFY}  |  dry-run={dry}  |  log={log_jsonl}")

    budget_gib = None
    if auto and vram_mode == "live":
        snap = lib_vram.sniff()
        if snap.get("ok"):
            budget_gib = snap["free_gib"]
            print(f"显存快照: free {budget_gib} GiB"
                  f"（used {snap['used_mib']}MiB / total {snap['total_mib']}MiB）")
        else:
            print(f"[warn] 显存探测不可用（{snap.get('error')}）→ 起始档保守降一档")
        if budget_arg is not None:
            budget_gib = float(budget_arg)
    elif auto:
        print("显存自适应: calibrated（按 11.91GB 标定边界表选档，不受 ComfyUI 缓存占用影响；"
              "要按实时显存选档加 --vram-mode live）")

    combos = [c for c in _combos(adapter) if (only is None or c[0] == only)]
    if not combos:
        print(f"[ERROR] --only {only} 不在 combos；可选: {[c[0] for c in _combos(adapter)]}")
        return 2

    results = []
    for c in combos:
        if start_override is not None:
            tier = start_override
        elif vram_mode == "live":
            tier = lib_vram.start_tier(c[1], budget_gib)
        else:
            tier = lib_vram.base_tier(c[1])      # calibrated：按标定边界表，不看实时占用
        vram_mode_field = vram_mode
        vctx = {"auto": auto, "budget_gib": budget_gib, "start_tier": tier,
                "tier": tier, "downgrades": []}
        while True:
            r = run_combo(adapter, workflow, c, te, dit, dry, vctx if auto else None, log_jsonl)
            if dry or not auto:
                break
            if r and r.get("ok"):
                break
            detail = "%s %s" % ((r or {}).get("detail") or "", (r or {}).get("error") or "")
            if not lib_vram.is_oom(detail):
                break
            if len(vctx["downgrades"]) >= max_dg or vctx["tier"] >= len(lib_vram.LADDER) - 1:
                print("   [OOM] 已达降档上限/已到底档，放弃")
                break
            old, new = vctx["tier"], vctx["tier"] + 1
            ow, oh = lib_vram.tier_wh(old)
            nw, nh = lib_vram.tier_wh(new)
            print(f"   [OOM] 识别为显存不足 → {ow}x{oh} 降到 {nw}x{nh} 自动重跑")
            vctx["downgrades"].append({"from": f"{ow}x{oh}", "to": f"{nw}x{nh}", "reason": "oom"})
            vctx["tier"] = new
        results.append(r)

    ok = sum(1 for r in results if r and r.get("ok"))
    if dry:
        print(f"\n===== dry-run 计划: {len(combos)} 档（未提交） =====")
        for c in combos:
            print(f"  [PLAN] {c[0]:>14} {c[1]}s/{frames_for(adapter, c[1])}帧 {c[2]}x{c[3]}  {c[4]}")
        return 0
    print(f"\n===== 汇总: {ok}/{len(combos)} 成功 =====")
    for r in results:
        if r:
            mark = "OK " if r.get("ok") else "FAIL"
            dg = ((r.get("vram") or {}).get("downgrades") or [])
            tail = f" {r['elapsed_sec']/60:.1f}min {r.get('outputs')}" if r.get("ok") \
                else f" {r.get('error')}: {str(r.get('detail'))[:80]}"
            if dg:
                tail += "  [降档] " + " → ".join(f"{d['from']}->{d['to']}" for d in dg)
            print(f"  [{mark}] {r['tag']:>14} {r['duration']}s/{r['frames']}帧 {r['width']}x{r['height']}" + tail)
    if results:
        rebuild_consolidated(log_json, log_jsonl, key=lambda r: r.get("tag"))
        print(f"合并视图: {log_json}")
    return 0 if ok == len(combos) else 1


if __name__ == "__main__":
    sys.exit(main())
