# -*- coding: utf-8 -*-
"""Flux.2 edit 重新从官方模板复制，保留2张LoadImage，再清理"""
import json, os, shutil
T = r'%USERPROFILE%\APP\ComfyUI-aki-v3\python\Lib\site-packages\comfyui_workflow_templates_json\templates'
E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'

# 重新复制
shutil.copy2(os.path.join(T,'image_flux2_klein_image_edit_9b_distilled.json'),
             os.path.join(E,'flux2_klein_edit.json'))

raw = open(os.path.join(E,'flux2_klein_edit.json'), encoding='utf-8').read()
indent = 2 if '\n  ' in raw else None
sep = (', ', ': ') if '", "' in raw else (',', ':')
d = json.loads(raw)

# 1. 删 MarkdownNote
d['nodes'] = [n for n in d['nodes'] if n.get('type') != 'MarkdownNote']
# 2. 模型名对正（所有子图 UNETLoader）
for sg in d['definitions']['subgraphs']:
    for n in sg['nodes']:
        if n.get('type') == 'UNETLoader':
            n['widgets_values'][0] = 'FLUX-2-klein-9b-fp8\\DarkBeast-Klein9b-V2-BFS-FP8.safetensors'
# 3. 清空顶层主节点 prompt（两个子图主节点 75 和 92）
for n in d['nodes']:
    if n.get('type') in ('7b34ab90-36f9-45ba-a665-71d418f0df18','65c22b29-59aa-496b-89c6-55a603658670'):
        n['widgets_values'][3] = ''
# 4. SaveImage -> SaveImageAdvanced（两个 SaveImage 9 和 122）
for n in d['nodes']:
    if n.get('type') == 'SaveImage':
        n['type'] = 'SaveImageAdvanced'
        n['widgets_values'] = ['Flux2-Klein-Edit','png','8-bit','sRGB']
# 5. 布局：保留两组（每组一个主节点+一个LoadImage+一个SaveImage），上下排列
# 顶层节点: 76 LoadImage, 9 SaveImage, 75 主节点, 122 SaveImage, 121 LoadImage, 92 主节点
for n in d['nodes']:
    if n['id']==75: n['pos']=[0,0]
    if n['id']==76: n['pos']=[-380,0]; n['size']=[290,110]
    if n['id']==9: n['pos']=[330,-10]; n['size']=[850,610]
    if n['id']==92: n['pos']=[0,850]
    if n['id']==121: n['pos']=[-380,850]; n['size']=[290,110]
    if n['id']==122: n['pos']=[330,840]; n['size']=[850,610]

with open(os.path.join(E,'flux2_klein_edit.json'),'w',encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=indent, separators=sep)

# 验证
d2 = json.load(open(os.path.join(E,'flux2_klein_edit.json'),encoding='utf-8'))
lds = [n for n in d2['nodes'] if n['type']=='LoadImage']
print('Flux.2 edit LoadImage 数量:', len(lds))
print('顶层节点:')
for n in d2['nodes']:
    print('  id=%-4s type=%s' % (n['id'], n['type']))
print('完成')
