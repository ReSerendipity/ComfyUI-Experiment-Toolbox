# -*- coding: utf-8 -*-
"""
把 Qwen_image_2_1_t2i.json（新版 definitions.subgraphs 格式）扁平化为 ComfyUI API prompt。
仅保留「KSampler -> VAEDecode -> ReservedVRAMSetter -> SaveImageAdvanced」这条主链路
（即子图 output slot 0，也就是顶层 SaveImageAdvanced 实际接收的那一路），
以便只测试采样器/调度器组合，不触发工作流里挂着的 SeedVR2 放大分支。
"""
import json

WF = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image\Qwen_image_2_1_t2i.json"
ID_OFFSET = 1000

w = json.load(open(WF, encoding="utf-8"))
sg = w["definitions"]["subgraphs"][0]
container = [n for n in w["nodes"] if n["id"] == 459][0]
cw = container["widgets_values"]
cwn = container["widgets_values_named"]

# 容器控件（官方原值，一律沿用，仅 sampler/scheduler 由外部注入）
PROMPT = cwn["prompt"]
NEG = cwn["negative_prompt"]
CFG = cwn["cfg"]                 # 1
STEPS = cwn["steps"]             # 25
W = cwn["width"]                 # 1024 (ResolutionSelector: 1:1 / 1MP / multiple 8)
H = cwn["height"]                # 1024
SEED = cwn["seed"]               # 1111119
UNET = cwn["unet_name"]
CLIP = cwn["clip_name"]
VAE = cwn["vae_name"]
SAVE_PREFIX = [n for n in w["nodes"] if n["id"] == 461][0]["widgets_values"][0]

def nid(old):
    return str(old + ID_OFFSET)

def build(sampler, scheduler, filename_prefix):
    return {
        nid(451): {"class_type": "UNETLoader",
                   "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        nid(453): {"class_type": "CLIPLoader",
                   "inputs": {"clip_name": CLIP, "type": "qwen_image", "device": "default"}},
        nid(454): {"class_type": "VAELoader",
                   "inputs": {"vae_name": VAE}},
        nid(456): {"class_type": "EmptyLatentImage",
                   "inputs": {"width": W, "height": H, "batch_size": 1}},
        nid(452): {"class_type": "TextEncodeQwenImage21",
                   "inputs": {"clip": [nid(453), 0],
                              "prompt": PROMPT,
                              "negative_prompt": NEG,
                              "resolution": 1024}},
        nid(458): {"class_type": "KSampler",
                   "inputs": {"model": [nid(451), 0],
                              "positive": [nid(452), 0],
                              "negative": [nid(452), 1],
                              "latent_image": [nid(456), 0],
                              "seed": SEED,
                              "steps": STEPS,
                              "cfg": CFG,
                              "sampler_name": sampler,
                              "scheduler": scheduler,
                              "denoise": 1}},
        nid(457): {"class_type": "VAEDecode",
                   "inputs": {"samples": [nid(458), 0], "vae": [nid(454), 0]}},
        nid(480): {"class_type": "ReservedVRAMSetter",
                   "inputs": {"anything": [nid(457), 0],
                              "reserved": 0.6,
                              "mode": "auto",
                              "seed": 295621904740914,
                              "auto_max_reserved": 0,
                              "clean_gpu_before": False}},
        nid(461): {"class_type": "SaveImageAdvanced",
                   "inputs": {"images": [nid(480), 0],
                              "filename_prefix": filename_prefix,
                              "format": "png",
                              "format.bit_depth": "8-bit",
                              "format.input_color_space": "sRGB"}},
    }

if __name__ == "__main__":
    import sys
    p = build(sys.argv[1] if len(sys.argv) > 1 else "euler",
              sys.argv[2] if len(sys.argv) > 2 else "simple", "ss_test/preview")
    print(json.dumps(p, ensure_ascii=False, indent=1)[:2500])
    print("...")
    print("prompt len:", len(PROMPT), "| seed:", SEED, "steps:", STEPS, "cfg:", CFG, "size:", W, H, "| save_prefix:", SAVE_PREFIX)
