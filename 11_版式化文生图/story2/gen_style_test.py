# -*- coding: utf-8 -*-
"""画风试点 · 同分镜同 seed，只换画风块

输出 `style_test/<画风>_p<页>.jpg`，并生成 `style_test.html` 做四宫格对比。

唯一变量原则：两页各自固定 seed，四种画风共用同一 seed，其余提示词一字不改。

用法：
  python gen_style_test.py            # 全 4 画风 × 2 页
  python gen_style_test.py --plan     # 只看计划
  python gen_style_test.py cel water  # 只跑指定画风
"""
import html
import io
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_data as SD
from layout_runner import SERVER, run

OUT = os.path.join(HERE, "style_test")
W, H = 800, 1200
STEPS, CFG, SAMPLER, SCHED = 30, 4.0, "euler", "simple"
# 官方推荐负向词；各画风再追加自己的（黑白网点要点名颜色）
NEG_BASE = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"
E = lambda s: html.escape(s, quote=False)


def fetch(image):
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(SERVER + "/view" + q, timeout=120) as r:
        return r.read()


def save_jpg(raw, dst, quality=88):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def build_html(done):
    """四画风 × 两页 的对比页。done: {(style_key, page_no): relpath}"""
    head = "".join("<th>%s<br><span>%s</span></th>" % (E(s["label"]), E(s["note"]))
                   for s in SD.STYLES)
    rows = []
    for p in SD.TEST_PAGES:
        cells = []
        for s in SD.STYLES:
            rel = done.get((s["key"], p["no"]))
            cells.append('<td>%s</td>' % (
                '<img src="%s" alt="%s" onclick="zoom(this)">' % (rel, E(s["label"]))
                if rel else '<div class="miss">未生成</div>'))
        rows.append('<tr><th class="row">P%d<br><span>%s</span></th>%s</tr>'
                    % (p["no"], E(p["name"]), "".join(cells)))

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>画风试点 · %(title)s</title>
<style>
:root{--bg:#f6f4ee;--paper:#fffefa;--ink:#1b1a17;--ink2:#565248;--ink3:#8d887a;
--line:#e3ded2;--accent:#b04a2f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7;
font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:48px 28px 80px}
h1{font-family:"Songti SC",Georgia,serif;font-size:34px;margin:0 0 8px}
.sub{color:var(--ink2);font-size:14px;margin:0 0 8px}
.meta{font-size:12.5px;color:var(--ink3);margin:0 0 30px}
table{width:100%%;border-collapse:separate;border-spacing:14px}
th{font-size:14px;font-weight:600;text-align:left;padding:0 0 6px}
th span{font-weight:400;font-size:11.5px;color:var(--ink3)}
th.row{width:96px;vertical-align:middle;font-family:"Songti SC",Georgia,serif;
font-size:15px;padding-right:6px}
th.row span{display:block;color:var(--ink3);font-size:11.5px;margin-top:2px}
td{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:10px;
vertical-align:top;width:22%%}
td img{width:100%%;border-radius:5px;display:block;cursor:zoom-in}
.miss{height:320px;display:flex;align-items:center;justify-content:center;
color:var(--ink3);font-size:12.5px}
.note{margin-top:34px;font-size:13px;color:var(--ink2);background:var(--paper);
border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:18px 22px}
.note b{color:var(--ink)}
#lb{position:fixed;inset:0;background:rgba(20,19,16,.93);display:none;align-items:center;
justify-content:center;z-index:99;padding:30px;cursor:zoom-out}
#lb.on{display:flex}#lb img{max-width:100%%;max-height:100%%}
@media(max-width:900px){table,tbody,tr,td,th{display:block;width:auto}
th.row{margin-top:26px}}
</style></head><body><div class="wrap">
<h1>画风试点 · %(title)s</h1>
<p class="sub">同一段分镜、同一个 seed，只换画风块——其余提示词一字不改。</p>
<p class="meta">%(nstyles)d 种画风 × %(npages)d 页 &nbsp;·&nbsp; %(size)s &nbsp;·&nbsp;
euler / %(steps)d 步 / CFG %(cfg).1f &nbsp;·&nbsp; 单种子单次生成，未修图</p>
<table><thead><tr><th></th>%(head)s</tr></thead><tbody>%(rows)s</tbody></table>
<div class="note">
<b>怎么挑：</b>看三件事——① 雨夜那页的<b>光比</b>够不够狠；② 老人那页的<b>手背与猫毛</b>有没有质感；
③ 台词气泡里的中文字在缩放后是否还认得出。选定一个，我按它出全 8 页。
<br><br>
<b>本轮已修的两处：</b>① 角色卡改为<b>按页取子集</b>（P1 只有少年与猫，P6 只有老人与猫），
第一轮把全员都画进来了；② 黑白网点改为<b>逐项交代网点替代方案</b>并把颜色写进负向词，
第一轮虽然加了「不使用任何彩色」，模型仍保留了蓝色卫衣与橘色斑块。
</div></div>
<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src="" alt=""></div>
<script>function zoom(e){document.getElementById('lbimg').src=e.src;
document.getElementById('lb').classList.add('on')}
document.addEventListener('keydown',function(e){
if(e.key==='Escape')document.getElementById('lb').classList.remove('on')})</script>
</body></html>""" % dict(title=E(SD.TITLE), nstyles=len(SD.STYLES),
                         npages=len(SD.TEST_PAGES), size=SD.SIZE, steps=STEPS,
                         cfg=CFG, head=head, rows="".join(rows))


def main(argv):
    want = [a for a in argv if not a.startswith("--")] or [s["key"] for s in SD.STYLES]
    if "--plan" in argv:
        for s in SD.STYLES:
            print("%-8s %-10s %s" % (s["key"], s["label"], s["note"]))
        for p in SD.TEST_PAGES:
            full = SD.page(p["body"], p["tone"], SD.STYLES[0]["block"], p["cast"])
            print("P%d %-8s seed=%d  角色=%s  %d 字"
                  % (p["no"], p["name"], p["seed"], "+".join(p["cast"]), len(full)))
        return 0

    os.makedirs(OUT, exist_ok=True)
    done, ok = {}, 0
    for p in SD.TEST_PAGES:
        for s in SD.STYLES:
            if s["key"] not in want:
                continue
            neg = ", ".join(x for x in [NEG_BASE, s.get("neg", "")] if x)
            rec = dict(name="styletest_%s_p%02d" % (s["key"], p["no"]),
                       prompt=SD.page(p["body"], p["tone"], s["block"], p["cast"]),
                       negative=neg,
                       width=W, height=H, steps=STEPS, cfg=CFG,
                       sampler=SAMPLER, scheduler=SCHED, seed=p["seed"])
            imgs = run(rec)
            rel = "%s_p%d.jpg" % (s["key"], p["no"])
            if imgs:
                size = save_jpg(fetch(imgs[0]), os.path.join(OUT, rel))
                done[(s["key"], p["no"])] = "style_test/" + rel
                ok += 1
                print("[saved]  %-18s %6.1fKB" % (rel, size / 1024), flush=True)

    open(os.path.join(HERE, "style_test.html"), "w", encoding="utf-8").write(build_html(done))
    print("[summary] %d 张；style_test.html 已写" % ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
