# -*- coding: utf-8 -*-
"""
模型家族横评 ①：发现候选家族。

扫描 ComfyUI 的 models/unet 下每个子文件夹 -> 按 SHA256 去重 -> 判定
「含 >= 2 个不同权重的文件夹」为 eligible，单模型文件夹为 skipped -> 输出
family_candidates.json。

只读取证：只读文件字节算 SHA256、只读 safetensors 头部 JSON。不加载权重、
不出图、不写 models/ 目录。--arch-probe none 可跳过架构判定。

用法（必须用 ComfyUI 自带 python）：
    python discover_families.py                      # 默认门槛 2
    python discover_families.py --min-unique 2
    python discover_families.py --comfy <ComfyUI 目录>
    python discover_families.py --out family_candidates.json
    python discover_families.py --arch-probe none     # 只算哈希，最快
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time
from collections import Counter, OrderedDict

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COMFY = r"C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI"

# ComfyUI 的 UNETLoader 前缀兜底表：把头部键前缀映射成友好架构名。
# 完整的 comfy.model_detection 判定需要能 import comfy（会拉起 torch），
# 因此这里只做「无依赖指纹匹配」，需要权威判定时用 --arch-probe comfy。
#
# ⚠️ 顺序即优先级，必须「最具体 → 最宽泛」：
#   FLUX.1-dev 与 FLUX.2 都有 img_in / time_in / txt_in / double_blocks.img_attn.qkv，
#   唯一区分是 FLUX.1-dev 独有 guidance_in + vector_in（guidance_embed=true），
#   所以 FLUX.1-dev 必须排在 FLUX.2 之前，否则 1-dev 会被误判成 2。
#   同理 QwenImage21 用 txt_in.in_layer/out_layer，QwenImage 用单个 txt_in.weight。
ARCH_FINGERPRINTS = OrderedDict([
    ("Z-Image/Lumina2", ("x_embedder.weight", "t_embedder.mlp.0.weight",
                         "final_layer.linear.weight")),
    ("Krea2", ("blocks.0.attn.wq.weight", "tmlp.0.weight",
               "txtmlp.1.weight")),
    ("QwenImage21", ("img_in.weight", "txt_in.in_layer.weight",
                     "transformer_blocks.0.attn.to_q.weight")),
    ("QwenImage", ("img_in.weight", "txt_in.weight",
                   "transformer_blocks.0.attn.to_q.weight")),
    ("FLUX.1-dev", ("double_blocks.0.img_attn.qkv.weight",
                    "double_blocks.0.txt_attn.qkv.weight",
                    "guidance_in.in_layer.weight", "vector_in.in_layer.weight")),
    ("FLUX.2", ("img_in.weight", "time_in.in_layer.weight", "txt_in.weight",
                "double_blocks.0.img_attn.qkv.weight")),
])


def sha256_of(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def safetensors_header(path):
    """只读头部 JSON。返回 (header_dict, meta) 或 (None, None)。"""
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n <= 0 or n > 200 * 1024 * 1024:
            return None, None
        h = json.loads(f.read(n).decode("utf-8", "replace"))
    return h.pop("__metadata__", None) or {}, h


def fingerprint_arch(keys):
    """无依赖架构指纹：按 ComfyUI 源码里的张量命名特征判定。"""
    ks = set(keys)
    for name, need in ARCH_FINGERPRINTS.items():
        if all(any(k.endswith(sfx) for k in ks) for sfx in need):
            return name
    return "unknown"


def comfy_arch_probe(path):
    """权威判定：复用 ComfyUI 自己的 comfy.model_detection（只读，不加载权重）。"""
    try:
        import torch
        import comfy.model_detection
        import comfy.model_patcher
        import comfy.sd
        import comfy.utils
    except Exception as e:
        return {"error": "import comfy failed: %s: %s" % (type(e).__name__, e)}
    try:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            h = json.loads(f.read(n).decode("utf-8", "replace"))
        h.pop("__metadata__", None)
        sd = {}
        for k, v in h.items():
            dt = {"F64": torch.float64, "F32": torch.float32, "F16": torch.float16,
                  "BF16": torch.bfloat16, "I64": torch.int64, "I32": torch.int32,
                  "I16": torch.int16, "I8": torch.int8, "U8": torch.uint8,
                  "BOOL": torch.bool}.get(v.get("dtype"), torch.float32)
            # meta 设备：有真实 shape/dtype 但零内存，用来喂 ComfyUI 的检测代码
            sd[k] = torch.empty(tuple(v["shape"]), dtype=dt, device="meta")
        prefix = comfy.model_detection.unet_prefix_from_state_dict(sd)
        temp = comfy.utils.state_dict_prefix_replace(sd, {prefix: ""}, filter_keys=True)
        if len(temp) > 0:
            sd = temp
        mc = comfy.model_detection.model_config_from_unet(sd, "", metadata=None)
        if mc is None:
            return {"model_config": None}
        qc = None
        try:
            from comfy.utils import detect_layer_quantization
            qc = str(detect_layer_quantization(sd, ""))
        except Exception:
            pass
        return {
            "model_config": mc.__class__.__name__,
            "model_class": mc.__class__.__name__,
            "image_model": (mc.unet_config or {}).get("image_model"),
            "latent_format": mc.latent_format.__class__.__name__,
            "sampling_settings": dict(getattr(mc, "sampling_settings", {}) or {}),
            "quant_config": str(getattr(mc, "quant_config", None)),
        }
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def dtypes_of(h):
    return dict(Counter(v.get("dtype") for v in h.values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy", default=DEFAULT_COMFY)
    ap.add_argument("--min-unique", type=int, default=2)
    ap.add_argument("--ext", nargs="*", default=[".safetensors"])
    ap.add_argument("--arch-probe", choices=["fingerprint", "comfy", "none"], default="fingerprint")
    ap.add_argument("--out", default=os.path.join(HERE, "family_candidates.json"))
    a = ap.parse_args()

    unet_root = os.path.join(a.comfy, "models", "unet")
    if not os.path.isdir(unet_root):
        sys.exit("[x] 找不到 unet 目录：%s" % unet_root)
    print("unet 根目录 : %s" % unet_root)
    print("门槛       : >= %d 个唯一权重" % a.min_unique)
    print("架构判定   : %s\n" % a.arch_probe)

    t0 = time.time()
    fams = OrderedDict()
    for name in sorted(os.listdir(unet_root)):
        d = os.path.join(unet_root, name)
        if not os.path.isdir(d):
            continue
        files = sorted(fn for fn in os.listdir(d) if os.path.splitext(fn)[1].lower() in a.ext)
        if not files:
            continue

        entries, by_hash = [], OrderedDict()
        for fn in files:
            p = os.path.join(d, fn)
            st = os.stat(p)
            h = sha256_of(p)
            rec = OrderedDict()
            rec["file"] = fn
            rec["rel"] = "%s/%s" % (name, fn)
            rec["size_bytes"] = st.st_size
            rec["size_mb"] = round(st.st_size / 2**20, 2)
            rec["mtime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            rec["sha256"] = h
            rec["sha256_head"] = h[:16]
            rec["sha256_tail"] = h[-16:]
            meta, hdr = safetensors_header(p)
            if hdr is None:
                rec["header"] = "UNREADABLE"
            else:
                rec["n_tensors"] = len(hdr)
                rec["dtypes"] = dtypes_of(hdr)
                rec["arch_fingerprint"] = fingerprint_arch(hdr.keys())
                if meta:
                    rec["embedded_metadata_keys"] = sorted(meta)[:12]
                if a.arch_probe == "comfy":
                    rec["arch_comfy"] = comfy_arch_probe(p)
            if h in by_hash:
                rec["duplicate_of"] = by_hash[h]
            else:
                by_hash[h] = fn
            entries.append(rec)
            print("  %-64s %9.1f MB  %s  %s"
                  % (fn[:64], rec["size_mb"], h[:16], rec.get("arch_fingerprint", "?")))

        uniq = [e for e in entries if "duplicate_of" not in e]
        dups = [e for e in entries if "duplicate_of" in e]
        status = "eligible" if len(uniq) >= a.min_unique else "skipped"
        note = ("%d 个唯一权重" % len(uniq)) if status == "eligible" else \
               ("仅 %d 个权重，未达门槛 %d" % (len(uniq), a.min_unique))
        if dups:
            note += "；去重 %d 个（%s）" % (
                len(dups), ", ".join("%s==%s" % (d["file"][:26], d["duplicate_of"][:26]) for d in dups))
        fams[name] = OrderedDict([
            ("unet_folder", name),
            ("status", status),
            ("reason", note),
            ("n_files", len(entries)),
            ("n_unique", len(uniq)),
            ("n_duplicates", len(dups)),
            ("weights", uniq),
            ("duplicate_files", dups),
        ])
        print("  -> %-9s %s\n" % (status, note))

    n_el = sum(1 for v in fams.values() if v["status"] == "eligible")
    n_sk = sum(1 for v in fams.values() if v["status"] == "skipped")
    n_w = sum(v["n_unique"] for v in fams.values() if v["status"] == "eligible")
    report = OrderedDict([
        ("generated", time.strftime("%Y-%m-%d %H:%M:%S")),
        ("unet_root", unet_root),
        ("min_unique_weights", a.min_unique),
        ("arch_probe", a.arch_probe),
        ("sha256_elapsed_s", round(time.time() - t0, 1)),
        ("summary", {"eligible_families": n_el, "skipped_families": n_sk,
                     "eligible_weights_total": n_w}),
        ("families", fams),
    ])
    json.dump(report, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("=" * 78)
    print("eligible 家族 %d 个 / skipped %d 个 / 参与权重合计 %d 个"
          % (n_el, n_sk, n_w))
    for k, v in fams.items():
        print("  %-8s %-22s %s" % (v["status"], k, v["reason"]))
    print("\n已写出: %s  (%.1fs)" % (a.out, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
