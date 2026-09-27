# -*- coding: utf-8 -*-
"""编辑类工作流基础清理：备份、清空提示词、删 MarkdownNote、模型名对正、布局统一"""
import json, os, shutil
E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'
BAK = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image\新建文件夹'
os.makedirs(BAK, exist_ok=True)

def load(fn):
    raw = open(os.path.join(E, fn), encoding='utf-8').read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    return json.loads(raw), indent, sep

def save(fn, data, indent, sep):
    with open(os.path.join(E, fn), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

# 备份
for fn in ['qwen_2_1_edit.json','qwen_edit_2511.json','flux2_klein_edit.json']:
    shutil.copy2(os.path.join(E, fn), os.path.join(BAK, fn.replace('.json','.init.bak')))

# === 1. qwen_2_1_edit ===
fn = 'qwen_2_1_edit.json'
data, indent, sep = load(fn)
# 删 MarkdownNote
data['nodes'] = [n for n in data['nodes'] if n.get('type') != 'MarkdownNote']
# 主节点 459：清空 prompt [1]
m = next(n for n in data['nodes'] if n['id']==459)
m['widgets_values'][1] = ''
# 布局统一
for n in data['nodes']:
    if n['id']==459: n['pos']=[0,0]
    if n['id']==13: n['pos']=[-380,310]; n['size']=[300,190]
    if n['id']==461: n['pos']=[330,-10]; n['size']=[850,610]
save(fn, data, indent, sep)
print('qwen_2_1_edit: 清空prompt, 删2个MarkdownNote, 布局统一')

# === 2. qwen_edit_2511 ===
fn = 'qwen_edit_2511.json'
data, indent, sep = load(fn)
# 模型文件名对正：fp8mixed -> 用户实际 nvfp4
for sg in data['definitions']['subgraphs']:
    for n in sg['nodes']:
        if n.get('type')=='UNETLoader' and n['widgets_values'] and 'edit_2511' in str(n['widgets_values'][0]):
            print('  2511 UNETLoader:', n['widgets_values'][0], '-> qwen_image_edit_2511_nvfp4.safetensors')
            n['widgets_values'][0] = 'Qwen-Image-Edit-2511\\qwen_image_edit_2511_nvfp4.safetensors'
# 顶层主节点 170 widgets 为空，提示词在子图 CLIPTextEncode——先找
for sg in data['definitions']['subgraphs']:
    for n in sg['nodes']:
        if n.get('type')=='CLIPTextEncode' and n.get('widgets_values'):
            print('  2511 CLIPTextEncode id=%d widgets=%s' % (n['id'], str(n['widgets_values'])[:80]))
save(fn, data, indent, sep)
print('qwen_edit_2511: 模型名对正')

# === 3. flux2_klein_edit ===
fn = 'flux2_klein_edit.json'
data, indent, sep = load(fn)
for sg in data['definitions']['subgraphs']:
    for n in sg['nodes']:
        if n.get('type')=='UNETLoader':
            n['widgets_values'][0] = 'FLUX-2-klein-9b-fp8\\DarkBeast-Klein9b-V2-BFS-FP8.safetensors'
# 顶层主节点 prompt [3] 清空
for n in data['nodes']:
    if n['id'] in (75,92):
        n['widgets_values'][3] = ''
save(fn, data, indent, sep)
print('flux2_klein_edit: 模型名对正, 清空2个prompt')
print('完成')
