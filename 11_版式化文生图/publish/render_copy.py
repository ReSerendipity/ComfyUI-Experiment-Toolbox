# -*- coding: utf-8 -*-
"""发布文案 · 核验 + 渲染

按平台上限核字数、跑判词表，全绿才写出 `发布文案.md`。有一条不过就 exit 1，不出稿。

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

# 封面 → 用在哪（与 cover_data.COVERS 的 key 对齐）
COVER_USE = {
    "comic_3x4": ("小红书 · 漫画篇主图", "抖音图文 · 竖版"),
    "method_3x4": ("小红书 · 方法篇主图",),
    "method_16x9": ("B 站 · 专栏封面", "知乎 · 文章封面"),
    "comic_4x3": ("抖音图文 · 横版",),
}
COVER_TEXT = {
    "comic_3x4": ("末班车 / 开往海见（竖排两列）", "全 8 页 · 一个完整的结局", "MOSS-IMAGE"),
    "method_3x4": ("一张图 当版面", "10 类版式骨架 · MOSS-Image 实测", "MOSS-IMAGE"),
    "method_16x9": ("版式是先验 / 文字要注入", "MOSS-Image 版式化文生图实测", "LAYOUT-CONDITIONED"),
    "comic_4x3": ("末班车 / 开往海见（竖排两列）", "废站等了三十年", "MOSS-IMAGE"),
}


def fmt(text):
    return text.format(model=CD.MODEL, hw=CD.HARDWARE,
                       seed=CD.SEED_NOTE, seed_short=CD.SEED_NOTE_SHORT)


def count(text):
    """平台字数口径：按字符计，不计空白。"""
    return len(re.sub(r"\s", "", text))


def check():
    rows, bad = [], []
    for p in CD.POSTS:
        plat = CD.PLATFORMS[p["platform"]]
        title, body = fmt(p["title"]), fmt(p["body"])
        ct, cb = count(title), count(body)
        ok_t, ok_b = ct <= plat["title_max"], cb <= plat["body_max"]
        rows.append((p, plat, title, body, ct, cb, ok_t, ok_b))
        if not ok_t:
            bad.append("%s 标题 %d 字 > 上限 %d" % (p["key"], ct, plat["title_max"]))
        if not ok_b:
            bad.append("%s 正文 %d 字 > 上限 %d" % (p["key"], cb, plat["body_max"]))
        for w in CD.BANNED:
            for field, val in (("标题", title), ("正文", body)):
                if w in val:
                    bad.append("%s %s 命中判词「%s」" % (p["key"], field, w))
    return rows, bad


def render(rows):
    out = ["# 发布文案", "",
           "> 由 `render_copy.py` 从 `copy_data.py` 生成，**不要直接改本文件**。",
           "> 口径纪律见 `copy_data.py` 头部；字数已按平台上限核验。", "",
           "## 口径速查（全平台逐字一致，不许漂移）", "",
           "| 项 | 值 |", "|---|---|",
           "| 模型 | %s |" % CD.MODEL,
           "| 硬件 | %s |" % CD.HARDWARE,
           "| 采样 | euler / 30 步 / CFG 4 |",
           "| 分辨率 | 800×1200（漫画）／1024×1536（类型样张） |",
           "| 单种子声明 | %s |" % CD.SEED_NOTE, ""]

    for p, plat, title, body, ct, cb, ok_t, ok_b in rows:
        fenced = p.get("fence", True)
        out += ["---", "",
                "## %s ｜ %s" % (plat["label"], p["role"]), "",
                "**标题**（%d / %d 字）" % (ct, plat["title_max"]), "",
                "```", title, "```", "",
                "**正文**（%d / %d 字）" % (cb, plat["body_max"]), ""]
        if fenced:
            out += ["```", body.strip(), "```", ""]
        else:
            # 长文不套代码块：正文自带标题，统一降一级避免打散本文档结构
            demoted = "\n".join(
                ("#" + ln) if ln.startswith("## ") else ln
                for ln in body.strip().split("\n"))
            out += [demoted, "",
                    "> 以上为纯文本正文，直接全选复制。表格用编辑器自带的表格功能重排一次即可。", ""]
        out += ["**话题 / 标签**", "", "```", p["tags"], "```", "",
                "**发布页必填**：AI 声明「%s」；封面比例 %s。" % (plat["ai_declare"], plat["cover"]),
                ""]

    out += ["---", "",
            "## 封面（四比例，各自重排，不是裁切）", "",
            "| 文件 | 比例 | 分辨率 | 用在哪 |", "|---|---|---|---|"]
    if CV:
        for c in CV.COVERS:
            uses = " / ".join(COVER_USE.get(c["key"], (c["for_"],)))
            out.append("| `covers/%s.jpg` | %s | %d×%d | %s |"
                       % (c["key"], c["ratio"], c["size"][0], c["size"][1], uses))
    out += ["", "**封面上的文字**（逐字核对，改字要重出图）", "",
            "| 文件 | 主标题 | 副标题 / 标语 | 角标 |", "|---|---|---|---|"]
    for k, (t, s, f) in COVER_TEXT.items():
        out.append("| `%s.jpg` | %s | %s | %s |" % (k, t, s, f))
    out += ["",
            "> 封面为模型整图生成，标题字随图出。若平台要求标题必须 100% 可控，"
            "改用 PIL 叠字：让模型只出底图（提示词里删掉全部文字块），再用系统字体排标题。", ""]

    out += ["---", "",
            "## 发布前逐页验收（每页一张表）", "",
            "| 项 | 判据 |", "|---|---|",
            "| 标题 | 在平台上限内，与本文案逐字一致 |",
            "| 正文 | 与本文案逐字一致；字数计数器正常 |",
            "| 素材 | 图片数量正确；封面比例符合平台要求 |",
            "| 话题 | 逐个是**点选**出来的 token，不是手打 `#` 纯文本 |",
            "| AI 声明 | 平台要求的选项已选 |",
            "| 发布按钮 | 未点击 |", "",
            "## 配图建议", "",
            "| 用途 | 素材 |", "|---|---|",
            "| 漫画篇 | `story/pages/01.jpg` – `08.jpg`（按页序） |",
            "| 方法篇 | `samples/` 下 10 张类型样张 |",
            "| 封面 | 由正文首句做标题，不用另做截图集 |", ""]
    return "\n".join(out)


def main(argv):
    rows, bad = check()
    print("%-14s %-14s %-12s %-14s" % ("post", "platform", "标题", "正文"))
    for p, plat, title, body, ct, cb, ok_t, ok_b in rows:
        print("%-14s %-14s %-12s %-14s" % (
            p["key"], plat["label"],
            "%d/%d %s" % (ct, plat["title_max"], "ok" if ok_t else "OVER"),
            "%d/%d %s" % (cb, plat["body_max"], "ok" if ok_b else "OVER")))

    warns = []
    for p in CD.POSTS:
        blob = fmt(p["title"]) + fmt(p["body"])
        for w in CD.SOFT_WARN:
            if w in blob:
                warns.append("%s 出现「%s」——没做对比就别引入对比，人工确认" % (p["key"], w))

    print()
    if warns:
        for w in warns:
            print("[warn] " + w)
    if bad:
        print()
        for b in bad:
            print("[FAIL] " + b)
        return 1

    print("[ok] 字数与判词全部通过")
    if "--check" not in argv:
        dst = os.path.join(HERE, "发布文案.md")
        open(dst, "w", encoding="utf-8").write(render(rows))
        print("[ok] 已写 %s" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
