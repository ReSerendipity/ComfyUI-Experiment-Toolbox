# -*- coding: utf-8 -*-
"""
模型家族横评 P1 增强 · lib③ ledger 与产物树互验 + 重放（ledger verify）。

台账是横评唯一的「跑过没跑过」判据：bench_family 每张图实时写
    ledger.json : {"<family>|<weight>|<prompt>|<seed>": {"ok","image","elapsed_s"}}
    <root>/<family>/<weight去扩展名>/<prompt>/s<seed>.{png,workflow.json,params.json,result.json}
台账与产物树**任何一侧单独成立都不算数**：台账写 ok=true 但 PNG 被删（报告照样引用
这张图、或 analyze 读不到文件）、PNG 在盘上但台账丢了（续跑会重跑一遍白烧 GPU）、
三件套缺一个（参数证据链断裂，事后无法复现这张图是哪个链路跑出来的）。
本库把这两侧逐条对账，全部**只读**。

思路出处（只借鉴思路，不 import、不拷项目专属字段）
    · Picture/tools/batch15_audit9_restore_ledger.py / _ledger_simverify.py /
      _ledger_fixpoint.py 的 docstring：台账是「可重放的观测真值」，与产物对不上时
      要么以台账为准，要么以产物为准，必须靠**双向对账 + 重放比对**来定谁在撒谎，
      而不是直接改文件。本库把那个思路收成 verify()：重放 result.json 与 ledger 的
      ok/elapsed/image 三项逐条比对，把「台账记的」和「盘上真的」都摆出来。
    · Picture/tools/inventory_gate.py 的门禁语义：漂移先列明细再谈处置。

五类对账（本库的主干，verify() 的 counts 里就是这五个数）
    ① missing_png  台账有记录但 PNG 不在盘上（含 ok=true 却无 image 字段）
    ② orphan_png   PNG 在盘上但台账无对应记录（续跑会白重跑）
    ③ failed       台账 ok=false 的项（附 result.json 里的 stage/error）
    ④ triple_gap   三件套 params/workflow/result 缺失（PNG 在但证据链断）
    ⑤ dup_key      重复 key：同一 task 落到多张 PNG（SaveImage 自动 _00001 后缀
                    造成的历史副本），或 ledger 里两个写法不同但规范化后同一 task
附加（不计入五类，另列 extras，供人判断）
    replay_mismatch  重放 result.json 后 ok/elapsed_s/image 与台账不一致
    path_anomaly     台账里 image 指向的路径与规范路径不是同一文件（分隔符/位置漂移）
    elapsed 统计     每 family 的张数/成功数/耗时合计与中位数（给续跑排期用）

plan_rerun(report) -> 缺失任务清单：把①③④⑤转成「该重跑哪些 task」的清单
    （family, weight, prompt, seed, reason, priority），本任务**只产出清单、不接线**，
    由后续集成方决定怎么喂回 bench_family。

零依赖（纯标准库）。不 import bench_family / analyze_family，故 import 无副作用。

用法（必须用 ComfyUI 自带 python）：
    python lib_ledger_verify.py --root "C:/.../ComfyUI/output/model_benchmark"
    python lib_ledger_verify.py --root <输出根> --ledger <ledger.json> --json
    python lib_ledger_verify.py --root <输出根> --plan          # 只打续跑清单
    python lib_ledger_verify.py --selftest                      # 合成台账五态演练
退出码：0 五类全 0 / 1 有对不上的项（已列明细）/ 2 用法或 IO 错。
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = r"C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI/output/model_benchmark"

KEY_SEP = "|"
TRIAD = (".params.json", ".workflow.json", ".result.json")
PNG = ".png"
# SaveImage 会给 filename_prefix 自动加 _00001 后缀；若前缀已指向最终目录，
# 同一张图会在目录里留下 s123.png 与 s123_00001.png 两份 → 必须当重复 key 报出来。
STEM_SUFFIX_RE = re.compile(r"_\d{5}$")

# 五类（顺序即报告与退出码的主干）
PRIMARY = ("missing_png", "orphan_png", "failed", "triple_gap", "dup_key")


class VerifyError(Exception):
    """用法/IO 错 → main() 映射为退出码 2。"""


# ── 规范化工具 ────────────────────────────────────────────────────────────
def parse_key(key):
    """"fam|weight|S1|123" -> (fam, weight, prompt, seed_int)；字段数不对返回 None。"""
    parts = str(key).split(KEY_SEP)
    if len(parts) != 4:
        return None
    fam, weight, pid, seed = parts
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        return None
    return (fam, weight, pid, seed)


def norm_task(fam, weight, pid, seed):
    """任务四元组（权重去扩展名、seed 归一），用于跨写法判重。"""
    return (fam, os.path.splitext(weight)[0], pid, int(seed))


def task_dir(root, task):
    fam, wstem, pid, _ = task
    return os.path.join(root, fam, wstem, pid)


def task_stem(root, task):
    return os.path.join(task_dir(root, task), "s%d" % task[3])


def canonical_key(task):
    return KEY_SEP.join([task[0], task[1], task[2], str(task[3])])


def _triple_key(item):
    """triple_gap 条目的 task 身份：台账侧条目带原始 key（可能带扩展名），
    产物树侧条目直接是规范 key，统一归一成规范 key 才能判重。"""
    k = item.get("task") or item.get("key")
    tk = parse_key(k) if k else None
    return canonical_key(norm_task(*tk)) if tk else k


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _norm_path(p):
    return os.path.normcase(os.path.abspath(str(p).replace("\\", os.sep).replace("/", os.sep)))


# ── 产物树扫描 ────────────────────────────────────────────────────────────
def scan_tree(root):
    """扫 <root>/<family>/<wstem>/<prompt>/ 下所有 PNG → {task: [png 路径, ...]}。

    只认三层目录族：family / wstem / prompt，第四层是 s<seed>.png。
    目录不存在返回空 dict（由调用方决定是不是错）。
    """
    out = defaultdict(list)
    if not os.path.isdir(root):
        return out
    for fam in sorted(os.listdir(root)):
        fd = os.path.join(root, fam)
        if not os.path.isdir(fd):
            continue
        for wstem in sorted(os.listdir(fd)):
            wd = os.path.join(fd, wstem)
            if not os.path.isdir(wd):
                continue
            for pid in sorted(os.listdir(wd)):
                pd = os.path.join(wd, pid)
                if not os.path.isdir(pd):
                    continue
                for fn in sorted(os.listdir(pd)):
                    if not fn.lower().endswith(PNG):
                        continue
                    m = re.match(r"^s(\d+)(_\d{5})?$", os.path.splitext(fn)[0])
                    if not m:
                        out[("?", fam, wstem, pid, fn)].append(os.path.join(pd, fn))
                        continue
                    task = (fam, wstem, pid, int(m.group(1)))
                    out[task].append(os.path.join(pd, fn))
    return out


# ── 主 API：verify ────────────────────────────────────────────────────────
def verify(root, ledger=None, ledger_path=None, check_triad=True, check_replay=True):
    """台账 × 产物树双向对账（+ 重放 result.json）。全部只读。

    参数
        root        跑测输出根（含 family 层）
        ledger      已解析的 ledger dict；不给则按 ledger_path / <root>/ledger.json 读
        ledger_path ledger 文件路径
        check_triad 是否检查三件套（默认查）
        check_replay 是否重放 result.json 与台账比对（默认查）
    返回 report dict：
        counts   {五类 + extras 各计数}
        lists    {五类明细 + extras 明细}
        stats    {张数/成功/耗时/每 family 明细}
        rerun    plan_rerun 的产物（见下）
        ok / exit_code
    """
    root = os.path.abspath(root)
    if ledger is None:
        lp = ledger_path or os.path.join(root, "ledger.json")
        if not os.path.isfile(lp):
            raise VerifyError("找不到台账：%s（也没有传 --ledger）" % lp)
        ledger = _read_json(lp)
        if ledger is None:
            raise VerifyError("台账不是合法 JSON：%s" % lp)
    if not isinstance(ledger, dict):
        raise VerifyError("台账顶层不是 dict（实际 %s）" % type(ledger).__name__)

    tree = scan_tree(root)

    # 台账 → task
    led_tasks, bad_keys, dup_keys, led_seen = {}, [], [], set()
    for k, v in ledger.items():
        tk = parse_key(k)
        if tk is None:
            bad_keys.append(k)
            continue
        nt = norm_task(*tk)
        if nt in led_seen:
            dup_keys.append({"key": canonical_key(nt), "raw_key": k,
                             "canonical": canonical_key(nt),
                             "reason": "ledger 里两个 key 规范化后同一 task"})
        led_seen.add(nt)
        led_tasks[nt] = {"raw_key": k, "value": v if isinstance(v, dict) else {}}

    missing_png, failed, replay_mismatch, path_anomaly = [], [], [], []
    for nt, rec in sorted(led_tasks.items()):
        v = rec["value"]
        pngs = tree.get(nt, [])
        ok = bool(v.get("ok"))
        img = v.get("image")
        if ok and not pngs:
            reason = "台账 ok=true 但盘上无 PNG"
            if not img:
                reason += "（且无 image 字段）"
            missing_png.append({"key": rec["raw_key"], "image_field": img,
                                "expected": task_stem(root, nt) + PNG, "reason": reason})
        elif ok and img:
            # 台账记的路径与规范路径是否同一文件（分隔符写法常不一致）
            if _norm_path(img) not in {_norm_path(p) for p in pngs}:
                if os.path.isfile(img):
                    path_anomaly.append({"key": rec["raw_key"], "image_field": img,
                                         "png_on_disk": pngs})
                else:
                    path_anomaly.append({"key": rec["raw_key"], "image_field": img,
                                         "png_on_disk": pngs, "note": "image 字段指向的文件不存在"})
        if not ok:
            rj = _read_json(task_stem(root, nt) + ".result.json") or {}
            failed.append({"key": rec["raw_key"], "stage": v.get("stage") or rj.get("stage"),
                           "error": (v.get("error") or rj.get("error") or "")[:300] or None,
                           "elapsed_s": v.get("elapsed_s", rj.get("elapsed_s"))})
        if check_replay:
            rj = _read_json(task_stem(root, nt) + ".result.json")
            if rj is None:
                continue
            diffs = []
            for fld in ("ok", "elapsed_s"):
                if fld in rj and fld in v and rj[fld] != v[fld]:
                    diffs.append({"field": fld, "ledger": v[fld], "result": rj[fld]})
            if "image" in rj and "image" in v and rj["image"] != v["image"]:
                diffs.append({"field": "image", "ledger": v["image"], "result": rj["image"]})
            if diffs:
                replay_mismatch.append({"key": rec["raw_key"], "diffs": diffs})

    # 产物树 → 台账：孤儿 PNG + 同 task 多张（重复 key）
    orphan_png, dup_png = [], []
    for nt, pngs in sorted(tree.items(), key=lambda kv: str(kv[0])):
        if isinstance(nt[0], str) and len(nt) == 5 and nt[0] == "?":
            # 文件名不匹配 s<seed>.png（如 s123_v2.png）：不是本模块认得的 task
            orphan_png.append({"task": "<?>%s/%s/%s" % (nt[1], nt[2], nt[3]),
                               "png": pngs, "reason": "文件名不匹配 s<seed>.png 约定"})
            continue
        if nt not in led_seen:
            orphan_png.append({"task": canonical_key(nt), "png": pngs,
                               "reason": "盘上有 PNG 但台账无记录（续跑会白重跑）"})
        if len(pngs) > 1:
            dup_png.append({"task": canonical_key(nt), "png": pngs,
                            "reason": "同一 task 落盘 %d 张 PNG（SaveImage 的 _00001 后缀副本？）"
                                      % len(pngs),
                            "stems": [STEM_SUFFIX_RE.sub("", os.path.splitext(os.path.basename(p))[0])
                                      for p in pngs]})
    dup_key = dup_keys + dup_png

    # 三件套
    triple_gap = []
    if check_triad:
        for nt in sorted(led_tasks):
            stem = task_stem(root, nt)
            miss = [t for t in TRIAD if not os.path.isfile(stem + t)]
            if miss:
                triple_gap.append({"key": led_tasks[nt]["raw_key"], "missing": miss,
                                   "dir": os.path.dirname(stem)})
        for nt, pngs in sorted(tree.items(), key=lambda kv: str(kv[0])):
            if len(nt) == 5:
                continue
            stem = os.path.splitext(pngs[0])[0]
            miss = [t for t in TRIAD if not os.path.isfile(stem + t)]
            if miss and canonical_key(nt) not in {_triple_key(g) for g in triple_gap}:
                triple_gap.append({"task": canonical_key(nt), "missing": miss,
                                   "dir": os.path.dirname(stem)})

    # 统计
    per_family = defaultdict(lambda: {"n": 0, "ok": 0, "elapsed_s": [], "prompt": set()})
    for nt, rec in led_tasks.items():
        v = rec["value"]
        f = per_family[nt[0]]
        f["n"] += 1
        f["ok"] += 1 if v.get("ok") else 0
        f["prompt"].add(nt[2])
        if isinstance(v.get("elapsed_s"), (int, float)):
            f["elapsed_s"].append(float(v["elapsed_s"]))
    stats = {"n_tasks": len(led_tasks), "n_png": sum(len(p) for p in tree.values()),
             "n_ok": sum(1 for r in led_tasks.values() if r["value"].get("ok")),
             "bad_keys": len(bad_keys), "families": {}}
    for fam in sorted(per_family):
        f = per_family[fam]
        el = sorted(f["elapsed_s"])
        stats["families"][fam] = {
            "tasks": f["n"], "ok": f["ok"], "prompts": len(f["prompt"]),
            "elapsed_sum_s": round(sum(el), 1),
            "elapsed_mean_s": round(sum(el) / len(el), 1) if el else None,
            "elapsed_median_s": (round(el[len(el) // 2], 1) if el else None),
            "elapsed_max_s": (round(el[-1], 1) if el else None),
        }

    counts = {
        "missing_png": len(missing_png), "orphan_png": len(orphan_png),
        "failed": len(failed), "triple_gap": len(triple_gap), "dup_key": len(dup_key),
        "replay_mismatch": len(replay_mismatch), "path_anomaly": len(path_anomaly),
        "bad_key": len(bad_keys),
    }
    drift = any(counts[k] for k in PRIMARY)
    report = {
        "root": root,
        "ledger_keys": len(ledger),
        "counts": counts,
        "ok": not drift,
        "exit_code": 0 if not drift else 1,
        "lists": {
            "missing_png": missing_png, "orphan_png": orphan_png, "failed": failed,
            "triple_gap": triple_gap, "dup_key": dup_key,
            "replay_mismatch": replay_mismatch, "path_anomaly": path_anomaly,
            "bad_key": bad_keys,
        },
        "stats": stats,
    }
    report["rerun"] = plan_rerun(report, root=root)
    return report


# ── 续跑清单（只产出清单，不接线）──────────────────────────────────────────
def plan_rerun(report, root=None):
    """把对账报告转成「该重跑哪些 task」的清单。纯函数，不碰磁盘。

    优先级：1=台账说失败（必重跑）→ 2=三件套缺（证据链断，重跑才补得回来）
    → 3=台账有记录但 PNG 不在（多半被人删了，重跑）→ 4=重复 key（先人工确认哪张是正本，
    别盲目重跑）。孤儿 PNG（②）不进清单——它是台账缺记录，该补台账不是补图。
    """
    root = root or report.get("root")
    pri = {
        "failed": (1, "台账 ok=false，重跑"),
        "triple_gap": (2, "三件套缺失，重跑才补得回证据链"),
        "missing_png": (3, "台账有记录但 PNG 缺失，重跑"),
        "dup_key": (4, "同 task 多张 PNG：先人工定正本，别盲目重跑"),
    }
    tasks = {}
    for cat, (p, why) in pri.items():
        for item in report["lists"].get(cat, []):
            k = item.get("key") or item.get("task")
            tk = parse_key(k) if k else None
            if tk is None:
                if item.get("task"):
                    tasks.setdefault(item["task"], {})["note"] = item.get("reason", "")
                    tasks[item["task"]].setdefault("priority", p)
                    tasks[item["task"]].setdefault("reasons", []).append(item.get("reason", ""))
                continue
            fam, weight, pid, seed = tk
            nt = norm_task(fam, weight, pid, seed)
            e = tasks.setdefault(canonical_key(nt), {
                "family": fam, "weight": weight, "prompt": pid, "seed": seed,
                "priority": p, "reasons": [], "stem": None, "dir": None})
            if p < e["priority"]:
                e["priority"] = p
                e["reasons"] = [why]
                e["weight"] = weight
            elif why not in e["reasons"]:
                e["reasons"].append(why)
    out = []
    for k, e in sorted(tasks.items(), key=lambda kv: (kv[1]["priority"], kv[0])):
        rec = {"key": k, "priority": e["priority"], "reasons": e["reasons"]}
        for f in ("family", "weight", "prompt", "seed"):
            if f in e:
                rec[f] = e[f]
        if e.get("family") and e.get("prompt"):
            task = (e["family"], e.get("weight", ""), e["prompt"], e.get("seed", 0))
            rec["dir"] = task_dir(root, task)
            rec["stem"] = task_stem(root, task)
        out.append(rec)
    return {
        "n_tasks": len(out),
        "by_priority": dict(Counter(r["priority"] for r in out)),
        "tasks": out,
        "note": "本清单只是建议清单；本库不写盘、不提交、不改参数。接线方式由集成方决定。",
    }


# ── 渲染 ──────────────────────────────────────────────────────────────────
def format_report(report, limit=10):
    c = report["counts"]
    L = ["=" * 78,
         "  ledger × 产物树 对账  root=%s" % report["root"],
         "  台账 %d 条 key（%d 条可解析，%d 条格式非法）  盘上 PNG %d 张"
         % (report["ledger_keys"], report["stats"]["n_tasks"], c["bad_key"],
            report["stats"]["n_png"]),
         "-" * 78,
         "  五类对账：①缺PNG=%d  ②孤儿PNG=%d  ③失败项=%d  ④三件套缺失=%d  ⑤重复key=%d"
         % (c["missing_png"], c["orphan_png"], c["failed"], c["triple_gap"], c["dup_key"]),
         "  附加：重放不一致=%d  路径异常=%d  非法key=%d"
         % (c["replay_mismatch"], c["path_anomaly"], c["bad_key"]),
         "-" * 78]
    titles = {"missing_png": "① 台账有记录但 PNG 缺失",
              "orphan_png": "② PNG 在盘上但台账缺记录",
              "failed": "③ 台账 ok=false",
              "triple_gap": "④ 三件套(params/workflow/result)缺失",
              "dup_key": "⑤ 重复 key",
              "replay_mismatch": "· 重放 result.json 与台账不一致",
              "path_anomaly": "· 台账 image 路径异常",
              "bad_key": "· 台账 key 格式非法（非 4 段或 seed 非整数）"}
    for cat in ("missing_png", "orphan_png", "failed", "triple_gap", "dup_key",
                "replay_mismatch", "path_anomaly", "bad_key"):
        items = report["lists"][cat]
        if not items:
            continue
        L.append("  %s  [%d]" % (titles[cat], len(items)))
        for x in items[:limit]:
            if cat == "failed":
                L.append("      %s  stage=%s elapsed=%s  err=%s"
                         % (x["key"], x.get("stage"), x.get("elapsed_s"),
                            (x.get("error") or "-")[:90]))
            elif cat == "triple_gap":
                L.append("      %s  缺 %s" % (x.get("key") or x.get("task"),
                                              ",".join(x["missing"])))
            elif cat == "dup_key":
                L.append("      %s  %s" % (x.get("canonical") or x.get("task"),
                                          x.get("reason", "")))
            elif cat in ("replay_mismatch", "path_anomaly"):
                L.append("      %s  %s" % (x.get("key"), str(x)[:150]))
            elif cat == "bad_key":
                L.append("      %r" % x)
            else:
                L.append("      %s  %s" % (x.get("key") or x.get("task"),
                                          x.get("reason", "")))
        if len(items) > limit:
            L.append("      …共 %d 条" % len(items))
    st = report["stats"]
    L.append("-" * 78)
    L.append("  统计：%d 个 task，成功 %d；每 family 耗时——" % (st["n_tasks"], st["n_ok"]))
    for fam, f in st["families"].items():
        L.append("      %-24s tasks=%-4d ok=%-4d prompts=%-3d 耗时 合计%8.1fs 均值%7.1fs 中位%7.1fs 峰值%7.1fs"
                 % (fam[:24], f["tasks"], f["ok"], f["prompts"], f["elapsed_sum_s"],
                    f["elapsed_mean_s"] or 0, f["elapsed_median_s"] or 0,
                    f["elapsed_max_s"] or 0))
    rr = report["rerun"]
    L.append("  续跑清单：%d 个 task（优先级分布 %s）" % (rr["n_tasks"], rr["by_priority"] or "无"))
    for t in rr["tasks"][:limit]:
        L.append("      P%d %s  %s" % (t["priority"], t["key"], "；".join(t["reasons"])))
    if rr["n_tasks"] > limit:
        L.append("      …共 %d 条" % rr["n_tasks"])
    L.append("  结论：" + ("五类全 0，对账通过 ✅（exit 0）" if report["ok"]
                        else "存在对不上的项 ⚠（exit 1）——先列明细，人工裁定谁在撒谎再处置"))
    return "\n".join(L)


# ── __main__ ──────────────────────────────────────────────────────────────
def _selftest():
    """合成一棵产物树 + 台账，把五类各造一个实例；再单独造一棵全干净的树验「零漂移」。
    全部落在系统临时目录，跑完即删，不碰工作区。"""
    import shutil
    import tempfile

    rows, bad = [], 0

    def mk(td, fam, wstem, pid, seed, triad=True, png=True, ok=True, elapsed=1.0):
        d = os.path.join(td, fam, wstem, pid)
        os.makedirs(d, exist_ok=True)
        stem = os.path.join(d, "s%d" % seed)
        if png:
            with open(stem + PNG, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")
        if triad:
            for t in TRIAD:
                with open(stem + t, "w", encoding="utf-8") as f:
                    json.dump({"ok": ok, "elapsed_s": elapsed,
                               "image": (stem + PNG) if png else None}, f)
        return stem

    td = tempfile.mkdtemp(prefix="ledgerverify_")
    try:
        a = mk(td, "FamA", "w1", "S1", 1)                                  # 正常
        b = mk(td, "FamA", "w1", "S2", 1, ok=False, elapsed=9.9)           # ③ 失败项
        c = mk(td, "FamA", "w2", "S1", 1)
        os.remove(c + ".result.json")                                       # ④ 三件套缺
        mk(td, "FamA", "w2", "S2", 1)
        os.remove(os.path.join(td, "FamA", "w2", "S2", "s1.png"))           # ① 缺 PNG
        mk(td, "FamB", "w9", "S1", 5)                                       # ② 孤儿 PNG
        e = mk(td, "FamB", "w9", "S1", 6)
        with open(e + "_00001.png", "wb") as f:                             # ⑤ 同 task 两张
            f.write(b"\x89PNG\r\n\x1a\n")
        led = {
            "FamA|w1.safetensors|S1|1": {"ok": True, "elapsed_s": 1.0, "image": a + PNG},
            "FamA|w1|S1|1": {"ok": True, "elapsed_s": 2.0, "image": a + PNG},   # ⑤ ledger 层重名
            "FamA|w1.safetensors|S2|1": {"ok": False, "elapsed_s": 9.9, "image": b + PNG},
            "FamA|w2.safetensors|S1|1": {"ok": True, "elapsed_s": 1.0, "image": c + PNG},
            "FamA|w2.safetensors|S2|1": {"ok": True, "elapsed_s": 1.0, "image": None},
            "broken_key": {"ok": True},
        }
        rep = verify(td, led)
        got = rep["counts"]
        want = {"missing_png": 1, "orphan_png": 2, "failed": 1, "triple_gap": 1,
                "dup_key": 2, "bad_key": 1}
        for k, v in want.items():
            ok = got[k] == v
            bad += 0 if ok else 1
            rows.append(("OK" if ok else "FAIL", "%-14s 期望=%d 实际=%d" % (k, v, got[k])))
        ok = rep["exit_code"] == 1 and not rep["ok"]
        bad += 0 if ok else 1
        rows.append(("OK" if ok else "FAIL", "有漂移时 exit_code=%d（应 1）" % rep["exit_code"]))
        keys = [t["key"] for t in rep["rerun"]["tasks"]]
        ok = (set(keys) == {"FamA|w1|S1|1", "FamA|w1|S2|1", "FamA|w2|S1|1",
                            "FamA|w2|S2|1", "FamB|w9|S1|6"})
        bad += 0 if ok else 1
        rows.append(("OK" if ok else "FAIL", "续跑清单 %d 条：%s" % (len(keys), " ".join(keys))))
        ok = rep["rerun"]["by_priority"] == {1: 1, 2: 1, 3: 1, 4: 2}
        bad += 0 if ok else 1
        rows.append(("OK" if ok else "FAIL", "优先级分布 %s（应 1:失败 2:三件套 3:缺图 4:重复）"
                     % rep["rerun"]["by_priority"]))
        rows.append(("--", "重放不一致=%d（dup 条故意让 elapsed 对不上、缺图条 image 字段为 "
                     "None；属附加项，不进五类）" % got["replay_mismatch"]))
    finally:
        shutil.rmtree(td, ignore_errors=True)

    td2 = tempfile.mkdtemp(prefix="ledgerverify_clean_")
    try:
        s1 = mk(td2, "FamX", "wa", "S1", 11, elapsed=3.5)
        s2 = mk(td2, "FamX", "wb", "S1", 11, elapsed=4.5)
        clean = {
            "FamX|wa.safetensors|S1|11": {"ok": True, "elapsed_s": 3.5, "image": s1 + PNG},
            "FamX|wb.safetensors|S1|11": {"ok": True, "elapsed_s": 4.5, "image": s2 + PNG},
        }
        r2 = verify(td2, clean)
        c2 = r2["counts"]
        ok = all(c2[k] == 0 for k in PRIMARY) and r2["exit_code"] == 0 and r2["ok"]
        bad += 0 if ok else 1
        rows.append(("OK" if ok else "FAIL", "全干净的树：五类=%s 附加(replay=%d path=%d) exit=%d"
                     % ({k: c2[k] for k in PRIMARY}, c2["replay_mismatch"],
                        c2["path_anomaly"], r2["exit_code"])))
        ok = r2["rerun"]["n_tasks"] == 0
        bad += 0 if ok else 1
        rows.append(("OK" if ok else "FAIL", "干净树续跑清单为空（实 %d 条）"
                     % r2["rerun"]["n_tasks"]))
    finally:
        shutil.rmtree(td2, ignore_errors=True)
    return rows, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="ledger × 产物树 对账（纯函数库，只读）")
    ap.add_argument("--root", default=DEFAULT_OUT)
    ap.add_argument("--ledger", default=None, help="台账路径（默认 <root>/ledger.json）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--plan", action="store_true", help="只打续跑清单")
    ap.add_argument("--no-triad", action="store_true")
    ap.add_argument("--no-replay", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args(argv)

    if a.selftest:
        print("=" * 78)
        print("  lib_ledger_verify 自测（合成台账，临时目录，已清理）")
        print("=" * 78)
        rows, bad = _selftest()
        for tag, msg in rows:
            print("  %-4s %s" % (tag, msg))
        print("\n结论：%s（%d 项失败）" % ("PASS" if bad == 0 else "FAIL", bad))
        return 0 if bad == 0 else 1

    t0 = time.time()
    try:
        rep = verify(a.root, ledger_path=a.ledger,
                     check_triad=not a.no_triad, check_replay=not a.no_replay)
    except VerifyError as e:
        print("[x] %s" % e)
        return 2
    except OSError as e:
        print("[x] IO 错：%s" % e)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return rep["exit_code"]
    if a.plan:
        rr = rep["rerun"]
        print("续跑清单：%d 个 task  优先级分布 %s" % (rr["n_tasks"], rr["by_priority"] or "无"))
        for t in rr["tasks"]:
            print("  P%d %-58s %s" % (t["priority"], t["key"], "；".join(t["reasons"])))
        print(rr["note"])
        return rep["exit_code"]
    print(format_report(rep, a.limit))
    print("  （本次对账耗时 %.1fs，只读，未写任何文件）" % (time.time() - t0))
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())