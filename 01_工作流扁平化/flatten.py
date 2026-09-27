# -*- coding: utf-8 -*-
"""
通用「子图格式工作流 → API prompt」扁平化器（含 bypass 透传与可达性裁剪）。

规则（2026-09-23 验证）：
  1. 容器 = 顶层 type 为 UUID（对应 definitions.subgraphs[].id）的节点
  2. 容器输入（-10）：sg.inputs[i].linkIds → origin_id==-10 & origin_slot==i 的 link，
     其 (target_id, target_slot) 指明注入「内部节点第 target_slot 个输入」；
     容器 positional widgets_values[i] 即该输入的值。
     ⚠️ 必须按 target_slot 对齐，不能用名字匹配（容器 input 名与内部语义会错位）
  3. 容器输出（-20）：sg.outputs[j].linkIds → target_id==-20 & target_slot==j 的 link，
     其 (origin_id, origin_slot) 即容器第 j 个输出的来源
  4. mode==4 = bypass：删除该节点，其下游接到其上游
  5. 只保留从 Save*/Preview* 反向可达的节点
"""
import json


def _containers(w):
    return [n for n in w["nodes"]
            if isinstance(n.get("type"), str) and "-" in n["type"] and len(n["type"]) > 30]


def _link(x):
    if isinstance(x, dict):
        return dict(id=x.get("id"), origin_id=x.get("origin_id"), origin_slot=x.get("origin_slot"),
                    target_id=x.get("target_id"), target_slot=x.get("target_slot"))
    if isinstance(x, (list, tuple)) and len(x) >= 5:
        return dict(id=x[0], origin_id=x[1], origin_slot=x[2], target_id=x[3], target_slot=x[4])
    return None


def flatten(path, overrides=None):
    """返回 (api_prompt, meta)。overrides: {class_type 或 原始数字ID: {参数: 值}}"""
    w = json.load(open(path, encoding="utf-8"))
    overrides = overrides or {}
    warnings = []
    sg_defs = {s["id"]: s for s in w.get("definitions", {}).get("subgraphs", [])}
    conts = _containers(w)
    cont_ids = [c["id"] for c in conts]

    idmap, off = {}, 1000
    for c in conts:
        for n in sg_defs.get(c["type"], {}).get("nodes", []):
            if n.get("id", 0) >= 0:
                idmap[(c["type"], n["id"])] = str(n["id"] + off)
        off += 1000
    for n in w["nodes"]:
        if n not in conts and n.get("id", 0) >= 0:
            idmap[("__top__", n["id"])] = "t%d" % n["id"]

    def nid(sg, old):
        return None if old < 0 else (idmap.get((sg, old)) or idmap.get(("__top__", old)))

    nodes, slot_names, links, oldids = {}, {}, {}, {}

    def add_node(sg, n):
        key = nid(sg, n["id"])
        if key is None:
            return
        ins, names = {}, []
        wv, wi = list(n.get("widgets_values") or []), 0
        # 关键：只要输入带 'widget' 标记就占一个位置值——即使它同时被连线
        # （ComfyUI 把「已连线」的 widget 值也照常序列化，作为回退值；先把 widget 填好，
        #   再用 links 覆盖，语义与前端一致）
        for inp in n.get("inputs", []):
            names.append(inp["name"])
            if "widget" not in inp:
                continue
            if wi >= len(wv):
                break
            val = wv[wi]
            if inp["name"] == "seed" and wi + 1 < len(wv) and isinstance(wv[wi + 1], str) \
                    and wv[wi + 1] in ("fixed", "randomize", "increment", "decrement"):
                wi += 1
            ins[inp["name"]] = val
            wi += 1
        nodes[key] = {"class_type": n.get("type"), "inputs": ins, "mode": n.get("mode", 0)}
        if n.get("title"):
            nodes[key]["_meta"] = {"title": n["title"]}
        slot_names[key] = names
        oldids[key] = n["id"]

    for c in conts:
        for n in sg_defs.get(c["type"], {}).get("nodes", []):
            if n.get("id", 0) >= 0:
                add_node(c["type"], n)
    for n in w["nodes"]:
        if n not in conts and n.get("id", 0) >= 0:
            add_node("__top__", n)

    # 内部连线
    for c in conts:
        for raw in sg_defs.get(c["type"], {}).get("links", []):
            l = _link(raw)
            if not l:
                continue
            s, t = nid(c["type"], l["origin_id"]), nid(c["type"], l["target_id"])
            if s and t:
                links.setdefault(t, {})[l["target_slot"]] = [s, l["origin_slot"]]

    # 容器输入注入（按 target_slot 对齐）
    ext_out = {}
    for c in conts:
        sg = sg_defs.get(c["type"], {})
        pos = list(c.get("widgets_values") or [])
        sg_links = [x for x in (_link(y) for y in sg.get("links", [])) if x]
        by_id = {n["id"]: n for n in sg.get("nodes", [])}
        for i, sinp in enumerate(sg.get("inputs", [])):
            for l in sg_links:
                if l["origin_id"] == -10 and l["origin_slot"] == i:
                    tid = nid(c["type"], l["target_id"])
                    src = by_id.get(l["target_id"])
                    if tid in nodes and src:
                        ins = src.get("inputs", [])
                        if l["target_slot"] < len(ins) and i < len(pos):
                            pname = ins[l["target_slot"]]["name"]
                            # 类型守卫：工作流的 positional 数组可能损坏（如 height 位置被塞了模型文件名）。
                            # 若目标输入原本是数值、而容器给的是非数值字符串，则不注入、保留节点自身值。
                            cur = nodes[tid]["inputs"].get(pname)
                            bad = (isinstance(cur, (int, float)) and not isinstance(cur, bool)
                                   and not isinstance(pos[i], (int, float))
                                   and cur is not None)
                            if bad:
                                warnings.append("%s: 容器 %s 的 %s 值 %r 类型不符（目标输入本为数值），"
                                                "已保留节点原值 %r" % (path, c["id"], pname, str(pos[i])[:40], cur))
                            else:
                                nodes[tid]["inputs"][pname] = pos[i]
                    break
        for j, sout in enumerate(sg.get("outputs", [])):
            for lid in (sout.get("linkIds") or []):
                for l in sg_links:
                    if l["id"] == lid and l["target_id"] == -20:
                        ext_out[(c["id"], j)] = [nid(c["type"], l["origin_id"]), l["origin_slot"]]

    # 顶层连线
    for raw in w.get("links", []):
        l = _link(raw)
        if not l:
            continue
        if l["origin_id"] in cont_ids:
            src = ext_out.get((l["origin_id"], l["origin_slot"]))
            t = nid("__top__", l["target_id"])
            if src and src[0] and t:
                links.setdefault(t, {})[l["target_slot"]] = list(src)
        else:
            s, t = nid("__top__", l["origin_id"]), nid("__top__", l["target_id"])
            if s and t:
                links.setdefault(t, {})[l["target_slot"]] = [s, l["origin_slot"]]

    # bypass 透传（必须递归解析：bypass 节点可能成链）
    bypassed = {k for k, v in nodes.items() if v.get("mode") == 4}

    def resolve(v):
        if v is None:
            return None
        sid, slot = v[0], v[1]
        n = 0
        while sid in bypassed and n < 64:
            nxt = None
            for s in sorted(links.get(sid, {})):
                nxt = links[sid][s]
                break
            if nxt is None:
                return None
            sid, slot = nxt[0], nxt[1]
            n += 1
        return [sid, slot]

    for t, mp in links.items():
        for slot, v in list(mp.items()):
            r = resolve(v)
            if r is None:
                mp.pop(slot)
            else:
                mp[slot] = r
    # 解析完成后再删除 bypass 节点本身
    for key in list(bypassed):
        nodes.pop(key, None); links.pop(key, None); slot_names.pop(key, None); oldids.pop(key, None)

    # 兜底：bypass 链若因上游未连线而断掉 model，直接接到 UNETLoader
    #（bypass 的 LoRA 本身是 no-op，接回 UNETLoader 与前端语义一致）
    unets = [k for k, v in nodes.items() if v["class_type"] == "UNETLoader"]
    if unets:
        for k, v in nodes.items():
            if v["class_type"] in ("KSampler", "KSamplerAdvanced", "ModelSamplingAuraFlow",
                                   "ModelSamplingFlux", "ModelSamplingSD3", "CFGGuider", "BasicGuider"):
                if "model" not in v["inputs"] and not any(
                        slot_names.get(k, [])[s] == "model" for s in links.get(k, {}) if s < len(slot_names.get(k, []))):
                    names = slot_names.get(k, [])
                    if "model" in names:
                        links.setdefault(k, {})[names.index("model")] = [unets[0], 0]

    # 可达性裁剪
    sinks = [k for k, v in nodes.items()
             if v["class_type"] in ("SaveImage", "SaveImageAdvanced", "SaveImagetoPath", "PreviewImage")]
    keep, stack = set(), list(sinks)
    while stack:
        k = stack.pop()
        if k in keep:
            continue
        keep.add(k)
        for v in links.get(k, {}).values():
            if v[0] in nodes and v[0] not in keep:
                stack.append(v[0])
    for k in list(nodes):
        if k not in keep:
            del nodes[k]; links.pop(k, None); slot_names.pop(k, None)

    # 组装 API
    api = {}
    for k, nd in nodes.items():
        ins = dict(nd["inputs"])
        for slot, v in links.get(k, {}).items():
            names = slot_names.get(k, [])
            if slot < len(names):
                ins[names[slot]] = [v[0], v[1]]
        node = {"class_type": nd["class_type"], "inputs": ins}
        if "_meta" in nd:
            node["_meta"] = nd["_meta"]
        api[k] = node

    # 应用覆盖（按 class_type 或原始 id）
    applied = []
    for key, node in api.items():
        o = overrides.get(node["class_type"]) or overrides.get(oldids.get(key))
        if o:
            for pk, pv in o.items():
                if pk in node["inputs"]:
                    applied.append((node["class_type"], oldids.get(key), pk, node["inputs"][pk], pv))
                    node["inputs"][pk] = pv
    for m in warnings:
        print("[flatten 警告] " + m)
    return api, applied


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else \
        r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image\Z_image_turbo.json"
    api, _ = flatten(p)
    print("节点数:", len(api))
    for k, v in api.items():
        print(" ", k, v["class_type"], "|", json.dumps(v["inputs"], ensure_ascii=False)[:150])
