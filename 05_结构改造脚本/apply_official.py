# -*- coding: utf-8 -*-
"""按本机官方模板原值修正 8 工作流采样参数
v2（2026-10-11，评估报告 P2-3）：幂等守卫——主节点 widgets_values 已与目标一致则跳过，
避免重复改写；改动前仍强制备份到 Image 目录的『新建文件夹』（*.official.bak）。
"""

import json, os, shutil
D = os.path.expandvars(r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image')
BAK = os.path.join(D, '新建文件夹')

MAIN_ID = {'Qwen_image_2_1_t2i.json': 459, 'Qwen_image.json': 65,
           'Qwen_image_2512.json': 65, 'Z_image.json': 60, 'flux.1-dev.json': 132}

# 按官方模板原值：索引->新值
EDITS = {
    'Qwen_image_2_1_t2i.json': {2: 1, 7: 'simple'},          # cfg 3->1, scheduler beta->simple
    'Qwen_image.json': {7: 'simple'},                        # scheduler beta->simple
    'Qwen_image_2512.json': {2: 4, 3: 50, 7: 'simple'},      # cfg3->4, steps25->50, beta->simple
    'Z_image.json': {2: 4, 3: 25, 6: 'res_multistep', 7: 'simple'},  # 官方原值
}


def _is_applied(m, edits):
    """幂等守卫：主节点 widgets_values 已与目标值一致 → 已应用。"""
    try:
        return all(m['widgets_values'][idx] == newv for idx, newv in edits.items())
    except (IndexError, KeyError, TypeError):
        return False


def main():
    for fn, edits in EDITS.items():
        path = os.path.join(D, fn)
        raw = open(path, encoding='utf-8').read()
        indent = 2 if '\n  ' in raw else None
        sep = (', ', ': ') if '", "' in raw else (',', ':')
        data = json.loads(raw)
        m = next(n for n in data['nodes'] if n['id'] == MAIN_ID[fn])
        if _is_applied(m, edits):
            print('[跳过] %s 主节点已按官方原值' % fn)
            continue
        os.makedirs(BAK, exist_ok=True)
        shutil.copy2(path, os.path.join(BAK, fn.replace('.json', '.official.bak')))
        for idx, newv in edits.items():
            old = m['widgets_values'][idx]
            m['widgets_values'][idx] = newv
            print('%-26s [%d] %r -> %r' % (fn, idx, old, newv))
        # flux.1-dev FluxGuidance 3.5 -> 4（官方原值）
        if fn == 'flux.1-dev.json':
            sg = data['definitions']['subgraphs'][0]
            fg = next(n for n in sg['nodes'] if n['id'] == 26)
            print('  FluxGuidance %r -> 4' % fg['widgets_values'][0])
            fg['widgets_values'][0] = 4
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

    # flux.1-dev 单独处理（不在 EDITS 的主节点改动里）
    path = os.path.join(D, 'flux.1-dev.json')
    raw = open(path, encoding='utf-8').read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    data = json.loads(raw)
    sg = data['definitions']['subgraphs'][0]
    fg = next(n for n in sg['nodes'] if n['id'] == 26)
    if fg['widgets_values'][0] == 4:
        print('[跳过] flux.1-dev FluxGuidance 已为 4')
    else:
        os.makedirs(BAK, exist_ok=True)
        shutil.copy2(path, os.path.join(BAK, 'flux.1-dev.official.bak'))
        print('flux.1-dev FluxGuidance %r -> 4' % fg['widgets_values'][0])
        fg['widgets_values'][0] = 4
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)
    print('完成')


if __name__ == '__main__':
    main()
