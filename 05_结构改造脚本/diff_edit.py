# -*- coding: utf-8 -*-
"""diff 当前编辑工作流 vs 官方模板，列出所有差异"""
import json, os
T = r'%USERPROFILE%\APP\ComfyUI-aki-v3\python\Lib\site-packages\comfyui_workflow_templates_json\templates'
E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'
PAIRS = [
    ('image_qwen_image_2_1_image_edit.json', 'qwen_2_1_edit.json'),
    ('image_qwen_image_edit_2511.json', 'qwen_edit_2511.json'),
    ('image_flux2_klein_image_edit_9b_distilled.json', 'flux2_klein_edit.json'),
]
for off, cur in PAIRS:
    print('====', cur, 'vs', off, '====')
    a = json.load(open(os.path.join(T, off), encoding='utf-8'))
    b = json.load(open(os.path.join(E, cur), encoding='utf-8'))
    # 顶层节点对比
    a_nodes = {n['id']: n for n in a['nodes']}
    b_nodes = {n['id']: n for n in b['nodes']}
    a_types = {n['type'] for n in a['nodes']}
    b_types = {n['type'] for n in b['nodes']}
    print('  顶层类型 有/无: 删=%s 加=%s' % (a_types - b_types, b_types - a_types))
    # 子图节点 widgets 对比
    for sgi, (sa, sb) in enumerate(zip(a['definitions']['subgraphs'], b['definitions']['subgraphs'])):
        a_sub = {n['id']: n for n in sa['nodes']}
        b_sub = {n['id']: n for n in sb['nodes']}
        for nid in sorted(set(a_sub) | set(b_sub)):
            na = a_sub.get(nid)
            nb = b_sub.get(nid)
            if na is None:
                print('  子图%d 新增节点 id=%s type=%s' % (sgi, nid, nb.get('type')))
            elif nb is None:
                print('  子图%d 删除节点 id=%s type=%s' % (sgi, nid, na.get('type')))
            else:
                wa = na.get('widgets_values')
                wb = nb.get('widgets_values')
                if wa != wb:
                    print('  子图%d id=%s type=%s widgets变:' % (sgi, nid, na.get('type')))
                    print('      官方: %s' % str(wa)[:90])
                    print('      当前: %s' % str(wb)[:90])
    print()
