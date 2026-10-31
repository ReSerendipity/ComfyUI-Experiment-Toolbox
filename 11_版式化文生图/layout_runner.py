# -*- coding: utf-8 -*-
"""版式化文生图 · API 直连驱动
================================

不经过 ComfyUI 前端、不改官方模板 JSON：直接把**展开后的子图**写成 API 格式
prompt，提交到 `/prompt`，轮询 `/history/<id>` 取产物。

为什么不用模板原图跑：
  官方 `MOSS-Image-SFT-t2i(官方模板).json` 的正文包在 `definitions.subgraphs` 里，
  提示词/步数/CFG 是**容器节点上的提升 widget**。改子图内部节点不生效，必须同时改
  `容器.widgets_values[]` + `widgets_values_named{}` 并触发回调，还容易踩「改文件被
  ComfyUI 自动保存覆盖」。本驱动把子图摊平成 9 个节点直接提交，参数就是参数，
  无隐式状态。

模型名口径（2026-10-29 实测）：
  模型放在 `models/*/MOSS-Image/` 子目录时，`/object_info` 返回的合法值是
  `MOSS-Image\\文件名`；写裸文件名会被判 `value_not_in_list`，节点输出被忽略、
  下游剪枝，最终 `status=success` 但 `outputs={}`——静默无图，最难查。
  本模块默认值已带子目录前缀，可用环境变量或 recipe 字段覆盖。

环境变量（可选）：
  COMFY_SERVER  默认 http://127.0.0.1:8188
  MOSS_UNET / MOSS_CLIP / MOSS_VAE  覆盖三件套

单独运行：
  python layout_runner.py recipe.json          # 批量跑 recipe 列表
  python layout_runner.py --probe              # 只做 /object_info 契约校验
"""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

SERVER = os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188").rstrip("/")

UNET = os.environ.get("MOSS_UNET", r"MOSS-Image\moss_image_sft_int8_convrot.safetensors")
CLIP = os.environ.get("MOSS_CLIP", r"MOSS-Image\qwen3.5_9b_int8_convrot.safetensors")
VAE = os.environ.get("MOSS_VAE", r"MOSS-Image\flux2-vae.safetensors")

# 官方推荐负向词（OpenMOSS USERGUIDE）
NEG_DEFAULT = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"

# 官方推荐：总像素 1M / 1.5M / 2M，宽高必须是 16 的倍数
MULTIPLE = 16


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(SERVER + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(path):
    with urllib.request.urlopen(SERVER + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def check_size(w, h):
    """分辨率守卫：宽高必须是 16 的倍数，总像素落在 0.25M~4M。"""
    if w % MULTIPLE or h % MULTIPLE:
        raise ValueError("%dx%d 不是 %d 的倍数；MOSS-Image 要求宽高均为 %d 的倍数"
                         % (w, h, MULTIPLE, MULTIPLE))
    mp = w * h / 1e6
    if not (0.25 <= mp <= 4.0):
        raise ValueError("%dx%d = %.2fM 像素，超出官方推荐区间 0.25M~4M" % (w, h, mp))
    return mp


def probe():
    """校验三件套在服务端 /object_info 里确实是合法值，避免静默无图。"""
    try:
        info = _get("/object_info")
    except urllib.error.URLError as e:
        print("  [x] 连不上 %s（%s）；先启动 ComfyUI" % (SERVER, e.reason))
        return ["server"]
    checks = [
        ("UNETLoader", "unet_name", UNET),
        ("CLIPLoader", "clip_name", CLIP),
        ("VAELoader", "vae_name", VAE),
    ]
    bad = []
    for node, field, value in checks:
        spec = info.get(node, {}).get("input", {}).get("required", {}).get(field, [])
        choices = spec[0] if spec and isinstance(spec[0], list) else []
        ok = value in choices
        print("  %-6s %-10s %s  %s" % ("ok" if ok else "MISS", node, value, "" if ok else
                                       "（不在下拉表；候选含 MOSS-Image 的有：%s）"
                                       % [c for c in choices if "MOSS" in c]))
        if not ok:
            bad.append(node)
    return bad


def build(r):
    """把一条 recipe 摊平成 API 格式 prompt（9 个节点，无子图）。"""
    w, h = int(r["width"]), int(r["height"])
    check_size(w, h)
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": r.get("unet", UNET), "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": r.get("clip", CLIP), "type": "moss_image",
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": r.get("vae", VAE)}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": r["prompt"]}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": r.get("negative", NEG_DEFAULT)}},
        "6": {"class_type": "EmptyFlux2LatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0], "seed": int(r["seed"]),
                         "steps": int(r.get("steps", 30)),
                         "cfg": float(r.get("cfg", 4.0)),
                         "sampler_name": r.get("sampler", "euler"),
                         "scheduler": r.get("scheduler", "simple"), "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": r["name"]}},
    }
    if r.get("slg"):
        # SkipLayerGuidanceDiTSimple 插在 UNET 与 KSampler 之间；官方建议跳过层 22
        g["10"] = {"class_type": "SkipLayerGuidanceDiTSimple",
                   "inputs": {"model": ["1", 0], "double_layers": str(r.get("slg_layer", "22")),
                              "single_layers": "", "scale": float(r.get("slg_scale", 0.5)),
                              "start_percent": 0.0, "end_percent": 1.0}}
        g["7"]["inputs"]["model"] = ["10", 0]
    return g


def run(r, timeout_s=3600, quiet=False):
    """提交一条 recipe 并等待产物，返回 images 列表（失败返回 None）。"""
    g = build(r)
    t0 = time.time()
    try:
        resp = _post("/prompt", {"prompt": g, "client_id": "layout-runner"})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("[reject] %s HTTP %s\n%s" % (r["name"], e.code, body[:2000]), flush=True)
        return None
    pid = resp["prompt_id"]
    if not quiet:
        print("[submit] %-22s %dx%d steps=%d cfg=%.1f %s seed=%d"
              % (r["name"], r["width"], r["height"], r.get("steps", 30),
                 r.get("cfg", 4.0), r.get("sampler", "euler"), r["seed"]), flush=True)
    while True:
        time.sleep(3)
        h = _get("/history/%s" % pid)
        if pid not in h:
            if time.time() - t0 > timeout_s:
                print("[timeout] %s" % r["name"], flush=True)
                return None
            continue
        entry = h[pid]
        st = entry.get("status", {})
        if st.get("status_str") == "error":
            print("[error] %s\n%s" % (r["name"], json.dumps(st, ensure_ascii=False)[:2000]),
                  flush=True)
            return None
        imgs = []
        for _nid, o in entry.get("outputs", {}).items():
            imgs.extend(o.get("images", []))
        if imgs:
            if not quiet:
                print("[done]   %-22s %.1fs -> %s"
                      % (r["name"], time.time() - t0,
                         ", ".join("%s/%s" % (i.get("subfolder", ""), i["filename"])
                                   for i in imgs)), flush=True)
            return imgs
        if st.get("status_str") == "success":
            # 典型症状：模型名不在下拉表 → 节点被忽略 → 下游剪枝 → success 但无图
            print("[warn]   %s success 但 outputs 为空；先跑 --probe 校验三件套名称"
                  % r["name"], flush=True)
            return None


def load_recipes(path):
    data = json.load(open(path, encoding="utf-8"))
    recs = data if isinstance(data, list) else [data]
    for r in recs:
        if "seed" not in r:
            r["seed"] = random.randint(1, 2 ** 48)
    return recs


def main(argv):
    if "--probe" in argv:
        print("[probe] %s" % SERVER)
        bad = probe()
        print("[probe] %s" % ("全部通过" if not bad else "缺失：%s" % ", ".join(bad)))
        return 0 if not bad else 1
    if not argv:
        print(__doc__)
        return 2
    recs = load_recipes(argv[0])
    out = []
    for r in recs:
        imgs = run(r)
        out.append({"name": r["name"], "seed": r["seed"], "images": imgs})
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if all(x["images"] for x in out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
