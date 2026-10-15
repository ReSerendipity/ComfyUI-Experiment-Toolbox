# -*- coding: utf-8 -*-
"""清空所有工作流提示词内容
   2026-10-14：接入 dry-run 开关（默认关闭）——--dry-run 不落盘不备份，只打印计划。"""

import json, os, shutil
import dryrun

GLOBAL_D = os.path.expandvars(r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image')

FILES = ['Qwen_image_2_1_t2i.json', 'krea2_turbo.json',
         'Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']

# 顶层主节点 id
MAIN_ID = {'Qwen_image_2_1_t2i.json': 459, 'krea2_turbo.json': 30,
           'Flux.2_Klein-9B-Distilled.json': 64, 'Qwen_image.json': 65,
           'Qwen_image_2512.json': 65, 'Z_image.json': 60,
           'Z_image_turbo.json': 82, 'flux.1-dev.json': 132}

def read(fn):
    raw = open(os.path.join(D, fn), encoding='utf-8').read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    return json.loads(raw), indent, sep

def write(fn, data, indent, sep):
    dryrun.write_json(os.path.join(D, fn), data, indent, sep)

def backup(fn):
    src = os.path.join(D, fn)
    dst = os.path.join(BAK_DIR, fn.replace('.json', '.prompt_clear.bak'))
    dryrun.guard_backup(src, dst)

dryrun.parse_args()
D = dryrun.resolve_target(GLOBAL_D)
BAK_DIR = os.path.join(D, '新建文件夹')
if not dryrun.is_dry_run():
    os.makedirs(BAK_DIR, exist_ok=True)

for fn in FILES:
    print('==', fn)
    backup(fn)
    data, indent, sep = read(fn)
    main = next(n for n in data['nodes'] if n['id'] == MAIN_ID[fn])
    wv = main['widgets_values']
    old = wv[0]
    wv[0] = ''
    print('  顶层主节点[0]: %r -> %r' % (old[:60] if isinstance(old, str) else old, ''))
    # K2：子图内 PrimitiveStringMultiline(19) 和 CLIPTextEncode(6) 也清
    if fn == 'krea2_turbo.json':
        sg = data['definitions']['subgraphs'][0]
        for n in sg['nodes']:
            if n['id'] in (19, 6):
                old = n['widgets_values'][0]
                n['widgets_values'][0] = ''
                print('  子图 id=%d %s: %r -> %r' % (n['id'], n['type'], old[:60], ''))
            # widgets_values_named 同步
            if 'widgets_values_named' in n and n['id'] in (19, 6):
                pass
    write(fn, data, indent, sep)
    print('  已写入')

print('完成')
