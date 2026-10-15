# -*- coding: utf-8 -*-
"""
MiniMax H3 t2v 时长档位受控跑测（参数轨·视频模型）
==================================================

固定（全部取自工作流原值，不修改）：
  DiT / TE / 双 VAE / 两个 LoRA 及强度 / Spectrum 等 4 个 patch 链参数 /
  steps=8 / sampler=res_multistep+simple / seed / prompt / 2× ULTRA 超分
仅切换：MiniMaxH3ImageToVideo.length（帧数）+ width/height（按时长-显存边界配对）。

帧数换算（复刻工作流内 ComfyMathExpression，2026-10-14 实测验证）：
  base = max(5, round(seconds * 24)); frames = base + (5 - (base % 17)) % 17   # 17k+5 网格

用法（需 ComfyUI 已在 8188；建议经 run.py h3dur 调用）：
  python run_h3_durations.py                 # 跑全部档位
  python run_h3_durations.py --dry-run       # 只扁平化+打印计划，0 提交
  python run_h3_durations.py --only 8s_1344x768
  python run_h3_durations.py --workflow <wf.json>     # 指定工作流（默认见 DEFAULT_WORKFLOW）
  python run_h3_durations.py --te <clip_name>         # 覆盖 TE（如换解限 TE）
  python run_h3_durations.py --dit <unet_name>        # 覆盖 DiT

日志：append-only JSONL（唯一事实源）+ 合并视图 JSON（由 jsonl 重建），同 run_combos.py 范式。
"""
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request

# flatten 住在 01_工作流扁平化（run.py 会注入 PYTHONPATH；裸跑时按相对位置兜底）
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "01_工作流扁平化"))
from flatten import flatten  # noqa: E402
from logutil import append_record, rebuild_consolidated  # noqa: E402

# ---------------- 常量集中在文件顶部（改常量不改逻辑） ----------------
COMFY = "http://127.0.0.1:8188"

DEFAULT_WORKFLOW = os.path.expandvars(
    r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Video\video_minimax_h3_t2v.json")

# 时长 × 分辨率配对（2026-10-14 在 12GB 可用显存实测的边界矩阵；换显存需重标定）
#   (tag, duration_sec, width, height, 说明)
COMBOS = [
    ("5s_1344x768",   5.0, 1344, 768, "基线档：1344×768 全配置可跑"),
    ("8s_1344x768",   8.0, 1344, 768, "1344×768 的显存上限档"),
    ("10s_1152x640", 10.0, 1152, 640, "10s 起需降分辨率至 1152×640"),
    ("11s_960x544",  11.0,  960, 544, "11s 需再降至 960×544"),
    ("15s_960x544",  15.0,  960, 544, "模型标称上限 15s，仍为 960×544"),
]

# H3 工作流子图内的关键节点（原始数字 ID，flatten overrides 按 ID 匹配）
NODE_I2V = 104          # MiniMaxH3ImageToVideo（length/width/height）
NODE_CLIP = 13          # CLIPLoader（clip_name）
NODE_UNET = 6           # UNETLoader（unet_name）
NODE_SR = 127           # RTXVideoSuperResolution（strength/image_encoding UI 条件隐藏但 API required）

# loader 类节点的文件输入（ComfyUI 0.39 起候选值是相对 models/ 的路径，
# 旧工作流 JSON 里可能存扁平名，提交前必须规范化，否则 400 value_not_in_list）
LOADER_INPUTS = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name",
                 "VAELoader": "vae_name", "LoraLoaderModelOnly": "lora_name"}

# 结果日志（与 run_combos 同级目录，避免落库）
LOG_DIR = os.path.join(_HERE, "h3_duration_logs")
LOG_JSONL = os.path.join(LOG_DIR, "result_log.jsonl")
LOG_JSON = os.path.join(LOG_DIR, "result_log.json")


def frames_for(seconds):
    """duration(秒) -> length(帧)，复刻工作流 ComfyMathExpression（17k+5 网格，24fps）。"""
    base = max(5, round(seconds * 24))
    return base + (5 - (base % 17)) % 17


def build_api(workflow, combo, te=None, dit=None):
    """flatten 工作流并按档位覆盖 length/width/height（可选覆盖 TE/DiT）。"""
    tag, dur, w, h, _note = combo
    overrides = {
        NODE_I2V: {"length": frames_for(dur), "width": w, "height": h},
    }
    # 容器 prompt 为空串时回退子图内 MiniMaxH3ImageToVideo 的 prompt 原值：
    # 前端语义是「空 widget 不覆盖内部链路值」，flatten 按链路注入空串，此处对齐前端。
    # （H3 t2v 工作流容器 prompt=''，实际生效的是子图内的详细分镜 prompt）
    try:
        wf = json.load(open(workflow, encoding="utf-8"))
        for sg in wf.get("definitions", {}).get("subgraphs", []):
            for n in sg.get("nodes", []):
                if n.get("type") == "MiniMaxH3ImageToVideo":
                    inner = (n.get("widgets_values_named") or {}).get("prompt") \
                        or (n.get("widgets_values") or [""])[0]
                    if inner:
                        overrides[NODE_I2V]["prompt"] = inner
                    break
    except Exception as e:
        print(f"   [warn] 读取子图 prompt 失败: {e}")
    if te:
        overrides[NODE_CLIP] = {"clip_name": te}
    if dit:
        overrides.setdefault(6, {})["unet_name"] = dit  # 6 = UNETLoader
    api, applied = flatten(workflow, overrides)
    return api, applied, frames_for(dur)


def post(url, obj=None, timeout=120):
    data = json.dumps(obj).encode() if obj is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def normalize_loader_names(api):
    """把 payload 里 loader 节点的扁平文件名规范化成 ComfyUI 0.39 的路径形式。

    返回 (fixed, missing)：fixed=已补前缀的 (class_type, 旧值, 新值)；
    missing=候选列表中不存在的（文件已被删/改名），调用方应拒绝提交。
    """
    flat2full = {}
    for ct, key in LOADER_INPUTS.items():
        try:
            info = post(f"{COMFY}/object_info/{ct}")
            for v in info[ct]["input"]["required"][key][0]:
                base = str(v).replace("\\", "/").split("/")[-1]
                flat2full.setdefault(base, v)
        except Exception as e:
            print(f"   [warn] object_info/{ct} 拉取失败: {e}")
    fixed, missing = [], []
    for k, nd in api.items():
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


def fill_sr_hidden_inputs(api):
    """补齐 RTXVideoSuperResolution 的 strength/image_encoding。

    这两个参数在 UI 条件隐藏（resize_type=scale 时不显示），工作流 widgets 未序列化、
    flatten 的 inputs 里没有它们；而 flatten 的 overrides 语义是「只覆盖已有输入」，
    补不进去。此处后处理直接按 object_info 默认值写入（2026-10-15 坑）。
    """
    filled = []
    for k, nd in api.items():
        if nd["class_type"] == "RTXVideoSuperResolution":
            for pk, pv in (("strength", 1.0), ("image_encoding", "8-bit RGB")):
                if pk not in nd["inputs"]:
                    nd["inputs"][pk] = pv
                    filled.append((k, pk, pv))
    return filled


def run_combo(workflow, combo, te=None, dit=None, dry=False):
    tag, dur, w, h, note = combo
    frames = frames_for(dur)
    api, applied, _ = build_api(workflow, combo, te, dit)
    print(f"[{tag}] {dur}s -> {frames}帧 | {w}x{h} | {note}")
    print(f"   overrides 应用 {len(applied)} 项: " +
          "; ".join(f"{a[0]}#{a[1]}.{a[2]}: {a[3]!r}->{a[4]!r}" for a in applied))
    if dry:
        print(f"   [dry-run] payload 节点数={len(api)}，未提交")
        return None
    filled = fill_sr_hidden_inputs(api)
    for k, pk, pv in filled:
        print(f"   [补缺] 节点{k} {pk}={pv}")
    fixed, missing = normalize_loader_names(api)
    for ct, old, new in fixed:
        print(f"   [规范化] {ct}: {old} -> {new}")
    if missing:
        print(f"   [ERROR] 以下模型文件在 ComfyUI 候选列表中不存在（已删/改名？），拒绝提交：")
        for ct, cur in missing:
            print(f"     {ct}: {cur!r}  （用 --dit/--te/--workflow 修正后重跑）")
        append_record(LOG_JSONL, {"tag": tag, "duration": dur, "frames": frames,
                                  "width": w, "height": h, "ok": False,
                                  "error": "loader_missing", "detail": missing})
        return None
    t0 = time.time()
    try:
        resp = post(f"{COMFY}/prompt", {"prompt": api, "client_id": "h3dur"})
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"   提交失败 HTTP {e.code}: {body}")
        append_record(LOG_JSONL, {"tag": tag, "duration": dur, "frames": frames,
                                  "width": w, "height": h, "ok": False,
                                  "error": f"http_{e.code}", "detail": body})
        return None
    pid = resp.get("prompt_id")
    print(f"   prompt_id={pid} 等待执行...")
    last = -1
    while True:
        time.sleep(10)
        try:
            hist = post(f"{COMFY}/history/{pid}")
        except Exception:
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
                   "interpreter": sys.version.split()[0], "comfyui_ver": None}
            print(f"   完成 {el/60:.1f} 分钟 | 输出: {outs}")
            append_record(LOG_JSONL, rec)
            return rec
        if status.get("status_str") == "error":
            msgs = status.get("messages", [])
            err = ""
            for m in msgs:
                if m and m[0] == "execution_error":
                    err = str(m[1].get("exception_message", ""))[:300]
            print(f"   执行错误: {err}")
            append_record(LOG_JSONL, {"tag": tag, "duration": dur, "frames": frames,
                                      "width": w, "height": h, "ok": False,
                                      "error": "exec_error", "detail": err,
                                      "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
            return None
        mm = int((time.time() - t0) // 60)
        if mm != last:
            last = mm
            print(f"   ...{mm}m{int((time.time()-t0) % 60)}s")


def main():
    args = sys.argv[1:]
    workflow = DEFAULT_WORKFLOW
    te = dit = None
    only = None
    dry = False
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
        i += 1
    if not os.path.exists(workflow):
        print(f"[ERROR] 工作流不存在: {workflow}")
        print("        用 --workflow <路径> 指定（本仓不含本机绝对路径，默认值仅本机维护者便利）")
        return 2
    os.makedirs(LOG_DIR, exist_ok=True)
    print(f"工作流: {workflow}")
    print(f"ComfyUI: {COMFY}  |  dry-run={dry}  |  log={LOG_JSONL}")
    combos = [c for c in COMBOS if (only is None or c[0] == only)]
    if not combos:
        print(f"[ERROR] --only {only} 不在 COMBOS；可选: {[c[0] for c in COMBOS]}")
        return 2
    results = [run_combo(workflow, c, te, dit, dry) for c in combos]
    ok = sum(1 for r in results if r and r.get("ok"))
    if dry:
        print(f"\n===== dry-run 计划: {len(combos)} 档（未提交） =====")
        for c in combos:
            print(f"  [PLAN] {c[0]:>14} {c[1]}s/{frames_for(c[1])}帧 {c[2]}x{c[3]}  {c[4]}")
        return 0
    print(f"\n===== 汇总: {ok}/{len(combos)} 成功 =====")
    for r in results:
        if r:
            mark = "OK " if r.get("ok") else "FAIL"
            print(f"  [{mark}] {r['tag']:>14} {r['duration']}s/{r['frames']}帧 {r['width']}x{r['height']}"
                  + (f" {r['elapsed_sec']/60:.1f}min {r.get('outputs')}" if r.get("ok") else f" {r.get('error')}: {str(r.get('detail'))[:80]}"))
    if not dry and any(results):
        rebuild_consolidated(LOG_JSON, LOG_JSONL, key=lambda r: r.get("tag"))
        print(f"合并视图: {LOG_JSON}")
    return 0 if ok == len(combos) else 1


if __name__ == "__main__":
    sys.exit(main())
