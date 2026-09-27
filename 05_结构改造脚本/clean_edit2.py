# -*- coding: utf-8 -*-
"""编辑类清理：删对比/注释/多余组、SaveImage→Advanced、布局统一"""
import json, os
E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'

def load(fn):
    raw = open(os.path.join(E, fn), encoding='utf-8').read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    return json.loads(raw), indent, sep
def save(fn, data, indent, sep):
    with open(os.path.join(E, fn), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

def remove_nodes_and_links(data, del_node_ids, del_link_ids):
    # 删节点
    data['nodes'] = [n for n in data['nodes'] if n['id'] not in del_node_ids]
    # 删连线
    data['links'] = [l for l in data['links'] if l[0] not in del_link_ids]
    # 清理其他节点 inputs 里的 link 引用
    for n in data['nodes']:
        for inp in (n.get('inputs') or []):
            if inp.get('link') in del_link_ids:
                inp['link'] = None

# === 1. qwen_2_1_edit: 删 ImageCompare(472) + links 707,708 ===
fn = 'qwen_2_1_edit.json'
data, indent, sep = load(fn)
remove_nodes_and_links(data, {472}, {707,708})
# 布局
for n in data['nodes']:
    if n['id']==459: n['pos']=[0,0]
    if n['id']==470: n['pos']=[-380,0]; n['size']=[290,110]
    if n['id']==475: n['pos']=[-380,200]; n['size']=[290,110]
    if n['id']==13: n['pos']=[-380,450]; n['size']=[300,190]
    if n['id']==461: n['pos']=[330,-10]; n['size']=[850,610]
save(fn, data, indent, sep)
print('qwen_2_1_edit: 删ImageCompare, 布局统一')

# === 2. flux2_klein_edit: 删第二组 92/121/122 + MarkdownNote 97, links 169/189/191 ===
fn = 'flux2_klein_edit.json'
data, indent, sep = load(fn)
remove_nodes_and_links(data, {92,121,122,97}, {169,189,191})
# SaveImage(9) -> SaveImageAdvanced
for n in data['nodes']:
    if n['id']==9:
        n['type']='SaveImageAdvanced'
        n['widgets_values']=['Flux2-Klein-Edit','png','8-bit','sRGB']
    if n['id']==75: n['pos']=[0,0]
    if n['id']==76: n['pos']=[-380,0]; n['size']=[290,110]
    if n['id']==9: n['pos']=[330,-10]; n['size']=[850,610]
save(fn, data, indent, sep)
print('flux2_klein_edit: 删第二组, SaveImage->Advanced, 布局')

# === 3. qwen_edit_2511: 删 MarkdownNote 82/157, SaveImage(9)->Advanced, 布局 ===
fn = 'qwen_edit_2511.json'
data, indent, sep = load(fn)
data['nodes'] = [n for n in data['nodes'] if n.get('type')!='MarkdownNote']
for n in data['nodes']:
    if n['id']==9:
        n['type']='SaveImageAdvanced'
        n['widgets_values']=['Qwen_Edit_2511','png','8-bit','sRGB']
    if n['id']==170: n['pos']=[0,0]
    if n['id']==41: n['pos']=[-380,0]; n['size']=[280,370]
    if n['id']==83: n['pos']=[-380,400]; n['size']=[280,370]
    if n['id']==9: n['pos']=[330,-10]; n['size']=[850,610]
save(fn, data, indent, sep)
print('qwen_edit_2511: 删注释, SaveImage->Advanced, 布局')
print('完成')
