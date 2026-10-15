# -*- coding: utf-8 -*-
"""修正 Z_image.json：从误改的 8步/turbo 改回原生全量最低标准
   2026-10-14：接入 dry-run 开关（默认关闭）——--dry-run 不落盘，只打印结构与将写入的 diff。"""

import json, os
import dryrun

GLOBAL_D = os.path.expandvars(r'%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows\Image')
dryrun.parse_args()
D = dryrun.resolve_target(GLOBAL_D)
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
dryrun.write_json(os.path.join(D, fn), data, indent, sep)
