# -*- coding: utf-8 -*-
"""
提示词变体闭环（E8 · 2026-10-16）
================================

补的缺口：横评轨已有提示词的**素材层**（fkit SFW 白名单）、**质检层**（fpqc）、
**鲁棒性层**（frobust 长度探针），但三层是并列的——没有「变体矩阵 → 真跑 →
按结果淘汰提示词」这条闭环。本模块把它接上：

  plan   读 fkit 白名单 → 按轴（默认 光位×构图×景别）笛卡尔积生成变体提示词
         → 每条先过 fpqc（文本层硬错直接淘汰，不用浪费 GPU）
         → 可选产出一份 bench_family 用的临时配置 + 提示词文件（0 提交）
  judge  跑测完成后读 ledger → 逐变体×家族统计 ok 率/耗时
         → 淘汰规则：文本层硬错 / 所有家族都跑失败 / ok 率低于阈值
         → 输出淘汰名单 + 存活提示词的家族评分表

边界：
  - 与 lib_sfw_prompts_kit、lib_prompt_qc 同轨（10）互调，Gate ⑥ 放行；
  - 不自己实现素材与规则，全部复用既有库，避免第二套口径；
  - 类目白名单不变：词条只能来自 fkit，不在白名单内的词一条都不生成。

用法：
  python lib_prompt_closedloop.py plan [--axes light_direction,composition,shot_size]
                                       [--per-axis 2] [--n 8] [--out-dir <dir>] [--config <cfg.json>]
  python lib_prompt_closedloop.py judge --ledger <ledger.json> [--variants <plan.json>] [--min-ok-rate 0.5]
  python lib_prompt_closedloop.py selftest
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib_sfw_prompts_kit as kit        # noqa: E402   同轨
import lib_prompt_qc as pqc              # noqa: E402   同轨

DEFAULT_AXES = ("light_direction", "composition", "shot_size")
JOINER = "，"
VARIANT_FMT = "V%02d"
DEFAULT_MIN_OK_RATE = 0.5


# ---------------- plan：变体矩阵 ----------------
def build_variants(axes=DEFAULT_AXES, per_axis=2, seed=None, limit=8, joiner=JOINER):
    """按轴笛卡尔积生成变体（词条一律来自 fkit 白名单）。

    per_axis 为每轴取几条；总数为各轴条数之积，超过 limit 时按序截断。
    """
    pools = []
    for ax in axes:
        if ax not in kit.BUILTIN:
            raise KeyError("未知类目 %r；可选：%s" % (ax, list(kit.CATEGORY_ORDER)))
        pools.append([(ax, v) for v in kit.get(ax, per_axis, seed=seed)])
    combos = [[]]
    for pool in pools:
        combos = [c + [p] for c in combos for p in pool]
    out = []
    for i, c in enumerate(combos[:limit], start=1):
        text = joiner.join(v for _ax, v in c)
        out.append({"id": VARIANT_FMT % i, "text": text,
                    "parts": {ax: v for ax, v in c},
                    "axes": list(axes)})
    return out


def qc_variants(variants, ignore_rules=("too_short",)):
    """每条变体过一遍 fpqc；返回 (带 qc 的 variants, 文本层淘汰名单)。

    check_text 返回的是 **findings 列表**（[{rule,severity,match,detail}]），不是 dict；
    只有 severity=error 的才算淘汰。

    ignore_rules 默认忽略 `too_short`：fpqc 的下限（500 字）是按本仓**整段成稿**
    提示词定的（S1 那类 1000+ 字英文长稿），而变体矩阵是「属性片段组合」，
    长度规则在片段阶段不适用；真正提交前的成稿仍由 fpqc 全量把关（CI Gate ②）。
    要给成稿用，请用 --qc-ignore 覆盖（留空即全量检查）。
    """
    kept, killed = [], []
    for v in variants:
        findings = pqc.check_text(v["text"], name=v["id"]) or []
        if isinstance(findings, dict):                 # 兼容老返回形态
            findings = findings.get("findings") or []
        fatal = [f for f in findings
                 if isinstance(f, dict) and f.get("severity") == "error"
                 and f.get("rule") not in ignore_rules]
        v["qc_flags"] = [f.get("rule") for f in findings if isinstance(f, dict)]
        v["qc_fatal"] = [f.get("rule") for f in fatal]
        if fatal:
            killed.append({"id": v["id"], "text": v["text"],
                           "reason": "文本层 QC：" + ",".join(sorted(set(v["qc_fatal"])))})
        else:
            kept.append(v)
    return kept, killed


def write_prompt_files(variants, out_dir):
    """把变体写成 fbench 能吃的提示词文件（<id>.txt），返回目录。"""
    os.makedirs(out_dir, exist_ok=True)
    for v in variants:
        with open(os.path.join(out_dir, "%s.txt" % v["id"]), "w", encoding="utf-8") as fh:
            fh.write(v["text"] + "\n")
    return out_dir


def make_bench_config(variants, prompt_dir, base_config_path=None, out_path=None,
                      families=None, weights_per_family=1, seeds=None):
    """生成一份临时 bench 配置：只跑这批变体、限定家族/权重/种子。"""
    base_path = base_config_path or os.path.join(HERE, "family_config.json")
    with open(base_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    ids = [v["id"] for v in variants]
    cfg.setdefault("bench", {})
    cfg["bench"]["prompts"] = ids
    # prompt_dir 必须存成**相对 bench_family.py 所在目录**的形态：
    # bench_family 里是 os.path.join(HERE, cfg["bench"]["prompt_dir"])，
    # 存相对仓库根的写法会被拼成 "...\10_模型家族横评\10_模型家族横评\prompt_variants"，
    # 16 个任务全部 SKIP（实测踩到）。
    try:
        cfg["bench"]["prompt_dir"] = os.path.relpath(
            os.path.abspath(prompt_dir), HERE).replace("\\", "/")
    except ValueError:                       # 跨盘符时 relpath 抛错，退回原值
        cfg["bench"]["prompt_dir"] = prompt_dir
    # 用 {pid: 文件名} 映射而不是列表：bench_family 的 find_prompt_file 是
    # `if prompt_files and pid in prompt_files`，对列表会判假（靠 <pid>.txt 兜底）。
    cfg["bench"]["prompt_files"] = {i: "%s.txt" % i for i in ids}
    if seeds:
        cfg["bench"]["seeds"] = list(seeds)
    fams = cfg.get("families") or {}
    keep = families or list(fams)
    trimmed = {}
    for name in keep:
        f = fams.get(name)
        if not f:
            continue
        f = dict(f)
        if weights_per_family:
            f["weights"] = list(f.get("weights") or [])[:weights_per_family]
        trimmed[name] = f
    cfg["families"] = trimmed
    out_path = out_path or os.path.join(prompt_dir, "bench_config.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    return out_path


# ---------------- judge：跑完后淘汰判定 ----------------
def _load_ledger(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    recs = []
    if isinstance(data, dict) and "records" in data:      # 归档形态
        recs = data["records"]
    elif isinstance(data, dict):
        for k, v in data.items():                          # 现行形态 "family|model|prompt|seed"
            if k.startswith("_") or not isinstance(v, dict):
                continue
            parts = str(k).split("|")
            recs.append({"family": parts[0] if parts else None,
                         "model": parts[1] if len(parts) > 1 else None,
                         "prompt": parts[2] if len(parts) > 2 else None,
                         "seed": parts[3] if len(parts) > 3 else None,
                         "ok": bool(v.get("ok")), "elapsed_s": v.get("elapsed_s")})
    return recs


def judge(ledger_path, variants=None, min_ok_rate=DEFAULT_MIN_OK_RATE):
    """读 ledger 判淘汰：产出「淘汰名单 + 存活提示词的家族评分表」。"""
    recs = _load_ledger(ledger_path)
    by_prompt = {}
    for r in recs:
        if not r.get("prompt"):
            continue
        by_prompt.setdefault(str(r["prompt"]), []).append(r)

    known = {v["id"]: v for v in (variants or [])}
    killed, alive = [], []
    for pid in sorted(by_prompt):
        rows = by_prompt[pid]
        fams = sorted({str(r.get("family")) for r in rows})
        n_ok = sum(1 for r in rows if r.get("ok"))
        ok_rate = round(n_ok / float(len(rows)), 4) if rows else 0.0
        elapsed = [float(r["elapsed_s"]) for r in rows if r.get("ok") and r.get("elapsed_s")]
        score = {"prompt": pid, "text": (known.get(pid) or {}).get("text"),
                 "families": fams, "runs": len(rows), "ok": n_ok, "ok_rate": ok_rate,
                 "mean_elapsed": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
                 "per_family": {f: _fam_stat(rows, f) for f in fams}}
        if ok_rate == 0.0 and len(fams) >= 1:
            killed.append({"prompt": pid, "reason": "所有家族均失败（ok 率 0）", "score": score})
        elif ok_rate < min_ok_rate:
            killed.append({"prompt": pid, "reason": "ok 率 %.2f 低于阈值 %.2f" % (ok_rate, min_ok_rate),
                           "score": score})
        else:
            alive.append(score)
    return {"ledger": ledger_path, "runs": len(recs), "prompts": len(by_prompt),
            "killed": killed, "alive": alive, "min_ok_rate": min_ok_rate}


def depersonalize(p):
    """输出路径脱敏：本机主目录改写为 %USERPROFILE% 形态。

    沿用 lib_video_qc / lib_inventory_gate 的同款口径（Gate ⑤ 公开仓红线，
    2026-10-15）：judge/plan 的 --json 会落盘到 07_样例输出与数据/，
    那里是 tracked 目录，ledger 等字段会带本机绝对路径，不脱敏会直接把
    CI 打红。兼容混合分隔符（ledger 实测是正斜杠形态，2026-10-16 修）。
    """
    home = os.path.expandvars(r"%USERPROFILE%")
    if not (home and home != "%USERPROFILE%" and p):
        return p
    if p.replace("/", "\\").startswith(home.replace("/", "\\")):
        return "%USERPROFILE%" + p[len(home):]
    return p


def _sanitize(obj):
    """递归脱敏：JSON 落盘前把字符串里的本机主目录改写成 %USERPROFILE%。"""
    if isinstance(obj, str):
        return depersonalize(obj)
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    return obj


def _dump_json(obj, path):
    """统一 JSON 落盘入口：脱敏后写盘（Gate ⑤）。"""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_sanitize(obj), fh, ensure_ascii=False, indent=1)
    print("json →", os.path.abspath(path))


def _fam_stat(rows, family):
    sub = [r for r in rows if str(r.get("family")) == family]
    if not sub:
        return None
    n_ok = sum(1 for r in sub if r.get("ok"))
    el = [float(r["elapsed_s"]) for r in sub if r.get("ok") and r.get("elapsed_s")]
    return {"runs": len(sub), "ok": n_ok,
            "ok_rate": round(n_ok / float(len(sub)), 4),
            "mean_elapsed": round(sum(el) / len(el), 1) if el else None}


# ---------------- 自检 ----------------
def _selftest():
    """合成：变体生成来自白名单、QC 淘汰生效、judge 三种判定。"""
    steps = []
    vs = build_variants(per_axis=2, limit=8)
    steps.append(("生成 %d 条变体（2×2×2）" % len(vs), len(vs) == 8))
    # 词条必须全部来自白名单
    all_ok = True
    for v in vs:
        for ax, val in v["parts"].items():
            if val not in kit.BUILTIN[ax]:
                all_ok = False
    steps.append(("所有词条都来自 fkit 白名单", all_ok))
    # id 唯一 + 文本非空
    steps.append(("id 唯一且文本非空",
                  len({v["id"] for v in vs}) == len(vs) and all(v["text"] for v in vs)))
    # QC 淘汰：注入一条含否定句的坏文本必须被淘汰（negation 是 error 级，不在忽略表内）
    bad = [{"id": "X01", "text": "不要出现任何文字，无水印", "parts": {}}]
    kept, killed = qc_variants(bad)
    steps.append(("文本层 QC 淘汰生效（否定句被杀：%s）" % bool(killed), bool(killed)))
    # 片段长度不该被 too_short 误杀（该规则针对整段成稿）
    frag = [{"id": "X02", "text": "侧向主光，三分法构图，中景", "parts": {}}]
    kept2, killed2 = qc_variants(frag)
    steps.append(("属性片段不被 too_short 误杀（可用 %d 条）" % len(kept2), len(kept2) == 1))
    # 但显式要求全量检查时必须杀（--qc-ignore 留空）
    _k3, killed3 = qc_variants(frag, ignore_rules=())
    steps.append(("全量检查时 too_short 照样命中", len(killed3) == 1))

    # judge：合成 ledger（一个全失败 / 一个半成功 / 一个全成功）
    import tempfile
    td = tempfile.mkdtemp(prefix="cloop_")
    led = {"A|m|S1|s1": {"ok": False, "elapsed_s": 10}, "B|m|S1|s1": {"ok": False, "elapsed_s": 10},
           "A|m|S2|s1": {"ok": True, "elapsed_s": 20}, "B|m|S2|s1": {"ok": False, "elapsed_s": 20},
           "A|m|S3|s1": {"ok": True, "elapsed_s": 30}, "B|m|S3|s1": {"ok": True, "elapsed_s": 30}}
    p = os.path.join(td, "ledger.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(led, fh)
    # 阈值取 0.6：S1(0.0 全家族失败) 与 S2(0.5 低于阈值) 淘汰，S3(1.0) 存活
    rep = judge(p, min_ok_rate=0.6)
    killed_ids = sorted(k["prompt"] for k in rep["killed"])
    alive_ids = sorted(a["prompt"] for a in rep["alive"])
    steps.append(("judge 淘汰名单=%s 存活=%s" % (killed_ids, alive_ids),
                  killed_ids == ["S1", "S2"] and alive_ids == ["S3"]))
    steps.append(("存活项带家族评分：%s" % (rep["alive"][0]["per_family"] if rep["alive"] else None),
                  bool(rep["alive"]) and rep["alive"][0]["per_family"].get("A", {}).get("ok_rate") == 1.0))
    # Gate ⑤：ledger 字段的本机路径落盘前必须脱敏
    leaked = {"ledger": rep["ledger"], "nested": [{"p": rep["ledger"]}]}
    clean = _sanitize(leaked)
    home = os.path.expandvars("%USERPROFILE%")
    steps.append(("落盘前递归脱敏（%s → %%USERPROFILE%%）" % rep["ledger"],
                  isinstance(clean["ledger"], str)
                  and (not home or not clean["ledger"].startswith(home))
                  and clean["nested"][0]["p"] == clean["ledger"]))
    return steps


# ---------------- CLI ----------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="提示词变体闭环：变体矩阵 → 跑测配置 → 淘汰判定")
    ap.add_argument("mode", nargs="?", default="plan",
                    choices=("plan", "judge", "selftest"))
    ap.add_argument("--axes", default=",".join(DEFAULT_AXES))
    ap.add_argument("--per-axis", type=int, default=2)
    ap.add_argument("--n", type=int, default=8, help="变体上限")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out-dir", default=None, help="变体提示词输出目录")
    ap.add_argument("--config", default=None, help="plan 模式顺带生成的 bench 配置路径")
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--weights-per-family", type=int, default=1)
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    ap.add_argument("--ledger", default=None, help="judge 模式读的 ledger")
    ap.add_argument("--variants", default=None, help="judge 模式读的 plan json（补文本）")
    ap.add_argument("--min-ok-rate", type=float, default=DEFAULT_MIN_OK_RATE)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    if a.mode == "selftest":
        bad = 0
        for msg, ok in _selftest():
            print(("OK   " if ok else "FAIL ") + msg)
            if not ok:
                bad += 1
        return 1 if bad else 0

    if a.mode == "plan":
        axes = tuple(x.strip() for x in a.axes.split(",") if x.strip())
        vs = build_variants(axes, a.per_axis, a.seed, a.n)
        kept, killed = qc_variants(vs)
        print("变体矩阵：轴=%s  生成 %d 条，文本层淘汰 %d 条，可用 %d 条"
              % (",".join(axes), len(vs), len(killed), len(kept)))
        for k in killed:
            print("  [淘汰] %s %s —— %s" % (k["id"], k["text"][:40], k["reason"]))
        for v in kept:
            print("  [可用] %s %s" % (v["id"], v["text"]))
        out = {"axes": list(axes), "variants": kept, "killed": killed}
        if a.out_dir:
            d = write_prompt_files(kept, a.out_dir)
            print("提示词文件 → %s" % d)
            out["prompt_dir"] = d
            if a.config:
                cfg = make_bench_config(kept, d, out_path=a.config, families=a.families,
                                        weights_per_family=a.weights_per_family, seeds=a.seeds)
                print("bench 配置 → %s（家族=%s 权重/家族=%d 种子=%s）"
                      % (cfg, a.families or "全部", a.weights_per_family, a.seeds or "沿用"))
                out["config"] = cfg
        if a.json:
            _dump_json(out, a.json)
        return 0

    # judge
    if not a.ledger:
        print("[x] judge 需要 --ledger <ledger.json>")
        return 2
    variants = None
    if a.variants and os.path.isfile(a.variants):
        with open(a.variants, encoding="utf-8") as fh:
            variants = json.load(fh).get("variants")
    rep = judge(a.ledger, variants, a.min_ok_rate)
    print("跑测记录 %d 条，覆盖 %d 条提示词（阈值 ok 率 %.2f）"
          % (rep["runs"], rep["prompts"], rep["min_ok_rate"]))
    print("\n[淘汰名单] %d 条" % len(rep["killed"]))
    for k in rep["killed"]:
        print("  ✗ %-6s %s —— %s" % (k["prompt"], (k["score"].get("text") or "")[:34], k["reason"]))
    print("\n[存活提示词 × 家族评分] %d 条" % len(rep["alive"]))
    for s in rep["alive"]:
        cells = " ".join("%s:%s%%(%.0fs)" % (f, int((v or {}).get("ok_rate", 0) * 100),
                                             (v or {}).get("mean_elapsed") or 0)
                         for f, v in s["per_family"].items())
        print("  ✓ %-6s 总 ok %d/%d  %s" % (s["prompt"], s["ok"], s["runs"], cells))
    if a.json:
        _dump_json(rep, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
