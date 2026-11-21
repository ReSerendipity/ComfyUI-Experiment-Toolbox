# -*- coding: utf-8 -*-
"""API prompt 静态体检：引用完整性、环路、执行顺序。

对标 pydn/ComfyUI-to-Python-Extension 的 `load_order.py`（递归 DFS），本模块改成
迭代 Kahn 拓扑排序：大图不会触发 Python 递归上限，且能在排序时直接报出环路和悬空引用。

用法：
    python workflow_lint.py <workflow.json|目录>
"""
import json
import os
import sys


def _refs(node):
    """产出该节点 input 里的所有 [node_id, slot] 引用。"""
    for name, value in (node.get("inputs") or {}).items():
        if (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], str) and isinstance(value[1], int)):
            yield name, value[0], value[1]


def lint_api(api):
    """返回 {ok, errors, warnings, order}；不修改入参。"""
    errors, warnings = [], []
    if not isinstance(api, dict):
        return {"ok": False, "errors": ["prompt 顶层不是对象"], "warnings": [], "order": []}
    ids = set(api)
    deps = {k: set() for k in api}
    rev = {k: set() for k in api}
    for node_id, node in api.items():
        if not isinstance(node, dict):
            errors.append("%s: 节点不是对象" % node_id)
            continue
        if not node.get("class_type"):
            errors.append("%s: 缺 class_type" % node_id)
        for input_name, src, slot in _refs(node):
            if src not in ids:
                errors.append("%s.%s: 引用不存在的节点 %s" % (node_id, input_name, src))
                continue
            if slot < 0:
                errors.append("%s.%s: 负 slot %d" % (node_id, input_name, slot))
            if src == node_id:
                errors.append("%s.%s: 自引用" % (node_id, input_name))
                continue
            deps[node_id].add(src)
            rev[src].add(node_id)

    # 迭代 Kahn，按 id 排序保证同一份 prompt 的顺序稳定可复现。
    pending = {k: len(v) for k, v in deps.items()}
    ready = sorted(k for k, v in pending.items() if v == 0)
    order = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for other in sorted(rev.get(cur, ())):
            pending[other] -= 1
            if pending[other] == 0:
                ready.append(other)
        ready.sort()
    if len(order) != len(ids):
        stuck = sorted(ids - set(order))
        errors.append("检测到环或不可达依赖：%s" % ", ".join(stuck[:8]))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "order": order}


def lint_file(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # 兼容 UI 工作流：若带 nodes/links 则提示先跑 flatten.py，而不是硬猜。
    if isinstance(data, dict) and "nodes" in data and "links" in data:
        return {"ok": False, "errors": ["这是 UI 工作流，请先经 flatten.py 转成 API prompt"],
                "warnings": [], "order": []}
    return lint_api(data)


def main(argv):
    target = argv[1] if len(argv) > 1 else "."
    paths = []
    if os.path.isdir(target):
        for root, _dirs, files in os.walk(target):
            for name in sorted(files):
                if name.endswith(".json"):
                    paths.append(os.path.join(root, name))
    else:
        paths.append(target)
    failed = 0
    for path in paths:
        try:
            report = lint_file(path)
        except (OSError, ValueError) as e:
            report = {"ok": False, "errors": ["读取失败: %s" % e], "order": []}
        status = "PASS" if report["ok"] else "FAIL"
        print("%s %s  nodes=%d" % (status, path, len(report.get("order") or [])))
        for err in report["errors"][:5]:
            print("  - " + err)
        failed += 0 if report["ok"] else 1
    print("合计 %d 个文件，失败 %d" % (len(paths), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
