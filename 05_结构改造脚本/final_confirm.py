# -*- coding: utf-8 -*-
"""最终确认：2.1 融合功能完整 + 备份 + 格式"""
import json, os, glob

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'

print('=== 2.1 融合功能复查 ===')
d = json.load(open(os.path.join(D, 'Qwen_image_2_1_t2i.json'), encoding='utf-8'))
sg = d['definitions']['subgraphs'][0]
types = [n.get('type') for n in sg['nodes']]
for t in ['LoraLoaderModelOnly', 'BatchPromptReaderWithClip', 'SeedVR2LoadVAEModel',
          'SeedVR2LoadDiTModel', 'SeedVR2VideoUpscaler', 'ReservedVRAMSetter']:
    print('  %-26s %d 个' % (t, types.count(t)))
print('  子图输出数:', len(sg['outputs']))
print('  lastLinkId:', sg['state']['lastLinkId'], ' lastNodeId:', sg['state']['lastNodeId'])

print()
print('=== 备份文件 ===')
for pat in ['*.pre_fusion.bak', '*.layout.bak', '*.step3.bak']:
    files = sorted(glob.glob(os.path.join(D, pat)))
    print('  %-20s %d 个' % (pat, len(files)))
    for f in files:
        print('     ', os.path.basename(f))

print()
print('=== 格式检查 ===')
for fn in sorted(os.listdir(D)):
    if not fn.endswith('.json'):
        continue
    raw = open(os.path.join(D, fn), encoding='utf-8').read()
    fmt = ('spaced' if '", "' in raw else 'compact')
    print('  %-36s %s' % (fn, fmt))
