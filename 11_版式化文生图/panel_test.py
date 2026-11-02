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

CAST = "少年，十七岁日本男高中生，黑色短发，深蓝色立领学生制服，肩上斜挎一个深色书包。"

# 16 个瞬间：(画面, 台词)。顺序即叙事顺序，按格数取前 N 条
BEATS = [
    ("黄昏的校门口，学生们从大门走出来", "放学铃响了"),
    ("空无一人的小车站，长椅上落着几片叶子", "车站没有人"),
    ("街角的面包店，橱窗里的灯还亮着", "面包店还开着"),
    ("一座石桥，桥下的水很浅，能看见河底的石头", "桥下的水很浅"),
    ("河堤，草被风吹得倒向一边", "河堤上起风了"),
    ("一只三花猫从矮墙上跳下来，落在少年身后", "一只猫跟着我"),
    ("雨点开始落下，打在柏油路上", "开始下雨"),
    ("少年撑开一把伞，伞下只有他一个人", "我只带了一把伞"),
    ("一栋旧公寓的门口，信箱锈住了", "到家门口"),
    ("二楼的一扇窗透出暖黄的灯光", "屋里的灯亮着"),
    ("餐桌上放着一碗还冒着热气的面", "桌上有一碗面"),
    ("一只空碗，筷子横放在碗沿上", "我吃完了"),
    ("水槽里泡着一只碗，水还在流", "碗洗好了"),
    ("房间，台灯的开关被按下", "灯关了"),
    ("黑暗的房间，窗帘透进一点街灯", "我躺下了"),
    ("清晨的窗，天刚亮，光落在被子上", "天亮了"),
    ("洗漱台，水龙头被关上，镜子上有水汽", "我洗了脸"),
    ("衣柜门开着，制服挂在门内侧", "换上制服"),
    ("玄关，少年蹲着系鞋带", "系好鞋带"),
    ("公寓楼梯间，水泥台阶，往下走", "下楼"),
    ("早晨的街道，店铺还没开门，人很少", "街上没人"),
    ("十字路口，信号灯是红的", "红灯"),
    ("学校的铁门半开着，门柱上有校牌", "到学校了"),
    ("教室，桌椅整齐，黑板擦干净了", "又是这里"),
]

# (key, 列, 行, 宽, 高)
CONFIGS = [
    ("4_2x2", 2, 2, 800, 1200),
    ("6_2x3", 2, 3, 800, 1200),
    ("8_2x4", 2, 4, 800, 1200),
    ("9_3x3", 3, 3, 800, 1200),
    ("12_3x4", 3, 4, 800, 1200),
    ("16_4x4", 4, 4, 800, 1200),
    ("20_4x5", 4, 5, 800, 1200),
    ("24_4x6", 4, 6, 800, 1200),
    ("12_3x4_hi", 3, 4, 1024, 1536),
    ("16_4x4_hi", 4, 4, 1024, 1536),
    ("24_4x6_hi", 4, 6, 1024, 1536),
]

STYLE = "统一画风：日式剧场版动画的厚涂美术风格，笔触可见，强明暗对比，电影级构图与景深虚化，写实光影但保留动画造型，绝非真人照片。"

# 漫画页面语法：不是等大网格。每档格数给一套「大小节奏 + 出血 + 错位」的排布描述。
GRAMMAR = (
    "整页采用日式漫画的页面语法，**不要等大的网格**："
    "画格大小明显不等，形成大小节奏；"
    "至少有一个画格出血——突破页面的左边或右边或上边，直接顶到纸张边缘；"
    "画格之间的间隙宽窄不一，格线不全是横平竖直，相邻两行之间允许横向错位；"
    "台词用圆形气泡，旁白用矩形框，两种形状必须区分。"
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
        scene, line = BEATS[i % len(BEATS)]
        # 气泡与旁白交替：偶数格用旁白框，奇数格用台词气泡
        if i % 2 == 0:
            tail = "画格下方有一枚白色矩形旁白框，内部以黑色小字中文写出："
        else:
            tail = "画格内有一枚白色圆形气泡，内部以黑色中文写出："
        parts.append("第%d格，%s：%s。%s" % (i + 1, "中景" if i % 3 else "近景", scene, tail))
        parts.append("")
        parts.append(line)
        parts.append("")
    parts += [
        STYLE,
        "",
        "本页出场角色（只画这几个，不要出现其他人物）：",
        CAST,
        "",
        "整页所有画格的人物造型、服装细节与画风保持一致，色调以黄昏的橘、夜雨的蓝灰与屋内暖黄为主。"
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
