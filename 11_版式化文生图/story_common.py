# -*- coding: utf-8 -*-
"""短篇漫画共用件：画风库 + 提示词拼装

第 4 部起统一从这里取画风块，避免每部重抄一遍。
`story/story_data.py`、`story2/`、`story3/` 是前三部手写的，保持原样不动。
"""

STYLES = [
    dict(key="paint", label="厚涂电影感", note="剧场版动画美术：笔触可见 + 强明暗 + 景深",
         block="统一画风：日式剧场版动画的厚涂美术风格，笔触可见，强明暗对比，电影级构图与景深虚化，写实光影但保留动画造型，绝非真人照片。",
         neg=""),
    dict(key="cel", label="彩色赛璐璐", note="清晰描线 + 平涂 + 柔和光影",
         block="统一画风：日式彩色漫画，清晰黑色描线，赛璐璐平涂上色，柔和光影，杂志彩页质感，绝非真人照片。",
         neg=""),
    dict(key="mono", label="黑白网点", note="全图仅黑白灰：纯黑实心 + 细密网点",
         block=("统一画风：日式黑白网点漫画，印刷在纸上的单色漫画。全图只使用黑、白与不同密度的灰色网点，"
                "没有任何彩色。人物与场景的明暗一律用网点密度表现：亮部留白，中间调稀疏网点，"
                "暗部用密集网点与纯黑实心。整体如同复印在纸上的漫画原稿，绝非真人照片。"),
         neg="color, colorful, chromatic, saturated colors, blue, orange, red, green, watercolor, painting"),
    dict(key="water", label="水彩柔光", note="淡彩晕开 + 纸纹可见 + 大量留白",
         block="统一画风：日式水彩漫画，淡彩渲染，颜色边缘柔和晕开，水彩纸纹理可见，大量留白，光线通透，绝非真人照片。",
         neg=""),
]
STYLE_BY_KEY = {s["key"]: s for s in STYLES}

# 全系列统一口径
CHOSEN = "paint"


def make_page(cast_map, body, tone, style_block, cast):
    """拼一页完整提示词：画格布局 + 画风块 + 本页角色子集 + 逐格 + 收束。"""
    people = "\n".join(cast_map[k] for k in cast)
    return (
        "竖版 2:3 画幅，一整页日式漫画，四边与画面边缘平行，居中排列，"
        "四周留少量白色页边。\n\n"
        + body.strip() + "\n\n"
        + style_block + "\n\n"
        + "本页出场角色（只画这几个，不要出现其他人物）：\n" + people + "\n\n"
        + "整页各格的人物造型、服装细节与画风保持一致，" + tone + "。"
    )
