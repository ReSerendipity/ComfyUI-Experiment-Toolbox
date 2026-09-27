# -*- coding: utf-8 -*-
"""按推荐修改 8 个工作流采样参数：全量模式最低标准"""
import json, os, shutil

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
BAK = os.path.join(D, '新建文件夹')

FILES = ['Qwen_image_2_1_t2i.json', 'krea2_turbo.json',
         'Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']
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
    with open(os.path.join(D, fn), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

# 主节点 widgets 修改表：fn -> {索引: 新值}
MAIN_EDITS = {
    'Qwen_image_2_1_t2i.json': {2: 3, 7: 'beta'},            # cfg 1->3, scheduler simple->beta
    'Flux.2_Klein-9B-Distilled.json': {6: 'euler'},          # sampler
    'Qwen_image.json': {2: 3, 3: 25, 6: 'euler', 7: 'beta'},
    'Qwen_image_2512.json': {2: 3, 3: 25, 6: 'euler', 7: 'beta'},
    'Z_image.json': {2: 1, 3: 8, 6: 'res_multistep', 7: 'simple'},
    'Z_image_turbo.json': {6: 'res_multistep', 7: 'simple'},
    'flux.1-dev.json': {1: 20, 5: 'euler', 6: 'simple'},
}

for fn in FILES:
    print('==', fn)
    shutil.copy2(os.path.join(D, fn), os.path.join(BAK, fn.replace('.json', '.sampler.bak')))
    data, indent, sep = read(fn)
    main = next(n for n in data['nodes'] if n['id'] == MAIN_ID[fn])
    if fn in MAIN_EDITS:
        for idx, newv in MAIN_EDITS[fn].items():
            old = main['widgets_values'][idx]
            main['widgets_values'][idx] = newv
            print('  主节点[%d]: %r -> %r' % (idx, old, newv))
    # 子图内同步修改
    sg = data['definitions']['subgraphs'][0]
    if fn == 'Flux.2_Klein-9B-Distilled.json':
        n = next(n for n in sg['nodes'] if n['id'] == 8)  # KSamplerSelect
        print('  KSamplerSelect: %r -> euler' % n['widgets_values'][0])
        n['widgets_values'][0] = 'euler'
    if fn == 'flux.1-dev.json':
        bs = next(n for n in sg['nodes'] if n['id'] == 17)  # BasicScheduler
        print('  BasicScheduler: %r -> simple,20' % bs['widgets_values'])
        bs['widgets_values'] = ['simple', 20, 1]
        fg = next(n for n in sg['nodes'] if n['id'] == 26)  # FluxGuidance
        print('  FluxGuidance: %r -> 3.5' % fg['widgets_values'][0])
        fg['widgets_values'][0] = 3.5
    write(fn, data, indent, sep)
    print('  已写入')
print('完成')
