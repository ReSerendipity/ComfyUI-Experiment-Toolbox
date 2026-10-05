# -*- coding: utf-8 -*-
"""
模型家族横评 P1 增强 · lib② 提示词提交前质检（prompt QC）。

为什么需要：10 个 S1..S9 提示词是横评的**控制变量**（README「跨全部权重恒定：
提示词套件逐字节一致，sha256 记账」）。任何一条提示词被顺手改一个字、粘进一段
模板废句、或混进否定式与质量后缀，跨权重对比的结论就全废了，而图上根本看不出
区别。所以提示词必须在**提交前**过一道机器闸，而不是出图后靠肉眼看图。

思路出处（只借鉴规则思路，规则清单在本模块自带，零 import）
    · Picture/tools/full_qc.py + tools/constants.py：把「模板句黑名单 / 裸相邻重复 /
      叠标点 / 质量后缀 / 否定式 / 字数窗」这几类做成可复用扫描器。本库只保留
      **项目无关的通用工程规则**，不搬任何分级词表、不搬任何 NSFW/SFW 专属判定。
    · AGENTS §14「写提示词的硬性要求」：不用否定式、不加质量后缀、正向描述优先、
      画面文字用引号包裹。

规则清单（rule / severity，severity ∈ error|warn|info）
    error  —— 会毁掉对比有效性或必然是废句，必须改
      negation      否定式（no/without/not/banned/不要/避免/无…）：本套提示词口径是
                    纯正向描述，否定式交给 negative_mode 或 ConditioningZeroOut 处理
      double_punct  叠标点（，，  。。 ，。 ，；…）：纯笔误
      dup_cjk       CJK 相邻重复（身材，身材）：纯笔误
      dup_bare      CJK 裸相邻重复（身材身材）：纯笔误（叠词白名单除外）
      dup_word      英文单词紧邻重复（the the）：纯笔误
      placeholder   未替换的模板占位符（{{ }} / ${} / <lora:…> / TODO / lorem ipsum）
      meta_leak     文件头混入文件名或 id（S1_portrait_frontal.txt: …）：像把
                    ledger 元数据抄进了提示词，会一起被喂进 CLIP
      unbalanced_quote  引号不成对：画面文字必须成对用英文双引号包裹
      empty         空文件 / 只有空白
      too_short / too_long  字数窗（默认 500~1000 字，去空白计；仅对正向提示词生效，
                    negative_mode 用的负向串文件不套此窗）
    warn   —— 值得人看一眼，不必然是错
      quality_suffix  质量/分辨率后缀（4K / 8K / Ultra HD / masterpiece / best quality）
      template_phrase  陈词滥调套话（trending on artstation 等）＝跨文件会撞车的模板句
      width_punct     全角中文标点混进西文提示词（，。；：）
      repeat_sentence 同一句在文件内重复出现（≥2 次，跨文件也会撞）
      lora_weight     <lora:name:0.8> 带权重：会污染「唯一变量＝UNet 权重」的控制变量口径
      mtime/编码类无 → 不设 info 规则，保持清单短

API
    check_text(txt, name="", cfg=None) -> [finding, ...]      纯函数，不碰磁盘
    check_file(path, cfg=None)          -> report dict        读一个文件
    scan(paths, cfg=None)               -> 总 report dict      批量扫目录/文件
finding = {"rule","severity","match","detail"}
退出码：0 无 error / 1 有 error / 2 用法或 IO 错。

用法（必须用 ComfyUI 自带 python）：
    python lib_prompt_qc.py prompts
    python lib_prompt_qc.py prompts/S1_portrait_frontal.txt --json
    python lib_prompt_qc.py prompts --min-chars 0 --max-chars 0     # 关掉字数窗
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 规则清单（项目无关；CJK 侧参考 Picture 的黑名单思路，英文侧为本项目自建）──────
RULE_TABLE = (
    ("negation",        "error", "否定式：改为纯正向描述，负向需求走 negative_mode"),
    ("double_punct",    "error", "叠标点/异类标点相邻"),
    ("dup_cjk",         "error", "CJK 相邻重复词（X，X）"),
    ("dup_bare",        "error", "CJK 裸相邻重复词（XX），叠词白名单除外"),
    ("dup_word",        "error", "英文单词紧邻重复（the the）"),
    ("placeholder",     "error", "未替换的模板占位符 / 残留标记"),
    ("meta_leak",       "error", "提示词里混进了文件名或 id（ledger 元数据泄漏）"),
    ("unbalanced_quote", "error", "英文双引号不成对"),
    ("empty",           "error", "空文件 / 全空白"),
    ("too_short",       "error", "字数低于下限（去空白计）"),
    ("too_long",        "error", "字数超上限（去空白计）"),
    ("quality_suffix",  "warn",  "质量 / 分辨率后缀：FLUX/Qwen 系不靠它加分，且跨文件撞车"),
    ("template_phrase", "warn",  "陈词滥调套话（跨文件会变成模板句）"),
    ("width_punct",     "warn",  "全角中文标点混进西文提示词"),
    ("repeat_sentence", "warn",  "同一句在文件内重复"),
    ("lora_weight",     "warn",  "<lora:…:w> 带权重：破坏「唯一变量＝UNet 权重」口径"),
)
SEVERITY = {r: s for r, s, _ in RULE_TABLE}
RULE_DESC = {r: d for r, _, d in RULE_TABLE}

# 否定式。中文侧注意别把「无」一刀切——中文正常词里含「无」（无缝/无穷/画框无线…），
# 故中文只收「不要 / 避免 / 别 / 没有」，西文收独立单词，词边界清晰、不误伤。
RE_NEGATION_EN = re.compile(
    r"(?i)(?<![\w'])\b(no|not|without|never|none|nothing|banned|avoid|excluding|"
    r"free of|devoid of|lacking|absent)\b")
RE_NEGATION_CN = re.compile(r"(不要|避免|不得|不能有|别出现|没有)")
# 质量 / 分辨率后缀。数字前加 (?<!\d) 免得把 "2048x1536" 里的 4K/8K 误判成后缀。
RE_QUALITY_SUFFIX = re.compile(
    r"(?i)(?<!\d)(4k|8k|16k|2k)\b(?!\s*[x×]\s*\d)"
    r"|\bultra\s?hd\b|\buhd\b|\bhigh\s?resolution\b"
    r"|\bmasterpiece\b|\bbest\s?quality\b|\bhigh\s?quality\b"
    r"|\bultra\s?(realistic|sharp|detailed|hd)\b"
    r"|\bhighly\s?detailed\b|\bhyper\s?detailed\b|\b8k\s?uhd\b"
    r"|\baward[- ]winning\b|\bphotorealistic\s?8k\b")
RE_DOUBLE_PUNC = re.compile(r"([,，。；;：:、!！?？~～])\s*\1+")
RE_DUP_CJK = re.compile(r"([一-鿿]{2})\s*[，,]\s*\1")
RE_DUP_BARE = re.compile(r"([一-鿿]{2})\1")
# 英文紧邻重复词（≥3 字母）；\1 反向引用需分词，先切词再比对更稳，见 _dup_words。
RE_DUP_WORD = re.compile(r"(?i)\b([a-z]{3,})\s+\1\b")
RE_PLACEHOLDER = re.compile(
    r"\{\{[^}]*\}\}|\$\{[^}]*\}|\{\d+\}|<\|[^|]*\|>"
    r"|\b(todo|tbd|fixme|xxx+|placeholder|lorem ipsum|dummy text"
    r"|insert \w+ here|your \w+ here)\b", re.I)
RE_LORA = re.compile(r"(?i)<\s*(lora|lyco|hypernet|hypernetwork)\s*:([^>]*?)>")
RE_META_LEAK = re.compile(r"(?m)^[ \t]*[^\n]{0,80}?\.(txt|json)\s*[:：]")
RE_WIDTH_PUNCT = re.compile(r"[，。；：、（）]")
# 负向提示词文件（negative_mode=real 用的那一串）：只做该做的检查，不套字数窗。
RE_NEG_FILE = re.compile(r"(?i)^neg|negative|^-_|^sub_")
RE_CJK = re.compile(r"[一-鿿]")

# CJK 合法叠词白名单（沿用通用叠词思路）：这些「轻轻/渐渐/层层」不算裸重复。
DUP_WHITELIST = frozenset((
    "轻轻 渐渐 缓缓 微微 默默 深深 淡淡 悄悄 纷纷 层层 点点 步步 细细 慢慢 "
    "恰恰 仅仅 常常 每每 偏偏 偷偷 暗暗 白白 远远 满满 空空 浓浓 频频 冉冉 "
    "熊熊 皑皑 茫茫 依依 历历 津津 勃勃 炯炯 耿耿 娓娓 潺潺 淅淅 簌簌 苍苍 "
    "萋萋 芊芊 楚楚 重重 阵阵 条条 缕缕 丝丝 滚滚 团团 人人 家家 岁岁 年年 "
    "天天 夜夜 日日 处处 件件 桩桩 声声 一层 快看 一闪 上车 一甩 扑通 咕咚 哗啦"
).split())

# 陈词滥调套话（英文，跨文件撞车高发区；CJK 侧的模板句黑名单思路见下方注释）。
# 注意：本表**不含任何分级/题材词表**，只是「摄影圈通用口水句」。
TEMPLATE_PHRASES = (
    "trending on artstation", "trending on deviantart", "artstation",
    "highly detailed, intricate", "intricate details", "award winning",
    "professional photography, 8k", "breathtaking", "stunning",
    "masterwork", "captivating", "mesmerizing", "eye-catching",
    "hyper-detailed, ultra", "photorealistic, 8k", "award-winning photography",
)
# CJK 模板句黑名单：通用「口水句」思路（跨文件重复即模板化），非题材/分级词。
TEMPLATE_PHRASES_CJK = (
    "光线斜斜打在她身上", "勾勒出柔和的身体轮廓", "窗外的光影", "投下斑驳的明暗",
    "划过桌面", "留下一道浅浅的痕迹", "咬了咬下唇", "眼神中带着一丝慵懒",
    "发丝随风", "拂过她的脸颊", "呼吸平缓而均匀", "胸口起伏",
)

DEFAULT_CFG = {
    "min_chars": 500,
    "max_chars": 1000,
    "globs": ("*.txt",),
    "skip_names": (),          # 整文件名跳过（默认只跳负向串）
    "apply_length_to_negative": False,
    "max_findings_per_rule": 5,
}


# ── 内部工具 ──────────────────────────────────────────────────────────────
def _f(rule, match, detail=None):
    return {"rule": rule, "severity": SEVERITY[rule], "match": match,
            "detail": detail if detail is not None else RULE_DESC[rule]}


def _clip(m, n=60):
    s = " ".join(str(m).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _cfg(cfg):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update({k: v for k, v in cfg.items() if v is not None})
    return c


def _sentences(txt):
    parts = re.split(r"(?<=[.!?。！？;；])\s+|\n+", txt)
    return [" ".join(p.split()).strip(" ,，、") for p in parts if p.strip(" ,，、")]


def _dup_words(txt):
    out = []
    for m in RE_DUP_WORD.finditer(txt):
        w = m.group(1).lower()
        if w not in DUP_WHITELIST:
            out.append(m.group(0))
    return out


def _role(path_or_name, cfg):
    base = os.path.basename(path_or_name or "")
    if any(fnmatch.fnmatch(base, s) for s in (cfg.get("skip_names") or ())):
        return "skip"
    return "negative" if RE_NEG_FILE.search(base) else "positive"


def _read(path):
    """提示词文件优先 utf-8；失败退回 gbk（Windows 本地 txt 常见），都不行就原样报错。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise OSError("无法解码（utf-8/gbk 均失败）：%s" % path)


# ── API ①：纯函数质检 ─────────────────────────────────────────────────────
def check_text(txt, name="", cfg=None):
    """对一段提示词跑全部规则 → findings 列表（空列表 = 干净）。不碰磁盘。"""
    c = _cfg(cfg)
    txt = txt if isinstance(txt, str) else ""
    role = _role(name, c)
    out = []
    if role == "skip":
        return out

    stripped = "".join(txt.split())
    if not stripped:
        return [_f("empty", _clip(txt, 20) or "<空文件>")]

    # 否定式
    for m in list(RE_NEGATION_EN.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("negation", m.group(0)))
    for m in list(RE_NEGATION_CN.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("negation", m.group(0)))

    # 叠标点
    dbl = sorted(set(m.group(0) for m in RE_DOUBLE_PUNC.finditer(txt)))
    for x in dbl[:c["max_findings_per_rule"]]:
        out.append(_f("double_punct", x))

    # 相邻重复（CJK 两类 + 英文单词）
    for m in list(RE_DUP_CJK.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("dup_cjk", m.group(0)))
    for m in list(RE_DUP_BARE.finditer(txt)):
        if m.group(1) not in DUP_WHITELIST:
            out.append(_f("dup_bare", m.group(0)))
        if len([x for x in out if x["rule"] == "dup_bare"]) >= c["max_findings_per_rule"]:
            break
    for x in _dup_words(txt)[:c["max_findings_per_rule"]]:
        out.append(_f("dup_word", x))

    # 占位符 / 元数据泄漏 / 负向嵌入
    for m in list(RE_PLACEHOLDER.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("placeholder", _clip(m.group(0))))
    for m in list(RE_META_LEAK.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("meta_leak", _clip(m.group(0))))
    for m in list(RE_LORA.finditer(txt)):
        if re.search(r":\s*[0-9]*\.?[0-9]+\s*>$", m.group(0)):
            out.append(_f("lora_weight", _clip(m.group(0))))
            break

    # 引号成对：直引号奇数、或中文弯引号左右不等，都算不成对
    if txt.count('"') % 2 != 0 or txt.count("“") != txt.count("”"):
        out.append(_f("unbalanced_quote",
                      '直引号 %d（奇偶异常） / “%d ”%d'
                      % (txt.count('"'), txt.count("“"), txt.count("”"))))

    # 质量后缀 + 模板套话
    for m in list(RE_QUALITY_SUFFIX.finditer(txt))[:c["max_findings_per_rule"]]:
        out.append(_f("quality_suffix", _clip(m.group(0))))
    for p in TEMPLATE_PHRASES + TEMPLATE_PHRASES_CJK:
        if p.lower() in txt.lower():
            out.append(_f("template_phrase", p))

    # 全角标点混入（文件本身没有 CJK 时才算问题）
    if not RE_CJK.search(txt):
        for m in list(RE_WIDTH_PUNCT.finditer(txt))[:c["max_findings_per_rule"]]:
            out.append(_f("width_punct", m.group(0)))

    # 句内重复
    seen, dup = set(), []
    for s in _sentences(txt):
        k = s.lower()
        if len(k) < 12:
            continue
        if k in seen and s not in dup:
            dup.append(s)
        seen.add(k)
    for s in dup[:c["max_findings_per_rule"]]:
        out.append(_f("repeat_sentence", _clip(s)))

    # 字数窗（负向串默认豁免）
    lo, hi = c["min_chars"], c["max_chars"]
    if role != "negative" or c["apply_length_to_negative"]:
        if lo and len(stripped) < lo:
            out.append(_f("too_short", "%d字 < %d" % (len(stripped), lo)))
        if hi and len(stripped) > hi:
            out.append(_f("too_long", "%d字 > %d" % (len(stripped), hi)))
    return out


# ── API ②：单文件 ─────────────────────────────────────────────────────────
def check_file(path, cfg=None):
    """读一个提示词文件 → report dict {path,name,role,chars,findings,counts}。"""
    c = _cfg(cfg)
    txt = _read(path)
    findings = check_text(txt, os.path.basename(path), c)
    role = _role(os.path.basename(path), c)
    counts = Counter(f["severity"] for f in findings)
    return {
        "path": os.path.abspath(path),
        "name": os.path.basename(path),
        "role": role,
        "chars": len("".join(txt.split())),
        "findings": findings,
        "counts": {"error": counts.get("error", 0),
                   "warn": counts.get("warn", 0),
                   "info": counts.get("info", 0)},
    }


# ── API ③：批量 ───────────────────────────────────────────────────────────
def _expand(paths, globs):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for g in globs:
                files.extend(sorted(glob.glob(os.path.join(p, "**", g), recursive=True)))
        elif os.path.isfile(p):
            files.append(p)
    return sorted(set(f for f in files if os.path.isfile(f)))


def scan(paths, cfg=None):
    """批量扫目录/文件 → 总 report（每文件一份 check_file 结果 + 汇总计数）。"""
    c = _cfg(cfg)
    if isinstance(paths, (str, bytes)):
        paths = [paths]
    files = _expand(list(paths), c["globs"])
    reports = [check_file(f, c) for f in files]
    by_rule = Counter()
    for r in reports:
        for f in r["findings"]:
            by_rule[f["rule"]] += 1
    n_err = sum(r["counts"]["error"] for r in reports)
    n_warn = sum(r["counts"]["warn"] for r in reports)
    return {
        "files": reports,
        "n_files": len(reports),
        "n_clean": sum(1 for r in reports if not r["findings"]),
        "n_error_files": sum(1 for r in reports if r["counts"]["error"]),
        "n_warn_files": sum(1 for r in reports if r["counts"]["warn"]),
        "findings_total": n_err + n_warn,
        "errors": n_err,
        "warnings": n_warn,
        "by_rule": dict(by_rule),
        "ok": n_err == 0,
        "exit_code": 0 if n_err == 0 else 1,
    }


def format_report(rep, verbose=True):
    L = ["=" * 78, "  提示词质检  文件 %d 个｜干净 %d｜有 error %d｜有 warn %d"
         % (rep["n_files"], rep["n_clean"], rep["n_error_files"], rep["n_warn_files"]), "=" * 78]
    for r in rep["files"]:
        tag = "OK  " if not r["findings"] else "WARN" if not r["counts"]["error"] else "ERR "
        L.append("  [%s] %-34s role=%-8s chars=%-5d err=%d warn=%d"
                 % (tag, r["name"][:34], r["role"], r["chars"],
                    r["counts"]["error"], r["counts"]["warn"]))
        if verbose:
            for f in r["findings"]:
                L.append("          %-5s %-16s %-34s %s"
                         % (f["severity"], f["rule"], f["match"][:34], f["detail"]))
    if rep["by_rule"]:
        L.append("  规则命中统计：" + "  ".join("%s=%d" % (k, v)
                                              for k, v in sorted(rep["by_rule"].items(),
                                                                 key=lambda x: -x[1])))
    L.append("  结论：" + ("零 error ✅（exit 0）" if rep["ok"]
                        else "存在 %d 处 error ⚠（exit 1）" % rep["errors"]))
    return "\n".join(L)


# ── __main__ ──────────────────────────────────────────────────────────────
def _selftest():
    """构造「每条规则各命中一次」的样本，证明规则真的会响（不依赖外部文件）。"""
    cases = [
        ("negation", "a portrait of a woman, no hat, without glasses"),
        ("double_punct", "a portrait，， soft light"),
        ("dup_cjk", "她身材，身材匀称"),
        ("dup_bare", "睫毛睫毛浓密"),
        ("dup_word", "a woman with the the red coat"),
        ("placeholder", "a portrait {{subject}} in {{style}} style"),
        ("meta_leak", "S1_portrait_frontal.txt: a portrait of a woman"),
        ("unbalanced_quote", 'the mug reads exactly "NORTHWIND 1974 in the centre'),
        ("empty", "   \n  "),
        ("too_short", "a woman"),
        ("quality_suffix", "a portrait, 4k, masterpiece, best quality"),
        ("template_phrase", "a portrait, trending on artstation, highly detailed"),
        ("width_punct", "a portrait，soft light"),
        ("repeat_sentence", "soft north light. soft north light. a portrait."),
        ("lora_weight", "a portrait <lora:film_grain:0.8>"),
    ]
    rows, bad = [], 0
    for rule, sample in cases:
        fs = check_text(sample, "S1_probe.txt")
        hit = [f for f in fs if f["rule"] == rule]
        ok = bool(hit)
        bad += 0 if ok else 1
        rows.append((rule, ok, sample[:44], (hit[0]["match"] if hit else "-")))
    # 干净的样本必须零 finding（正向描述 + 成对引号 + 字数窗内）
    good = ("Photorealistic frontal head-and-shoulders portrait of an East Asian woman in her "
            "late twenties, facing the camera directly, calm almond-shaped eyes with visible "
            "catchlights, straight nose, soft matte lips, healthy pale skin showing real pores, "
            "charcoal wool turtleneck sweater and small silver hoop earrings, lips closed in a "
            "relaxed half-smile, eye-level camera at her eye height, centred symmetrical framing, "
            "soft north-facing window light from the left, blurred bookshelf background, shallow "
            "depth of field, shot on Fujifilm X-T5 with a 35mm f/1.4 lens, natural colour.")
    gf = check_text(good, "S1_good.txt", {"min_chars": 0})
    bad += 0 if not gf else 1
    # 负向串文件豁免字数窗（真实 NEG_real.txt 只有 212 字，不该报 too_short）
    negf = check_text("blurry, low resolution, deformed hands, jpeg artifacts",
                      "NEG_real.txt")
    neg_ok = not [f for f in negf if f["rule"] in ("too_short", "too_long")]
    bad += 0 if neg_ok else 1
    return rows, gf, negf, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="提示词提交前质检（纯函数库）")
    ap.add_argument("paths", nargs="*", default=[os.path.join(HERE, "prompts")])
    ap.add_argument("--glob", nargs="*", default=None, help="目录扫描的通配（默认 *.txt）")
    ap.add_argument("--min-chars", type=int, default=None)
    ap.add_argument("--max-chars", type=int, default=None, help="0 = 关闭上限")
    ap.add_argument("--json", action="store_true", help="输出 JSON（便于接入流水线）")
    ap.add_argument("--quiet", action="store_true", help="只打有 finding 的文件")
    ap.add_argument("--rules", action="store_true", help="打印规则清单后退出")
    ap.add_argument("--selftest", action="store_true", help="跑合成样本自测（不碰工作区文件）")
    a = ap.parse_args(argv)

    if a.rules:
        for r, s, d in RULE_TABLE:
            print("  %-16s %-5s %s" % (r, s, d))
        return 0

    if a.selftest:
        print("=" * 78)
        print("  lib_prompt_qc 自测（合成样本，不读工作区）")
        print("=" * 78)
        rows, gf, negf, bad = _selftest()
        for rule, ok, sample, hit in rows:
            print("  %-4s %-16s 样本=%-46s 命中=%s"
                  % ("OK" if ok else "FAIL", rule, sample, hit))
        print("  %-4s 干净样本零 finding（实际 %d 条：%s）"
              % ("OK" if not gf else "FAIL", len(gf),
                 ",".join(f["rule"] for f in gf) or "-"))
        print("  %-4s 负向串豁免字数窗（实际 %d 条：%s）"
              % ("OK" if not [f for f in negf if f["rule"] in ("too_short", "too_long")] else "FAIL",
                 len(negf), ",".join(f["rule"] for f in negf) or "-"))
        print("\n结论：%s（%d 项失败）" % ("PASS" if bad == 0 else "FAIL", bad))
        return 0 if bad == 0 else 1

    cfg = {}
    if a.glob:
        cfg["globs"] = tuple(a.glob)
    if a.min_chars is not None:
        cfg["min_chars"] = a.min_chars
    if a.max_chars is not None:
        cfg["max_chars"] = a.max_chars
    try:
        rep = scan(a.paths or [os.path.join(HERE, "prompts")], cfg)
    except OSError as e:
        print("[x] IO 错：%s" % e)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    elif a.quiet:
        print(format_report(rep, verbose=False))
        for r in rep["files"]:
            if r["findings"]:
                print("  %s" % r["name"])
                for f in r["findings"]:
                    print("      %-5s %-16s %s" % (f["severity"], f["rule"], f["match"]))
    else:
        print(format_report(rep, verbose=True))
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())