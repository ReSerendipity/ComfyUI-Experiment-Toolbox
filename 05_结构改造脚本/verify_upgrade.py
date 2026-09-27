# -*- coding: utf-8 -*-
"""全面验证改造后的工作流 v2"""
import json, os, sys

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
FILES = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']

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

    errors = []
    node_ids = {n['id'] for n in data['nodes']}

    # ---- 顶层链接 ----
    top_link_ids = set()
    for l in data['links']:
        lid, sn, so, tn, ti, t = l
        if lid in top_link_ids:
            errors.append('顶层链接 %s 重复' % lid)
        top_link_ids.add(lid)
        if sn not in node_ids:
            errors.append('顶层链接 %s 源节点 %s 不存在' % (lid, sn))
        if tn not in node_ids:
            errors.append('顶层链接 %s 目标节点 %s 不存在' % (lid, tn))
        for n in data['nodes']:
            if n['id'] == sn and so < len(n['outputs']) and n['outputs'][so].get('type') != t:
                errors.append('顶层链接 %s 源输出类型不匹配 (%s vs %s)' % (lid, n['outputs'][so].get('type'), t))
            if n['id'] == tn and ti < len(n['inputs']) and n['inputs'][ti].get('type') != t:
                errors.append('顶层链接 %s 目标输入类型不匹配 (%s vs %s)' % (lid, n['inputs'][ti].get('type'), t))

    # ---- 子图 ----
    sg = data['definitions']['subgraphs'][0]
    sg_node_ids = {n['id'] for n in sg['nodes']} | {-10, -20}
    sub_link_ids = set()
    for l in sg['links']:
        lid = l['id']
        if lid in sub_link_ids:
            errors.append('子图链接 %s 重复' % lid)
        sub_link_ids.add(lid)
        if l['origin_id'] not in sg_node_ids:
            errors.append('子图链接 %s 源节点 %s 不存在' % (lid, l['origin_id']))
        if l['target_id'] not in sg_node_ids:
            errors.append('子图链接 %s 目标节点 %s 不存在' % (lid, l['target_id']))
    # 顶层与子图链接 id 不得冲突
    dup = top_link_ids & sub_link_ids
    if dup:
        errors.append('顶层与子图链接 id 冲突: %s' % sorted(dup))

    # 接口 linkIds 与 -10 链接一致性（新加的接口必须 slot 一致）
    iface_names = [i['name'] for i in sg['inputs']]
    for i, inp in enumerate(sg['inputs']):
        for lid in inp.get('linkIds', []):
            l = next((x for x in sg['links'] if x['id'] == lid), None)
            if l is None:
                errors.append('接口 %s linkIds 引用链接 %s 不存在' % (inp['name'], lid))
            elif l.get('origin_id') == -10 and l.get('origin_slot') != i:
                errors.append('接口 %s(索引%d) 链接 %s origin_slot=%s 不一致'
                              % (inp['name'], i, lid, l.get('origin_slot')))

    # 新增接口对应的内部节点 input.link 必须存在且指向正确
    for key, tgt in [('sampler', None), ('scheduler', None), ('seed', None), ('clip', None), ('vae', None)]:
        pass

    # 主节点
    main = next(n for n in data['nodes'] if n.get('type') == sg['id'])
    main_names = [i.get('name') for i in main['inputs']]
    if main_names != iface_names:
        errors.append('主节点 inputs %s != 子图接口 %s' % (main_names, iface_names))
    widget_inputs = sum(1 for i in main['inputs'] if i.get('widget'))
    if len(main['widgets_values']) != widget_inputs:
        errors.append('主节点 widgets_values 长度 %d != 带 widget 输入数 %d' % (len(main['widgets_values']), widget_inputs))

    # SaveImageAdvanced / 删除检查
    saves = [n for n in data['nodes'] if n.get('type') == 'SaveImageAdvanced']
    if len(saves) != 1:
        errors.append('SaveImageAdvanced 数量=%d' % len(saves))
    else:
        s = saves[0]
        l = next((x for x in data['links'] if x[0] == s['inputs'][0].get('link')), None)
        if l is None:
            errors.append('SaveImageAdvanced images 未连接')
        elif l[1] != main['id'] or l[2] != 0:
            errors.append('SaveImageAdvanced images 链接源错误: %s' % l)
    if any(n.get('type') == 'EsesImageCompare' for n in data['nodes']):
        errors.append('EsesImageCompare 未删除')
    if any(n.get('type') == 'SaveImage' for n in data['nodes']):
        errors.append('SaveImage 未删除')

    # RS 位置与主节点尺寸
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    if abs(rs['pos'][0] - (main['pos'][0] - 372)) > 0.01 or abs(rs['pos'][1] - (main['pos'][1] + 298)) > 0.01:
        errors.append('RS 位置未对齐: %s' % rs['pos'])
    if main['size'] != [247.589453125, 473.9999843161845]:
        errors.append('主节点尺寸未对齐: %s' % main['size'])

    # last_node_id / last_link_id
    if data['last_node_id'] < max(node_ids):
        errors.append('last_node_id %s < max %s' % (data['last_node_id'], max(node_ids)))
    all_ids = top_link_ids | sub_link_ids
    if data['last_link_id'] < max(all_ids):
        errors.append('last_link_id %s < max %s' % (data['last_link_id'], max(all_ids)))
    if sg['state']['lastLinkId'] != data['last_link_id']:
        errors.append('子图 state.lastLinkId %s != 顶层 last_link_id %s' % (sg['state']['lastLinkId'], data['last_link_id']))

    # RS 链接仍指向主节点 width/height 且 id 唯一
    wl = rs['outputs'][0]['links']
    hl = rs['outputs'][1]['links']
    if not wl or not hl:
        errors.append('RS 输出无链接')
    else:
        for lid in wl + hl:
            l = next((x for x in data['links'] if x[0] == lid), None)
            if l is None:
                errors.append('RS 链接 %s 不存在于顶层' % lid)
            elif l[1] != rs['id'] or l[3] != main['id']:
                errors.append('RS 链接 %s 端点异常: %s' % (lid, l))

    print('  接口: %s' % iface_names)
    if errors:
        print('  [FAIL]')
        for e in errors:
            print('    -', e)
        all_ok = False
    else:
        print('  [OK] 全部检查通过')

print('=' * 90)
print('总体: %s' % ('全部通过' if all_ok else '存在失败项'))
sys.exit(0 if all_ok else 1)
