# -*- coding: utf-8 -*-
"""
模型家族横评 · 提示词鲁棒性探针（长度 / 精简对照）—— 纯函数库，不碰 ComfyUI。

要回答的问题
    「同一条提示词，砍掉器材/光线修饰从句之后，权重的能力排序会不会变？」
    如果排序不变，说明 S1–S9 的分数里有相当一部分是被「器材堆料」撑起来的，
    排除了「写得更长＝更强」的误判；反之则说明长度本身是有效变量，
    后续所有横评结论都必须附带长度说明。

对应思路来源
    Picture/tools/render_compare.py 的 --mode slim（对照脚本 slim_prompt()）。
    差异：那边是「砍尾部陈设填充 + 提交出图」，这边是
      ① 砍「器材 / 镜头 / 光线修饰 / 影调 / 画质后缀」从句；
      ② 锚点优先——主体 / 动作 / 角度断言 / 硬文字 / 计数 / 空间关系任一命中即免删；
      ③ 纯计划，不 POST /prompt、不轮询、不落图。

核心 API
    slimify(txt) -> dict
        {"text", "chars_full", "chars_slim", "ratio", "word_full", "word_slim",
         "changes": [{"index", "action", "rule", "anchors", "text", "chars"}],
         "anchors_full": {...}, "anchors_slim": {...}, "anchor_ok": bool}
        规则完全可复现（纯正则 + 固定顺序，无随机、无模型、无外部状态）。

    plan_pairs(full_dir, out_manifest=None) -> list[dict]
        扫描目录下全部 *.txt，为每条产出「完整版 / 精简版」配对计划；
        out_manifest 非空时把清单写成 JSON。**只产计划，不提交出图、不调 ComfyUI。**

    assert_anchor_retention(full, slim) -> dict   锚点保留逐项判定
    negative_hits(txt) -> list[str]              否定句式扫描（禁 negative prompt）
    quality_suffix_hits(txt) -> list[str]        画质后缀扫描
    hard_literals(txt) -> list[str]             引号包裹的硬文字断言

用法（必须用 ComfyUI 自带 python）：
    python -X utf8 lib_prompt_robust.py --selftest
    python -X utf8 lib_prompt_robust.py --prompt prompts/S1_portrait_frontal.txt
    python -X utf8 lib_prompt_robust.py --plan prompts --manifest _slim_plan.json
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

# =============================================================================
# 一、锚点规则（ANCHOR）：命中任一即视为「不可删的语义核」
#     顺序即优先级，仅用于记录，判定是「集合非空」而非「取首个」。
# =============================================================================
ANCHOR_RULES = (
    ("hard_literal", r"[\"“][^\"”]{1,80}[\"”]"),
    ("count", r"\bexactly\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)"
             r"\s+(?:people|persons|figures|adults|plates|books|cups|items|objects)\b"),
    ("angle", r"\beye[- ]level\b|\beye height\b|\blow(?:er)?(?:ed)? camera angle\b|"
              r"\bhigh angle\b|\bsteep high angle\b|\btop[- ]down\b|\bworm'?s[- ]eye\b|"
              r"\bthree[- ]quarter\b|\bfrontal\b|\bfull[- ]length\b|\bhead[- ]and[- ]shoulders\b|"
              r"\bviewpoint\b|\bperspective\b|\bprofile\b|\bfrom behind\b|\brear view\b|"
              r"\bfrom below\b|\bfrom above\b|\blooking upward\b|\blooking downward\b|"
              r"\btilted\b|\bframing\b|\bcomposition\b|\bparallel to the ground\b|"
              r"\blevel and square\b|\bsquare to the (?:camera|lens)\b|"
              r"\b(?:into|toward|towards) the lens\b|\bstraight into the (?:camera|lens)\b|"
              r"\bgaze\b"),
    ("spatial", r"\bto the left of\b|\bto the right of\b|\bdirectly\b|\bbeside\b|"
                r"\bbehind\b|\bin front of\b|\bflanked\b|\bbetween\b|\bon the same line\b|"
                r"\bfills? the\b|\binside the frame\b|\bwithin the frame\b|\bcent(?:re|ered|red)\b|"
                r"\balong the\b|\bacross the\b|\bweighed\b"),
    ("action", r"\bwear(?:s|ing)\b|\bstand(?:s|ing)?\b|\bsit(?:s|ting)?\b|\bwalk(?:s|ing)?\b|"
               r"\bcarry(?:ies|ing)\b|\bhold(?:s|ing)?\b|\brest(?:s|ing)?\b|\bturn(?:s|ing|ed)?\b|"
               r"\brotate(?:s|ing|ted)?\b|\blook(?:s|ing)?\b|\bglanc(?:e|es|ing)\b|"
               r"\bweight\b|\blean(?:s|ing)?\b|\brais(?:e|es|ing)\b|\blift(?:s|ing)?\b|"
               r"\bslic(?:e|es|ing)\b|\bdrift(?:s|ing)?\b|\bfall(?:s|ing)?\b|\bgaze\b"),
    ("subject", r"\bwoman\b|\bwomen\b|\bman\b|\bmen\b|\bgirl\b|\bboy\b|\bstudent\b|"
                r"\badult(?:s)?\b|\bfigure\b|\bperson\b|\bpeople\b|\bmale\b|\bfemale\b|"
                r"\bhair\b|\beyes?\b|\bnose\b|\blips?\b|\bface\b|\bskin\b|\bfreckles?\b|"
                r"\bearrings?\b|\bbuild\b|\bwaist\b|\bhips?\b|\bbreasts?\b|\bshoulders?\b|"
                r"\bthighs?\b|\blegs?\b|\bneck\b|\bcheek\b|\bfingers?\b|\bhands?\b"),
)

# =============================================================================
# 二、删减规则（DROP）：全部不命中锚点时才生效
#     OVERRIDE 类可压过 subject/action（它们描述的是「谁」而不是「断言」），
#     但压不过 hard_literal / count / angle / spatial。
# =============================================================================
DROP_RULES = (
    # (rule, kind, regex)；kind=override 表示可压过弱锚点
    ("optics", "override", r"\bshallow depth of field\b|\bdeep focus\b|\bbokeh\b|"
                           r"\bf/[\d.]+\b|\baperture\b|\bfocus keeping\b"),
    ("gear", "override", r"\bshot on\b|\bHasselblad\b|\bFujifilm\b|\bCanon\b|\bNikon\b|"
                         r"\bSony\b|\b\d{2,3}\s?mm\b|\bmedium format\b|"
                         r"\bfull[- ]frame\b|\bsensor\b|\bISO\b|\bshutter\b|"
                         r"\blens(?:es)? at\b|\blens\b(?=[^.]{0,40}\bf/)"),
    ("light_mod", "override", r"\bkey light\b|\bfill light\b|\brim light\b|\bwindow light\b|"
                              r"\bdaylight\b|\bsoftbox\b|\bvolumetric\b|"
                              r"\bfalloff into shadow\b|\bshadow falling\b|"
                              r"\bshadows? (?:across|on|behind)\b|\blight modell?ing\b|"
                              r"\bcast(?:s|ing)? long\b|\bwraparound\b"),
    ("atmosphere", "override", r"\bheavy atmospheric haze\b|\bdust motes\b|"
                                r"\bairborne dust\b|\bgrain\b|\bhaze\b"),
    ("grade", "override", r"\bnatural (?:warm )?colou?r\b|\bcolou?r cast\b|"
                          r"\bcolou?r palette\b|\bsaturated\b|\brestrained neutral\b|"
                          r"\bmuted\b|\bgraded\b"),
    ("quality_suffix", "override", r"\b\d{1,2}\s?[kK]\b|\b8K\b|\b4K\b|\bUHD\b|\bHDR\b|"
                                   r"\bmasterpiece\b|\bbest quality\b|\bultra[- ]?hd\b|"
                                   r"\baward[- ]winning\b|\bhighly detailed\b|"
                                   r"\bprofessional photo\b|\b8k\b"),
    ("filler", "weak", r"\bclean uncluttered background\b|\bplain \w+ backdrop\b|"
                      r"\bnegative space\b|\bno visible clutter\b"),
)

# 弱锚点：可被 override 类删减规则压过
WEAK_ANCHORS = frozenset(("subject", "action"))
# 强锚点：任何删减规则都不能压过
STRONG_ANCHORS = frozenset(("hard_literal", "count", "angle", "spatial"))

_SPLIT_RE = re.compile(r"(?<=[,;.])\s+|(?<=[,;.])$")
_SENT_END = (".", ";", ",", "!", "?", ":")

NEGATIVE_RE = re.compile(
    r"\b(?:no|not|without|avoid|nor|never|absent|lacking|free of)\b", re.I)
QUALITY_SUFFIX_RE = re.compile(
    r"\b\d{1,2}\s?[kK]\b|\b8K\b|\b4K\b|\bUHD\b|\bHDR\b|\bmasterpiece\b|"
    r"\bbest quality\b|\bultra[- ]?hd\b|\baward[- ]winning\b|\bhighly detailed\b", re.I)
HARD_LITERAL_RE = re.compile(r"[\"“]([^\"”]{1,80})[\"”]")


# =============================================================================
# 三、基础工具（纯函数）
# =============================================================================
def chars(text):
    """不含空白字符数——本项目一切长度断言的统一口径。"""
    return len(re.sub(r"\s+", "", text or ""))


def words(text):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text or ""))


def split_clauses(text):
    """切成子句。保留子句末尾的原始断句符，便于原样重组。"""
    text = (text or "").strip()
    if not text:
        return []
    raw = [c.strip() for c in re.split(r"(?<=[,;.])\s+", text) if c.strip()]
    if not raw:
        return [text]
    tail = ""
    if raw and raw[-1] and raw[-1][-1] in _SENT_END:
        tail = raw[-1][-1]
        raw[-1] = raw[-1][:-1]
    out = []
    for i, c in enumerate(raw):
        c = c.strip()
        if not c:
            continue
        end = tail if i == len(raw) - 1 else ""
        out.append(c + end)
    return out


def anchors_of(clause):
    """子句命中的锚点类别集合（有序返回，便于报告稳定）。"""
    hits = []
    for name, pat in ANCHOR_RULES:
        if re.search(pat, clause, re.I):
            hits.append(name)
    return hits


def _match_drop(clause):
    """返回 (rule, kind) 或 None。override 优先于 weak。"""
    best = None
    for rule, kind, pat in DROP_RULES:
        if re.search(pat, clause, re.I):
            if kind == "override":
                return rule, kind
            best = best or (rule, kind)
    return best


def hard_literals(text):
    return HARD_LITERAL_RE.findall(text or "")


def negative_hits(text):
    return sorted({m.group(0).lower() for m in NEGATIVE_RE.finditer(text or "")})


def quality_suffix_hits(text):
    return sorted({m.group(0) for m in QUALITY_SUFFIX_RE.finditer(text or "")})


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# =============================================================================
# 四、slimify —— 锚点优先的确定性精简
# =============================================================================
def slimify(txt):
    """按规则生成精简版并回报变更清单。

    规则（顺序固定、无随机、同样输入必得同样输出）：
      R0 首子句（主体/身份句）无条件保留；
      R1 子句命中任一强锚点（硬文字/计数/角度/空间关系）→ 保留；
      R2 子句命中弱锚点（主体/动作）且无删减规则命中 → 保留；
      R3 子句被 override 类删减规则命中 → 删（弱锚点不豁免）；
      R4 子句被 weak 类删减规则命中且锚点为空 → 删；
      R5 重组时保证以句号收尾、不产生「，，」类标点病句。

    返回 dict，字段见模块 docstring。
    """
    full = (txt or "").strip()
    clauses = split_clauses(full)
    changes, kept = [], []

    for idx, cl in enumerate(clauses):
        body = cl.rstrip("".join(_SENT_END)).strip()
        end = cl[len(body):]
        anchors = anchors_of(cl)
        strong = [a for a in anchors if a in STRONG_ANCHORS]
        weak = [a for a in anchors if a in WEAK_ANCHORS]
        hit = _match_drop(cl)

        if idx == 0:
            kept.append((idx, cl, body, end, anchors))
            continue
        if strong:
            kept.append((idx, cl, body, end, anchors))
            continue
        if hit and hit[1] == "override":
            changes.append({"index": idx, "action": "drop", "rule": hit[0],
                            "anchors": anchors, "text": cl, "chars": chars(cl)})
            continue
        if not weak:
            if hit:
                changes.append({"index": idx, "action": "drop", "rule": hit[0],
                                "anchors": anchors, "text": cl, "chars": chars(cl)})
            else:
                kept.append((idx, cl, body, end, anchors))
            continue
        kept.append((idx, cl, body, end, anchors))

    slim = _rebuild(kept)
    slim = slim if slim.endswith(".") else slim + "."
    slim = re.sub(r"[,;]\s*([,;.])", r"\1", slim)
    slim = re.sub(r"\. ([a-z])", lambda m: ". " + m.group(1).upper(), slim)
    slim = re.sub(r"\s{2,}", " ", slim).strip()

    af, as_ = anchors_of(full), anchors_of(slim)
    return {
        "text": slim,
        "chars_full": chars(full),
        "chars_slim": chars(slim),
        "word_full": words(full),
        "word_slim": words(slim),
        "ratio": round(chars(slim) / chars(full), 4) if chars(full) else 1.0,
        "clauses_total": len(clauses),
        "clauses_kept": len(kept),
        "changes": changes,
        "anchors_full": sorted(set(af)),
        "anchors_slim": sorted(set(as_)),
        "anchor_ok": not (STRONG_ANCHORS & set(af)) - set(as_),
        "hard_literals_full": hard_literals(full),
        "hard_literals_slim": hard_literals(slim),
        "negative_full": negative_hits(full),
        "negative_slim": negative_hits(slim),
        "quality_suffix_full": quality_suffix_hits(full),
        "quality_suffix_slim": quality_suffix_hits(slim),
        "sha256_full": sha256_text(full),
        "sha256_slim": sha256_text(slim),
    }


def _rebuild(kept):
    """按原顺序重组保留子句，保证断句符单调、不产生标点病句。"""
    parts = []
    for _idx, _cl, body, end, _an in kept:
        if not body:
            continue
        parts.append(body + (end if end in ".;" else ","))
    out = "".join(parts)
    out = re.sub(r"[,;](?=[,;.])", "", out)
    out = re.sub(r"([,;]){2,}", lambda m: m.group(0)[0], out)
    out = re.sub(r"([.;!?])(?=[A-Za-z])", r"\1 ", out)
    return out.rstrip(",;").strip()


# =============================================================================
# 五、锚点保留判定 + 配对计划
# =============================================================================
def assert_anchor_retention(full, slim):
    """逐项核对精简版是否仍保住全部强锚点类别与硬文字原文。"""
    af, as_ = set(anchors_of(full)), set(anchors_of(slim))
    strong_full = sorted(STRONG_ANCHORS & af)
    lost = [a for a in strong_full if a not in as_]
    lit_full, lit_slim = hard_literals(full), hard_literals(slim)
    lost_lit = [x for x in lit_full if x not in lit_slim]
    angle_re = dict(ANCHOR_RULES)["angle"]
    spatial_re = dict(ANCHOR_RULES)["spatial"]
    lost_angle = [m.group(0) for m in re.finditer(angle_re, full or "", re.I)
                  if m.group(0).lower() not in (slim or "").lower()]
    lost_spatial = [m.group(0) for m in re.finditer(spatial_re, full or "", re.I)
                    if m.group(0).lower() not in (slim or "").lower()]
    return {
        "strong_anchors_full": strong_full,
        "strong_anchors_slim": sorted(STRONG_ANCHORS & as_),
        "lost_anchor_kinds": lost,
        "lost_hard_literals": lost_lit,
        "lost_angle_terms": lost_angle,
        "lost_spatial_terms": lost_spatial,
        "ok": (not lost) and (not lost_lit) and (not lost_angle) and (not lost_spatial),
    }


def plan_pairs(full_dir, out_manifest=None):
    """为目录下每条 *.txt 产出「完整版 / 精简版」配对计划。

    只读 + 只写清单，**不 POST /prompt、不轮询、不出图**。
    out_manifest 为 None 时不落盘，仅返回内存清单。
    """
    rows = []
    names = sorted(f for f in os.listdir(full_dir) if f.lower().endswith(".txt"))
    for fn in names:
        path = os.path.join(full_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            full = f.read().strip()
        r = slimify(full)
        ret = assert_anchor_retention(full, r["text"])
        rows.append({
            "file": fn,
            "rel": os.path.relpath(path, full_dir).replace("\\", "/"),
            "chars_full": r["chars_full"],
            "chars_slim": r["chars_slim"],
            "word_full": r["word_full"],
            "word_slim": r["word_slim"],
            "ratio": r["ratio"],
            "clauses_total": r["clauses_total"],
            "clauses_kept": r["clauses_kept"],
            "dropped": len(r["changes"]),
            "drop_rules": sorted({c["rule"] for c in r["changes"]}),
            "dropped_texts": [c["text"] for c in r["changes"]],
            "anchor_ok": ret["ok"],
            "lost_hard_literals": ret["lost_hard_literals"],
            "negative_full": r["negative_full"],
            "negative_slim": r["negative_slim"],
            "is_negative_list": bool(r["negative_full"]) and not r["anchors_full"],
            "quality_suffix_full": r["quality_suffix_full"],
            "quality_suffix_slim": r["quality_suffix_slim"],
            "sha256_full": r["sha256_full"],
            "sha256_slim": r["sha256_slim"],
            "pair_id": "%s__slim" % os.path.splitext(fn)[0],
            "render": {"submit": False, "seeds": [], "note": "plan-only"},
            "slim_text": r["text"],
        })
    if out_manifest:
        d = os.path.dirname(os.path.abspath(out_manifest))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(out_manifest, "w", encoding="utf-8") as f:
            json.dump({"pairs": rows, "render_submitted": False}, f,
                      ensure_ascii=False, indent=1)
    return rows


# =============================================================================
# 六、__main__ —— 自测 / 单条演示 / 批量计划
# =============================================================================
def _selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    sample = os.path.join(here, "prompts", "S1_portrait_frontal.txt")
    if not os.path.isfile(sample):
        sample = os.path.join(here, "S1_portrait_frontal.txt")
    with open(sample, "r", encoding="utf-8") as f:
        full = f.read().strip()
    r = slimify(full)
    ret = assert_anchor_retention(full, r["text"])

    print("=" * 74)
    print("  提示词鲁棒性探针 · selftest  (%s)" % os.path.basename(sample))
    print("=" * 74)
    print("chars  full=%d  slim=%d  ratio=%.3f" % (r["chars_full"], r["chars_slim"], r["ratio"]))
    print("words  full=%d  slim=%d" % (r["word_full"], r["word_slim"]))
    print("clauses total=%d kept=%d dropped=%d"
          % (r["clauses_total"], r["clauses_kept"], len(r["changes"])))
    print("-" * 74)
    print("被删子句（按规则）:")
    for c in r["changes"]:
        print("  [%-14s anchors=%-22s] %s"
              % (c["rule"], ",".join(c["anchors"]) or "-", c["text"]))
    print("-" * 74)
    print("锚点 full=%s" % (",".join(r["anchors_full"]),))
    print("锚点 slim=%s" % (",".join(r["anchors_slim"]),))
    print("硬文字 full=%s  slim=%s" % (r["hard_literals_full"], r["hard_literals_slim"]))
    print("否定词 full=%s  slim=%s" % (r["negative_full"], r["negative_slim"]))
    print("画质后缀 full=%s  slim=%s" % (r["quality_suffix_full"], r["quality_suffix_slim"]))
    print("-" * 74)
    print("slim 全文:\n  %s" % r["text"])
    print("-" * 74)

    assert ret["strong_anchors_full"], "强锚点为空，样例不符合本库写法"
    assert ret["ok"], "锚点保留失败: %s" % json.dumps(ret, ensure_ascii=False)
    assert chars(r["text"]) < chars(full), "精简版未变短"
    assert not r["negative_slim"], "精简版引入否定词"
    assert r["hard_literals_slim"] == r["hard_literals_full"], "硬文字被删"
    print("ASSERT OK  强锚点 %s 全部保留；硬文字逐字保留；无否定词；长度 %.0f%%"
          % ("/".join(ret["strong_anchors_full"]), 100 * r["ratio"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="提示词长度/精简鲁棒性对照探针（纯函数库，不调 ComfyUI）")
    ap.add_argument("--selftest", action="store_true", help="对 prompts/S1 实跑 slimify 并断言")
    ap.add_argument("--prompt", help="对单条 .txt 实跑 slimify")
    ap.add_argument("--plan", help="对目录下全部 .txt 产出配对计划")
    ap.add_argument("--manifest", help="配对计划 JSON 输出路径（配合 --plan）")
    ap.add_argument("--show-slim", action="store_true", help="打印精简版全文")
    a = ap.parse_args(argv)

    did = False
    if a.selftest:
        _selftest()
        did = True
    if a.prompt:
        with open(a.prompt, "r", encoding="utf-8") as f:
            full = f.read().strip()
        r = slimify(full)
        ret = assert_anchor_retention(full, r["text"])
        print("== %s ==" % os.path.basename(a.prompt))
        print("chars %d -> %d (%.1f%%)  words %d -> %d"
              % (r["chars_full"], r["chars_slim"], 100 * r["ratio"],
                 r["word_full"], r["word_slim"]))
        for c in r["changes"]:
            print("  DROP[%-14s] %s" % (c["rule"], c["text"]))
        if a.show_slim:
            print("SLIM: %s" % r["text"])
        print("anchor_ok=%s lost=%s"
              % (ret["ok"], ret["lost_anchor_kinds"] or ret["lost_angle_terms"]))
        did = True
    if a.plan:
        rows = plan_pairs(a.plan, a.manifest)
        print("== plan %s ==" % a.plan)
        print("%-38s %6s %6s %6s %6s %5s %s"
              % ("file", "full", "slim", "wf", "ws", "ratio", "anchor_ok"))
        for r in rows:
            print("%-38s %6d %6d %6d %6d %5.2f %s"
                  % (r["file"], r["chars_full"], r["chars_slim"],
                     r["word_full"], r["word_slim"], r["ratio"], r["anchor_ok"]))
        bad = [r["file"] for r in rows if not r["anchor_ok"]]
        print("anchor_ok %d/%d%s"
              % (len(rows) - len(bad), len(rows),
                 ("  FAILED: " + ", ".join(bad)) if bad else ""))
        if a.manifest:
            print("manifest -> %s（render_submitted=false，未提交任何出图）" % a.manifest)
        did = True
    if not did:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())