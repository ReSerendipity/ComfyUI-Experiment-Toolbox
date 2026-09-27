# -*- coding: utf-8 -*-
"""查看 8 个工作流顶层布局（主节点/RS/Save 的 pos/size/type）"""
import json, os

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
FILES = ['Qwen_image_2_1_t2i.json', 'krea2_turbo.json',
         'Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
         'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']
for fn in FILES:
    data = json.load(open(os.path.join(D, fn), encoding='utf-8'))
    print('=' * 70)
    print(fn)
    for n in data['nodes']:
        t = n.get('type', '')
        mark = ''
        if t in ('ResolutionSelector', 'SaveImage', 'SaveImageAdvanced', 'MarkdownNote') or len(t) == 36:
            mark = '  <<<'
            print('  id=%s type=%s pos=%s size=%s widgets=%s%s' % (
                n.get('id'), t[:40], n.get('pos'), n.get('size'),
                (n.get('widgets_values') or [])[:3], mark))
        else:
            print('  id=%s type=%s pos=%s size=%s' % (n.get('id'), t[:40], n.get('pos'), n.get('size')))
