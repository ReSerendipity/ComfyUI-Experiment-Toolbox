# -*- coding: utf-8 -*-
"""短篇集总目录

扫描 `story*/story.json`，生成 `series.html`：11 部短篇的封面、简介与阅读器入口。

用法：
  python build_series.py
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
E = lambda s: html.escape(s, quote=False)

# 展示顺序：先第一部，再按选题清单顺序
ORDER = [
    ("story", ""), ("story2", ""), ("story3", ""),
    ("story4", ""), ("story5", ""), ("story6", ""),
    ("story7", ""), ("story8", ""), ("story9", ""),
    ("story10", ""), ("story11", ""), ("story12", ""),
]


def load(d):
    p = os.path.join(HERE, d, "story.json")
    if not os.path.isfile(p):
        return None
    s = json.load(open(p, encoding="utf-8"))
    s["_dir"] = d
    return s


def main():
    items = []
    for d, _ in ORDER:
        s = load(d)
        if s:
            items.append(s)

    cards = []
    for s in items:
        d = s["_dir"]
        cover = "%s/%s" % (d, s["pages"][0]["image"])
        cards.append("""
    <a class="card" href="{dir}/reader.html">
      <img src="{cover}" alt="{title}" loading="lazy">
      <div class="body">
        <div class="idx">{no:02d}</div>
        <h3>{title}</h3>
        <p class="jp">{sub}</p>
        <p class="log">{log}</p>
        <div class="meta"><span>{n} 页</span><span>{genre}</span><span>{style}</span></div>
      </div>
    </a>""".format(dir=d, cover=cover, title=E(s["title"]),
                     sub=E(s.get("subtitle", "")), log=E(s.get("logline", "")),
                     n=len(s["pages"]), genre=E(s.get("genre", "")),
                     style=E(s.get("style", "")),
                     no=len(cards) + 1))

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>短篇集 · 版式化文生图</title>
<style>
:root{--bg:#f6f4ee;--paper:#fffefa;--ink:#1b1a17;--ink2:#565248;--ink3:#8d887a;
--line:#e3ded2;--accent:#b04a2f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;
font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:64px 32px 90px}
h1{font-family:"Songti SC",Georgia,serif;font-size:40px;margin:0 0 10px}
.sub{color:var(--ink2);max-width:760px;margin:0 0 12px}
.meta{font-size:12.5px;color:var(--ink3);margin:0 0 42px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
.card{display:flex;flex-direction:column;background:var(--paper);border:1px solid var(--line);
border-radius:14px;overflow:hidden;text-decoration:none;color:inherit;transition:.18s}
.card:hover{transform:translateY(-3px);box-shadow:0 14px 34px rgba(0,0,0,.1)}
.card img{width:100%;display:block;background:#efece4}
.card .body{padding:18px 20px 20px;position:relative}
.idx{font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--accent);letter-spacing:.1em}
.card h3{font-family:"Songti SC",Georgia,serif;font-size:19px;margin:4px 0 2px}
.jp{font-size:11.5px;color:var(--ink3);letter-spacing:.12em;margin:0 0 10px}
.log{font-size:12.5px;color:var(--ink2);margin:0 0 14px;display:-webkit-box;
-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.meta span{font-size:11px;color:var(--ink3);border:1px solid var(--line);border-radius:999px;
padding:2px 8px;margin-right:6px;white-space:nowrap}
footer{margin-top:60px;padding-top:26px;border-top:1px solid var(--line);
font-size:12.5px;color:var(--ink3)}
@media(max-width:980px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){.grid{grid-template-columns:1fr}.wrap{padding:40px 18px 60px}}
</style></head><body><div class="wrap">
<h1>短篇集</h1>
<p class="sub">同一套版式化提示词方法，同一画风口径，十一部日式短篇。每部 8 页，起承转合完整、有结局。</p>
<p class="meta">__N__ 部 · 每部 8 页 · 800×1200 · 厚涂电影感 · 单种子单次生成，未修图</p>
<div class="grid">__CARDS__
</div>
<footer>全部提示词在各自的 <code>story_data.py</code>，可复现；阅读器一页一屏，方向键翻页。</footer>
</div></body></html>"""
    doc = doc.replace("__N__", str(len(items))).replace("__CARDS__", "".join(cards))

    out = os.path.join(HERE, "series.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("written %s（%d 部）" % (out, len(items)))
    for s in items:
        print("  %-9s %-14s %d 页  %s" % (s["_dir"], s["title"], len(s["pages"]),
                                          s.get("style", "")))


if __name__ == "__main__":
    main()
