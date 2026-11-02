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
# Qwen 取自 image_qwen_Image_2512.json（turbo 权重，步数按 turbo 口径下调）；
# 其余按家族蒸馏/非蒸馏性质给（klein、turbo、NSFW-turbo 都是蒸馏档，低步数 CFG 1）
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
    "qwen_uc": dict(
        unet=r"Qwen-Image-2.1\qwen-image-2.1-UC-int8_convrot.safetensors",
        clip=r"Qwen-Image-2.1\qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
        clip_type="qwen_image",
        vae=r"Qwen-Image-2.1\qwen_image_2.1_vae_bf16.safetensors",
        latent="EmptySD3LatentImage",
        steps=30, cfg=4.0, sampler="euler", scheduler="simple",
        aura_shift=3.1,
    ),
    "flux2": dict(
        unet=r"FLUX-2-klein-9b\BigLoveKlein2_fp8.safetensors",
        clip=r"FLUX-2-klein-9b\qwen3-8b-heretic-v1.4_klein9b_int8_convrot.safetensors",
        clip_type="flux2",
        vae=r"FLUX.2-klein-9b\flux2-vae.safetensors",
        latent="EmptyFlux2LatentImage",
        steps=8, cfg=1.0, sampler="euler", scheduler="simple",
    ),
    "flux3": dict(
        unet=r"FLUX-3-klein\flux3_image_klein_sd_int8_convrot.safetensors",
        clip=r"FLUX-3-klein\qwen3vl_4b_int8_convrot.safetensors",
        clip_type="flux3",
        vae=r"FLUX-3-klein\flux2-vae.safetensors",
        latent="EmptyFlux2LatentImage",
        steps=8, cfg=1.0, sampler="euler", scheduler="simple",
    ),
    "krea2": dict(
        unet=r"Krea2-turbo\krea2TurboNSFWAIO_v10.safetensors",
        clip=r"Krea2\qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors",
        clip_type="krea2",
        vae=r"Qwen-image+ Krea2\qwen_image_vae.safetensors",
        latent="EmptySD3LatentImage",
        steps=8, cfg=1.0, sampler="euler", scheduler="simple",
    ),
    "zimage": dict(
        unet=r"Z-image-turbo\zimageTurboNSFWByStable_2602NSFWFP8.safetensors",
        clip=r"Z-image\qwen3-4b-heretic_fp8_e4m3fn.safetensors",
        clip_type="lumina2",
        vae=r"FLUX-1-dev + Z-image\ae.safetensors",
        latent="EmptySD3LatentImage",
        steps=8, cfg=1.0, sampler="euler", scheduler="simple",
    ),
    # FLUX.1-dev 要双文本编码器，走 DualCLIPLoader
    "flux1": dict(
        unet=r"FLUX-1-dev\fluxNSFWUNLOCKED.safetensors",
        clip=r"FLUX-1-dev\clip_l.safetensors",
        clip2=r"FLUX-1-dev\t5xxl_fp8_e4m3fn.safetensors",
        clip_type="flux",
        vae=r"FLUX-1-dev + Z-image\ae.safetensors",
        latent="EmptySD3LatentImage",
        steps=20, cfg=3.5, sampler="euler", scheduler="simple",
    ),
    # Qwen-Image-2512（nvfp4，需 Blackwell）。口径取自 2026-10-31 四语文字评测：50 步 / CFG 4
    "qwen2512": dict(
        unet=r"Qwen-image-2512\qwen-image-2512-nvfp4-Ultra.safetensors",
        clip=r"Qwen-image-2512-edit\qwen_2.5_vl_7b_huihui_abliterated_int8_convrot.safetensors",
        clip_type="qwen_image",
        vae=r"Qwen-image+ Krea2\qwen_image_vae.safetensors",
        latent="EmptySD3LatentImage",
        steps=50, cfg=4.0, sampler="euler", scheduler="simple",
        aura_shift=3.1,
    ),
}

# 文字能力不足、不参与版式对照的家族（依据 2026-10-31 四语文字评测）
# krea2 / flux2 / flux1 的失败证据见该次评测的 card_zh_*.jpg
EXCLUDED = {
    "flux1": "四语评测里把中文写成韩文，版式也出不来",
    "flux2": "菜单大面积伪汉字（花苑乌龙 / 桃漪孰铡湆）",
    "krea2": "菜单多处错字（炭焙→核桃、陈皮→柽皮）",
}

NEG = ("低分辨率，低画质，肢体畸形，文字模糊，文字扭曲，伪汉字，"
       "画面过饱和，构图混乱")


def build(fam, r):
    f = FAMILIES[fam]
    w, h = int(r["width"]), int(r["height"])
    LR.check_size(w, h)
    if f.get("clip2"):
        clip_node = {"class_type": "DualCLIPLoader",
                     "inputs": {"clip_name1": f["clip"], "clip_name2": f["clip2"],
                                "type": f["clip_type"], "device": "default"}}
    else:
        clip_node = {"class_type": "CLIPLoader",
                     "inputs": {"clip_name": f["clip"], "type": f["clip_type"],
                                "device": "default"}}
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": f["unet"], "weight_dtype": "default"}},
        "2": clip_node,
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
    if f.get("clip2"):
        lst = info["DualCLIPLoader"]["input"]["required"]["clip_name2"][0]
        if f["clip2"] not in lst:
            bad.append("DualCLIPLoader.clip_name2 不含 %s" % f["clip2"])
        types = info["DualCLIPLoader"]["input"]["required"]["type"][0]
    else:
        types = info["CLIPLoader"]["input"]["required"]["type"][0]
    if f["clip_type"] not in types:
        bad.append("%s.type 不含 %s"
                   % ("DualCLIPLoader" if f.get("clip2") else "CLIPLoader", f["clip_type"]))
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
    if not argv or argv[0] in ("--list", "--help"):
        print("可用家族：")
        for k, v in FAMILIES.items():
            print("  %-8s steps=%-2d cfg=%.1f  %s" % (k, v["steps"], v["cfg"], v["unet"]))
        print("\n可用类型：", ", ".join(sorted(LT.TYPES)))
        print("\n用法：")
        print("  python model_ab.py --list")
        print("  python model_ab.py --smoke                     # 每个家族跑一张，验图通不通")
        print("  python model_ab.py tarot --seed=20261111")
        print("  python model_ab.py --types=all                 # 10 类 × 全家族")
        print("  python model_ab.py --types=all --models=moss,qwen")
        return 0

    args = [a for a in argv if not a.startswith("--")]
    opts = [a for a in argv if a.startswith("--")]
    models = list(FAMILIES)
    seed = 20261111
    smoke = "--smoke" in opts
    for a in opts:
        if a.startswith("--models="):
            models = a.split("=", 1)[1].split(",")
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a == "--types=all":
            args = sorted(LT.TYPES)
    if smoke:
        args = ["tarot"]
    if not args:
        args = ["tarot"]

    ok = fail = 0
    # 家族在外、类型在内：每个模型只换入一次权重，避免每张图都切模型
    for fam in models:
        bad = probe(fam)
        if bad:
            for b in bad:
                print("[probe-FAIL] %s: %s" % (fam, b))
            fail += len(args)
            continue
        print("\n########## %s  steps=%d cfg=%.1f"
              % (fam, FAMILIES[fam]["steps"], FAMILIES[fam]["cfg"]), flush=True)
        for key in args:
            t = LT.TYPES[key]
            w, h = t["size"]
            rec = dict(name="ab_%s_%d" % (key, seed), prompt=t["prompt"], negative=NEG,
                       width=w, height=h, seed=seed)
            imgs = submit(fam, rec)
            if imgs:
                size = save(fam, key, imgs[0])
                print("[saved]  samples_ab/%s_%s.jpg  %.1fKB"
                      % (key, fam, size / 1024), flush=True)
                ok += 1
            else:
                fail += 1

    print("\n[summary] ok=%d fail=%d（%d 类 × %d 家族）"
          % (ok, fail, len(args), len(models)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
