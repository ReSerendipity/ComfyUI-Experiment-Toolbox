# -*- coding: utf-8 -*-
"""跨模型对照矩阵页

扫 `samples_ab/<type>_<family>.jpg`，生成 `ab_matrix.html`：
行 = 版式类型，列 = 模型家族，格子里直接放成品图。

用法：
  python build_ab.py
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AB = os.path.join(HERE, "samples_ab")
E = lambda s: html.escape(s, quote=False)

TYPES = [
    ("tarot", "塔罗牌", "标签级"),
    ("dossier", "人物档案卡", "标签级"),
    ("magazine", "杂志封面", "标题级"),
    ("poster", "电影海报", "标题级"),
    ("app_ui", "手机 App 界面", "标签级"),
    ("packaging", "产品包装", "段落级"),
    ("infographic", "中文信息图", "段落级"),
    ("elevation", "建筑立面图", "标注级"),
    ("storyboard", "电影故事板", "标签级"),
    ("yonkoma", "四格漫画", "对话级"),
]
FAMILIES = [
    ("moss", "MOSS-Image SFT", "30 步 / CFG 4 / euler"),
    ("qwen", "Qwen-Image-2.1-turbo", "8 步 / CFG 1 / euler"),
]
# 其余家族已排除：中文文字能力不足，见 06_文档与结论/版式化是否MOSS专属-跨模型对照.md
# 判定依据是 2026-10-31 的四语文字评测（9 模型 × 4 语言，同提示词同 seed）


def main():
    head = "".join(
        '<th><span class="fam">%s</span><span class="par">%s</span></th>'
        % (E(label), E(par)) for _k, label, par in FAMILIES)

    rows = []
    for key, label, dens in TYPES:
        cells = []
        for fam, _l, _p in FAMILIES:
            p = os.path.join(AB, "%s_%s.jpg" % (key, fam))
            if os.path.isfile(p):
                cells.append('<td><img src="samples_ab/%s_%s.jpg" alt="%s %s" '
                             'loading="lazy" onclick="zoom(this)"></td>' % (key, fam, key, fam))
            else:
                cells.append('<td><div class="miss">—</div></td>')
        rows.append('<tr><th class="row"><b>%s</b><span>%s</span></th>%s</tr>'
                    % (E(label), E(dens), "".join(cells)))

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>跨模型对照 · 版式化文生图</title>
<style>
:root{--bg:#f5f3ed;--paper:#fffefa;--ink:#1b1a17;--ink2:#565248;--ink3:#8d887a;
--line:#e0dbcf;--accent:#b04a2f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7;
font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1720px;margin:0 auto;padding:52px 26px 80px}
h1{font-family:"Songti SC",Georgia,serif;font-size:34px;margin:0 0 8px}
.sub{color:var(--ink2);font-size:14px;margin:0 0 8px;max-width:900px}
.meta{font-size:12.5px;color:var(--ink3);margin:0 0 30px}
table{width:100%;border-collapse:separate;border-spacing:8px}
thead th{font-size:12px;font-weight:600;text-align:left;padding:0 0 8px;vertical-align:bottom}
.fam{display:block;font-size:12.5px;color:var(--ink)}
.par{display:block;font-size:10.5px;color:var(--ink3);font-weight:400;margin-top:2px}
th.row{width:104px;text-align:left;vertical-align:middle;font-family:"Songti SC",Georgia,serif}
th.row b{display:block;font-size:14px;font-weight:600}
th.row span{display:block;font-size:11px;color:var(--ink3);font-weight:400;margin-top:2px}
td{background:var(--paper);border:1px solid var(--line);border-radius:8px;
padding:6px;vertical-align:top;width:11.5%}
td img{width:100%;display:block;border-radius:4px;cursor:zoom-in}
.miss{height:150px;display:flex;align-items:center;justify-content:center;color:#c9c3b6}
.note{margin-top:36px;font-size:13px;color:var(--ink2);background:var(--paper);
border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:18px 22px}
.note b{color:var(--ink)}
.note ul{margin:8px 0 0;padding-left:20px}
.note li{margin:4px 0}
#lb{position:fixed;inset:0;background:rgba(18,17,15,.94);display:none;align-items:center;
justify-content:center;z-index:99;padding:28px;cursor:zoom-out}
#lb.on{display:flex}#lb img{max-width:100%;max-height:100%}
@media(max-width:1100px){td{width:auto}table,tbody,tr{display:block}
thead{display:none}th.row{margin-top:26px}td{display:inline-block;width:31%;margin:4px 1%}}
</style></head><body><div class="wrap">
<h1>跨模型对照 · 版式化文生图</h1>
<p class="sub">同一段版式化提示词、同一个 seed，两个模型各跑十类。看两件事：
<b>版式骨架有没有落位</b>、<b>中文字有没有写对</b>。</p>
<p class="meta">__N__ 张 · 10 类版式 × 2 个模型 · 单种子单次生成，未修图</p>
<table><thead><tr><th></th>__HEAD__</tr></thead><tbody>__ROWS__</tbody></table>
<div class="note">
<b>怎么读这张表：</b>
<ul>
<li>版式骨架两个模型都成立；差别集中在<b>文字</b>与<b>质感</b>。</li>
<li>MOSS 出厚涂装饰感，Qwen 出平涂干净感；Qwen 快约 2.4 倍。</li>
<li>难度递增大致是 包装 &lt; 塔罗 &lt; 四格 &lt; 海报 &lt; 封面 &lt; 界面 &lt; 故事板 &lt; 信息图 &lt; 档案卡 &lt; 立面图。
「标注级」的立面图（尺寸线、标高、标题栏小字）是全场最难的一格。</li>
<li><b>为什么只有两个模型</b>：其余家族在 2026-10-31 的四语文字评测里已经暴露出文字能力不足
（FLUX.1-dev 把中文写成韩文；FLUX.2-klein 大面积伪汉字；Krea2 菜单多处错字），
不再纳入版式对照。判定依据见 <code>06_文档与结论/版式化是否MOSS专属-跨模型对照.md</code>。</li>
</ul>
</div></div>
<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src="" alt=""></div>
<script>function zoom(e){document.getElementById('lbimg').src=e.src;
document.getElementById('lb').classList.add('on')}
document.addEventListener('keydown',function(e){
if(e.key==='Escape')document.getElementById('lb').classList.remove('on')})</script>
</body></html>"""

    n = sum(1 for k, _l, _d in TYPES for f, _a, _b in FAMILIES
            if os.path.isfile(os.path.join(AB, "%s_%s.jpg" % (k, f))))
    doc = (doc.replace("__N__", str(n))
              .replace("__HEAD__", head)
              .replace("__ROWS__", "".join(rows)))

    out = os.path.join(HERE, "ab_matrix.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("written %s（%d 张）" % (out, n))


if __name__ == "__main__":
    main()
