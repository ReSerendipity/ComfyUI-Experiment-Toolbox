# -*- coding: utf-8 -*-
"""检查 6 个自定义工作流文件格式是否与各自 step3.bak 一致"""
import os

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
files = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']
for fn in files:
    cur = open(os.path.join(D, fn), encoding='utf-8').read()
    bak = open(os.path.join(D, fn.replace('.json', '.step3.bak')), encoding='utf-8').read()
    cur_fmt = ('spaced' if '", "' in cur else 'compact') + ('+indent' if '\n  ' in cur else '')
    bak_fmt = ('spaced' if '", "' in bak else 'compact') + ('+indent' if '\n  ' in bak else '')
    same = '一致' if cur_fmt == bak_fmt else '!! 不一致'
    print('%-36s 当前:%-14s 备份:%-14s %s' % (fn, cur_fmt, bak_fmt, same))
