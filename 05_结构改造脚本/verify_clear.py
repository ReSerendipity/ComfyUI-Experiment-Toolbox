# -*- coding: utf-8 -*-
import json, os, glob
D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
FILES = ['Qwen_image_2_1_t2i.json', 'krea2_turbo.json',
         'Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']
MAIN_ID = {'Qwen_image_2_1_t2i.json': 459, 'krea2_turbo.json': 30,
           'Flux.2_Klein-9B-Distilled.json': 64, 'Qwen_image.json': 65,
           'Qwen_image_2512.json': 65, 'Z_image.json': 60,
           'Z_image_turbo.json': 82, 'flux.1-dev.json': 132}
ok = True
for fn in FILES:
    try:
        d = json.load(open(os.path.join(D, fn), encoding='utf-8'))
        main = next(n for n in d['nodes'] if n['id'] == MAIN_ID[fn])
        v = main['widgets_values'][0]
        good = (v == '')
        print('[OK]' if good else '[FAIL]', fn, '-> prompt0=%r' % (v[:40] if isinstance(v, str) else v))
        if not good: ok = False
    except Exception as e:
        print('[FAIL]', fn, e); ok = False
# K2 子图
d = json.load(open(os.path.join(D, 'krea2_turbo.json'), encoding='utf-8'))
for n in d['definitions']['subgraphs'][0]['nodes']:
    if n['id'] in (6, 19):
        print('K2 子图 id=%d %s -> %r' % (n['id'], n['type'], n['widgets_values'][0][:40]))
# 备份
baks = glob.glob(os.path.join(D, '新建文件夹', '*.prompt_clear.bak'))
print('备份数:', len(baks))
print('总体:', '通过' if ok else '失败')
