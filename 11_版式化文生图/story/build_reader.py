# -*- coding: utf-8 -*-
"""短篇漫画阅读器构建

读 `story.json` 生成 `reader.html`：一页一屏、竖排滚动、方向键翻页。
不用 fetch 读 JSON（file:// 下会被 CORS 拦），页表直接内联进 HTML。

用法：
  python build_reader.py
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
E = lambda s: html.escape(s, quote=False)

S = json.load(open(os.path.join(HERE, "story.json"), encoding="utf-8"))

pages = []
for p in S["pages"]:
    pages.append("""
  <section class="pg" id="p{n}">
    <img src="{src}" alt="第 {n} 页" onclick="zoom(this)">
    <div class="cap"><b>第 {n} 页</b><span>{cap}</span></div>
  </section>""".format(n=p["no"], src=p["image"], cap=E(p.get("caption", ""))))

nav = "".join('<a href="#p%d">%d</a>' % (p["no"], p["no"]) for p in S["pages"])

doc = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {sub}</title>
<style>
:root {{ --bg:#14120f; --paper:#1c1916; --ink:#e8e2d6; --dim:#9a9285; --accent:#c8563a;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif; line-height:1.8; }}
.cover {{ min-height:100vh; display:flex; flex-direction:column; justify-content:center;
  align-items:center; text-align:center; padding:40px 24px; border-bottom:1px solid #2b2722; }}
.cover .jp {{ font-size:13px; letter-spacing:.4em; color:var(--dim); margin-bottom:22px; }}
.cover h1 {{ font-family:"Songti SC","Source Han Serif SC",Georgia,serif; font-weight:600;
  font-size:46px; margin:0 0 10px; letter-spacing:.04em; }}
.cover .rule {{ width:56px; height:2px; background:var(--accent); margin:26px 0; }}
.cover p {{ max-width:560px; color:var(--dim); font-size:14.5px; margin:0 0 30px; }}
.cover .meta {{ font-size:12.5px; color:#6f675c; letter-spacing:.08em; }}
.scroll {{ color:var(--accent); font-size:12px; letter-spacing:.2em; margin-top:44px; }}
.pages {{ max-width:820px; margin:0 auto; padding:56px 20px 40px; }}
.pg {{ margin:0 0 64px; scroll-margin-top:24px; }}
.pg img {{ width:100%; display:block; border-radius:4px; cursor:zoom-in;
  box-shadow:0 18px 50px rgba(0,0,0,.55); }}
.cap {{ display:flex; gap:12px; align-items:baseline; font-size:12.5px;
  color:var(--dim); margin-top:12px; padding-left:2px; }}
.cap b {{ color:var(--accent); font-weight:600; flex:0 0 auto; }}
.end {{ text-align:center; color:var(--dim); font-size:13px; padding:40px 0 80px;
  border-top:1px solid #2b2722; margin-top:20px; }}
.end em {{ display:block; font-style:normal; font-family:"Songti SC",Georgia,serif;
  font-size:19px; color:var(--ink); margin-bottom:8px; }}
nav {{ position:fixed; right:18px; top:50%; transform:translateY(-50%); z-index:40;
  display:flex; flex-direction:column; gap:4px; }}
nav a {{ width:26px; height:26px; line-height:26px; text-align:center; font-family:var(--mono);
  font-size:11px; color:#6f675c; text-decoration:none; border-radius:4px; }}
nav a:hover {{ background:#2b2722; color:var(--ink); }}
#lb {{ position:fixed; inset:0; background:rgba(8,7,6,.96); display:none;
  align-items:center; justify-content:center; z-index:999; padding:24px; cursor:zoom-out; }}
#lb.on {{ display:flex; }}
#lb img {{ max-width:100%; max-height:100%; }}
@media (max-width:760px) {{ nav {{ display:none; }} .cover h1 {{ font-size:32px; }} }}
</style>
</head>
<body>

<div class="cover">
  <div class="jp">{sub}</div>
  <h1>{title}</h1>
  <div class="rule"></div>
  <p>{logline}</p>
  <div class="meta">{genre} &nbsp;·&nbsp; 全 {n} 页 &nbsp;·&nbsp; {size}</div>
  <div class="scroll">向 下 滚 动 开 始 阅 读</div>
</div>

<nav>{nav}</nav>

<div class="pages">{pages}
  <div class="end"><em>— 完 —</em>{note}</div>
</div>

<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src="" alt=""></div>
<script>
var ids = [{ids}], i = 0;
function zoom(el) {{
  document.getElementById('lbimg').src = el.src;
  document.getElementById('lb').classList.add('on');
}}
document.addEventListener('keydown', function (e) {{
  if (e.key === 'Escape') document.getElementById('lb').classList.remove('on');
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {{
    i = Math.min(i + 1, ids.length - 1); location.hash = 'p' + ids[i];
  }}
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {{
    i = Math.max(i - 1, 0); location.hash = 'p' + ids[i];
  }}
}});
window.addEventListener('scroll', function () {{
  var y = window.scrollY + window.innerHeight * 0.35;
  ids.forEach(function (id, k) {{
    var el = document.getElementById('p' + id);
    if (el && el.offsetTop <= y) i = k;
  }});
}});
</script>
</body>
</html>""".format(
    title=E(S["title"]), sub=E(S.get("subtitle", "")), logline=E(S.get("logline", "")),
    genre=E(S.get("genre", "")), n=len(S["pages"]), size=E(S.get("size", "")),
    nav=nav, pages="".join(pages), note=E(S.get("note", "")),
    ids=",".join(str(p["no"]) for p in S["pages"]))

out = os.path.join(HERE, "reader.html")
open(out, "w", encoding="utf-8").write(doc)
print("written %s (%.1f KB)" % (out, len(doc) / 1024))
