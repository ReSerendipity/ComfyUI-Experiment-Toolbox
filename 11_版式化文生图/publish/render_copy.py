# -*- coding: utf-8 -*-
"""发布文案 · 核验 + 渲染

核三件事：主标题与备选标题是否在口径内、正文是否在口径内、判词表是否零命中。
全绿才写出 `发布文案.md`，有一条不过就 exit 1，不出稿。

用法：
  python render_copy.py            # 核验并渲染
  python render_copy.py --check    # 只核验，不写文件
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import copy_data as CD

try:
    import cover_data as CV
except ImportError:
    CV = None

# 四比例定稿（skill §6.1 / 结案自检第 11 条要求齐全）
COVER_MAIN = {
    "comic_3x4": "小红书首图 · 抖音竖版",
    "comic_4x3": "抖音图文横版",
    "comic_16x9": "B 站视频封面 · 知乎",
    "comic_9x16": "竖屏全屏 · 短视频封面",
}
# 备选：方法篇单独成篇时才用，不属于本次统一文案
COVER_ALT = {
    "method_3x4": "方法篇 · 小红书首图",
    "method_16x9": "方法篇 · B 站视频封面",
}
COVER_TEXT = {
    "comic_3x4": ("末班车 / 开往海见（竖排两列）", "全 8 页 · 一个完整的结局", "MOSS-IMAGE"),
    "comic_4x3": ("末班车 / 开往海见（竖排两列）", "废站等了三十年", "MOSS-IMAGE"),
    "comic_16x9": ("末班车 / 开往海见（横排两行）", "废站等了三十年", "MOSS-IMAGE"),
    "comic_9x16": ("末班车 / 开往海见（竖排两列）", "全 8 页", "MOSS-IMAGE"),
    "method_3x4": ("一张图 当版面", "10 类版式骨架 · MOSS-Image 实测", "MOSS-IMAGE"),
    "method_16x9": ("版式是先验 / 文字要注入", "MOSS-Image 版式化文生图实测", "LAYOUT-CONDITIONED"),
}


def fmt(text):
    return text.format(model=CD.MODEL, hw=CD.HARDWARE, seed=CD.SEED_NOTE)


def count(text):
    """平台字数口径：按字符计，不计空白。"""
    return len(re.sub(r"\s", "", text))


def check():
    title = fmt(CD.POST["title"])
    alts = [fmt(a) for a in CD.POST["title_alts"]]
    body = fmt(CD.POST["body"])
    bad = []

    ct, cb = count(title), count(body)
    if ct > CD.SPEC["title_max"]:
        bad.append("主标题 %d 字 > 口径 %d" % (ct, CD.SPEC["title_max"]))
    if cb > CD.SPEC["body_max"]:
        bad.append("正文 %d 字 > 口径 %d" % (cb, CD.SPEC["body_max"]))
    for a in alts:
        if count(a) > CD.SPEC["title_max"]:
            bad.append("备选标题「%s」%d 字 > 口径 %d" % (a, count(a), CD.SPEC["title_max"]))
    for w in CD.BANNED:
        for field, val in (("标题", title), ("正文", body)):
            if w in val:
                bad.append("%s 命中判词「%s」" % (field, w))
    for a in alts:
        for w in CD.BANNED:
            if w in a:
                bad.append("备选标题「%s」命中判词「%s」" % (a, w))
    return title, alts, body, ct, cb, bad


def render(title, alts, body, ct, cb):
    o = ["# 发布文案", "",
         "> 由 `render_copy.py` 从 `copy_data.py` 生成，**不要直接改本文件**。",
         "> **一份文案通投**：主标题 + 正文 + 标签全平台同一份，不按平台改写。",
         "> 核验口径：%s（标题 ≤%d 字、正文 ≤%d 字）。"
         % (CD.SPEC["ref"], CD.SPEC["title_max"], CD.SPEC["body_max"]), ""]

    o += ["## 标题（%d / %d 字）" % (ct, CD.SPEC["title_max"]), "", "```", title, "```", "",
          "**备选标题**（同口径内，换钩子不改事实）", ""]
    for i, a in enumerate(alts, 1):
        o += ["%d. %s（%d 字）" % (i, a, count(a))]
    o += ["", "## 正文（%d / %d 字）" % (cb, CD.SPEC["body_max"]), "", "```", body.strip(), "```", "",
          "## 标签", "", "```", CD.POST["tags"], "```", "",
          "> 标签在正文里只是参考写法。发布页必须输入 `#` 后**点选建议**，"
          "手打的 `#纯文本` 平台不认。", ""]

    o += ["---", "", "## 平台适配（同一份文案，装得下所有平台）", "",
          "| 平台 | 标题上限 | 正文上限 | 话题入口 | 封面比例 | AI 声明 |",
          "|---|---|---|---|---|---|"]
    for row in CD.PLATFORM_CEILING:
        o.append("| " + " | ".join(row) + " |")
    o += ["",
          "主标题 %d 字、正文 %d 字，均在最小上限内，**不需要为任何平台另写一份**。" % (ct, cb), ""]

    o += ["---", "", "## 封面（四比例齐全，各自重排，不是裁切）", "",
          "| 文件 | 比例 | 分辨率 | 用在哪 |", "|---|---|---|---|"]
    if CV:
        for c in CV.COVERS:
            if c["key"] in COVER_MAIN:
                o.append("| `covers/%s.jpg` | %s | %d×%d | %s |"
                         % (c["key"], c["ratio"], c["size"][0], c["size"][1],
                            COVER_MAIN[c["key"]]))
    o += ["", "**备选**（方法篇单独成篇时才用，本次不用）", "",
          "| 文件 | 比例 | 分辨率 | 用在哪 |", "|---|---|---|---|"]
    if CV:
        for c in CV.COVERS:
            if c["key"] in COVER_ALT:
                o.append("| `covers/%s.jpg` | %s | %d×%d | %s |"
                         % (c["key"], c["ratio"], c["size"][0], c["size"][1],
                            COVER_ALT[c["key"]]))
    o += ["", "**封面上的文字**（逐字核对，改字必须重出图）", "",
          "| 文件 | 主标题 | 副标题 / 标语 | 角标 |", "|---|---|---|---|"]
    for k in list(COVER_MAIN) + list(COVER_ALT):
        if k in COVER_TEXT:
            t, s, f = COVER_TEXT[k]
            o.append("| `%s.jpg` | %s | %s | %s |" % (k, t, s, f))
    o += ["",
          "> 封面标题字随图生成。若某平台要求标题 100% 可控，改用 PIL 叠字："
          "让模型只出底图（提示词里删掉全部文字块），再用系统字体排标题。", ""]

    o += ["---", "", "## 配图", "",
          "| 用途 | 素材 |", "|---|---|",
          "| 正文配图 | `story/pages/01.jpg` – `08.jpg`（按页序） |",
          "| 首图 / 封面 | `covers/` 下对应比例 |", ""]

    o += ["## 发布前自检", "",
          "| 项 | 判据 |", "|---|---|",
          "| 标题 | 与本文案逐字一致，字数在平台上限内 |",
          "| 正文 | 与本文案逐字一致 |",
          "| 素材 | 8 页按序；封面比例与平台要求一致 |",
          "| 标签 | 逐个是**点选**出来的 token |",
          "| AI 声明 | 平台要求的选项已选 |",
          "| 发布按钮 | 由你点 |", ""]
    return "\n".join(o)


def main(argv):
    title, alts, body, ct, cb, bad = check()
    print("主标题  %d / %d 字  %s" % (ct, CD.SPEC["title_max"], title))
    for a in alts:
        print("备选    %d / %d 字  %s" % (count(a), CD.SPEC["title_max"], a))
    print("正文    %d / %d 字" % (cb, CD.SPEC["body_max"]))

    warns = [w for w in CD.SOFT_WARN if w in title or w in body]
    print()
    for w in warns:
        print("[warn] 出现「%s」——没做对比就别引入对比，人工确认" % w)
    if bad:
        for b in bad:
            print("[FAIL] " + b)
        return 1

    print("[ok] 字数与判词全部通过")
    if "--check" not in argv:
        dst = os.path.join(HERE, "发布文案.md")
        open(dst, "w", encoding="utf-8").write(render(title, alts, body, ct, cb))
        print("[ok] 已写 %s" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
