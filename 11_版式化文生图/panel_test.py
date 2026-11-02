# -*- coding: utf-8 -*-
"""格数上限探针：同一段故事，只改格数与排布

要回答的是「一页最多能塞几格还不漂移」。控制变量：
- 故事相同（少年回家路上的 12 个瞬间，按顺序取前 N 个）
- 画幅相同（默认 800×1200）、采样相同、seed 相同
- **只有格数与排布在变**

每格都带一句短台词，这样可以逐格核对「第几格开始写错」。

用法：
  python panel_test.py --plan
  python panel_test.py                        # 默认 8 个配置 × moss
  python panel_test.py --models=moss,qwen     # 两个模型
  python panel_test.py --only=6x2,12x3        # 只跑指定配置
"""
import io
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import layout_runner as LR
from model_ab import FAMILIES, NEG, build, probe, submit

OUT = os.path.join(HERE, "samples_panels")

CAST = (
    "阿透，十七岁日本男高中生，黑色短发，深蓝色立领学生制服，肩上斜挎一个深色书包。\n"
    "千夏，十七岁日本女高中生，齐肩黑发，同款深蓝色立领学生制服（女式），背一个白色帆布包。"
)

# 一幕戏的 12 个节拍：(画面动作, 文字, 类型)
# 类型：说=圆形台词气泡（注明谁说的、尾部指向谁）／白=矩形旁白（只补画面看不到的）／静=无字
BEATS = [
    ("黄昏的无人车站，阿透坐在长椅上，手里捏着一张揉皱的时刻表", "阿透",
     "末班车……还有四十分钟。", "说"),
    ("站台另一头，千夏拖着脚步走过来，书包带子滑到手腕", None,
     "这个站，一天只有四班车。", "白"),
    ("千夏在隔两个座位的地方坐下，把书包放在膝上，两个人都不说话", None, "", "静"),
    ("阿透侧过眼睛偷看她，她低头按手机，屏幕是暗的", "千夏",
     "……没信号。", "说"),
    ("千夏抬头看站牌，站牌上的时刻被雨水泡得发白", "千夏",
     "这站……真的还有车吗？", "说"),
    ("阿透转过头，正对着她，两个人的视线第一次接上", "阿透",
     "有。四点二十。", "说"),
    ("一阵风穿过站台，长椅上的落叶被卷起来，两个人的头发都被吹乱", None, "", "静"),
    ("千夏把手插进外套口袋，缩了缩肩，往他那边挪了半个座位", "千夏",
     "我以为，没人会在这一站下车。", "说"),
    ("阿透看着铁轨一直延伸进黑暗里，没有回头", "阿透",
     "我每天都坐。", "说"),
    ("铁轨尽头出现一点灯光，越来越近，把铁轨照成两条亮线", "千夏",
     "……来了。", "说"),
    ("两个人同时站起来，千夏往车门方向走，走了两步回过头", "千夏",
     "明天，也这个点？", "说"),
    ("阿透愣了一下，点头，车门打开，光整片洒在站台上", "阿透",
     "嗯。", "说"),
    ("车门滑开，车厢里几乎空着，只有几盏灯亮着", None, "", "静"),
    ("两个人一前一后上车，他站在门边，她往里走了几步，回头", "千夏",
     "……你坐哪儿？", "说"),
    ("他抬手，指了指靠门的位置，书包还挂在肩上", "阿透",
     "这儿。", "说"),
    ("车门关上，车厢轻轻一晃，窗外的站台开始向后退", "千夏",
     "明天见。", "说"),
]

# (key, 列, 行, 宽, 高)
CONFIGS = [
    ("4_2x2", 2, 2, 800, 1200),
    ("6_2x3", 2, 3, 800, 1200),
    ("8_2x4", 2, 4, 800, 1200),
    ("9_3x3", 3, 3, 800, 1200),
    ("12_3x4", 3, 4, 800, 1200),
    ("16_4x4", 4, 4, 800, 1200),
    ("12_3x4_hi", 3, 4, 1024, 1536),
    ("16_4x4_hi", 4, 4, 1024, 1536),
]

STYLE = "统一画风：日式剧场版动画的厚涂美术风格，笔触可见，强明暗对比，电影级构图与景深虚化，写实光影但保留动画造型，绝非真人照片。"

# 漫画页面语法：不是等大网格。每档格数给一套「大小节奏 + 出血 + 错位」的排布描述。
GRAMMAR = (
    "整页采用日式漫画的页面语法，**不要等大的网格**："
    "画格大小明显不等，形成大小节奏；"
    "至少有一个画格出血——突破页面的左边或右边或上边，直接顶到纸张边缘；"
    "画格之间的间隙宽窄不一，格线不全是横平竖直，相邻两行之间允许横向错位。\n"
    "这一页是一段有来有往的对白戏，靠人物说话推进："
    "台词用圆形气泡，气泡尾部必须指向说话的那个人；旁白用矩形框，"
    "**旁白只补画面里看不到的信息**（时间、前情、心里想的），"
    "绝对不要用旁白复述画面里已经画出来的东西（不要写「车站没有人」「灯亮着」这类看图就懂的句子）；"
    "没有台词的格子就让它安静，不要给它配任何说明文字。"
)

LAYOUTS = {
    4: "页面上部是一个横贯全宽、左右出血的大画格；中部左右分成两格，左边窄、右边宽，两格高度不一样；"
       "底部一个横贯全宽的画格，比中部两格矮，右下角略低。",
    6: "页面上部是一个横贯全宽、左右出血的大画格；第二行左右分成两格，左窄右宽；"
       "第三行左侧是一个竖长的画格，高度占两行，右侧上下各一个小画格。",
    8: "页面上部是一个横贯全宽、左右出血的大画格；第二行分成三格，宽窄不等；"
       "第三行左侧一个竖长画格，右侧上下各一格；底部一个横贯全宽、比上部矮的窄画格。",
    9: "页面上部是一个横贯全宽、左右出血的大画格；第二行与第三行左右各两格，四格大小都不相等；"
       "第四行分成三格，宽窄不等；底部一个横贯全宽的窄画格。",
    12: "页面上部一个横贯全宽、左右出血的宽画格；中间三行，每行三格，宽窄与高度都不相等，"
        "其中第三行左侧一格竖长、跨两行；底部一个横贯全宽的窄画格。",
    16: "页面上部一个横贯全宽、左右出血的宽画格；其余分四行，每行四格，但四格宽窄与高度都不相等，"
        "相邻行之间横向错位；底部一行四格比上面几行矮。",
    20: "页面上部一个横贯全宽、左右出血的宽画格；其余分五行，每行四格，宽窄与高度都不相等，"
        "相邻行之间横向错位。",
    24: "页面上部一个横贯全宽、左右出血的宽画格；其余分六行，每行四格，宽窄与高度都不相等，"
        "相邻行之间横向错位，最下面一行最矮。",
}


def prompt_for(cols, rows, n):
    """按 cols×rows 的格数，用漫画页面语法排布，取前 n 个瞬间。"""
    total = cols * rows
    # 素材不够长会取模重复，伪装成「模型重复台词」——先在这里挡住
    assert total <= len(BEATS), (
        "格数 %d 超过素材数 %d，会取模重复；先补 BEATS" % (total, len(BEATS)))
    lay = LAYOUTS.get(total, "页面上部一个横贯全宽、左右出血的宽画格；其余分成若干行，"
                             "每行三到四格，宽窄与高度都不相等。")
    parts = [
        "竖版 2:3 画幅，一整页日式漫画，四边与画面边缘平行，居中排列，四周留少量白色页边。",
        "",
        "页面为纯白底。" + lay,
        "",
        GRAMMAR,
        "",
    ]
    for i in range(total):
        scene, who, line, kind = BEATS[i]
        if kind == "说":
            tail = ("画格内有一枚白色圆形气泡，气泡尾部明确指向%s，"
                    "内部以黑色中文写出：" % who)
        elif kind == "白":
            tail = "画格上方有一枚白色矩形旁白框，内部以黑色小字中文写出："
        else:
            tail = "这一格没有任何文字，也没有气泡或旁白框。"
        shot = ("大远景", "中景", "近景", "特写")[i % 4]
        if kind == "静":
            parts.append("第%d格，%s：%s。%s" % (i + 1, shot, scene, tail))
        else:
            parts.append("第%d格，%s：%s。%s" % (i + 1, shot, scene, tail))
            parts.append("")
            parts.append(line)
        parts.append("")
    parts += [
        STYLE,
        "",
        "本页出场角色（只画这几个，不要出现其他人物）：",
        CAST,
        "",
        "整页所有画格的人物造型、服装细节与画风保持一致，色调以黄昏的橙、站台灯的暖黄与夜色的深蓝为主。"
        "画格数量必须是 %d 格，不多不少。" % total,
    ]
    return "\n".join(parts)


def save(fam, key, image, quality=88):
    q = "?filename=%s&subfolder=%s&type=%s" % (
        urllib.parse.quote(image["filename"]),
        urllib.parse.quote(image.get("subfolder", "")),
        image.get("type", "output"))
    with urllib.request.urlopen(LR.SERVER + "/view" + q, timeout=120) as r:
        raw = r.read()
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    if max(w, h) > 1300:
        k = 1300 / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "%s_%s.jpg" % (key, fam))
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(dst)


def main(argv):
    if "--plan" in argv:
        for key, c, r, w, h in CONFIGS:
            p = prompt_for(c, r, c * r)
            print("%-12s %d 格 %d×%d %4dx%-4d %4d 字" % (key, c * r, c, r, w, h, len(p)))
        return 0

    models = ["moss"]
    only = None
    seed = 20261111
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        if a.startswith("--models="):
            models = a.split("=", 1)[1].split(",")
        elif a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")

    ok = fail = 0
    for fam in models:
        bad = probe(fam)
        if bad:
            for b in bad:
                print("[probe-FAIL] %s: %s" % (fam, b))
            continue
        print("\n########## %s" % fam, flush=True)
        for key, c, r, w, h in CONFIGS:
            if only and key not in only:
                continue
            n = c * r
            rec = dict(name="pn_%s_%s_s%d" % (key, fam, seed), prompt=prompt_for(c, r, n),
                       negative=NEG, width=w, height=h, seed=seed)
            imgs = submit(fam, rec)
            if imgs:
                size = save(fam, key, imgs[0])
                print("[saved]  samples_panels/%s_%s.jpg  %.1fKB" % (key, fam, size / 1024),
                      flush=True)
                ok += 1
            else:
                fail += 1

    print("\n[summary] ok=%d fail=%d" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
