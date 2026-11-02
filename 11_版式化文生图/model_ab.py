# -*- coding: utf-8 -*-
"""跨模型对照：同一段版式化提示词、同一个 seed，换模型跑

用来回答「版式化这套效果是不是只有 MOSS-Image 有」。

每个家族的三件套与采样口径按各自官方模板给（见 FAMILIES 注释）；
资源名在提交前用 /object_info 校验，避免静默无图。

用法：
  python model_ab.py --list
  python model_ab.py tarot                     # 跑默认家族（moss + qwen）
  python model_ab.py tarot --models moss,qwen --seed 20261111
"""
import io
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import layout_runner as LR
import layout_types as LT

OUT = os.path.join(HERE, "samples_ab")

# 三件套与采样口径：MOSS 取自 image_moss_image_t2i.json；
# Qwen 取自 image_qwen_Image_2512.json（turbo 权重，步数按 turbo 口径下调）
FAMILIES = {
    "moss": dict(
        unet=r"MOSS-Image\moss_image_sft_int8_convrot.safetensors",
        clip=r"MOSS-Image\qwen3.5_9b_int8_convrot.safetensors",
        clip_type="moss_image",
        vae=r"MOSS-Image\flux2-vae.safetensors",
        latent="EmptyFlux2LatentImage",
        steps=30, cfg=4.0, sampler="euler", scheduler="simple",
    ),
    "qwen": dict(
        unet=r"Qwen-Image-2.1-turbo\qwen-image-2.1-turbo-int8-convrot.safetensors",
        clip=r"Qwen-Image-2.1\qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
        clip_type="qwen_image",
        vae=r"Qwen-Image-2.1\qwen_image_2.1_vae_bf16.safetensors",
        latent="EmptySD3LatentImage",
        steps=8, cfg=1.0, sampler="euler", scheduler="simple",
        aura_shift=3.1,
    ),
}

NEG = ("低分辨率，低画质，肢体畸形，文字模糊，文字扭曲，伪汉字，"
       "画面过饱和，构图混乱")


def build(fam, r):
    f = FAMILIES[fam]
    w, h = int(r["width"]), int(r["height"])
    LR.check_size(w, h)
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": f["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": f["clip"], "type": f["clip_type"],
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": f["vae"]}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": r["prompt"]}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": r.get("negative", NEG)}},
        "6": {"class_type": f["latent"],
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0], "seed": int(r["seed"]),
                         "steps": f["steps"], "cfg": f["cfg"],
                         "sampler_name": f["sampler"],
                         "scheduler": f["scheduler"], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": r["name"]}},
    }
    if f.get("aura_shift"):
        # Qwen 官方模板用 ModelSamplingAuraFlow 调 shift，插在 UNET 与 KSampler 之间
        g["10"] = {"class_type": "ModelSamplingAuraFlow",
                   "inputs": {"model": ["1", 0], "shift": float(f["aura_shift"])}}
        g["7"]["inputs"]["model"] = ["10", 0]
    return g


def probe(fam):
    """三件套是否都在 /object_info 下拉表里（否则会静默无图）。"""
    f = FAMILIES[fam]
    info = LR._get("/object_info")
    bad = []
    for node, field, val in [("UNETLoader", "unet_name", f["unet"]),
                             ("CLIPLoader", "clip_name", f["clip"]),
                             ("VAELoader", "vae_name", f["vae"])]:
        lst = info[node]["input"]["required"][field][0]
        if val not in lst:
            bad.append("%s.%s 不含 %s" % (node, field, val))
    if f["clip_type"] not in info["CLIPLoader"]["input"]["required"]["type"][0]:
        bad.append("CLIPLoader.type 不含 %s" % f["clip_type"])
    if f["latent"] not in info:
        bad.append("缺少节点 %s" % f["latent"])
    return bad


def submit(fam, r):
    g = build(fam, r)
    try:
        resp = LR._post("/prompt", {"prompt": g, "client_id": "model-ab"})
    except urllib.error.HTTPError as e:
        print("[reject] %s %s HTTP %s\n%s"
              % (fam, r["name"], e.code, e.read().decode("utf-8", "replace")[:1200]),
              flush=True)
        return None
    pid = resp["prompt_id"]
    print("[submit] %-5s %-18s %dx%d steps=%d cfg=%.1f seed=%d"
          % (fam, r["name"], r["width"], r["height"],
             FAMILIES[fam]["steps"], FAMILIES[fam]["cfg"], r["seed"]), flush=True)
    import time
    t0 = time.time()
    while True:
        time.sleep(3)
        h = LR._get("/history/%s" % pid)
        if pid in h:
            entry = h[pid]
            if entry.get("status", {}).get("status_str") == "error":
                print("[error] %s" % fam, flush=True)
                return None
            imgs = []
            for _n, o in entry.get("outputs", {}).items():
                imgs.extend(o.get("images", []))
            if imgs:
                print("[done]   %-5s %-18s %.1fs" % (fam, r["name"], time.time() - t0),
                      flush=True)
                return imgs
            if entry.get("status", {}).get("status_str") == "success":
                print("[warn]   %s success 但无产物" % fam, flush=True)
                return None
        elif time.time() - t0 > 900:
            print("[timeout] %s" % fam, flush=True)
            return None


def save(fam, key, image, quality=90):
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(LR.SERVER + "/view" + q, timeout=120) as resp:
        raw = resp.read()
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "%s_%s.jpg" % (key, fam))
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def main(argv):
    if not argv or argv[0] == "--list":
        print("可用家族：")
        for k, v in FAMILIES.items():
            print("  %-5s unet=%s  steps=%d cfg=%.1f"
                  % (k, v["unet"], v["steps"], v["cfg"]))
        print("可用类型：", ", ".join(sorted(LT.TYPES)))
        return 0

    key = argv[0]
    t = LT.TYPES[key]
    models = ["moss", "qwen"]
    seed = 20261111
    for a in argv[1:]:
        if a.startswith("--models="):
            models = a.split("=", 1)[1].split(",")
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])

    w, h = t["size"]
    rec = dict(name="ab_%s_%d" % (key, seed), prompt=t["prompt"], negative=NEG,
               width=w, height=h, seed=seed)

    ok = 0
    for fam in models:
        bad = probe(fam)
        if bad:
            for b in bad:
                print("[probe-FAIL] %s: %s" % (fam, b))
            continue
        imgs = submit(fam, rec)
        if imgs:
            size = save(fam, key, imgs[0])
            print("[saved]  samples_ab/%s_%s.jpg  %.1fKB" % (key, fam, size / 1024),
                  flush=True)
            ok += 1
    print("[summary] %d/%d" % (ok, len(models)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
