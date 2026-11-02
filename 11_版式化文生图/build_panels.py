# -*- coding: utf-8 -*-
"""格数上限对照页

扫 `samples_panels/*.jpg`，生成 `panels.html`：按目标格数排列，标注实测格数与判定。

用法：
  python build_panels.py
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "samples_panels")
E = lambda s: html.escape(s, quote=False)

# (文件名 key, 目标格数, 分辨率, 实测格数, 判定)
ROWS = [
    ("4_2x2_moss", 4, "800×1200", "5（1 格静默）", "通过"),
    ("6_2x3_moss", 6, "800×1200", "6", "部分失效"),
    ("8_2x4_moss", 8, "800×1200", "10", "失效"),
]


def main():
    cards = []
    for key, n, size, actual, verdict in ROWS:
        p = os.path.join(D, key + ".jpg")
        if not os.path.isfile(p):
            continue
        cls = {"通过": "ok", "部分失效": "mid"}.get(verdict, "bad")
        cards.append("""
  <figure class="card">
    <img src="samples_panels/%(key)s.jpg" alt="%(n)d 格" loading="lazy" onclick="zoom(this)">
    <figcaption>
      <div class="top"><b>%(n)d 格</b><span class="tag %(cls)s">%(verdict)s</span></div>
      <div class="sub">%(size)s &nbsp;·&nbsp; 实测 %(actual)s</div>
    </figcaption>
  </figure>""" % dict(key=key, n=n, size=size, actual=actual,
                     verdict=verdict, cls=cls))

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>漫画格数上限实测</title>
<style>
:root{--bg:#f5f3ed;--paper:#fffefa;--ink:#1b1a17;--ink2:#565248;--ink3:#8d887a;
--line:#e0dbcf;--accent:#b04a2f;--ok:#2f7d4f;--bad:#b03a2e;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7;
font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:52px 28px 80px}
h1{font-family:"Songti SC",Georgia,serif;font-size:34px;margin:0 0 8px}
.sub{color:var(--ink2);font-size:14px;margin:0 0 8px;max-width:920px}
.meta{font-size:12.5px;color:var(--ink3);margin:0 0 34px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.card{margin:0;background:var(--paper);border:1px solid var(--line);border-radius:12px;
overflow:hidden}
.card img{width:100%;display:block;cursor:zoom-in;background:#efece4}
figcaption{padding:12px 14px 14px}
.top{display:flex;align-items:center;gap:10px;justify-content:space-between}
.top b{font-family:"Songti SC",Georgia,serif;font-size:16px}
.tag{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid}
.tag.ok{color:var(--ok);border-color:#bcd8c7;background:#f2f8f4}
.tag.bad{color:var(--bad);border-color:#e6c4bf;background:#fbf3f2}
.tag.mid{color:#9a6a12;border-color:#e6d6ad;background:#fdf8ec}
.sub2,.sub{font-size:11.5px;color:var(--ink3)}
.note{margin-top:38px;font-size:13px;color:var(--ink2);background:var(--paper);
border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:20px 24px}
.note b{color:var(--ink)}
.note table{border-collapse:collapse;margin:10px 0 4px;font-size:12.5px}
.note th,.note td{border:1px solid var(--line);padding:5px 10px;text-align:left}
.note th{background:#faf8f3;font-weight:600}
.note ul{margin:8px 0 0;padding-left:20px}
.note li{margin:4px 0}
#lb{position:fixed;inset:0;background:rgba(18,17,15,.94);display:none;align-items:center;
justify-content:center;z-index:99;padding:26px;cursor:zoom-out}
#lb.on{display:flex}#lb img{max-width:100%;max-height:100%}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){.grid{grid-template-columns:1fr}.wrap{padding:36px 16px 60px}}
</style></head><body><div class="wrap">
<h1>漫画格数上限实测</h1>
<p class="sub">同一幕戏（黄昏的无人车站，两个高中生等末班车）、同一个 seed、同一套漫画页面语法
（画格大小不等 + 出血格 + 横向错位），每格按 <b>说</b>／<b>白</b>／<b>静</b> 三种类型分，
<b>只改格数</b>。</p>
<p class="meta">MOSS-Image SFT · 30 步 / CFG 4 / euler · seed 20261111 · 单种子单次生成，未修图</p>
<div class="grid">__CARDS__
</div>
<div class="note">
<b>结论：瓶颈不是格数，是「谁在说」</b>
<table>
<tr><th>层</th><th>失效点</th><th>表现</th></tr>
<tr><td>台词文字</td><td>8 格内没失效</td><td>全部逐字正确</td></tr>
<tr><td><b>气泡归属</b></td><td><b>6 格开始错</b></td><td>女主的台词被安到男主脸上</td></tr>
<tr><td>格数控制</td><td>8 格开始失控</td><td>要 8 格出 10 格</td></tr>
</table>
<ul>
<li><b>4 格是「对白 + 归属 + 格数」三样全对的最后一档。</b></li>
<li>每格按类型分三种：<b>说</b>（圆形气泡 + 写明说话人 + 尾部指向）、
<b>白</b>（矩形旁白，只补画面看不到的信息）、<b>静</b>（无字留白）。
「静默格」是漫画的停顿手法，不算缺陷。</li>
<li><b>旁白不能复述画面。</b>写「车站没有人」「灯亮着」这类看图就懂的句子，
就变成给图配字幕了——那不是漫画。</li>
<li><b>说话人必须逐格写死。</b>只写「气泡尾部指向说话的人」等于留空，模型只能猜；
写成「气泡尾部明确指向千夏」才生效。</li>
<li>6–8 格能出好看的页面，但要逐格核气泡归属；8 格以上先解决格数失控。</li>
</ul>
<b>未完成</b>：9 / 12 格没跑——生成时 ComfyUI 队列被其他任务占着，撤了自己的待跑任务没有抢占 GPU。
</div></div>
<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src="" alt=""></div>
<script>function zoom(e){document.getElementById('lbimg').src=e.src;
document.getElementById('lb').classList.add('on')}
document.addEventListener('keydown',function(e){
if(e.key==='Escape')document.getElementById('lb').classList.remove('on')})</script>
</body></html>"""

    doc = doc.replace("__CARDS__", "".join(cards))
    out = os.path.join(HERE, "panels.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("written %s（%d 张）" % (out, len(cards)))


if __name__ == "__main__":
    main()
