# -*- coding: utf-8 -*-
"""验证修改后的工作流文件：JSON 合法性、链接一致性、节点完整性、差异范围。"""
import json
import os

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
FILES = [
    'Flux.2_Klein-9B-Distilled.json',
    'Qwen_image.json',
    'Qwen_image_2512.json',
    'Z_image.json',
    'Z_image_turbo.json',
    'flux.1-dev.json',
]

all_ok = True
for fn in FILES:
    path = os.path.join(D, fn)
    bak = path + '.bak'
    print('=' * 70)
    print(fn)
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        print('  [OK] JSON 合法')
    except Exception as e:
        print('  [FAIL] JSON 解析失败:', e)
        all_ok = False
        continue

    # 1. 链接引用完整性
    node_ids = {n['id'] for n in data['nodes']}
    link_ids = set()
    bad = []
    for l in data['links']:
        lid, sn, so, tn, ti, t = l
        if lid in link_ids:
            bad.append('link %s 重复' % lid)
        link_ids.add(lid)
        if sn not in node_ids:
            bad.append('link %s 源节点 %s 不存在' % (lid, sn))
        if tn not in node_ids:
            bad.append('link %s 目标节点 %s 不存在' % (lid, tn))
        # 校验源输出/目标输入存在且类型匹配
        for n in data['nodes']:
            if n['id'] == sn and so < len(n['outputs']):
                if n['outputs'][so].get('type') != t:
                    bad.append('link %s 源输出类型 %s != %s' % (lid, n['outputs'][so].get('type'), t))
            if n['id'] == tn and ti < len(n['inputs']):
                if n['inputs'][ti].get('type') != t:
                    bad.append('link %s 目标输入类型 %s != %s' % (lid, n['inputs'][ti].get('type'), t))
    if bad:
        print('  [FAIL] 链接问题:')
        for b in bad:
            print('    -', b)
        all_ok = False
    else:
        print('  [OK] %d 条链接引用完整、类型匹配' % len(data['links']))

    # 2. ResolutionSelector 节点及其连接
    rs = [n for n in data['nodes'] if n.get('type') == 'ResolutionSelector']
    if len(rs) != 1:
        print('  [FAIL] ResolutionSelector 节点数量=%d' % len(rs))
        all_ok = False
    else:
        r = rs[0]
        outs = r['outputs']
        print('  [OK] ResolutionSelector id=%s pos=%s' % (r['id'], r['pos']))
        for o in outs:
            if not o.get('links'):
                print('  [FAIL] 输出 %s 无链接' % o['name'])
                all_ok = False
        # 找到主节点（有 width/height 输入且被链接）
        main_ok = False
        for n in data['nodes']:
            w_l = [x for x in n.get('inputs', []) if 'width' in x.get('name', '') and x.get('link')]
            h_l = [x for x in n.get('inputs', []) if 'height' in x.get('name', '') and x.get('link')]
            if w_l and h_l:
                main_ok = True
                print('  [OK] 主节点 id=%s: width<-link%s height<-link%s'
                      % (n['id'], w_l[0]['link'], h_l[0]['link']))
        if not main_ok:
            print('  [FAIL] 未找到被链接 width/height 的主节点')
            all_ok = False

    # 3. last_node_id / last_link_id 覆盖所有节点与链接
    if data['last_node_id'] < max(node_ids):
        print('  [FAIL] last_node_id=%s < max node id=%s' % (data['last_node_id'], max(node_ids)))
        all_ok = False
    if data['last_link_id'] < max(link_ids):
        print('  [FAIL] last_link_id=%s < max link id=%s' % (data['last_link_id'], max(link_ids)))
        all_ok = False

    # 4. 与备份的差异（只应新增节点+链接+last_*）
    with open(bak, encoding='utf-8') as f:
        old = json.load(f)
    old_node_ids = {n['id'] for n in old['nodes']}
    added = [n for n in data['nodes'] if n['id'] not in old_node_ids]
    changed = [n for n in data['nodes'] if n['id'] in old_node_ids and n != next(o for o in old['nodes'] if o['id'] == n['id'])]
    print('  [OK] 新增节点: %s' % [a['type'] for a in added])
    print('      修改节点: %s' % [c['id'] for c in changed])
    print('      新增链接数: %d, last_node_id %s->%s, last_link_id %s->%s'
          % (len(data['links']) - len(old['links']), old['last_node_id'], data['last_node_id'],
             old['last_link_id'], data['last_link_id']))

print('=' * 70)
print('总体: %s' % ('全部通过' if all_ok else '存在失败项'))
