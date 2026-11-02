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
    ("4_2x2_moss", 4, "800×1200", "4", "通过"),
    ("6_2x3_moss", 6, "800×1200", "7（1 格静默）", "通过"),
    ("8_2x4_moss", 8, "800×1200", "8", "通过"),
    ("9_3x3_moss", 9, "800×1200", "10（1 格静默）", "通过"),
    ("12_3x4_moss", 12, "800×1200", "15", "漂移"),
    ("16_4x4_moss", 16, "800×1200", "16", "漂移"),
    ("20_4x5_moss", 20, "800×1200", "20", "漂移"),
    ("12_3x4_hi_moss", 12, "1024×1536", "15", "漂移"),
    ("16_4x4_hi_moss", 16, "1024×1536", "16", "漂移"),
]


def main():
    cards = []
    for key, n, size, actual, verdict in ROWS:
        p = os.path.join(D, key + ".jpg")
        if not os.path.isfile(p):
            continue
        cls = "ok" if verdict == "通过" else "bad"
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
<p class="sub">同一段故事（少年回家路上的 16 个瞬间）、同一个 seed、同一套漫画页面语法
（画格大小不等 + 出血格 + 横向错位 + 气泡/旁白分级），<b>只改格数</b>。</p>
<p class="meta">MOSS-Image SFT · 30 步 / CFG 4 / euler · seed 20261111 · 单种子单次生成，未修图</p>
<div class="grid">__CARDS__
</div>
<div class="note">
<b>结论</b>
<table>
<tr><th>目标格数</th><th>800×1200</th><th>1024×1536</th><th>判定</th></tr>
<tr><td>4 / 6 / 8 / 9</td><td>格数基本准，台词全对</td><td>—</td><td>通过</td></tr>
<tr><td>12</td><td>出了 15 格，1 处伪汉字</td><td>15 格，重复 + 错序</td><td>漂移</td></tr>
<tr><td>16</td><td>16 格，3 组台词重复</td><td>16 格，2 组重复</td><td>漂移</td></tr>
<tr><td>20</td><td>20 格，重复 + 顺序错乱</td><td>—</td><td>漂移</td></tr>
</table>
<ul>
<li><b>漫画语法下，9 格以内稳。</b>6 格与 9 格各多出 1 个「静默格」（没有台词的空镜）——
这在漫画里是正常手法，不算缺陷。</li>
<li><b>12 格开始漂</b>：格数失控（要 12 出 15）、台词重复、顺序错乱、偶发伪汉字。</li>
<li><b>加分辨率救不回来</b>：1024×1536 同样漂。瓶颈不是像素，是模型对版面的注意力分配。</li>
<li><b>对比等大网格</b>：同一套测试用「等大网格」跑，20 格仍然干净、24 格才破。
也就是说<b>不等大排版吃掉了一半的格数余量</b>——换来的是漫画感。</li>
<li>20 格时单格画面质感也降级（厚涂退成平涂），说明高格数下模型会牺牲每格的渲染质量。</li>
</ul>
<b>怎么用</b>：一页 8–9 格是漫画语法的舒适区，能做大小节奏、出血、跨格；
真要 12 格以上，改回等大网格（故事板式）或拆成两页。
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
