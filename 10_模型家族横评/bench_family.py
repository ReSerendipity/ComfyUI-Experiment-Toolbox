# -*- coding: utf-8 -*-
"""
模型家族横评 ②：配置驱动跑测（family / model / prompt / seed 四层输出）。

控制变量口径
    跨全部权重恒定：提示词套件（逐字节一致，sha256 记账）、种子集合、分辨率、评分口径。
    同文件夹内部恒定：family_config 里钉死的 clip_loaders / vae / latent_class /
      sampler / scheduler / steps / cfg / model_sampling / guidance / negative_mode
      全部数值固定，唯一变量 = UNet 权重。
    例外：family_config.weight_overrides 可为单个权重整条替换链路，并打
      declared_exception 标记（见 FLUX-2-klein-9b / Flux.2 Klein 9B fp8 darkBeast）。

复用与出处
    flatten()  : 直接 import 01_工作流扁平化/flatten.py（sys.path 注入，不拷贝代码）。
    post/wait/collect : 抄自 03_受控跑测/run_models.py（同文件，模块级有 makedirs
                 副作用，不能 import）。
    prune_llm / DROP_TYPES / DROP_ALWAYS / BatchPromptReaderWithClip 改写：
                 抄自 03_受控跑测/run_models.py 第 100-165 行，出处见下方注释。

用法（必须用 ComfyUI 自带 python）：
    python bench_family.py --config family_config.json --dry-run
    python bench_family.py --config family_config.json --calibration
    python bench_family.py --config family_config.json --families FLUX-1-dev
    python bench_family.py --config family_config.json --all
    python bench_family.py ... --out <输出根> --comfy <ComfyUI 目录>
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLBOX = os.path.dirname(HERE)
# 工具箱同目录 import 约定：把 01_ 的目录加进 sys.path，直接 import flatten
for _d in ("01_工作流扁平化", "03_受控跑测", "04_结果分析"):
    _p = os.path.join(TOOLBOX, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, HERE)

import flatten as wf_flatten  # noqa: E402  01_工作流扁平化/flatten.py

# ---- 以下三个常量与 post/wait/collect/prune_llm 抄自 03_受控跑测/run_models.py ----
# 出处：03_受控跑测/run_models.py 第 61-97 行（HTTP）与第 100-165 行（剪枝）。
# 不 import run_models 的原因：它在模块级执行 os.makedirs(OUT)，import 即产生副作用。
DROP_TYPES = {"TextGenerate", "PrimitiveStringMultiline", "PreviewAny", "PrimitiveBoolean"}
DROP_ALWAYS = {"BatchPromptReaderWithClip"}
# --------------------------------------------------------------------------------


def post(api, path, payload, timeout=120):
    req = urllib.request.Request(api + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def wait(api, pid, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(api + "/history/" + pid, timeout=15) as r:
                h = json.loads(r.read().decode())
        except Exception:
            time.sleep(3)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") in ("success", "error") or st.get("completed"):
                msgs = st.get("messages") or []
                err = [m[1] for m in msgs if m[0] == "execution_error"]
                # ComfyUI 即使一个节点都没命中也会发 execution_cached 且 nodes 为空列表，
                # 所以必须看 nodes 里有没有东西，不能只看消息类型（否则会误报命中）
                cnodes = []
                for m in msgs:
                    if m[0] == "execution_cached" and m[1].get("nodes"):
                        cnodes = list(m[1]["nodes"])
                return (st.get("status_str") == "success"), h[pid].get("outputs", {}), \
                    (json.dumps(err[-1], ensure_ascii=False)[:1500] if err else None), cnodes
        time.sleep(2)
    return False, None, "timeout", False


def images_from(outputs):
    out = []
    for nid, v in (outputs or {}).items():
        if not isinstance(v, dict):
            continue
        for key in ("images", "image", "gifs"):
            for im in (v.get(key) or []):
                if isinstance(im, dict) and im.get("filename"):
                    out.append((nid, key, im))
    return out


def gpu_stats(api, timeout=20):
    """GET /system_stats -> {vram_free, vram_total, vram_free_mb, ...}；失败返回 None。"""
    try:
        with urllib.request.urlopen(api + "/system_stats", timeout=timeout) as r:
            d = json.loads(r.read().decode())
        dev = (d.get("devices") or [{}])[0]
        free, total = dev.get("vram_free"), dev.get("vram_total")
        return {
            "gpu": dev.get("name", ""),
            "vram_total": total,
            "vram_free": free,
            "vram_total_mb": round(total / 2**20, 1) if total else None,
            "vram_free_mb": round(free / 2**20, 1) if free else None,
        }
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def prune_llm(api):
    """去掉 LLM 提示词增强链路。抄自 03_受控跑测/run_models.py:105-130。
    ComfySwitchNode 同时承担 model / prompt 选路，不能直接删——先把「非 LLM 上游」
    直连给下游，再删开关与 LLM 链。"""
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
    for k in [k for k, v in api.items() if v["class_type"] in DROP_TYPES]:
        api.pop(k, None)
    for v in api.values():
        for kk, vv in list(v["inputs"].items()):
            if isinstance(vv, list) and str(vv[0]) not in api:
                v["inputs"].pop(kk)
    return api


def drop_batch_reader(api, rebuild_empty_encode=True):
    """旁路 BatchPromptReaderWithClip。抄自 03_受控跑测/run_models.py:137-165。
    它的输出是 CONDITIONING，类型上接不到它的 clip 输入（CLIP != CONDITIONING），
    因此替换成同语义的「空提示词编码」。"""
    dropped = []
    for k in [k for k, v in api.items() if v["class_type"] in DROP_ALWAYS]:
        clip_link = None
        for vv in api[k]["inputs"].values():
            if isinstance(vv, list) and str(vv[0]) in api and \
                    api[str(vv[0])]["class_type"] in ("DualCLIPLoader", "CLIPLoader"):
                clip_link = list(vv)
                break
        rep = None
        if rebuild_empty_encode and clip_link:
            nk = "gen_neg_" + k
            api[nk] = {"class_type": "CLIPTextEncode",
                       "inputs": {"clip": clip_link, "text": ""},
                       "_meta": {"title": "空提示词编码（替代批量提示词读取器）"}}
            rep = [nk, 0]
        for v2 in api.values():
            for kk, vv in list(v2["inputs"].items()):
                if isinstance(vv, list) and str(vv[0]) == k:
                    if rep:
                        v2["inputs"][kk] = list(rep)
                    else:
                        v2["inputs"].pop(kk)
        api.pop(k, None)
        dropped.append(k)
    for v in api.values():
        for k, val in list(v["inputs"].items()):
            if isinstance(val, list) and str(val[0]) not in api:
                v["inputs"].pop(k)
    return api


def dangling_prune(api):
    for v in api.values():
        for k, val in list(v["inputs"].items()):
            if isinstance(val, list) and str(val[0]) not in api:
                v["inputs"].pop(k)
    return api


def first_of(api, cls):
    for k, v in api.items():
        if v["class_type"] == cls:
            return k
    return None


def winpath(p):
    """ComfyUI 在 Windows 上给 loader 枚举的相对路径是反斜杠分隔的
    （folder_paths.get_filename_list -> 'FLUX-1-dev\\xxx.safetensors'）。
    配置里为了跨平台可读统一写正斜杠，写进图之前必须转成反斜杠，
    否则 UNETLoader / CLIPLoader / VAELoader 会报 value_not_in_list。"""
    return str(p).replace("/", "\\")


def fetch_enums(api, timeout=120):
    """拉 /object_info，取 loader 的真实枚举值。--validate 用它验证
    「这个名字 ComfyUI 真的认不认识」。结构：input.required.<field>[0] = 列表。"""
    try:
        with urllib.request.urlopen(api + "/object_info", timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except Exception:
        return None

    def lst(node, field):
        try:
            return list(d[node]["input"]["required"][field][0])
        except Exception:
            return None

    return {
        "unet": lst("UNETLoader", "unet_name"),
        "text": lst("CLIPLoader", "clip_name"),
        "vae": lst("VAELoader", "vae_name"),
    }


def find_prompt_file(prompts_dir, pid, prompt_files=None):
    """提示词 id -> 文件。先查配置里的显式映射，再退化到 <pid>*.txt 通配。"""
    if prompt_files and pid in prompt_files:
        p = os.path.join(prompts_dir, prompt_files[pid])
        if os.path.isfile(p):
            return p
    p = os.path.join(prompts_dir, pid + ".txt")
    if os.path.isfile(p):
        return p
    import glob
    hits = sorted(glob.glob(os.path.join(prompts_dir, pid + "*.txt")))
    return hits[0] if hits else None


def force_positive_text(api, text):
    """把「真正喂给采样器的那条正向链」上的 CLIPTextEncode.text 设为受控提示词。

    不能只找 positive 输入：FLUX.1-dev 链路是
        CLIPTextEncode -> FluxGuidance -> BasicGuider(conditioning)
    整条链上没有任何节点带 positive 输入。所以这里从 guider/采样器的
    (positive | conditioning) 反向 BFS，找第一个 CLIPTextEncode。
    """
    srcs = []
    for v in api.values():
        ct = v["class_type"]
        if ct in ("CFGGuider", "KSampler", "KSamplerAdvanced"):
            for f in ("positive",):
                if isinstance(v["inputs"].get(f), list):
                    srcs.append(str(v["inputs"][f][0]))
        elif ct == "BasicGuider":
            if isinstance(v["inputs"].get("conditioning"), list):
                srcs.append(str(v["inputs"]["conditioning"][0]))
    if not srcs:
        return None
    seen, queue = set(), list(srcs)
    hit = None
    while queue:
        k = queue.pop(0)
        if k in seen or k not in api:
            continue
        seen.add(k)
        if api[k]["class_type"] == "CLIPTextEncode":
            hit = k
            break
        for v in api[k]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in api:
                queue.append(v[0])
    if hit and "text" in api[hit]["inputs"]:
        api[hit]["inputs"]["text"] = text
        return hit
    return None


def build_graph(fam, weight_file, prompt_text, seed, prefix, cfg, prune_on, neg_text):
    """扁平化用户工作流 -> 施加 family_config 常量 -> 返回 API 图。"""
    wf_abs = os.path.join(cfg["_comfy_root"], fam["workflow"].replace("/", os.sep))
    # 扁平化需要一个磁盘文件；写到系统临时目录并在 finally 里删掉，
    # 避免在模块目录里留下 _edited_workflow.json 之类的垃圾
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="familybench_", suffix=".json")
    os.close(fd)
    try:
        w = json.load(open(wf_abs, encoding="utf-8"))
        w = copy.deepcopy(w)

        # 1) 容器 positional 覆盖（_container_edits 形如 {"10": ""}）
        for key, val in (fam.get("_container_edits") or {}).items():
            if key.startswith("_"):
                continue
            conts = [n for n in w["nodes"]
                     if isinstance(n.get("type"), str) and "-" in n["type"] and len(n["type"]) > 30]
            for c in conts:
                wv = list(c.get("widgets_values") or [])
                i = int(key)
                if 0 <= i < len(wv):
                    wv[i] = val
                c["widgets_values"] = wv
        json.dump(w, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        api, _ = wf_flatten.flatten(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    # 2) 剪枝
    if prune_on:
        if any(v["class_type"] in DROP_TYPES for v in api.values()):
            api = prune_llm(api)
        if any(v["class_type"] in DROP_ALWAYS for v in api.values()):
            api = drop_batch_reader(api, cfg["_prune"].get("rebuild_batch_reader_as_empty_encode", True))
        api = dangling_prune(api)

    # 3) UNETLoader -> 权重槽
    uk = first_of(api, "UNETLoader")
    if not uk:
        raise RuntimeError("工作流里没有 UNETLoader：%s" % fam["workflow"])
    api[uk]["inputs"]["unet_name"] = winpath("%s/%s" % (fam["unet_folder"], weight_file))
    api[uk]["inputs"]["weight_dtype"] = "default"

    # 4) text encoder
    clips = fam["clip_loaders"]
    dk = first_of(api, "DualCLIPLoader")
    ck = first_of(api, "CLIPLoader")
    if dk and len(clips) == 2:
        api[dk]["inputs"]["clip_name1"] = winpath(clips[0]["clip_name"])
        api[dk]["inputs"]["clip_name2"] = winpath(clips[1]["clip_name"])
        api[dk]["inputs"]["type"] = clips[0]["type"]
        api[dk]["inputs"]["device"] = clips[0].get("device", "default")
    elif ck and clips:
        api[ck]["inputs"]["clip_name"] = winpath(clips[0]["clip_name"])
        api[ck]["inputs"]["type"] = clips[0]["type"]
        api[ck]["inputs"]["device"] = clips[0].get("device", "default")

    # 5) VAE
    vk = first_of(api, "VAELoader")
    if vk:
        api[vk]["inputs"]["vae_name"] = winpath(fam["vae"])

    # 6) latent 尺寸
    lk = first_of(api, fam["latent_class"]) or first_of(api, "EmptyLatentImage") \
        or first_of(api, "EmptySD3LatentImage") or first_of(api, "EmptyFlux2LatentImage")
    if lk:
        api[lk]["inputs"]["width"] = cfg["_width"]
        api[lk]["inputs"]["height"] = cfg["_height"]
        if "batch_size" in api[lk]["inputs"]:
            api[lk]["inputs"]["batch_size"] = 1

    # 7) model_sampling / guidance
    ms = fam.get("model_sampling")
    if ms:
        mk = first_of(api, ms["node"])
        if mk:
            ins = api[mk]["inputs"]
            for k2 in ("max_shift", "base_shift"):
                if k2 in ms and k2 in ins:
                    ins[k2] = ms[k2]
            if "shift" in ms and "shift" in ins:
                ins["shift"] = ms["shift"]
    gd = fam.get("guidance")
    if gd:
        gk = first_of(api, gd["node"])
        if gk and "guidance" in api[gk]["inputs"]:
            api[gk]["inputs"]["guidance"] = gd["value"]

    # 8) 采样参数
    seeded = []
    for k, v in api.items():
        ct = v["class_type"]
        if ct == "KSampler":
            for f2, val in (("steps", fam["steps"]), ("cfg", fam["cfg"]),
                            ("sampler_name", fam["sampler"]),
                            ("scheduler", fam["scheduler"]), ("seed", seed)):
                if f2 in v["inputs"]:
                    v["inputs"][f2] = val
                    seeded.append("%s.%s=%s" % (k, f2, val))
        elif ct == "KSamplerSelect":
            v["inputs"]["sampler_name"] = fam["sampler"]
        elif ct == "BasicScheduler":
            for f2, val in (("steps", fam["steps"]), ("scheduler", fam["scheduler"])):
                if f2 in v["inputs"]:
                    v["inputs"][f2] = val
        elif ct == "Flux2Scheduler":
            for f2, val in (("steps", fam["steps"]), ("width", cfg["_width"]),
                            ("height", cfg["_height"])):
                if f2 in v["inputs"]:
                    v["inputs"][f2] = val
        elif ct == "CFGGuider":
            v["inputs"]["cfg"] = fam["cfg"]
        elif ct == "RandomNoise":
            v["inputs"]["noise_seed"] = seed
    # Flux2Scheduler 需 width/height（工作流里常是 PrimitiveInt 链），兜底补
    f2s = first_of(api, "Flux2Scheduler")
    if f2s:
        api[f2s]["inputs"].setdefault("width", cfg["_width"])
        api[f2s]["inputs"].setdefault("height", cfg["_height"])
    for pk in (first_of(api, "PrimitiveInt"),):
        if pk:
            pass  # 保留工作流自有值，仅记录

    # 9) negative
    pos_src = force_positive_text(api, prompt_text)
    if fam["negative_mode"] == "real":
        ck2 = first_of(api, "CLIPLoader")
        if ck2 and pos_src:
            nk = "bench_neg"
            api[nk] = {"class_type": "CLIPTextEncode",
                       "inputs": {"clip": [ck2, 0], "text": neg_text},
                       "_meta": {"title": "受控负向提示词"}}
            for v in api.values():
                if v["class_type"] in ("CFGGuider", "KSampler", "KSamplerAdvanced"):
                    for f3 in ("negative",):
                        if f3 in v["inputs"]:
                            v["inputs"][f3] = [nk, 0]

    # 10) 保存前缀
    for v in api.values():
        if v["class_type"] in ("SaveImage", "SaveImageAdvanced") and "filename_prefix" in v["inputs"]:
            v["inputs"]["filename_prefix"] = prefix

    # 11) 只保留原图，不做 SeedVR2 放大：把 Preview 分支从 Save 断开
    for k in [k for k, v in api.items() if v["class_type"] == "PreviewImage"]:
        api.pop(k, None)
    api = dangling_prune(api)
    # 12) 保险：再强制一次提示词（剪枝可能换掉 positive 上游）
    force_positive_text(api, prompt_text)

    api["_bench_meta"] = {"positive_node": pos_src, "seeded": seeded,
                          "unet_node": uk, "pruned": prune_on}
    return api


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "family_config.json"))
    ap.add_argument("--out", default=None, help="输出根目录（默认 <comfy>/output/model_benchmark）")
    ap.add_argument("--comfy", default=None, help="ComfyUI 目录（覆盖配置）")
    ap.add_argument("--api", default=None)
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--weights", nargs="*", default=None, help="按文件名过滤")
    ap.add_argument("--prompts", nargs="*", default=None)
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    ap.add_argument("--calibration", action="store_true",
                    help="每条链路 1 张（S1 × 第一个种子），作为批量前置闸门")
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stop-on-first-fail", action="store_true",
                    help="任何一张 SUBMIT_FAIL / 执行失败 / OOM 立刻停手（不重试、不改参数），"
                         "把现场留给人工判断")
    ap.add_argument("--validate", action="store_true",
                    help="每个权重构建一次 API 图并做结构体检（悬空连线/必需节点/"
                         "unet_name/提示词一致性）。0 提交、0 出图。")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    cfg["_comfy_root"] = (a.comfy or cfg["comfy"]["comfy_root"]).replace("\\", "/").rstrip("/")
    api_url = a.api or cfg["comfy"]["api"]
    cfg["_width"] = cfg["bench"]["width"]
    cfg["_height"] = cfg["bench"]["height"]
    cfg["_prune"] = cfg.get("prune", {})
    neg_text = (cfg.get("negative") or {}).get("real_text", "")
    out_root = a.out or os.path.join(cfg["_comfy_root"], "output",
                                     cfg["comfy"].get("out_subdir", "model_benchmark"))
    timeout = a.timeout or cfg["bench"].get("poll_timeout_s", 1800)
    prompts_dir = os.path.join(HERE, cfg["bench"].get("prompt_dir", "prompts"))
    prompt_files = cfg["bench"].get("prompt_files") or {}

    # 组装权重清单
    fams = {}
    all_fams = cfg["families"]
    for fname, fcfg in all_fams.items():
        if fcfg.get("enabled") is False:
            continue
        if a.families and fname not in a.families:
            continue
        weights = list(fcfg.get("weights") or [])
        if not weights:
            cand = os.path.join(HERE, "family_candidates.json")
            if os.path.isfile(cand):
                rep = json.load(open(cand, encoding="utf-8"))
                got = (rep.get("families", {}).get(fcfg["unet_folder"], {}) or {}).get("weights", [])
                weights = [w["file"] for w in got]
        if a.weights:
            weights = [w for w in weights if w in a.weights]
        rows = []
        for wf in weights:
            eff = copy.deepcopy(fcfg)
            ov = (fcfg.get("weight_overrides") or {}).get(wf)
            if ov:
                for k2, v2 in ov.items():
                    if not k2.startswith("_"):
                        eff[k2] = v2
                eff["_override_note"] = ov.get("_why", "")
            rows.append((wf, eff))
        fams[fname] = rows

    pr_ids = a.prompts or cfg["bench"]["prompts"]
    seeds = a.seeds or cfg["bench"]["seeds"]

    print("config     : %s" % a.config)
    print("comfy      : %s" % cfg["_comfy_root"])
    print("api        : %s" % api_url)
    print("out        : %s" % out_root)
    print("prompts    : %s" % " ".join(pr_ids))
    print("seeds      : %s" % seeds)
    print("resolution : %dx%d" % (cfg["_width"], cfg["_height"]))
    print()
    n_models = 0
    for fname, rows in fams.items():
        if not rows:
            print("  %-18s (无可用权重)" % fname)
            continue
        chains = sorted({r[1]["chain"] for r in rows})
        print("  %-18s weights=%-2d chain(s)=%s%s"
              % (fname, len(rows), ",".join(chains),
                 "   <-- DECLARED EXCEPTION" if len(chains) > 1 else ""))
        for wf, eff in rows:
            flag = "  [declared_exception]" if eff.get("declared_exception") else ""
            print("      %-58s %s%s" % (wf[:58], eff["chain"], flag))
            n_models += 1

    if a.calibration:
        # 每条链路取第一个权重：chain -> (family, weight_file, eff)
        sel = {}
        for fname, rows in fams.items():
            for wf, eff in rows:
                sel.setdefault(eff["chain"], (fname, wf, eff))
        tasks = [(v[0], v[1], v[2], pr_ids[0], seeds[0]) for v in sel.values()]
    else:
        tasks = [(fn, wf, eff, p, s)
                 for fn, rows in fams.items() for wf, eff in rows
                 for p in pr_ids for s in seeds]

    print("\nPLAN      : %d models x %d prompts x %d seeds = %d images"
          % (n_models, len(pr_ids), len(seeds),
             n_models * len(pr_ids) * len(seeds)))
    if a.calibration:
        print("CALIBRATE : %d 张（每条链路 1 张）" % len(tasks))
    if a.validate:
        # 结构体检：每个权重构建一次图，检查悬空连线 / 必需节点 / 钉死常量 / 提示词一致。
        # 全程不 POST、不出图。
        print("\n-- validate（构建 API 图做结构体检，0 提交 0 出图）--")
        enums = fetch_enums(api_url)
        if enums:
            print("已拉取 ComfyUI loader 枚举：unet=%d text=%d vae=%d"
                  % (len(enums.get("unet") or []), len(enums.get("text") or []),
                     len(enums.get("vae") or [])))
        else:
            print("警告：拉不到 /object_info，跳过「名字是否被 ComfyUI 认可」这项体检")
        bad = 0
        for fname, rows in fams.items():
            for wfile, eff in rows:
                pid = (a.prompts or cfg["bench"]["prompts"])[0]
                pdir = find_prompt_file(prompts_dir, pid, prompt_files)
                text = open(pdir, encoding="utf-8").read().strip() if pdir else ""
                issues = []
                try:
                    g = build_graph(eff, wfile, text, (a.seeds or cfg["bench"]["seeds"])[0],
                                    "validate/placeholder", cfg,
                                    bool(cfg["_prune"].get("prompt_enhance_off", True)), neg_text)
                except Exception as e:
                    import traceback
                    print("  %-18s %-46s BUILD_FAIL %s" % (fname, wfile[:46], e))
                    traceback.print_exc(limit=4)
                    bad += 1
                    continue
                meta = g.pop("_bench_meta", {})
                cts = {v["class_type"] for v in g.values()}
                for need in ("UNETLoader", "VAELoader", "VAEDecode"):
                    if need not in cts:
                        issues.append("缺 " + need)
                if not ({"CLIPLoader", "DualCLIPLoader"} & cts):
                    issues.append("缺 CLIPLoader/DualCLIPLoader")
                if not ({"SaveImage", "SaveImageAdvanced"} & cts):
                    issues.append("缺 SaveImage")
                for k, v in g.items():
                    for f2, val in v["inputs"].items():
                        if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) \
                                and val[0] not in g:
                            issues.append("悬空连线 %s.%s -> %s" % (k, f2, val[0]))
                uk = meta.get("unet_node")
                if uk:
                    got = g[uk]["inputs"]["unet_name"]
                    want = winpath("%s/%s" % (eff["unet_folder"], wfile))
                    if got != want:
                        issues.append("unet_name %r != %r" % (got, want))
                    if enums and enums.get("unet") and got not in enums["unet"]:
                        issues.append("UNETLoader 不认这个 unet_name：%r" % got)
                else:
                    issues.append("未定位 UNETLoader")
                # text encoder / vae 的名字必须真的在 ComfyUI 枚举里（防分隔符/改名写错）
                for lk2 in (first_of(g, "CLIPLoader"), first_of(g, "DualCLIPLoader")):
                    if not lk2:
                        continue
                    for f2 in ("clip_name", "clip_name1", "clip_name2"):
                        v2 = g[lk2]["inputs"].get(f2)
                        if isinstance(v2, str) and enums and enums.get("text") \
                                and v2 not in enums["text"]:
                            issues.append("CLIPLoader 不认 %s=%r" % (f2, v2))
                vk2 = first_of(g, "VAELoader")
                if vk2:
                    v2 = g[vk2]["inputs"].get("vae_name")
                    if isinstance(v2, str) and enums and enums.get("vae") \
                            and v2 not in enums["vae"]:
                        issues.append("VAELoader 不认 vae_name=%r" % v2)
                # 钉死常量抽查
                for v in g.values():
                    if v["class_type"] == "KSampler":
                        for f2, want in (("steps", eff["steps"]), ("cfg", eff["cfg"]),
                                         ("sampler_name", eff["sampler"]),
                                         ("scheduler", eff["scheduler"])):
                            if f2 in v["inputs"] and v["inputs"][f2] != want:
                                issues.append("KSampler.%s=%r != %r"
                                              % (f2, v["inputs"][f2], want))
                    if v["class_type"] == "Flux2Scheduler" and v["inputs"].get("steps") != eff["steps"]:
                        issues.append("Flux2Scheduler.steps=%r != %r"
                                      % (v["inputs"].get("steps"), eff["steps"]))
                    if v["class_type"] == "CFGGuider" and v["inputs"].get("cfg") != eff["cfg"]:
                        issues.append("CFGGuider.cfg=%r != %r" % (v["inputs"].get("cfg"), eff["cfg"]))
                pn = meta.get("positive_node")
                ptxt = g.get(pn, {}).get("inputs", {}).get("text") if pn else None
                if ptxt != text:
                    issues.append("正向提示词未逐字节注入（len=%s want=%s）"
                                  % (len(ptxt or ""), len(text)))
                resid = [k for k, v in g.items()
                         if v["class_type"] in (DROP_TYPES | DROP_ALWAYS)]
                if resid:
                    issues.append("剪枝残留 %s" % resid)
                status = "OK" if not issues else "ISSUES(%d)" % len(issues)
                print("  %-18s %-46s %-4s nodes=%-3d %s"
                      % (fname, wfile[:46], status, len(g),
                         ("chain=%s" % eff["chain"]) + ("" if not issues else "  " + "; ".join(issues))))
                bad += 1 if issues else 0
        print("\nvalidate 结束：%d 个权重，%d 个有问题" % (n_models, bad))
        return 1 if bad else 0

    if a.dry_run:
        print("\n-- dry run, 0 提交 --")
        for t in tasks:
            print("   %-18s %-52s %-4s %d" % (t[0], t[1][:52], t[3], t[4]))
        return 0

    os.makedirs(out_root, exist_ok=True)
    lp = os.path.join(out_root, "ledger.json")
    led = json.load(open(lp, encoding="utf-8")) if os.path.isfile(lp) else {}
    t00 = time.time()
    n_ok = n_fail = n_skip = 0
    for i, (fname, wfile, eff, pid, seed) in enumerate(tasks, 1):
        pdir = find_prompt_file(prompts_dir, pid, prompt_files)
        if not pdir:
            print("[%3d/%3d] SKIP 缺提示词文件 %s%s(.txt)" % (i, len(tasks), prompts_dir, pid))
            continue
        text = open(pdir, encoding="utf-8").read().strip()
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        d = os.path.join(out_root, fname, os.path.splitext(wfile)[0], pid)
        os.makedirs(d, exist_ok=True)
        stem = os.path.join(d, "s%d" % seed)
        if os.path.isfile(stem + ".png") and not a.force:
            print("[%3d/%3d] SKIP 已存在 %s" % (i, len(tasks), os.path.basename(stem)))
            n_skip += 1
            continue
        rel = os.path.relpath(d, out_root).replace("\\", "/")
        # SaveImage 会自己加 _00001 后缀，所以前缀不能指向最终目录，否则同一张图
        # 会在四层目录里留下 s<seed>.png 和 s<seed>_00001.png 两份，fanalyze 会重复计数。
        # 前缀指向独立的 raw 目录，再由本脚本复制成规范文件名。
        raw_sub = cfg["comfy"].get("raw_out_subdir", "model_benchmark_raw")
        prefix = "%s/%s/s%d" % (raw_sub, rel, seed)

        try:
            g = build_graph(eff, wfile, text, seed, prefix, cfg, bool(cfg["_prune"].get("prompt_enhance_off", True)), neg_text)
        except Exception as e:
            print("[%3d/%3d] FLATTEN_FAIL %s: %s" % (i, len(tasks), wfile, e))
            n_fail += 1
            continue
        meta = g.pop("_bench_meta", {})
        json.dump(g, open(stem + ".workflow.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        pn = meta.get("positive_node")
        enc_text = (g.get(pn, {}).get("inputs", {}).get("text")
                    if pn and isinstance(g.get(pn), dict) else None)
        json.dump({"family": fname, "weight": wfile, "chain": eff["chain"],
                   "declared_exception": bool(eff.get("declared_exception")),
                   "override_note": eff.get("_override_note", ""),
                   "workflow": eff["workflow"], "unet_name": g[meta.get("unet_node", "")]["inputs"]["unet_name"]
                   if meta.get("unet_node") else None,
                   "unet_weight_dtype": g[meta["unet_node"]]["inputs"].get("weight_dtype")
                   if meta.get("unet_node") else None,
                   "clip_loaders": eff["clip_loaders"], "vae": eff["vae"],
                   "latent_class": eff["latent_class"], "width": cfg["_width"],
                   "height": cfg["_height"], "sampler": eff["sampler"],
                   "scheduler": eff["scheduler"], "steps": eff["steps"], "cfg": eff["cfg"],
                   "model_sampling": eff.get("model_sampling"), "guidance": eff.get("guidance"),
                   "sample_chain": eff.get("sample_chain"),
                   "negative_mode": eff["negative_mode"],
                   "negative_text": (neg_text if eff["negative_mode"] == "real"
                                     else "(ConditioningZeroOut)"),
                   "seed": seed, "prompt_id": pid, "prompt_file": os.path.basename(pdir),
                   "prompt_sha256": sha, "prompt_chars": len(text),
                   # 证据：真正写进 CLIPTextEncode 的文本的 sha256，必须与 prompt_sha256 同值，
                   # 用来证明提示词没被 LLM 改写器 / ComfySwitchNode / 字符串拼接动过
                   "positive_node": pn,
                   "positive_text_sha256": (hashlib.sha256(enc_text.encode("utf-8")).hexdigest()
                                             if enc_text is not None else None),
                   "positive_text_chars": (len(enc_text) if enc_text is not None else None),
                   "prompt_unmodified": (enc_text == text),
                   "pruned": meta.get("pruned")},
                  open(stem + ".params.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        t0 = time.time()
        res, err = post(api_url, "/prompt", {"prompt": g, "client_id": cfg["comfy"].get("client_id", "bench")})
        if err or not res:
            print("[%3d/%3d] SUBMIT_FAIL %s" % (i, len(tasks), str(err)[:200]))
            json.dump({"ok": False, "stage": "submit", "error": str(err)[:4000]},
                      open(stem + ".result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            led["%s|%s|%s|%d" % (fname, wfile, pid, seed)] = {"ok": False, "stage": "submit"}
            json.dump(led, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            n_fail += 1
            continue
        ok, outs, werr, cached_nodes = wait(api_url, res["prompt_id"], timeout)
        el = round(time.time() - t0, 1)
        imgs = images_from(outs)
        saved = None
        if ok and imgs:
            nid, key, im = imgs[-1]
            cands = [os.path.join(cfg["_comfy_root"], "output", im.get("subfolder") or "", im["filename"]),
                     os.path.join(cfg["_comfy_root"], "output", prefix, im["filename"])]
            sp = next((c for c in cands if os.path.isfile(c)), None)
            if sp:
                open(stem + ".png", "wb").write(open(sp, "rb").read())
                saved = stem + ".png"
        ok = ok and bool(saved)
        vram = gpu_stats(api_url)
        json.dump({"ok": ok, "prompt_id": res["prompt_id"], "elapsed_s": el,
                   "status_str": "success" if ok else "error", "cached_nodes": cached_nodes,
                   "image": saved, "error": werr, "gpu_after": vram},
                  open(stem + ".result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        led["%s|%s|%s|%d" % (fname, wfile, pid, seed)] = {"ok": ok, "elapsed_s": el, "image": saved}
        json.dump(led, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n_ok += 1 if ok else 0
        n_fail += 0 if ok else 1
        print("[%3d/%3d] %-6s %-18s %-46s %-4s %7.1fs  vram_free=%s%s%s"
              % (i, len(tasks), "OK" if ok else "FAIL", fname, wfile[:46], pid, el,
                 ("%.0fMB" % vram["vram_free_mb"]) if vram.get("vram_free_mb") else "?",
                 ("  [cached:%s]" % ",".join(map(str, cached_nodes))) if cached_nodes else "  [cold]",
                 "" if ok else "  ERR=" + str(werr)[:300]), flush=True)
        if not ok and a.stop_on_first_fail:
            print("\n[ABORT] 第 %d/%d 张失败，按 --stop-on-first-fail 立刻停手。"
                  "不重试、不改参数。错误原文：\n%s" % (i, len(tasks), werr), flush=True)
            print("已完成 %d 张，ledger: %s" % (n_ok, lp), flush=True)
            return 2
    print("\nSUMMARY ok=%d fail=%d skip=%d  total=%.1f min  ledger=%s"
          % (n_ok, n_fail, n_skip, (time.time() - t00) / 60, lp))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
