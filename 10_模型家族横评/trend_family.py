# -*- coding: utf-8 -*-
"""
历史趋势回归 ftrend（E5 · 2026-10-16）
======================================

解决的问题：既有对账（fverify）回答的是「这次 vs 磁盘产物」，
没有「这次 vs 上次」。跑测台账本来就是 append-only 的快照序列，
不拿来比时间就浪费了——同一权重这次 ok 率掉了、耗时涨了，
只有跨快照比才看得见。

设计：
  - **纯文件消费**：只读 JSON/JSONL，不 import 03 轨任何模块
    （Gate ⑥：10 轨只准 import 01，跨轨 import 会被 CI 打红）；
  - 三种快照形态统一归一：
      ① `{"records":[{family,model,prompt,seed,ok,elapsed_s}]}`  归档台账（family-bench-ledger/1）
      ② `{ "family|model|prompt|seed": {ok, elapsed_s, image} }`  现行 ledger.json
      ③ JSONL（时长跑测 result_log.jsonl，字段 tag/ok/elapsed_sec）
  - 判回归三类：ok 率下降（硬）／耗时上涨超阈值（软）／对象消失（软）。

用法（只读，不跑图）：
  python trend_family.py                       # 自动发现默认快照源
  python trend_family.py --sources a.json b.json
  python trend_family.py --json trend.json     # 结果落盘
  python trend_family.py --selftest            # 合成双快照自检（CI 可纳）

退出码：0=无硬回归；1=检出硬回归（可直接当 CI 闸门用）。
"""
import argparse
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMFY_OUT = os.path.join(
    os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI"), "output")

# 默认快照源（按时间从旧到新排；运行时展开，不写死本机绝对路径）
DEFAULT_SOURCES = [
    os.path.join(ROOT, "07_样例输出与数据", "family_bench_20261006", "ledger_sanitized.json"),
    os.path.join(COMFY_OUT, "model_benchmark", "ledger.json"),
]
DEFAULT_DURATION_LOG = os.path.join(ROOT, "03_受控跑测", "h3_duration_logs", "result_log.jsonl")

def display_path(p):
    """把溯源路径写成可公开形态（公开仓红线，见 docs/CONTRIBUTING.md 第 1 条 / CI Gate ⑤）。

    DEFAULT_SOURCES 由运行时展开得到绝对路径，直接写进基线台账就会把本机主目录带进
    公开仓；这里只做展示层归一：仓内→仓内相对，仓外主目录下→%USERPROFILE% 形态。
    """
    ap = os.path.abspath(p)
    home = os.path.expandvars(r"%USERPROFILE%")
    for base, mark in ((ROOT, ""), (home, "%USERPROFILE%")):
        if not base:
            continue
        nb, na = os.path.normcase(base), os.path.normcase(ap)
        if na == nb or na.startswith(nb + os.sep):
            rest = ap[len(base):].lstrip("\\/")
            if not mark:
                return rest or "."
            return os.path.join(mark, rest) if rest else mark
    return ap

SLOWER_PCT_DEFAULT = 25.0


# ---------------- 归一化 ----------------
def _records_from_archived(data):
    """形态①：{'records':[{family,model,prompt,seed,ok,elapsed_s}]}。"""
    out = []
    for r in data.get("records", []):
        out.append({"family": r.get("family"), "model": r.get("model"),
                    "key": "|".join(str(x) for x in (r.get("family"), r.get("model"),
                                                     r.get("prompt"), r.get("seed"))),
                    "ok": bool(r.get("ok")),
                    "elapsed": r.get("elapsed_s") if r.get("ok") else None})
    return out


def _records_from_kv(data):
    """形态②：{'family|model|prompt|seed': {ok, elapsed_s, image}}。"""
    out = []
    for k, v in data.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        parts = str(k).split("|")
        family = parts[0] if parts else None
        model = parts[1] if len(parts) > 1 else None
        out.append({"family": family, "model": model, "key": k,
                    "ok": bool(v.get("ok")),
                    "elapsed": v.get("elapsed_s") if v.get("ok") else None})
    return out


def _records_from_jsonl(path):
    """形态③：JSONL（时长跑测日志），字段 tag/ok/elapsed_sec。"""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
            out.append({"family": "duration", "model": r.get("tag"),
                        "key": str(r.get("tag")), "ok": bool(r.get("ok")),
                        "elapsed": r.get("elapsed_sec") if r.get("ok") else None})
    return out


def load_snapshot(path):
    """读一个快照 → {'label':..., 'path':..., 'records':[...]}；不可读返回 None。"""
    if not os.path.isfile(path):
        return None
    try:
        if path.lower().endswith(".jsonl"):
            recs = _records_from_jsonl(path)
            data = {}
        else:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            recs = _records_from_archived(data) if isinstance(data, dict) and "records" in data \
                else _records_from_kv(data) if isinstance(data, dict) else []
    except Exception as e:                                   # noqa: BLE001
        print("[warn] 快照读取失败 %s: %s" % (path, type(e).__name__))
        return None
    if not recs:
        return None
    label = (data.get("_run_window") if isinstance(data, dict) else None) \
        or time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
    return {"label": label, "path": display_path(path), "records": recs,
            "mtime": os.path.getmtime(path)}


# ---------------- 聚合与比较 ----------------
MODEL_EXT = (".safetensors", ".gguf", ".ckpt", ".bin", ".pt", ".pth", ".sft")


def norm_model(name):
    """权重名归一：剥掉扩展名。

    为什么必须剥：2026-09-30 那批台账记的是 `fluxNSFWUNLOCKED`，2026-10-15 这批记的是
    `fluxNSFWUNLOCKED.safetensors`——同一个权重两种写法，不归一会被当成「旧的消失 +
    新的出现」8 组假回归，把真信号（哪些权重真的没了）淹掉。
    """
    if not name:
        return name
    s = str(name).strip()
    low = s.lower()
    for ext in MODEL_EXT:
        if low.endswith(ext):
            return s[: -len(ext)]
    return s


def aggregate(records, group="model"):
    """按对象聚合 → {key: {n, ok, ok_rate, mean_elapsed}}。

    group='model' 按「家族|权重」聚合（跨 prompt/seed），这是横评真正关心的粒度；
    group='key' 则逐条对比（含 prompt/seed 维度）。
    """
    agg = {}
    for r in records:
        if group == "model":
            k = "%s|%s" % (r.get("family"), norm_model(r.get("model")))
        else:
            k = r["key"]
        a = agg.setdefault(k, {"n": 0, "ok": 0, "elapsed": []})
        a["n"] += 1
        if r["ok"]:
            a["ok"] += 1
            if r.get("elapsed") is not None:
                a["elapsed"].append(float(r["elapsed"]))
    for k, a in agg.items():
        a["ok_rate"] = round(a["ok"] / float(a["n"]), 4) if a["n"] else 0.0
        a["mean_elapsed"] = round(sum(a["elapsed"]) / len(a["elapsed"]), 2) if a["elapsed"] else None
        del a["elapsed"]
    return agg


def compare(prev, cur, slower_pct=SLOWER_PCT_DEFAULT):
    """两个聚合结果 → 逐对象 diff 列表（含 flags）。"""
    rows = []
    for k in sorted(set(prev) | set(cur)):
        p, c = prev.get(k), cur.get(k)
        if p is None:
            rows.append({"object": k, "prev": None, "cur": c, "flags": ["new"]})
            continue
        if c is None:
            rows.append({"object": k, "prev": p, "cur": None, "flags": ["disappeared"]})
            continue
        flags = []
        if c["ok_rate"] < p["ok_rate"]:
            flags.append("ok_rate_down")
        if p.get("mean_elapsed") and c.get("mean_elapsed"):
            delta = (c["mean_elapsed"] - p["mean_elapsed"]) / p["mean_elapsed"] * 100.0
            if delta > slower_pct:
                flags.append("slower")
        else:
            delta = None
        rows.append({"object": k, "prev": p, "cur": c,
                     "delta_ok_rate": round(c["ok_rate"] - p["ok_rate"], 4),
                     "delta_elapsed_pct": round(delta, 1) if delta is not None else None,
                     "flags": flags})
    return rows


def build_report(snapshots, group="model", slower_pct=SLOWER_PCT_DEFAULT):
    """多快照 → 连续两两比较的报告。"""
    snaps = [s for s in (load_snapshot(p) for p in snapshots) if s]
    snaps.sort(key=lambda s: s["mtime"])
    pairs = []
    for i in range(1, len(snaps)):
        prev = aggregate(snaps[i - 1]["records"], group)
        cur = aggregate(snaps[i]["records"], group)
        rows = compare(prev, cur, slower_pct)
        hard = [r for r in rows if "ok_rate_down" in r["flags"]]
        pairs.append({"from": snaps[i - 1]["label"], "to": snaps[i]["label"],
                      "from_path": snaps[i - 1]["path"], "to_path": snaps[i]["path"],
                      "objects": len(rows), "hard": len(hard),
                      "flags": {f: sum(1 for r in rows if f in r["flags"])
                                for f in ("ok_rate_down", "slower", "disappeared", "new")},
                      "rows": rows})
    return {"ok": True, "snapshots": [{"label": s["label"], "path": s["path"],
                                       "records": len(s["records"])} for s in snaps],
            "pairs": pairs, "hard_total": sum(p["hard"] for p in pairs)}


# ---------------- 合成自检（CI 可纳） ----------------
def _selftest():
    """合成「上一版 / 这一版」两快照，验证三类回归都能被检出、且不误报。"""
    steps = []
    tmp = tempfile.mkdtemp(prefix="ftrend_selftest_")

    def snap(name, recs):
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"_schema": "family-bench-ledger/1", "records": recs}, fh)
        return p

    def rec(fam, mdl, pr, sd, ok=True, el=50.0):
        return {"family": fam, "model": mdl, "prompt": pr, "seed": sd,
                "ok": ok, "elapsed_s": el}

    base = [rec("F", "m1", "S1", "s1"), rec("F", "m1", "S1", "s2"),
            rec("F", "m2", "S1", "s1"), rec("F", "m2", "S1", "s2")]
    p_same = snap("a.json", base)
    p_cur = snap("b.json", base)

    # ① 完全一致 → 不得有任何回归
    rep = build_report([p_same, p_cur])
    steps.append(("两快照完全一致时不报回归：flags=%s"
                  % (rep["pairs"][0]["flags"],), rep["hard_total"] == 0))

    # ② ok 率下降（m1 一半失败）→ 必须命中硬回归
    worse = [rec("F", "m1", "S1", "s1"), rec("F", "m1", "S1", "s2", ok=False),
             rec("F", "m2", "S1", "s1"), rec("F", "m2", "S1", "s2")]
    rep = build_report([p_same, snap("c.json", worse)])
    hit = [r for r in rep["pairs"][0]["rows"] if "ok_rate_down" in r["flags"]]
    steps.append(("ok 率下降被判为硬回归（命中 %d 项）" % len(hit), len(hit) == 1))

    # ③ 耗时翻倍 → 必须命中 slower（且不算硬回归）
    slow = [rec("F", "m1", "S1", "s1", el=120.0), rec("F", "m1", "S1", "s2", el=120.0),
            rec("F", "m2", "S1", "s1"), rec("F", "m2", "S1", "s2")]
    rep = build_report([p_same, snap("d.json", slow)])
    sl = [r for r in rep["pairs"][0]["rows"] if "slower" in r["flags"]]
    steps.append(("耗时翻倍被判 slower（命中 %d 项，硬回归 %d）"
                  % (len(sl), rep["hard_total"]), len(sl) == 1 and rep["hard_total"] == 0))

    # ④ 对象消失 → disappeared
    gone = [rec("F", "m1", "S1", "s1"), rec("F", "m1", "S1", "s2")]
    rep = build_report([p_same, snap("e.json", gone)])
    dp = [r for r in rep["pairs"][0]["rows"] if "disappeared" in r["flags"]]
    steps.append(("对象消失被判 disappeared（命中 %d 项）" % len(dp), len(dp) == 1))

    # ⑤ 权重名带不带 .safetensors 必须视为同一对象（否则历史台账全变假回归）
    suffixed = [rec("F", "m1.safetensors", "S1", "s1"), rec("F", "m1.safetensors", "S1", "s2"),
                rec("F", "m2.safetensors", "S1", "s1"), rec("F", "m2.safetensors", "S1", "s2")]
    rep = build_report([p_same, snap("f.json", suffixed)])
    flags = rep["pairs"][0]["flags"]
    steps.append(("扩展名差异不算 disappeared/new：flags=%s" % (flags,),
                  flags.get("disappeared", 0) == 0 and flags.get("new", 0) == 0))
    return steps


# ---------------- CLI ----------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="历史趋势回归：同一对象跨快照对比（只读）")
    ap.add_argument("--sources", nargs="*", default=None, help="快照文件（按 mtime 排序）")
    ap.add_argument("--duration-log", default=None, help="时长跑测 JSONL（单独一路对比）")
    ap.add_argument("--group", default="model", choices=("model", "key"))
    ap.add_argument("--slower-pct", type=float, default=SLOWER_PCT_DEFAULT)
    ap.add_argument("--json", default=None, help="结果写到此 JSON")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        bad = 0
        for msg, ok in _selftest():
            print(("OK   " if ok else "FAIL ") + msg)
            if not ok:
                bad += 1
        return 1 if bad else 0

    sources = a.sources or DEFAULT_SOURCES
    rep = build_report(sources, a.group, a.slower_pct)
    if not rep["snapshots"] or len(rep["snapshots"]) < 2:
        print("[!] 可用快照不足 2 个，无法做趋势对比：%s"
              % [s["path"] for s in rep["snapshots"]])
        if os.path.isfile(DEFAULT_DURATION_LOG):
            rep = build_report([DEFAULT_DURATION_LOG], a.group, a.slower_pct)
            print("（时长日志单快照也不构成趋势；请用 --sources 指定 ≥2 个快照）")
        return 0

    print("快照序列：")
    for s in rep["snapshots"]:
        print("  %-28s %6d 条  %s" % (s["label"], s["records"], s["path"]))
    for pair in rep["pairs"]:
        print("\n=== %s → %s ===" % (pair["from"], pair["to"]))
        print("对象 %d 个 | flags: %s | 硬回归 %d 项" % (pair["objects"], pair["flags"], pair["hard"]))
        for r in pair["rows"]:
            if not r["flags"]:
                continue
            p, c = r.get("prev"), r.get("cur")
            print("  %-46s %s" % (r["object"][:46], ",".join(r["flags"])) +
                  ("" if not (p and c) else
                   "  ok率 %.2f→%.2f  耗时 %s→%s" % (p["ok_rate"], c["ok_rate"],
                                                     p["mean_elapsed"], c["mean_elapsed"])))
        if pair["hard"] == 0:
            print("  无硬回归（ok 率未下降）")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=1)
        print("\njson ->", os.path.abspath(a.json))
    return 1 if rep["hard_total"] else 0


if __name__ == "__main__":
    sys.exit(main())
