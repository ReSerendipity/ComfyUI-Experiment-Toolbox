# -*- coding: utf-8 -*-
"""
模型家族横评 P3 隔离轨 · lib_sfw_prompts_kit —— SFW/中性提示词素材包（正向供词）。

定位（与同目录另两个库的分工）
    lib_prompt_qc      —— 拦截：违规/废句扫描器，输出 finding（**减法**）
    lib_prompt_robust  —— 精简：砍修饰从句做对照实验（**做减法的对照基线**）
    lib_sfw_prompts_kit—— 供词：中性正向素材片段（**加法**），供 expand/改写/加料时取用
    三者关系：qc 管「不能写什么」，robust 管「写多少」，kit 管「还能写什么」。
    本库**不含任何规则拦截逻辑**，也**不含任何分级词条**，只提供结构化正向素材。

隔离声明（重要）
    Picture 的 词库.json 是成人向分级词库（34,289 条词条 / 128 个顶级类目）。
    本模块**只搬运其中项目无关、非限制级的维度**，并把三类东西挡在门外：
      ① 内置素材 100% 自写（`BUILTIN`），不复制词库原文，一个字都没有抄；
      ② 外部词库导入走 `EXTERNAL_ALLOW` 白名单（81 个通用类目 / 20,521 条），
         白名单外的 46 个类目 / 12,593 条按域整类拒绝，见 `SKIP_TABLE`；
      ③ 白名单类目内部再有 6 个子桶 / 438 条按域拒绝，见 `PARTIAL_SKIP`。
    本模块**不内置任何限制级关键词表**——安全保证来自「类目白名单 + 结构闸门」
    而不是「敏感词黑名单」：黑名单要靠穷举维护且必然漏，而白名单是封闭集。
    外部导入的每一条仍会过 `_gate()` 结构闸门（分级后缀 / 数字测量式 / 空条 / 超长 /
    半角逗号裸测量），不通过的条目被丢掉并计入 `rejected`。

API
    list_categories()            -> [str]              内置类目名（按维度顺序）
    category_counts()            -> {类目: 条数}
    get(category, n=1, seed=None, exclude=()) -> [str]  确定性轮换取词（同 seed 同结果）
    compose(dims=None, n_each=1, sep="，", seed=None) -> str   拼一段正向素材
    load_external(path, limit_per_cat=200, deny_terms=None)
        -> {"pool": {类目: [条目]}, "report": {...}}   可选：外部通用词库导入
    audit_external(path)         -> 审计报表（只含类目名与计数，**不含词条正文**）
    EXTERNAL_ALLOW / SKIP_TABLE / PARTIAL_SKIP / ROUTE_TABLE   —— 审计常量（计数）

退出码：0 正常 / 1 用法或 IO 错。

用法（纯标准库，任意 python 可跑）：
    python -X utf8 lib_sfw_prompts_kit.py                 # 打印纳入/跳过类目与计数
    python -X utf8 lib_sfw_prompts_kit.py --sample 3       # 每类抽 3 条看看
    python -X utf8 lib_sfw_prompts_kit.py --compose light_direction,composition,color_scheme
    python -X utf8 lib_sfw_prompts_kit.py --audit "D:/some/通用词库.json"   # 外部库审计
"""
import argparse
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

# =============================================================================
# 一、内置素材（BUILTIN）：全部为本模块自写的中性摄影/场景词汇，项目无关、SFW
#     维度顺序＝组稿顺序：光 → 时/天 → 构图 → 机位 → 镜头 → 色彩 → 材质 → 场景 → 氛围 → 后期
# =============================================================================
BUILTIN = {
    "light_direction": (
        "侧向主光", "逆光轮廓", "顶光压顶", "顺光平铺", "窗口侧光", "环形柔光包裹",
        "分割光勾边", "轮廓光描边", "伦勃朗三角光", "蝴蝶光", "大面积天光漫射",
        "实用光源投射", "双侧夹光", "底部反光板补光",
    ),
    "light_quality": (
        "硬光高反差", "柔光低反差", "柔箱布光", "阴天散射光", "烛光跳动暖光",
        "霓虹混合光", "月光冷调", "舞台聚光", "荧光灯管平光", "金色时段斜射光",
        "蓝调时刻环境光", "正午硬顶光", "雾中漫射柔光", "多灯位交叉补光",
    ),
    "color_temperature": (
        "约2700K 暖黄烛光", "3200K 钨丝灯白", "4000K 中性白", "5200K 日光白",
        "5600K 标准日光", "6500K 阴天冷白", "7000K 蓝调时刻", "8500K 阴影冷调",
        "双色温对比", "白平衡向暖偏 200K",
    ),
    "time_of_day": (
        "清晨薄雾时段", "上午通透时段", "正午顶光时段", "午后柔光时段", "黄昏前黄金时段",
        "日落逆光时段", "蓝调时刻", "夜晚人工光时段", "深夜低照度时段", "凌晨微光时段",
    ),
    "weather": (
        "晴朗", "薄云", "阴天", "细雨", "大雨", "低雾", "薄雾", "小雪", "大风",
        "无风静稳", "闷热潮湿", "雨后初霁", "雷雨将至",
    ),
    "weather_effect": (
        "逆光光晕", "雨丝反光", "地面湿反射", "雪地高反照", "雾气散射柔化",
        "丁达尔光束", "镜头雨滴", "热气蒸腾扭曲", "风吹浮尘", "露珠挂镜",
    ),
    "composition": (
        "三分法构图", "中心对称构图", "引导线构图", "框中框构图", "对角线构图",
        "大面积留白", "黄金分割落点", "重复韵律构图", "前景遮挡层次", "负空间构图",
        "高低错落层次", "几何块面构图", "框景式构图", "斜线分割构图",
    ),
    "shot_size": (
        "极特写", "特写", "近景", "中景", "中全景", "全身景", "远景", "大远景",
        "俯瞰全景", "仰视全景", "俯拍全景", "半身近景",
    ),
    "camera_angle": (
        "平视机位", "俯拍机位", "仰拍机位", "顶视机位", "贴地低角度", "高角度俯视",
        "荷兰角倾斜", "过肩视角", "侧面视角", "背面视角", "斜侧四十五度",
    ),
    "depth_of_field": (
        "极浅景深", "浅景深", "中等景深", "大景深全景清晰", "焦点前实后虚",
        "前景虚化压暗", "焦外奶油化", "背景压缩感", "移轴微缩景深", "全景深合成",
    ),
    "lens_kit": (
        "24mm 广角定焦", "35mm 广角定焦", "50mm 标准定焦", "85mm 中长焦定焦",
        "100mm 微距", "135mm 长焦", "16-35mm 广角变焦", "70-200mm 长焦变焦",
        "200mm 超长焦", "移轴镜头", "鱼眼镜头", "微距镜头 1:1",
    ),
    "camera_settings": (
        "f/1.2 大光圈", "f/2.8", "f/5.6", "f/11 景深优先", "1/1000s 凝固动作",
        "1/60s 轻微动态模糊", "ISO 100 低噪", "ISO 800 弱光", "曝光补偿 -0.3EV",
        "包围曝光合成", "白平衡锁定 5600K",
    ),
    "color_scheme": (
        "冷暖对比配色", "单色调配色", "邻近色配色", "互补色撞色", "低饱和莫兰迪配色",
        "高明度奶油色系", "暗调低-key 影调", "亮调高-key 影调", "中性灰调",
        "同色系深浅渐变", "一点点青橙对比", "无彩色灰阶",
    ),
    "material_surface": (
        "亚光陶瓷", "拉丝金属", "氧化铜绿", "磨砂玻璃", "湿润石面", "粗陶土",
        "抛光大理石", "氧化皮革", "织纹亚麻", "水磨石台面", "生锈铁皮",
        "半透明树脂", "磨砂铝板", "藤编纹理", "实木原色",
    ),
    "texture_detail": (
        "细密颗粒质感", "做旧划痕", "织物经纬", "水波涟漪", "木纹年轮",
        "石材凿痕", "金属拉丝纹", "玻璃折射纹", "落叶脉络", "羽毛绒感",
        "指纹油污", "龟裂旧漆",
    ),
    "scene_generic": (
        "安静的室内工作室", "黄昏天台", "雨后街角", "晨雾湖面", "老式电梯厢",
        "堆满杂物的仓库", "空旷阅览室", "夜班便利店", "无人的码头", "林间小径",
        "玻璃幕墙中庭", "老城区屋顶菜园", "空置的影院放映厅", "露营帐篷营地",
        "深夜仍在营业的面馆", "摆满陶罐的手作市集",
    ),
    "background_props": (
        "斑驳旧墙面", "折叠椅", "粗陶花瓶", "木质长桌", "垂落窗帘", "悬挂灯泡",
        "旧木箱", "绿植盆栽", "镜面立柱", "不锈钢台面", "整面书架", "磨砂玻璃隔断",
        "折叠椅阵列", "手推车",
    ),
    "ambience_mood": (
        "安静", "慵懒", "清冷", "明快", "庄重", "神秘", "温暖", "疏离", "活泼", "肃穆",
        "怀旧", "空旷寂寥",
    ),
    "post_fx": (
        "轻微暗角", "胶片颗粒", "柔和高光溢出", "高光去饱和", "渐晕压角",
        "白平衡偏移", "对比度提升", "高光压缩", "局部提亮", "轻度锐化",
        "色调分离", "柔和扩散",
    ),
}

CATEGORY_ORDER = tuple(BUILTIN.keys())

# =============================================================================
# 二、外部通用词库的白名单 / 拒绝表（审计于 Picture/词库.json，2026-10-05）
#     只记**类目名与条数**，不记任何词条正文。计数口径见文件末尾 AUDIT_NOTE。
#     通用类目 81 个（其中 6 个为「只取通用子桶」的类目）→ 净纳入 20,367 条
#     对账：34,289 = 净纳入 20,367 + 整类拒绝 12,593 + 子桶拒绝 438 + 路由专用 891
# =============================================================================
EXTERNAL_ALLOW = (
    ("光线", 437), ("光线方向", 93), ("光线特效", 130), ("色温效果", 93),
    ("阴影类型", 90), ("色调调整", 102), ("滤镜风格", 93), ("色彩体系", 104),
    ("时间氛围", 80), ("时间光线匹配", 125), ("天气", 80), ("天气效果", 96),
    ("季节细节", 114), ("季节意象", 200), ("天气氛围", 110), ("构图", 145),
    ("视角", 100), ("景深控制", 90), ("背景元素", 100), ("装饰元素", 99),
    ("场景道具细分", 100), ("场景构建", 25), ("材质细节", 150), ("自然材质", 90),
    ("建筑材质", 99), ("建筑", 288), ("地理", 180), ("视觉艺术风格", 1279),
    ("数字与设计风格", 500), ("艺术", 1087), ("设计", 974), ("幻想", 1092),
    ("镜面", 276), ("环境音", 80), ("音乐", 170), ("乐器", 84), ("音乐氛围", 90),
    ("音效", 79), ("动态效果", 125), ("动态/运动", 97), ("抽象概念", 100),
    ("感官通感", 125), ("心理空间", 125), ("文化编码", 125), ("地域文化", 125),
    ("文化符号", 100), ("文化与历史风格", 735), ("时间线", 120), ("时间叙事", 30),
    ("转场方式", 80), ("运动户外", 84), ("运动", 179), ("生态", 1482), ("载具", 1279),
    ("宠物", 1573), ("植物盆栽", 106), ("花卉", 188), ("传统节令", 96),
    ("节日", 227), ("美食", 474), ("甜点样式", 87), ("菜系分类", 84),
    ("饮品类型", 84), ("科技", 178), ("数码科技", 96), ("街头潮流", 111),
    ("古玩文房", 87), ("文具手帐", 94), ("茶器花艺", 94), ("星空宇宙", 85),
    ("水下世界", 99), ("潮玩手办", 88), ("香氛生活", 98), ("图文设计", 75),
    ("创意主题", 150), ("情绪/氛围", 158), ("氛围形容词库", 173),
    ("质感形容词库", 120), ("色彩心理学", 24),
    ("镜头", 181), ("场景", 1502),
)

# 分级/身体/年龄/服饰/人物域，整类拒绝：46 类 / 12,593 条
SKIP_GROUPS = (
    ("身体与体型域", (
        ("身体", 549), ("体型细分", 348), ("身体特征标记", 272), ("身体叙事", 124),
        ("身体姿态细分", 80), ("呼吸模式", 95), ("步态", 120), ("手势库", 99))),
    ("外貌与妆造域", (
        ("头发", 569), ("面容", 602), ("妆造", 568), ("神态表情", 384), ("姿态", 772))),
    ("服饰与配件域", (
        ("服饰", 1310), ("面料纹理", 86), ("珠宝材质", 96), ("鞋履类型", 84),
        ("包包款式", 87), ("眼镜款式", 63), ("头饰类型", 75), ("首饰珠宝", 92),
        ("服装状态", 75), ("季节服装场景匹配", 60))),
    ("年龄与人物设定域", (
        ("年龄人生阶段", 538), ("外貌原型档", 102), ("原型套装", 114),
        ("性格气质", 912), ("气质人设", 158), ("身份职业", 423),
        ("声音特征", 391), ("人声", 100))),
    ("分级内容专属域（原键名不复现，3 类）", (
        ("<分级行为句类>", 727), ("<分级幻想扩展类>", 131), ("<分级深度阶类>", 254))),
    ("多人关系与叙事域", (
        ("双人关系", 109), ("多人关系", 105), ("关系动力学", 125),
        ("情绪姿态匹配", 125), ("道具互动", 40), ("冲突类型", 105),
        ("情绪弧线", 105), ("因果关系", 105), ("叙事元素", 100),
        ("动作节奏", 105), ("环境交互", 125))),
    ("题材锚点域", (("场景锚点", 984),)),
)

# 白名单类目内部按域拒绝的子桶：6 桶 / 438 条。
# 实现口径：**只按子桶白名单放行**（`SUBBUCKET_KEEP`），默认全拒——
# 白名单之外的子桶连内容都不看就丢掉，这样受限子桶的原名不必出现在本文件里。
SUBBUCKET_KEEP = {
    "镜头": ("通用构图", "景别构图", "参数", "景深与画面效果", "器材库", "设备互动类别"),
    "镜面": ("反射面载体", "镜中构图", "强化反射句"),
    "音效": ("音效_动作音效", "音效_环境音效", "音效_特殊音效", "音乐氛围_音乐类型"),
    "氛围形容词库": ("高级质感", "情绪氛围", "空间氛围", "氛围类型_来源后期"),
    "质感形容词库": ("面料质感", "材质质感", "织物质感", "金属质感", "液体质感", "光影质感"),
    # "场景" 无需白名单：整类通用，仅靠 _LEVEL_CAT_RE 剔掉带分级后缀的子桶。
}

# 只报中性描述 + 条数，不复现受限子桶原名
PARTIAL_SKIP = (
    ("镜头", 219, "按场景类型切分的专属子桶，与被隔离的场景路由绑定"),
    ("场景", 65, "带分级后缀的空间子桶"),
    ("镜面", 49, "肢体姿态子桶"),
    ("音效", 20, "身体域音效子桶"),
    ("氛围形容词库", 25, "人物域子桶"),
    ("质感形容词库", 60, "身体域表面质感子桶"),
)

# 不是受限内容，但属于外部库的**项目专属路由分桶**（与其 SFW 类目表一一对应），
# 允许导入、不进内置默认池、也不计入「跳过」。
ROUTE_TABLE = (("场景归档池", 891),)

AUDIT_NOTE = (
    "审计对象：Picture/词库.json（128 个顶级类目 / 34,289 条词条）。"
    "计数口径：dict 递归 + list 标量叶子计数（下划线开头的元数据键不计）。"
    "对账：34,289 = 整类拒绝 12,593 + 路由专用 891 + 白名单毛计数 20,805；"
    "白名单毛计数再减子桶拒绝 438 = 净纳入 20,367。"
    "外部类目名仅为路由标识，本模块不含其词条正文。"
)


def _skip_table():
    out = []
    for _label, cats in SKIP_GROUPS:
        out.extend(cats)
    return tuple(out)


SKIP_TABLE = _skip_table()
SKIP_TOTAL_ENTRIES = sum(n for _c, n in SKIP_TABLE)
SKIP_TOTAL_CATS = len(SKIP_TABLE)
ALLOW_TOTAL_ENTRIES = sum(n for _c, n in EXTERNAL_ALLOW)
ALLOW_TOTAL_CATS = len(EXTERNAL_ALLOW)
ROUTE_TOTAL_ENTRIES = sum(n for _c, n in ROUTE_TABLE)

# 结构闸门（全部项目无关，不含任何限制级词）：
#   ① 分级后缀（如 _L<数字> 这类分级标记位）
#   ② 数字+单位的测量式
#   ③ 空条 / 超长 / 元数据残留
import re as _re

_LEVEL_SUFFIX_RE = _re.compile(r"_L[0-9]{1,2}\b|_[Ll][0-9]+\b")
_LEVEL_CAT_RE = _re.compile(r"_L[0-9]")
_MEASURE_RE = _re.compile(r"[0-9０-９]+\s*(?:cm|CM|mm|kg|K|度|档|秒|f/)")
_META_RE = _re.compile(r"^[\s_＿\-—=·]+|[\s_＿\-—=·]+$")
MAX_ENTRY_CHARS = 40


def _gate(entry, deny_terms=()):
    """结构闸门：只判结构与分级标记位，不做内容审查。返回 (ok, reason)。"""
    if not isinstance(entry, str):
        return False, "not_str"
    e = entry.strip()
    if not e:
        return False, "empty"
    if len(e) > MAX_ENTRY_CHARS:
        return False, "too_long"
    if _META_RE.match(entry):
        return False, "meta_residue"
    if _LEVEL_SUFFIX_RE.search(e):
        return False, "level_suffix"
    if _MEASURE_RE.search(e):
        return False, "measure_form"
    for t in deny_terms:
        if t and t in e:
            return False, "caller_deny"
    return True, ""


def _pick(pool, n, seed=None, exclude=()):
    """确定性轮转：同 seed 同结果（md5 命名空间），无随机、不可复现性问题。"""
    cand = [x for x in pool if x not in exclude]
    if not cand:
        return []
    base = 0
    if seed is not None:
        base = int(hashlib.md5(str(seed).encode("utf-8")).hexdigest()[:8], 16)
    if n >= len(cand):
        out = list(cand)
    else:
        idx = [(base + i * 7 + (base >> (3 * (i % 4)))) % len(cand) for i in range(n)]
        seen, uniq = set(), []
        for i in idx:
            while i in seen:
                i = (i + 1) % len(cand)
            seen.add(i)
            uniq.append(cand[i])
        out = uniq
    return out[:n] if n < len(cand) else out


def list_categories():
    return list(CATEGORY_ORDER)


def category_counts():
    return {k: len(v) for k, v in BUILTIN.items()}


def get(category, n=1, seed=None, exclude=()):
    """取 n 条素材；类目不存在抛 KeyError（拼错类目名要立刻炸，不要静默返回空）。"""
    if category not in BUILTIN:
        raise KeyError("未知类目：%s（可用：%s）" % (category, ", ".join(CATEGORY_ORDER)))
    return _pick(BUILTIN[category], n, seed, exclude)


def compose(dims=None, n_each=1, sep="，", seed=None, exclude=()):
    """按维度顺序拼一段正向素材。dims 缺省＝默认 6 维（光/构图/镜头/色彩/材质/氛围）。"""
    dims = dims or ("light_quality", "composition", "camera_angle",
                    "color_scheme", "material_surface", "ambience_mood")
    parts = []
    for d in dims:
        parts.extend(get(d, n_each, seed=seed, exclude=exclude))
    return sep.join(parts)


# ── 可选：外部通用词库导入（默认不读任何文件，必须显式传路径）────────────────
def _iter_entries(node):
    """遍历一个节点下的全部词条叶子（不做任何过滤）。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("_"):
                continue
            yield from _iter_entries(v)
    elif isinstance(node, list):
        for it in node:
            if isinstance(it, str):
                yield it
            elif isinstance(it, dict):
                for v in it.values():
                    if isinstance(v, str):
                        yield v
                    else:
                        yield from _iter_entries(v)
            else:
                yield str(it)


def _iter_by_subbucket(node, keep_keys):
    """**只在第一层**按子桶白名单放行；白名单内的子桶内部结构不受限制。
    （早期版本把白名单递归下传，导致白名单子桶若是 dict 就被整桶丢掉——
      计数对不上时先查这里。）"""
    if not isinstance(node, dict):
        yield from _iter_entries(node)
        return
    for k, v in node.items():
        if k.startswith("_") or k not in keep_keys:
            continue
        yield from _iter_entries(v)


def _subbucket_keep(parent):
    """该父类目下的放行子桶；None = 不做子桶级限制（只按分级标记位剔）。"""
    return SUBBUCKET_KEEP.get(parent)


def audit_external(path):
    """审计一个外部词库：只报**类目名 + 条数 + 拒绝原因**，绝不输出词条正文。"""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "path": os.path.abspath(path),
                "error": "%s: %s" % (type(e).__name__, e)}
    if not isinstance(data, dict):
        return {"ok": False, "path": os.path.abspath(path), "error": "顶层不是 dict"}

    allow_names = {c for c, _n in EXTERNAL_ALLOW}
    skip_names = {c for c, _n in SKIP_TABLE if not c.startswith("<")}
    route_names = {c for c, _n in ROUTE_TABLE}
    unknown = []
    in_allow = in_skip = in_skip_level = in_route = 0
    in_allow_gross = in_partial_drop = 0
    unknown_entries = 0
    for key, node in data.items():
        if key.startswith("_") or key == "组装顺序":
            continue
        n = sum(1 for _ in _iter_entries(node))
        if key in allow_names:
            keep = _subbucket_keep(key)
            if keep is not None:
                kept = sum(1 for _ in _iter_by_subbucket(node, keep))
            elif isinstance(node, dict):
                # 父类目无子桶白名单时，只在「子桶键」这一层剔分级后缀标记位
                kept = sum(sum(1 for _ in _iter_entries(v))
                           for k, v in node.items()
                           if not k.startswith("_") and not _LEVEL_CAT_RE.search(k))
            else:
                kept = n
            in_allow += kept
            in_allow_gross += n
            in_partial_drop += n - kept
        elif key in skip_names:
            in_skip += n
        elif _LEVEL_CAT_RE.search(key):
            # 键名带分级标记位 → 归入分级内容专属域（原名不复现，只计数）
            in_skip_level += n
        elif key in route_names:
            in_route += n
        else:
            unknown.append((key, n))
            unknown_entries += n
    return {
        "ok": True,
        "path": os.path.abspath(path),
        "categories_total": len([k for k in data if not k.startswith("_") and k != "组装顺序"]),
        "entries_allow_gross": in_allow_gross,
        "entries_partial_drop": in_partial_drop,
        "entries_allow_net": in_allow,
        "entries_route_only": in_route,
        "entries_skip_named": in_skip,
        "entries_skip_level_tag": in_skip_level,
        "entries_skip_total": in_skip + in_skip_level + unknown_entries,
        "entries_unknown": unknown_entries,
        "unknown_categories": sorted(unknown, key=lambda kv: -kv[1]),
        "note": AUDIT_NOTE,
    }


def load_external(path, limit_per_cat=200, deny_terms=(), include_route_only=False):
    """按白名单导入外部通用词库。返回 {"pool": {...}, "report": {...}}。"""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:                                       # noqa: BLE001
        return {"pool": {}, "report": {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}}
    allow_names = {c for c, _n in EXTERNAL_ALLOW}
    route_names = {c for c, _n in ROUTE_TABLE}
    pool, report = {}, {"ok": True, "path": os.path.abspath(path), "kept": {},
                        "gate_rejected": {}, "dropped_categories": []}
    for key, node in data.items():
        if key.startswith("_") or key == "组装顺序":
            continue
        if _LEVEL_CAT_RE.search(key) and key not in allow_names:
            # 键名带分级标记位 → 归入分级内容专属域（原名不复现）
            report["dropped_categories"].append((key, "分级标记位类目"))
            continue
        if key in route_names and not include_route_only:
            report["dropped_categories"].append((key, "项目专属路由分桶"))
            continue
        if key not in allow_names and key not in route_names:
            report["dropped_categories"].append((key, "非白名单类目"))
            continue
        keep = _subbucket_keep(key)
        if keep is not None:
            stream = _iter_by_subbucket(node, keep)
        elif isinstance(node, dict):
            stream = (e for k, v in node.items()
                      if not k.startswith("_") and not _LEVEL_CAT_RE.search(k)
                      for e in _iter_entries(v))
        else:
            stream = _iter_entries(node)
        got, rej = [], {}
        for e in stream:
            ok, why = _gate(e, deny_terms)
            if ok:
                if e not in got:
                    got.append(e)
            else:
                rej[why] = rej.get(why, 0) + 1
            if limit_per_cat and len(got) >= limit_per_cat:
                break
        if got:
            pool[key] = got
        if rej:
            report["gate_rejected"][key] = rej
    report["kept"] = {k: len(v) for k, v in pool.items()}
    report["kept_total"] = sum(len(v) for v in pool.values())
    return {"pool": pool, "report": report}


# =============================================================================
# 三、CLI：打印纳入/跳过台账（只含类目名与计数）
# =============================================================================
def _print_ledger(sample=0):
    counts = category_counts()
    total = sum(counts.values())
    print("=" * 66)
    print("内置素材包（自写，项目无关，%d 个类目 / %d 条）" % (len(counts), total))
    print("=" * 66)
    print("%-3s%-18s%6s" % ("#", "内置类目", "条数"))
    print("-" * 66)
    for i, c in enumerate(CATEGORY_ORDER, 1):
        print("%-3d%-18s%6d%s" % (i, c, counts[c],
                                   ("   " + " / ".join(_pick(BUILTIN[c], sample)))
                                   if sample else ""))
    print("-" * 66)
    print("外部通用词库白名单：%d 类 / %d 条（可导入，默认不读任何文件）"
          % (ALLOW_TOTAL_CATS, ALLOW_TOTAL_ENTRIES))
    print("")
    print("整类跳过（%d 类 / %d 条，只列类目名与条数）："
          % (SKIP_TOTAL_CATS, SKIP_TOTAL_ENTRIES))
    for label, cats in SKIP_GROUPS:
        print("  · %s：%d 类 / %d 条" % (label, len(cats), sum(n for _c, n in cats)))
        print("      " + "  ".join("%s(%d)" % (c, n) for c, n in cats))
    print("")
    print("子桶跳过（%d 桶 / %d 条）：" % (len(PARTIAL_SKIP), sum(n for _p, n, _r in PARTIAL_SKIP)))
    for parent, n, reason in PARTIAL_SKIP:
        print("  · %s(%d)：%s" % (parent, n, reason))
    print("")
    print("项目专属路由分桶（%d 类 / %d 条）：既不纳入也不拒绝，导入需显式开关"
          % (len(ROUTE_TABLE), ROUTE_TOTAL_ENTRIES))
    for c, n in ROUTE_TABLE:
        print("  · %s(%d)" % (c, n))
    print("")
    print(AUDIT_NOTE)
    print("隔离声明：内置素材 100% 自写，未复制外部词库任何词条正文；"
          "本模块不含限制级词条，也不含敏感词黑名单（改用类目白名单 + 结构闸门）。")


def main(argv=None):
    ap = argparse.ArgumentParser(description="SFW/中性提示词素材包（正向供词）")
    ap.add_argument("--sample", type=int, default=0, help="每类抽 N 条示例（0=不抽）")
    ap.add_argument("--compose", default=None, help="逗号分隔的类目名，拼一段正向素材")
    ap.add_argument("--n-each", type=int, default=2)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--audit", default=None, help="审计一个外部词库（只报类目名与计数）")
    ap.add_argument("--audit-names", action="store_true",
                    help="连「白名单外未登记」的类目原名一起打印（默认不打印："
                         "外部库受限类目名可能含限制级词面）")
    a = ap.parse_args(argv)

    if a.audit:
        rep = audit_external(a.audit)
        if not rep.get("ok"):
            print("[ERR]", rep.get("error"))
            return 1
        print("外部词库审计：", rep["path"])
        print("  类目总数                          :", rep["categories_total"])
        print("  白名单类目（毛计数）              :", rep["entries_allow_gross"])
        print("  子桶拒绝                          : -", rep["entries_partial_drop"])
        print("  白名单类目（净纳入）              :", rep["entries_allow_net"])
        print("  路由专用（需显式开关）            :", rep["entries_route_only"])
        print("  整类拒绝（具名域）                :", rep["entries_skip_named"])
        print("  整类拒绝（分级标记位，原名不复现）:", rep["entries_skip_level_tag"])
        print("  整类拒绝（白名单外未登记，原名默认不复现）:", rep["entries_unknown"])
        print("  整类拒绝合计                      :", rep["entries_skip_total"])
        if a.audit_names and rep["unknown_categories"]:
            print("  白名单外类目（名+条数）：")
            for k, n in rep["unknown_categories"]:
                print("      %s(%d)" % (k, n))
        print(" ", rep["note"])
        return 0

    if a.compose:
        dims = [d.strip() for d in a.compose.split(",") if d.strip()]
        try:
            print(compose(dims, n_each=a.n_each, seed=a.seed))
        except KeyError as e:
            print("[ERR]", e)
            return 1
        return 0

    _print_ledger(sample=a.sample)
    return 0


if __name__ == "__main__":
    sys.exit(main())
