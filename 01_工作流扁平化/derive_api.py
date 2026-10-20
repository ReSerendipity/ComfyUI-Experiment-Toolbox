# -*- coding: utf-8 -*-
"""官方模板 → 可提交 API prompt 的派生层（结构裁剪 + 契约校验 + 模型名动态解析）。

定位：`flatten.py` 只负责「子图 → 扁平 API」，本模块在其上补三件模板派生的必备动作：

1. **开关分支物理裁剪** —— 官方模板普遍带 `ComfySwitchNode` 惰性开关（prompt upsampler、
   SLG / 引导技巧等）。后端对惰性 switch 只跳过「执行」，不跳过「校验」；且未选分支仍留在
   图里会被可达性算法保留，既拖慢首跑也让提示词有被改写的风险。本模块按开关值把下游
   直连到选定分支，再删开关节点本身与失效分支 —— 是物理删除，不是标记。

2. **不可达节点清理** —— 裁剪后从 `Save*`/`Preview*` 反向可达性重算，丢掉孤立节点。

3. **契约校验** —— 提交前用 `/object_info` 逐节点核对：未知输入、必填缺失、连线悬空、
   输出 slot 越界。返回可读错误列表，空列表才算可提交。

模型名（含子目录前缀）一律从 `/object_info` 动态解析，禁止硬编码 —— 模型放进
`models/*/子目录/` 后，合法值是 `子目录\\文件名`，裸名会 `value_not_in_list`。

用法：
    import derive_api as D
    api, _ = flatten.flatten(tpl_path)
    api = D.resolve_switches(api, decisions={"1016": False})   # 关闭 upsampler
    api = D.prune_unreachable(api)
    D.patch(api, {"KSampler": {"steps": 50}, "CLIPLoader": {"type": "moss_image"}})
    errs = D.validate(api)
    assert not errs, errs

命令行自检：
    python derive_api.py <模板.json> [--host http://127.0.0.1:8188]
"""
import json
import os
import urllib.parse
import urllib.request

DEFAULT_HOST = os.environ.get("COMFY_HOST", "http://127.0.0.1:8188")

SWITCH_CLASSES = ("ComfySwitchNode", "ComfySwitch", "SwitchNode")
SINK_CLASSES = ("SaveImage", "SaveImageAdvanced", "SaveImagetoPath", "PreviewImage",
                "PreviewAny", "SaveVideo", "SaveAnimatedWEBP", "VHS_VideoCombine")


def _get(host, path, timeout=30):
    with urllib.request.urlopen(host + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _is_link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)


def resolve_switches(api, decisions=None):
    """把 switch 节点折叠成直连。

    decisions: {node_id: bool}，显式指定某开关取 True/False；未指定的沿用节点自身 switch 值。
    返回新的 api（不原地改）。
    """
    decisions = decisions or {}
    api = json.loads(json.dumps(api))  # 深拷贝
    switch_ids = [k for k, v in api.items() if v["class_type"] in SWITCH_CLASSES]
    folded = []
    for sid in switch_ids:
        node = api[sid]
        sel = decisions.get(sid, node["inputs"].get("switch"))
        key = "on_true" if sel else "on_false"
        target = node["inputs"].get(key)
        if not _is_link(target):
            # 分支是字面值或缺失：无法直连，保留开关交由后端处理
            folded.append((sid, sel, None))
            continue
        for k, v in api.items():
            if k == sid:
                continue
            for iname, iv in list(v["inputs"].items()):
                if _is_link(iv) and iv[0] == sid:
                    v["inputs"][iname] = list(target)
        del api[sid]
        folded.append((sid, sel, target))
    return api, folded


def prune_unreachable(api):
    """从 sink 节点反向重算可达性，删除孤立节点。"""
    api = json.loads(json.dumps(api))
    sinks = [k for k, v in api.items() if v["class_type"] in SINK_CLASSES]
    keep, stack = set(), list(sinks)
    while stack:
        k = stack.pop()
        if k in keep or k not in api:
            continue
        keep.add(k)
        for v in api[k]["inputs"].values():
            if _is_link(v) and v[0] in api and v[0] not in keep:
                stack.append(v[0])
    return {k: v for k, v in api.items() if k in keep}


def patch(api, overrides):
    """按 class_type 覆盖输入值。overrides: {class_type: {param: value}}"""
    api = json.loads(json.dumps(api))
    applied = []
    for k, node in api.items():
        o = overrides.get(node["class_type"])
        if not o:
            continue
        for pk, pv in o.items():
            if pk in node["inputs"]:
                applied.append((node["class_type"], k, pk, node["inputs"][pk], pv))
                node["inputs"][pk] = pv
    return api, applied


def set_by_id(api, node_id, values):
    """按节点 id 精确赋值（用于同类型多实例，如两个 CLIPTextEncode）。"""
    api = json.loads(json.dumps(api))
    if node_id not in api:
        raise KeyError("节点 %s 不存在" % node_id)
    api[node_id]["inputs"].update(values)
    return api


def resolve_models(host=DEFAULT_HOST, family_hint=None, patterns=None):
    """从 /object_info 动态解析三件套真实名（含子目录前缀）。

    patterns: {"unet": [...子串...], "clip": [...], "vae": [...]}，默认按 MOSS-Image 取。
    返回 (unet_name, clip_name, vae_name)；解析结果不唯一时抛错（禁止猜）。
    """
    patterns = patterns or {
        "unet": ["moss_image"],
        "clip": ["qwen3.5_9b"],
        "vae": ["MOSS-Image"],
    }
    unets = _get(host, "/object_info/UNETLoader")["UNETLoader"]["input"]["required"]["unet_name"][0]
    clips = _get(host, "/object_info/CLIPLoader")["CLIPLoader"]["input"]["required"]["clip_name"][0]
    vaes = _get(host, "/object_info/VAELoader")["VAELoader"]["input"]["required"]["vae_name"][0]
    out = []
    for key, pool in (("unet", unets), ("clip", clips), ("vae", vaes)):
        cand = [x for x in pool if any(p.lower() in x.lower() for p in patterns[key])]
        if family_hint:
            narrowed = [x for x in cand if family_hint.lower() in x.lower()]
            if narrowed:
                cand = narrowed
        if len(cand) != 1:
            raise ValueError("%s 解析不唯一（%d 个候选）: %s" % (key, len(cand), cand))
        out.append(cand[0])
    return tuple(out)


def object_info_cache(api, host=DEFAULT_HOST):
    cache = {}
    for node in api.values():
        ct = node["class_type"]
        if ct not in cache:
            try:
                cache[ct] = _get(host, "/object_info/" + urllib.parse.quote(ct))[ct]
            except Exception as e:  # noqa: BLE001
                cache[ct] = {"__error__": str(e)}
    return cache


def validate(api, host=DEFAULT_HOST):
    """提交前结构 + 契约校验。返回错误字符串列表（空 = 可提交）。"""
    errs = []
    oi = object_info_cache(api, host)
    for nid, node in api.items():
        ct = node["class_type"]
        spec = oi.get(ct) or {}
        if "__error__" in spec:
            errs.append("节点 %s 类型 %s 不存在: %s" % (nid, ct, spec["__error__"]))
            continue
        req = spec.get("input", {}).get("required", {})
        opt = spec.get("input", {}).get("optional", {})
        allowed = set(req) | set(opt)
        outs = spec.get("output", [])
        for iname, iv in node["inputs"].items():
            if iname not in allowed:
                errs.append("节点 %s(%s) 未知输入 '%s'" % (nid, ct, iname))
                continue
            if _is_link(iv):
                src = iv[0]
                if src not in api:
                    errs.append("节点 %s(%s).%s 连线悬空 -> %s" % (nid, ct, iname, src))
                else:
                    src_outs = oi.get(api[src]["class_type"], {}).get("output", [])
                    if iv[1] >= len(src_outs):
                        errs.append("节点 %s(%s).%s slot %d 越界（源 %s 仅 %d 个输出）"
                                    % (nid, ct, iname, iv[1], api[src]["class_type"], len(src_outs)))
        for rname in req:
            if rname not in node["inputs"]:
                errs.append("节点 %s(%s) 缺必填输入 '%s'" % (nid, ct, rname))
    return errs


def summary(api):
    lines = ["节点数 %d" % len(api)]
    for k, v in api.items():
        lines.append("  %-5s %-30s %s" % (k, v["class_type"],
                                          json.dumps(v["inputs"], ensure_ascii=False)[:150]))
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import flatten

    path = sys.argv[1]
    host = DEFAULT_HOST
    if "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
    api, _ = flatten.flatten(path)
    api = prune_unreachable(api)
    print(summary(api))
    errs = validate(api, host)
    print("\n校验:", "OK" if not errs else "\n  " + "\n  ".join(errs))
