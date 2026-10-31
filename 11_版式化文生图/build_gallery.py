# -*- coding: utf-8 -*-
"""版式化文生图 · 画廊构建

由 `layout_types.py` 直接生成 `gallery.html`：提示词与实跑一致，不手抄。
若存在 `story/story.json`，同时渲染短篇漫画阅读区。

用法：
  python build_gallery.py            # 写 gallery.html
"""
import html
import json
import os

import layout_types as LT

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
STORY = os.path.join(HERE, "story", "story.json")

E = lambda s: html.escape(s, quote=False)

# 展示顺序 + 一句话定位 + 实拍备注
META = {
    "tarot": ("塔罗牌", "外框 + 罗马数字 + 中英牌名，单主体强象征",
              "XVII 与 7 颗小星位置准确，金线双框完整"),
    "dossier": ("人物档案卡", "左立绘 + 右数据面板，能力条形图按数值等比",
                "四条能力条长度与 8/9/7/6 严格等比，红章自然压边"),
    "magazine": ("杂志封面", "刊名横贯顶部 + 左侧导读 + 价格角标 + 条码",
                 "刊名 / 期号 / 三条导读 / ¥38.00 / 条码全部到位"),
    "poster": ("电影海报", "主视觉占上 2/3 + 标语 + 主标题 + credit block",
               "中英标题层级正确，四行 credit block 字号自动缩小且可读"),
    "app_ui": ("手机 App 界面", "状态栏 → 主数据卡 → 三分类卡 → 列表 → 底部 tab",
               "金额 / 图标 / tab 全对；环形进度弧被画成分段（已知弱点）"),
    "packaging": ("产品包装", "封口条 → 圆形插画 → 品牌 → 品名风味 → 刻度 + 净含量",
                  "几乎可直接投产，烘焙刻度指针与产地行都在"),
    "infographic": ("中文信息图", "标题带 + 四等高区块（图标 / 阶段 / 说明 / 数字）",
                    "四区块对齐严格，橙色数字层级清楚"),
    "elevation": ("建筑立面图", "图框 + 正立面 + 尺寸线 / 标高 + 标题栏 + 指北针",
                  "尺寸线、标高符号、标题栏全部成图；开窗数未严格按 3 扇"),
    "storyboard": ("电影故事板", "2×3 画格，每格一条 镜号 / 景别 / 运镜 说明条",
                   "六格叙事连贯，铅笔排线质感统一，英文说明条全部正确"),
    "yonkoma": ("四格漫画", "2×2 等大格，起承转合，每格一枚台词气泡",
                "四格气泡台词全对，猫与人物造型跨格一致"),
}
ORDER = ["tarot", "dossier", "magazine", "poster", "app_ui", "packaging",
         "infographic", "elevation", "storyboard", "yonkoma"]
FAMILY_COLOR = {"A": "#b04a2f", "B": "#2f5d50"}

PRINCIPLES = [
    ("01", "先声明「这是一件完整的平面物」",
     "开头第一句不是描述画面，而是锁定对象：<b>整张…完整展示 / 四边与画面边缘平行 / "
     "居中排列 / 四周留少量背景</b>。这一句决定模型进入「排版模式」还是「插画模式」。"),
    ("02", "版式骨架用方位词顺序推进",
     "顶部 → 中央 → 底部，左侧 → 右侧，逐区块描述、不跳序。模型按 token 顺序建版面，"
     "乱序会把后提到的区块挤到错位。"),
    ("03", "文字块单独成段 +「写出：」+ 空行 + 原文",
     "文字渲染的触发格式。<b>写出：\\n\\n青眼白龙\\n\\n四个字横向排列…</b> —— 换行即分段，"
     "原文独占一行，模型才把它当「要画的字」而不是「要理解的描述」。"),
    ("04", "文字四件套：颜色 + 字号 + 字体 + 对齐",
     "每个文字块都给全：<b>黑色 / 大号 / 楷书风格 / 位置偏左</b>。缺任何一项，模型会自己选。"),
    ("05", "数量与数值必须写死",
     "8 枚星、9 格、ATK/3000、89631143、¥3,842.60、1900 M。模糊表述会被四舍五入。"),
    ("06", "结尾一段枚举色板做全局收束",
     "<b>配色限定为米白、深棕、淡赭与一点橙红</b> 比零散提色更能压住一致性。"),
    ("07", "否定约束写在相关段落同句内",
     "「不使用任何彩色」「绝非真人照片」「无阴影无材质」——有效，但堆在末尾会衰减。"),
]

PARAM_TABLE = [
    ("采样器", "euler", "er_sde", "两种都能复刻成功；模板默认也正常"),
    ("步数", "30", "25", "25 步已足够，30 步更稳，耗时 +30%"),
    ("CFG", "4.0", "2.5", "CFG 4 文字更锐，2.5 画面更柔；文字密集时用 4"),
    ("调度器", "simple", "simple", "无差异"),
    ("分辨率", "1024×1536 / 720×1280", "1024×1536", "宽高必须为 16 的倍数；总像素 1M–2M 最佳"),
    ("SLG", "关", "关（switch=false）", "官方建议开时跳过层 22；动漫风格可能过曝"),
]


def _img(key):
    p = os.path.join(SAMPLES, "%s.jpg" % key)
    return "samples/%s.jpg" % key if os.path.isfile(p) else ""


def render_type_card(k):
    t = LT.get(k)
    label, tagline, note = META[k]
    fam = t["family"][0]
    w, h = t["size"]
    src = _img(k)
    if src:
        media = '<img src="%s" alt="%s" loading="lazy">' % (src, E(label))
    else:
        media = ('<div class="missing">samples/%s.jpg 缺失<br>'
                 '<span>python gen_types.py %s</span></div>' % (k, k))
    return """
    <article class="tcard" data-family="{fam}">
      <div class="tcard-media" onclick="zoom(this)">
        {media}
        <span class="badge" style="--c:{color}">{family}</span>
      </div>
      <div class="tcard-body">
        <div class="tcard-head"><h3>{label}</h3><code>{key}</code></div>
        <p class="tagline">{tagline}</p>
        <dl class="spec">
          <dt>版式骨架</dt><dd>{skeleton}</dd>
          <dt>文字密度</dt><dd>{density}</dd>
          <dt>分辨率</dt><dd>{w} × {h} · 30 步 · CFG 4.0 · euler</dd>
        </dl>
        <p class="note"><span>实拍</span>{note}</p>
        <details><summary>查看完整提示词（{plen} 字）</summary><pre>{prompt}</pre></details>
      </div>
    </article>""".format(fam=fam, media=media, color=FAMILY_COLOR[fam], family=E(t["family"]),
                         label=E(label), key=k, tagline=E(tagline), skeleton=E(t["skeleton"]),
                         density=E(t["density"]), w=w, h=h, note=E(note),
                         plen=len(t["prompt"]), prompt=E(t["prompt"]))


def render_story():
    """story/story.json 存在则渲染阅读区。"""
    if not os.path.isfile(STORY):
        return ""
    s = json.load(open(STORY, encoding="utf-8"))
    pages = []
    for p in s.get("pages", []):
        pages.append("""
      <figure class="page">
        <img src="story/{src}" alt="第 {n} 页" loading="lazy" onclick="zoom(this)">
        <figcaption><b>第 {n} 页</b> · {cap}<em>{line}</em></figcaption>
      </figure>""".format(src=p["image"], n=p["no"], cap=E(p.get("caption", "")),
                          line=E(p.get("line", ""))))
    return """
<section id="story">
  <div class="sec-head"><span class="no">04</span><h2>{title}</h2></div>
  <p class="sec-sub">{logline}</p>
  <div class="story-meta">
    <span>题材 <b>{genre}</b></span><span>页数 <b>{n} 页</b></span>
    <span>画幅 <b>{size}</b></span><span>口径 <b>euler / 30 步 / CFG 4</b></span>
  </div>
  <div class="story">{pages}</div>
  <p class="sec-sub" style="margin-top:26px">{note}</p>
</section>""".format(title=E(s.get("title", "")), logline=E(s.get("logline", "")),
                     genre=E(s.get("genre", "")), n=len(s.get("pages", [])),
                     size=E(s.get("size", "")), pages="".join(pages), note=E(s.get("note", "")))


def main():
    types_html = "\n".join(render_type_card(k) for k in ORDER)
    principles = "".join('<li><span class="num">%s</span><h4>%s</h4><p>%s</p></li>' % (n, E(t), c)
                         for n, t, c in PRINCIPLES)
    ptable = "".join("<tr><td>%s</td><td class='mono'>%s</td><td class='mono'>%s</td><td>%s</td></tr>"
                     % (E(a), E(b), E(c), E(d)) for a, b, c, d in PARAM_TABLE)
    story_html = render_story()

    doc = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>版式化文生图 · 类型库与复刻方法</title>
<style>
:root {{ --bg:#f6f4ee; --paper:#fffefa; --ink:#1b1a17; --ink2:#565248; --ink3:#8d887a;
  --line:#e3ded2; --accent:#b04a2f; --green:#2f5d50;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-size:15px; line-height:1.75;
  font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1240px; margin:0 auto; padding:0 32px; }}
h1,h2,h3,h4 {{ font-family:"Songti SC","Source Han Serif SC",Georgia,serif; font-weight:600; }}
header {{ padding:74px 0 42px; border-bottom:1px solid var(--line); }}
.kicker {{ font-size:12px; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); margin-bottom:18px; }}
header h1 {{ font-size:42px; line-height:1.3; margin:0 0 18px; }}
header h1 em {{ font-style:normal; color:var(--accent); }}
.lede {{ font-size:16px; color:var(--ink2); max-width:800px; margin:0 0 28px; }}
.meta-row {{ display:flex; flex-wrap:wrap; gap:10px; }}
.chip {{ font-size:12.5px; padding:5px 12px; border:1px solid var(--line); border-radius:999px;
  background:var(--paper); color:var(--ink2); }}
.chip b {{ color:var(--ink); font-weight:600; }}
nav {{ position:sticky; top:0; z-index:50; background:rgba(246,244,238,.93);
  backdrop-filter:blur(10px); border-bottom:1px solid var(--line); }}
nav .wrap {{ display:flex; gap:26px; align-items:center; height:52px; overflow-x:auto; }}
nav a {{ color:var(--ink2); text-decoration:none; font-size:13.5px; white-space:nowrap; }}
nav a:hover {{ color:var(--accent); }}
nav .brand {{ font-weight:600; color:var(--ink); margin-right:8px; font-size:13.5px; }}
section {{ padding:62px 0 8px; }}
.sec-head {{ display:flex; align-items:baseline; gap:16px; margin-bottom:8px; }}
.sec-head .no {{ font-family:var(--mono); font-size:12px; color:var(--accent); letter-spacing:.1em; }}
.sec-head h2 {{ font-size:28px; margin:0; }}
.sec-sub {{ color:var(--ink2); max-width:860px; margin:6px 0 32px; }}
ol.principles {{ list-style:none; margin:0; padding:0; display:grid;
  grid-template-columns:repeat(2,1fr); gap:2px; background:var(--line);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
ol.principles li {{ background:var(--paper); padding:24px 26px; }}
ol.principles li:last-child {{ grid-column:1/-1; }}
ol.principles .num {{ font-family:var(--mono); font-size:12px; color:var(--accent); }}
ol.principles h4 {{ margin:6px 0 8px; font-size:17px; }}
ol.principles p {{ margin:0; font-size:13.5px; color:var(--ink2); }}
ol.principles b {{ color:var(--ink); font-weight:600; background:#f3ece2; padding:0 3px; border-radius:3px; }}
.filters {{ display:flex; gap:8px; margin-bottom:24px; flex-wrap:wrap; }}
.filters button {{ font:inherit; font-size:13px; padding:6px 15px; border-radius:999px;
  border:1px solid var(--line); background:var(--paper); color:var(--ink2); cursor:pointer; }}
.filters button.on {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
.tgrid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:26px; }}
.tcard {{ background:var(--paper); border:1px solid var(--line); border-radius:14px;
  overflow:hidden; display:flex; flex-direction:column; }}
.tcard-media {{ position:relative; background:#efece4; display:flex; align-items:center;
  justify-content:center; padding:22px; min-height:300px; }}
.tcard-media img {{ max-width:100%; max-height:460px; border-radius:6px; display:block;
  box-shadow:0 8px 28px rgba(0,0,0,.13); cursor:zoom-in; }}
.missing {{ font-size:12.5px; color:var(--ink3); text-align:center; }}
.missing span {{ font-family:var(--mono); color:var(--accent); }}
.badge {{ position:absolute; top:14px; left:14px; font-size:11px; letter-spacing:.06em;
  background:var(--c); color:#fff; padding:3px 10px; border-radius:999px; }}
.tcard-body {{ padding:20px 24px 22px; display:flex; flex-direction:column; gap:12px; flex:1; }}
.tcard-head {{ display:flex; align-items:baseline; gap:10px; }}
.tcard-head h3 {{ margin:0; font-size:19px; }}
.tcard-head code {{ font-family:var(--mono); font-size:11.5px; color:var(--ink3); }}
.tagline {{ margin:0; font-size:13.5px; color:var(--ink2); }}
dl.spec {{ margin:0; display:grid; grid-template-columns:72px 1fr; gap:6px 12px; font-size:12.5px; }}
dl.spec dt {{ color:var(--ink3); }}
dl.spec dd {{ margin:0; color:var(--ink); }}
.note {{ margin:0; font-size:12.5px; color:var(--ink2); background:#f4f1e9;
  border-radius:6px; padding:9px 12px; }}
.note span {{ font-size:11px; letter-spacing:.1em; color:var(--accent); margin-right:8px; font-weight:600; }}
details summary {{ cursor:pointer; font-size:12.5px; color:var(--accent); }}
details pre {{ white-space:pre-wrap; font-family:inherit; font-size:12.5px; line-height:1.8;
  color:var(--ink2); background:#f8f6f0; border:1px solid var(--line); border-radius:8px;
  padding:16px; margin:12px 0 0; max-height:340px; overflow:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; background:var(--paper);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
th,td {{ text-align:left; padding:12px 16px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:11.5px; letter-spacing:.12em; color:var(--ink3); font-weight:600; background:#f9f7f1; }}
tr:last-child td {{ border-bottom:none; }}
td.mono {{ font-family:var(--mono); font-size:12.5px; }}
.story-meta {{ display:flex; flex-wrap:wrap; gap:22px; font-size:12.5px; color:var(--ink3);
  margin-bottom:26px; padding-bottom:18px; border-bottom:1px solid var(--line); }}
.story-meta b {{ color:var(--ink); }}
.story {{ display:grid; grid-template-columns:repeat(2,1fr); gap:28px; }}
.story .page {{ margin:0; }}
.story .page img {{ width:100%; border-radius:8px; border:1px solid var(--line);
  box-shadow:0 10px 30px rgba(0,0,0,.1); cursor:zoom-in; display:block; }}
.story figcaption {{ font-size:12.5px; color:var(--ink2); margin-top:10px; }}
.story figcaption b {{ color:var(--accent); }}
.story figcaption em {{ display:block; font-style:normal; color:var(--ink3); font-size:12px; margin-top:3px; }}
pre.shell {{ background:#1b1a17; color:#e8e3d6; border-radius:10px; padding:20px 24px;
  font-family:var(--mono); font-size:12.5px; line-height:1.85; overflow:auto; }}
pre.shell .c {{ color:#8d887a; }}
footer {{ margin-top:66px; padding:34px 0 60px; border-top:1px solid var(--line);
  font-size:12.5px; color:var(--ink3); }}
footer b {{ color:var(--ink2); }}
#lb {{ position:fixed; inset:0; background:rgba(20,19,16,.93); display:none;
  align-items:center; justify-content:center; z-index:999; padding:36px; cursor:zoom-out; }}
#lb.on {{ display:flex; }}
#lb img {{ max-width:100%; max-height:100%; border-radius:6px; }}
@media (max-width:900px) {{
  .tgrid,.story,ol.principles {{ grid-template-columns:1fr; }}
  header h1 {{ font-size:30px; }}
  .wrap {{ padding:0 20px; }}
}}
</style>
</head>
<body>

<header><div class="wrap">
  <div class="kicker">MOSS-Image · Layout-Conditioned Text-to-Image</div>
  <h1>把「一张图」当<em>版面</em>来生成<br>类型库与复刻方法</h1>
  <p class="lede">
    以两张版式化作品为基准做复刻验证，把「结构化中文提示词」抽象成两条主线共 10 类版式骨架，
    再用同一套骨架做出连贯短篇漫画。
  </p>
  <div class="meta-row">
    <span class="chip">模型 <b>moss_image_sft_int8_convrot</b></span>
    <span class="chip">文本编码器 <b>qwen3.5_9b_int8_convrot</b></span>
    <span class="chip">VAE <b>flux2-vae</b></span>
    <span class="chip">口径 <b>euler / 30 步 / CFG 4</b></span>
    <span class="chip">模块 <b>11_版式化文生图</b></span>
  </div>
</div></header>

<nav><div class="wrap">
  <span class="brand">目录</span>
  <a href="#method">01 七个要素</a>
  <a href="#types">02 类型矩阵</a>
  <a href="#params">03 参数口径</a>
  {story_nav}
  <a href="#usage">05 复用方式</a>
</div></nav>

<main class="wrap">

<section id="method">
  <div class="sec-head"><span class="no">01</span><h2>可复刻的七个要素</h2></div>
  <p class="sec-sub">
    核心结论：<b>版式是模型的先验，文字是必须显式注入的内容</b>。
    同 seed 同参数，1751 字结构化提示词能复刻出逐字正确的卡牌；换成 9 字短提示，
    卡牌结构仍然完整，但说明栏文字退化成伪汉字、卡号变成乱码。
    由此得到七条可复用规则，详见 <code>docs/版式化提示词七要素.md</code>。
  </p>
  <ol class="principles">{principles}</ol>
</section>

<section id="types">
  <div class="sec-head"><span class="no">02</span><h2>类型扩展矩阵</h2></div>
  <p class="sec-sub">
    两条主线：<b>A 单画布多区块排版</b>（一张图 = 一个完整信息载体）与
    <b>B 多画布叙事序列</b>（一张图 = N 个镜头或画格）。每条类型都给出可复用的版式骨架、
    文字密度档位与推荐分辨率，全部单 seed 单次生成通过验收。
  </p>
  <div class="filters">
    <button class="on" onclick="filt(this,'all')">全部 10 类</button>
    <button onclick="filt(this,'A')">A 单画布排版 8 类</button>
    <button onclick="filt(this,'B')">B 叙事序列 2 类</button>
  </div>
  <div class="tgrid">
{types}
  </div>
</section>

<section id="params">
  <div class="sec-head"><span class="no">03</span><h2>参数口径</h2></div>
  <p class="sec-sub">
    原作标注的参数与官方模板默认值并不一致，实测两者都能复刻成功。
    <b>稳定性来自提示词结构，不来自采样参数</b>——参数只影响锐度与耗时。
  </p>
  <table>
    <thead><tr><th>项</th><th>本次口径</th><th>官方模板默认</th><th>实测结论</th></tr></thead>
    <tbody>{ptable}</tbody>
  </table>
</section>

{story}

<section id="usage">
  <div class="sec-head"><span class="no">05</span><h2>复用方式</h2></div>
  <p class="sec-sub">
    驱动把官方模板的子图摊平成 9 个节点直接提交 <code>/prompt</code>，
    不经前端、不改模板 JSON，参数就是参数，没有隐式状态。
  </p>
  <pre class="shell"><span class="c"># 0. 必须用 ComfyUI 自带 python，且 ComfyUI 已在 127.0.0.1:8188</span>
<span class="c"># 1. 契约自检：三件套是否在 /object_info 下拉表里（避免静默无图）</span>
python run.py lay --probe

<span class="c"># 2. 列类型 / 跑全部 / 跑指定类型</span>
python run.py lay --list
python run.py lay
python run.py lay tarot dossier

<span class="c"># 3. 自定义：写 recipe.json 交给驱动</span>
python run.py layrun recipe.json

<span class="c"># recipe.json 字段</span>
{{ "name": "my_card", "prompt": "...", "width": 1024, "height": 1536,
  "steps": 30, "cfg": 4.0, "sampler": "euler", "scheduler": "simple", "seed": 0 }}</pre>
  <p class="sec-sub" style="margin-top:22px">
    模型名口径：模型放在 <code>models/*/MOSS-Image/</code> 子目录时，组合框合法值是
    <code>MOSS-Image\\文件名</code>。写裸名会被判 <code>value_not_in_list</code>，
    节点输出被忽略、下游剪枝，最终 <code>status=success</code> 但 <code>outputs={{}}</code>——
    静默无图，最难查。所以第一步永远是 <code>--probe</code>。
  </p>
</section>

</main>

<footer><div class="wrap">
  <b>11 · 版式化文生图</b> &nbsp;·&nbsp; ComfyUI-Experiment-Toolbox &nbsp;·&nbsp;
  结论内核 <code>06_文档与结论/MOSS-Image-版式化文生图实测结论.md</code>。
  全部样张为单 seed 单次生成，未做后期修图。
</div></footer>

<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src="" alt=""></div>
<script>
function zoom(el) {{
  var src = el.tagName === 'IMG' ? el.src : el.querySelector('img').src;
  document.getElementById('lbimg').src = src;
  document.getElementById('lb').classList.add('on');
}}
function filt(btn, f) {{
  document.querySelectorAll('.filters button').forEach(function(b){{ b.classList.remove('on'); }});
  btn.classList.add('on');
  document.querySelectorAll('.tcard').forEach(function(c){{
    c.style.display = (f === 'all' || c.dataset.family === f) ? '' : 'none';
  }});
}}
document.addEventListener('keydown', function(e){{
  if (e.key === 'Escape') document.getElementById('lb').classList.remove('on');
}});
</script>
</body>
</html>""".format(principles=principles, types=types_html, ptable=ptable,
                 story=story_html,
                 story_nav='<a href="#story">04 短篇漫画</a>' if story_html else "")

    out = os.path.join(HERE, "gallery.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("written %s (%.1f KB)" % (out, len(doc) / 1024))


if __name__ == "__main__":
    main()
