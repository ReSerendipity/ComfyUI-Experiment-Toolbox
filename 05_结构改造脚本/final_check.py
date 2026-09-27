# -*- coding: utf-8 -*-
"""最终整体检查：8 个文件 JSON 完整性 + 备份存在性 + 2.1 拓扑摘要"""
import json, os, glob

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
FILES = ['Qwen_image_2_1_t2i.json', 'krea2_turbo.json',
         'Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']

print('=== JSON 解析检查 ===')
for fn in FILES:
    try:
        with open(os.path.join(D, fn), encoding='utf-8') as f:
            d = json.load(f)
        n_sub = len(d.get('definitions', {}).get('subgraphs', []))
        print('  [OK] %-36s 顶层节点=%d 子图=%d' % (fn, len(d.get('nodes', [])), n_sub))
    except Exception as e:
        print('  [FAIL]', fn, e)

print()
print('=== 备份文件 ===')
for pat in ['*.bak', '*.step2.bak', '*.step3.bak', '*.pre_fusion.bak']:
    files = glob.glob(os.path.join(D, pat))
    print('  %-20s %d 个' % (pat, len(files)))
    for f in sorted(files):
        print('     ', os.path.basename(f))

print()
print('=== 2.1 融合后拓扑摘要 ===')
d = json.load(open(os.path.join(D, 'Qwen_image_2_1_t2i.json'), encoding='utf-8'))
sg = d['definitions']['subgraphs'][0]
by_type = {}
for n in sg['nodes']:
    t = n['type']
    by_type[t] = by_type.get(t, 0) + 1
for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
    print('  %-30s x%d' % (t, c))
print('  子图链接总数:', len(sg['links']))
print('  子图输出:', [(o['name'], o['linkIds']) for o in sg['outputs']])
main = next(n for n in d['nodes'] if n['type'] == sg.get('name') or n.get('type', '').startswith('c291'))
# 主节点按 uuid 找
main = next(n for n in d['nodes'] if n.get('type') == 'c291ceec-b98f-4751-9d0b-7bc288f27b30')
print('  主节点输出:', [(o['name'], o['links']) for o in main['outputs']])
save = next(n for n in d['nodes'] if n.get('type') == 'SaveImageAdvanced')
print('  SaveImageAdvanced 输入链接:', save['inputs'][0].get('link'))
rs = next(n for n in d['nodes'] if n.get('type') == 'ResolutionSelector')
print('  ResolutionSelector:', rs.get('widgets_values'), '→ 链接', [l for l in d['links'] if l[0] in (670, 671)])
