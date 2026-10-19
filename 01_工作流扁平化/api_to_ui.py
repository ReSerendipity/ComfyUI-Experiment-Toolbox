# -*- coding: utf-8 -*-
"""扁平 API 工作流 → ComfyUI UI 工作流（可在网页 UI 打开）的反向转换器。

flatten.py / derive_api.py 负责「UI/模板 → 可提交 API」；本模块补反方向：
把评测用的扁平 API 图（/prompt 格式）转回 UI 图，便于在网页 UI 里打开、
改参数、人工复核。线性图为主；布局按依赖深度分列，确定性排布。

用法：
    python api_to_ui.py --api my_eval.json --out my_eval_ui --title "评测版"
    python api_to_ui.py --api my_eval.json --out my_eval_ui --orders node_orders.json

--orders：可选的 `node_orders.json`（各 class 的 INPUT/RETURN 顺序，可由
`/object_info` 抓取脚本生成）。提供时连线类型精确；缺省用 "*" 占位。

已知边界：widget 表 WIDGETS 覆盖常用类；遇到未收录 class 会显式报错并
提示扩充（宁可不转也不产出坏图）。动态 combo / autogrow（点号扁平名输入）
的类（如 ReferenceMultiLatent）暂不支持，报错列出。
"""
import argparse, json, sys

# UI widgets_values 顺序（每类的 widget 名，按 UI 顺序）
WIDGETS = {
    "UNETLoader": ["unet_name", "weight_dtype"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "VAELoader": ["vae_name"],
    "CLIPTextEncode": ["text"],
    "ConditioningZeroOut": [],
    "CFGGuider": ["cfg"],
    "KSamplerSelect": ["sampler_name"],
    "Flux2Scheduler": ["steps", "width", "height"],
    "RandomNoise": ["noise_seed", "control_after_generate"],
    "EmptyFlux2LatentImage": ["width", "height", "batch_size"],
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "SamplerCustomAdvanced": [],
    "VAEDecode": [],
    "VAEEncode": [],
    "SaveImage": ["filename_prefix"],
    "LoadImage": ["image", "upload"],
    "KSampler": ["seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "ReferenceLatent": [],
    "ImageScaleToTotalPixels": ["upscale_method", "megapixels", "resolution_steps"],
    "GetImageSize": [],
    "PreviewImage": [],
    "NoteNode": ["text"],
}
DEFAULTS = {"control_after_generate": "fixed", "upload": "image",
            "device": "default", "weight_dtype": "default", "upscale_method": "nearest-exact"}
NUMERIC_DEFAULTS = ("seed", "noise_seed", "steps", "width", "height", "batch_size",
                    "cfg", "denoise", "megapixels")

# 不支持转换的类（动态 combo / autogrow：输入名是点号扁平名，UI 表示不同）
UNSUPPORTED_HINTS = ("ReferenceMultiLatent",)


def convert(api_path, out_path, title, orders=None):
    g = json.load(open(api_path, encoding="utf-8"))
    for nid, n in g.items():
        ct = n.get("class_type", "")
        if ct in UNSUPPORTED_HINTS or any(k in n.get("inputs", {}) for k in
                                          ("resolution.megapixels", "images.image0")):
            raise SystemExit(f"[skip] node {nid} ({ct}) 含动态 combo/autogrow 扁平名输入，"
                             f"UI 表示需手工处理；本转换器不支持。")

    depth = {}
    def dep(nid, seen=()):
        if nid in depth: return depth[nid]
        if nid in seen: return 0
        d = 0
        for v in g[nid].get("inputs", {}).values():
            if isinstance(v, list): d = max(d, dep(str(v[0]), seen + (nid,)) + 1)
        depth[nid] = d; return d
    for nid in g: dep(nid)

    order = sorted(g, key=lambda n: (depth[n], int(n) if n.isdigit() else 0))
    idmap = {old: i + 1 for i, old in enumerate(order)}
    nodes, links = [], []
    link_id = 0
    by_id = {}
    for old in order:
        n = g[old]; ct = n["class_type"]
        if ct not in WIDGETS:
            raise SystemExit(f"[unknown] class 未收录 widget 表：{ct}（节点 {old}）。"
                             f"请在 WIDGETS 中补该类的 widget 顺序后重试。")
        wv = []
        for w in WIDGETS[ct]:
            v = n.get("inputs", {}).get(w)
            if v is None or isinstance(v, list):
                v = DEFAULTS.get(w, 0 if w in NUMERIC_DEFAULTS else "")
            wv.append(v)
        node = {"id": idmap[old], "type": ct,
                "pos": [60 + depth[old] * 400, 60 + (order.index(old) % 6) * 220],
                "size": [340, 130], "flags": {}, "order": order.index(old), "mode": 0,
                "inputs": [], "outputs": [],
                "properties": {"Node name for S&R": ct},
                "widgets_values": wv}
        by_id[old] = node; nodes.append(node)
    for old in order:
        n = g[old]; node = by_id[old]
        for in_name, v in n.get("inputs", {}).items():
            if not isinstance(v, list): continue
            src_old, slot = str(v[0]), int(v[1])
            src = by_id[src_old]
            if orders and src["type"] in orders:
                ret = orders[src["type"]]["return"]
                itype = ret[slot] if slot < len(ret) else "*"
            else:
                itype = "*"
            link_id += 1
            while len(src["outputs"]) <= slot:
                src["outputs"].append({"name": f"out{len(src['outputs'])}", "type": itype, "links": []})
            src["outputs"][slot]["links"].append(link_id)
            node["inputs"].append({"name": in_name, "type": itype, "link": link_id})
            links.append([link_id, src["id"], slot, node["id"], len(node["inputs"]) - 1, itype])
    ui = {"id": "api2ui-" + out_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].split(".")[0],
          "revision": 0, "last_node_id": max(idmap.values()), "last_link_id": link_id,
          "nodes": nodes, "links": links, "groups": [], "config": {},
          "extra": {"title": title, "note": "由扁平 API 工作流转换（api_to_ui.py）；参数与提交记录一致"},
          "version": 0.4}
    errs = []
    ids = {n["id"] for n in nodes}
    for l in links:
        if l[1] not in ids or l[3] not in ids: errs.append(f"link {l[0]} dangling")
    for n in nodes:
        for i in n["inputs"]:
            if i["link"] not in {l[0] for l in links}:
                errs.append(f"node {n['id']} input {i['name']} link missing")
    if errs:
        raise SystemExit("UI 转换结构自检失败: " + "; ".join(errs))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ui, f, ensure_ascii=False, indent=1)
    print(f"[ok] {out_path}  nodes={len(nodes)} links={len(links)}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="扁平 API 工作流 → UI 工作流（反向转换）")
    ap.add_argument("--api", required=True, help="扁平 API 工作流 JSON（/prompt 格式）")
    ap.add_argument("--out", required=True, help="输出 UI 工作流路径（.json）")
    ap.add_argument("--title", default="API→UI 转换", help="UI 图标题")
    ap.add_argument("--orders", default=None, help="可选 node_orders.json（class 的 INPUT/RETURN 顺序），提供则连线类型精确")
    a = ap.parse_args()
    orders = json.load(open(a.orders, encoding="utf-8")) if a.orders else None
    convert(a.api, a.out, a.title, orders)


if __name__ == "__main__":
    main()
