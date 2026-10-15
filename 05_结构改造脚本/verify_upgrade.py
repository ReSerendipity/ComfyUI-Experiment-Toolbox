# -*- coding: utf-8 -*-
"""工作流升级改造验证器（结构轨 05）。

三种运行模式：
  无参数            → 对本机 ComfyUI 原件目录跑全面验证（原行为，需本机环境，不在 CI 里跑）
  --sample [路径]   → 只作用于仓内脱敏最小样本，输出确定性 通过/失败（CI 可复现验收路径）
  --break <名称>    → 配合 --sample：在内存中破坏一处结构不变量，演示失败信号（不落盘、不碰样本文件）
  --selftest        → 合成演练：样本本身必须通过；逐一破坏每类不变量，各必须失败且指明不变量

设计纪律：本轨脚本是「当操作说明书读」的一次性手术脚本，**不在真实原件上盲跑**；
仓内可复现的验收只作用于 sample_workflow_minimal.json（脱敏最小样本，无本机路径/模型名）。

不变量清单（errors 逐条带 [INV:名称] 前缀，失败信息可直接定位）：
  toplink-unique   toplink-refs   toplink-types
  sublink-unique   sublink-refs   top-sub-idconflict   iface-slot
  main-align       main-widgets   save-single          save-wiring
  forbidden-node   layout-rs      layout-main          counters
  sg-counter-sync  wiring-rs

用法示例：
  python verify_upgrade.py --selftest
  python verify_upgrade.py --sample            # CI 等价命令
  python verify_upgrade.py --sample --break iface-slot
退出码：0 全部通过 / 1 存在失败项 / 2 用法或 IO 错。
"""

import argparse
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SAMPLE = os.path.join(HERE, 'sample_workflow_minimal.json')

# ---- 本机原件模式（原行为）：硬编码常量集中在文件顶部 ----
D = os.path.expandvars(r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image')
FILES = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']


def _find(data, lid):
    return next((x for x in data['links'] if x[0] == lid), None)


def _find_sg(sg, lid):
    return next((x for x in sg['links'] if x['id'] == lid), None)


def check_workflow(data):
    """对一份工作流 dict 跑全部结构不变量，返回 ['[INV:xx] 说明', ...]（空 = 通过）。"""
    errors = []
    node_ids = {n['id'] for n in data['nodes']}

    # ---- 顶层链接 ----
    top_link_ids = set()
    for l in data['links']:
        lid, sn, so, tn, ti, t = l
        if lid in top_link_ids:
            errors.append('[INV:toplink-unique] 顶层链接 %s 重复' % lid)
        top_link_ids.add(lid)
        if sn not in node_ids:
            errors.append('[INV:toplink-refs] 顶层链接 %s 源节点 %s 不存在' % (lid, sn))
        if tn not in node_ids:
            errors.append('[INV:toplink-refs] 顶层链接 %s 目标节点 %s 不存在' % (lid, tn))
        for n in data['nodes']:
            if n['id'] == sn and so < len(n['outputs']) and n['outputs'][so].get('type') != t:
                errors.append('[INV:toplink-types] 顶层链接 %s 源输出类型不匹配 (%s vs %s)' % (lid, n['outputs'][so].get('type'), t))
            if n['id'] == tn and ti < len(n['inputs']) and n['inputs'][ti].get('type') != t:
                errors.append('[INV:toplink-types] 顶层链接 %s 目标输入类型不匹配 (%s vs %s)' % (lid, n['inputs'][ti].get('type'), t))

    # ---- 子图 ----
    sg = data['definitions']['subgraphs'][0]
    sg_node_ids = {n['id'] for n in sg['nodes']} | {-10, -20}
    sub_link_ids = set()
    for l in sg['links']:
        lid = l['id']
        if lid in sub_link_ids:
            errors.append('[INV:sublink-unique] 子图链接 %s 重复' % lid)
        sub_link_ids.add(lid)
        if l['origin_id'] not in sg_node_ids:
            errors.append('[INV:sublink-refs] 子图链接 %s 源节点 %s 不存在' % (lid, l['origin_id']))
        if l['target_id'] not in sg_node_ids:
            errors.append('[INV:sublink-refs] 子图链接 %s 目标节点 %s 不存在' % (lid, l['target_id']))
    # 顶层与子图链接 id 不得冲突
    dup = top_link_ids & sub_link_ids
    if dup:
        errors.append('[INV:top-sub-idconflict] 顶层与子图链接 id 冲突: %s' % sorted(dup))

    # 接口 linkIds 与 -10 链接一致性（新加的接口必须 slot 一致）
    iface_names = [i['name'] for i in sg['inputs']]
    for i, inp in enumerate(sg['inputs']):
        for lid in inp.get('linkIds', []):
            l = _find_sg(sg, lid)
            if l is None:
                errors.append('[INV:iface-slot] 接口 %s linkIds 引用链接 %s 不存在' % (inp['name'], lid))
            elif l.get('origin_id') == -10 and l.get('origin_slot') != i:
                errors.append('[INV:iface-slot] 接口 %s(索引%d) 链接 %s origin_slot=%s 不一致'
                              % (inp['name'], i, lid, l.get('origin_slot')))

    # 主节点
    main = next(n for n in data['nodes'] if n.get('type') == sg['id'])
    main_names = [i.get('name') for i in main['inputs']]
    if main_names != iface_names:
        errors.append('[INV:main-align] 主节点 inputs %s != 子图接口 %s' % (main_names, iface_names))
    widget_inputs = sum(1 for i in main['inputs'] if i.get('widget'))
    if len(main['widgets_values']) != widget_inputs:
        errors.append('[INV:main-widgets] 主节点 widgets_values 长度 %d != 带 widget 输入数 %d' % (len(main['widgets_values']), widget_inputs))

    # SaveImageAdvanced / 删除检查
    saves = [n for n in data['nodes'] if n.get('type') == 'SaveImageAdvanced']
    if len(saves) != 1:
        errors.append('[INV:save-single] SaveImageAdvanced 数量=%d' % len(saves))
    else:
        s = saves[0]
        l = _find(data, s['inputs'][0].get('link'))
        if l is None:
            errors.append('[INV:save-wiring] SaveImageAdvanced images 未连接')
        elif l[1] != main['id'] or l[2] != 0:
            errors.append('[INV:save-wiring] SaveImageAdvanced images 链接源错误: %s' % l)
    if any(n.get('type') == 'EsesImageCompare' for n in data['nodes']):
        errors.append('[INV:forbidden-node] EsesImageCompare 未删除')
    if any(n.get('type') == 'SaveImage' for n in data['nodes']):
        errors.append('[INV:forbidden-node] SaveImage 未删除')

    # RS 位置与主节点尺寸
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    if abs(rs['pos'][0] - (main['pos'][0] - 372)) > 0.01 or abs(rs['pos'][1] - (main['pos'][1] + 298)) > 0.01:
        errors.append('[INV:layout-rs] RS 位置未对齐: %s' % rs['pos'])
    if main['size'] != [247.589453125, 473.9999843161845]:
        errors.append('[INV:layout-main] 主节点尺寸未对齐: %s' % main['size'])

    # last_node_id / last_link_id
    if data['last_node_id'] < max(node_ids):
        errors.append('[INV:counters] last_node_id %s < max %s' % (data['last_node_id'], max(node_ids)))
    all_ids = top_link_ids | sub_link_ids
    if data['last_link_id'] < max(all_ids):
        errors.append('[INV:counters] last_link_id %s < max %s' % (data['last_link_id'], max(all_ids)))
    if sg['state']['lastLinkId'] != data['last_link_id']:
        errors.append('[INV:sg-counter-sync] 子图 state.lastLinkId %s != 顶层 last_link_id %s' % (sg['state']['lastLinkId'], data['last_link_id']))

    # RS 链接仍指向主节点 width/height 且 id 唯一
    wl = rs['outputs'][0]['links']
    hl = rs['outputs'][1]['links']
    if not wl or not hl:
        errors.append('[INV:wiring-rs] RS 输出无链接')
    else:
        for lid in wl + hl:
            l = _find(data, lid)
            if l is None:
                errors.append('[INV:wiring-rs] RS 链接 %s 不存在于顶层' % lid)
            elif l[1] != rs['id'] or l[3] != main['id']:
                errors.append('[INV:wiring-rs] RS 链接 %s 端点异常: %s' % (lid, l))

    return errors, iface_names


def _print_report(fn, errors, iface_names):
    print('=' * 90)
    print(fn)
    if errors:
        print('  [FAIL]')
        for e in errors:
            print('    -', e)
    else:
        print('  接口: %s' % iface_names)
        print('  [OK] 全部检查通过')


# ---- 原件模式 ----
def run_originals():
    all_ok = True
    for fn in FILES:
        path = os.path.join(D, fn)
        print('=' * 90)
        print(fn)
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print('  [FAIL] 读取/解析失败:', e)
            all_ok = False
            continue
        errors, iface_names = check_workflow(data)
        if errors:
            print('  [FAIL]')
            for e in errors:
                print('    -', e)
            all_ok = False
        else:
            print('  接口: %s' % iface_names)
            print('  [OK] 全部检查通过')
    print('=' * 90)
    print('总体: %s' % ('全部通过' if all_ok else '存在失败项'))
    return 0 if all_ok else 1


def load_sample(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# ---- 破坏器：每个只针对一处不变量，全部在内存副本上操作 ----
def _mut_toplink_dup(data):
    data['links'].append(list(data['links'][0]))

def _mut_toplink_refs(data):
    data['links'][0][3] = 999

def _mut_toplink_types(data):
    data['links'][2][5] = 'MASK'

def _mut_sublink_refs(data):
    data['definitions']['subgraphs'][0]['links'][0]['target_id'] = 999

def _mut_top_sub_idconflict(data):
    data['definitions']['subgraphs'][0]['links'][0]['id'] = 3

def _mut_iface_slot(data):
    sg = data['definitions']['subgraphs'][0]
    lid = sg['inputs'][2]['linkIds'][0]
    for l in sg['links']:
        if l['id'] == lid:
            l['origin_slot'] = 0

def _mut_main_widgets(data):
    main = data['nodes'][0]
    main['widgets_values'].append('extra')

def _mut_save_single(data):
    data['nodes'] = [n for n in data['nodes'] if n.get('type') != 'SaveImageAdvanced']

def _mut_layout_rs(data):
    for n in data['nodes']:
        if n.get('type') == 'ResolutionSelector':
            n['pos'] = [n['pos'][0] + 10, n['pos'][1]]

def _mut_counters(data):
    data['last_link_id'] = 0

def _mut_wiring_rs(data):
    for n in data['nodes']:
        if n.get('type') == 'ResolutionSelector':
            n['outputs'][0]['links'] = []

MUTATIONS = {
    'toplink-dup': ('toplink-unique', _mut_toplink_dup),
    'toplink-refs': ('toplink-refs', _mut_toplink_refs),
    'toplink-types': ('toplink-types', _mut_toplink_types),
    'sublink-refs': ('sublink-refs', _mut_sublink_refs),
    'top-sub-idconflict': ('top-sub-idconflict', _mut_top_sub_idconflict),
    'iface-slot': ('iface-slot', _mut_iface_slot),
    'main-widgets': ('main-widgets', _mut_main_widgets),
    'save-single': ('save-single', _mut_save_single),
    'layout-rs': ('layout-rs', _mut_layout_rs),
    'counters': ('counters', _mut_counters),
    'wiring-rs': ('wiring-rs', _mut_wiring_rs),
}


def _selftest(sample_path):
    """返回 (steps, 失败数)。steps: [(消息, ok)]。样本只读；破坏全部在内存副本上。"""
    steps = []
    try:
        base = load_sample(sample_path)
    except Exception as e:
        return [('%s 读取失败: %s' % (sample_path, e), False)], 1

    errors, _ = check_workflow(copy.deepcopy(base))
    steps.append(('样本 %s 全部不变量通过' % os.path.basename(sample_path), not errors))
    for e in errors:
        steps.append(('  违背: ' + e, False))
    bad = 0 if not errors else 1

    for name, (inv, mutate) in sorted(MUTATIONS.items()):
        data = copy.deepcopy(base)
        mutate(data)
        errs, _ = check_workflow(data)
        hit = any('[INV:%s]' % inv in e for e in errs)
        ok = bool(errs) and hit
        steps.append(('破坏 %-19s -> FAIL 且指明 [INV:%s]（实际 %d 条违背）'
                      % (name, inv, len(errs)), ok))
        if not ok:
            bad += 1
            for e in errs:
                steps.append(('  实际违背: ' + e, None))
    return steps, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description='工作流升级结构验证（原件模式 / 仓内样本模式 / selftest）')
    ap.add_argument('--sample', nargs='?', const=DEFAULT_SAMPLE, default=None, metavar='PATH',
                    help='只验证仓内脱敏样本（默认 %s）' % os.path.basename(DEFAULT_SAMPLE))
    ap.add_argument('--break', dest='break_inv', choices=sorted(MUTATIONS), default=None,
                    help='配合 --sample：内存中破坏一处不变量，演示失败信号')
    ap.add_argument('--selftest', action='store_true', help='样本通过 + 逐不变量破坏演练（不写任何文件）')
    a = ap.parse_args(argv)

    if a.selftest:
        sp = a.sample or DEFAULT_SAMPLE
        print('=' * 78)
        print('  verify_upgrade selftest（仓内脱敏样本，只读，破坏仅内存副本）')
        print('=' * 78)
        steps, bad = _selftest(sp)
        for msg, ok in steps:
            tag = 'OK  ' if ok else ('FAIL' if ok is False else '--  ')
            print('  %s %s' % (tag, msg))
        print('\n结论：%s（%d 项失败）' % ('PASS' if bad == 0 else 'FAIL', bad))
        return 1 if bad else 0

    if a.sample is not None:
        try:
            data = load_sample(a.sample)
        except Exception as e:
            print('[FAIL] 读取/解析样本失败: %s' % e)
            return 2
        if a.break_inv:
            MUTATIONS[a.break_inv][1](data)
            print('（已在内存中破坏不变量: %s —— 样本文件未被改动）' % a.break_inv)
        errors, iface_names = check_workflow(data)
        _print_report(os.path.basename(a.sample), errors, iface_names)
        print('总体: %s' % ('全部通过' if not errors else '存在失败项'))
        return 0 if not errors else 1

    if a.break_inv:
        print('[用法错误] --break 需要配合 --sample 使用')
        return 2

    # 无参数：原件模式需本机 ComfyUI 目录，缺目录时明确报错而不是逐项 FAIL 混淆信号
    if not os.path.isdir(D):
        print('[环境缺失] 本机工作流目录不存在: %s' % D)
        print('CI / 无本机环境请改用: python verify_upgrade.py --sample 或 --selftest')
        return 2
    return run_originals()


if __name__ == '__main__':
    sys.exit(main())
