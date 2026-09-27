# -*- coding: utf-8 -*-
"""修正 Z_image.json：从误改的 8步/turbo 改回原生全量最低标准"""
import json, os
D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
fn = 'Z_image.json'
raw = open(os.path.join(D, fn), encoding='utf-8').read()
indent = 2 if '\n  ' in raw else None
sep = (', ', ': ') if '", "' in raw else (',', ':')
data = json.loads(raw)
m = next(n for n in data['nodes'] if n['id'] == 60)
print('改前:', m['widgets_values'][2], m['widgets_values'][3], m['widgets_values'][6], m['widgets_values'][7])
# 官方：30-50步 cfg3-5，euler + sgm_uniform
m['widgets_values'][2] = 3      # cfg 最低 3
m['widgets_values'][3] = 30     # steps 最低 30
m['widgets_values'][6] = 'euler'
m['widgets_values'][7] = 'sgm_uniform'
print('改后:', m['widgets_values'][2], m['widgets_values'][3], m['widgets_values'][6], m['widgets_values'][7])
with open(os.path.join(D, fn), 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)
print('已写入')
