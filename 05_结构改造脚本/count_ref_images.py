# -*- coding: utf-8 -*-
import json, os
T = r'%USERPROFILE%\APP\ComfyUI-aki-v3\python\Lib\site-packages\comfyui_workflow_templates_json\templates'
OFFICIAL = {
    'Qwen 2.1 edit': 'image_qwen_image_2_1_image_edit.json',
    'Qwen edit 2511': 'image_qwen_image_edit_2511.json',
    'Flux.2 Klein 9b distilled edit': 'image_flux2_klein_image_edit_9b_distilled.json',
    'Flux.2 Klein 9b base edit': 'image_flux2_klein_image_edit_9b_base.json',
}
for label, fn in OFFICIAL.items():
    p = os.path.join(T, fn)
    if not os.path.exists(p):
        print(label, '不存在'); continue
    d = json.load(open(p, encoding='utf-8'))
    print('====', label, '====')
    # 顶层 LoadImage
    lds = [n for n in d['nodes'] if n.get('type')=='LoadImage']
    print('  顶层 LoadImage 数量:', len(lds))
    for n in lds:
        print('    id=%s file=%s' % (n['id'], n['widgets_values'][0] if n.get('widgets_values') else '?'))
    # 子图里参考图相关
    for sg in d.get('definitions',{}).get('subgraphs',[]):
        for n in sg['nodes']:
            t = n.get('type','')
            if t in ('TextEncodeQwenImage21','TextEncodeQwenImageEditPlus','VAEEncode','ReferenceLatent','FluxKontextMultiReferenceLatentMethod','GetImageSize','ImageScaleToTotalPixels'):
                imgs = [i for i in (n.get('inputs') or []) if i.get('type')=='IMAGE' or 'image' in (i.get('name') or '').lower()]
                print('  子图 id=%s type=%s 图片输入=%s' % (n['id'], t, [(i.get('name'), i.get('link')) for i in imgs]))
    print()
