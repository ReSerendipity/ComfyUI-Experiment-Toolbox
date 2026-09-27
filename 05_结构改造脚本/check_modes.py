# -*- coding: utf-8 -*-
"""检查 6 个自定义工作流子图中 LoRA / SeedVR2 / RVS 节点的 mode"""
import json, os

d = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
files = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']
for fn in files:
    with open(os.path.join(d, fn), encoding='utf-8') as f:
        data = json.load(f)
    sg = data['definitions']['subgraphs'][0]
    print('=' * 70)
    print(fn)
    for n in sg['nodes']:
        t = n.get('type', '')
        if 'SeedVR2' in t or t == 'LoraLoaderModelOnly' or t == 'ReservedVRAMSetter':
            wv = n.get('widgets_values')
            extra = ''
            if t == 'LoraLoaderModelOnly':
                extra = ' lora=%s' % (wv[0] if wv else None)
            print('  id=%s %s mode=%s%s' % (n.get('id'), t, n.get('mode'), extra))
