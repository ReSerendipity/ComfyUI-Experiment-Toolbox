# -*- coding: utf-8 -*-
"""
将 Qwen_image_2_1_t2i.json 中的 ResolutionSelector 节点应用到其他 ComfyUI 工作流。
模板取自 Qwen_image_2_1_t2i.json（comfy-core 0.36.0，含 preview 输入）。
对每个工作流：
  1) 新增 ResolutionSelector 节点（id = last_node_id + 1），摆放在主节点左上方；
  2) 新增两条 INT 链接：width -> 主节点.width 输入, height -> 主节点.height 输入；
  3) 更新主节点对应输入的 link 字段、last_node_id、last_link_id；
  4) 保持原紧凑 JSON 格式写回。
"""
import json
import os
import shutil
import copy

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'
SRC = os.path.join(D, 'Qwen_image_2_1_t2i.json')

# 各工作流: 文件名 -> (主节点id, width输入索引, height输入索引)
TARGETS = {
    'Flux.2_Klein-9B-Distilled.json': (64, 4, 5),
    'Qwen_image.json': (65, 4, 5),
    'Qwen_image_2512.json': (65, 4, 5),
    'Z_image.json': (60, 4, 5),
    'Z_image_turbo.json': (82, 4, 5),
    'flux.1-dev.json': (132, 3, 4),
}


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        # 与源文件一致：紧凑格式、ensure_ascii=False（ComfyUI 原生导出格式）
        f.write(json.dumps(data, ensure_ascii=False, separators=(',', ':')))


def make_selector_node(node_id, main_node, order):
    """按 Qwen_image_2_1_t2i 中 ResolutionSelector(0.36.0) 的构造生成新节点。"""
    main_pos = main_node.get('pos', [0, 0])
    return {
        'id': node_id,
        'type': 'ResolutionSelector',
        'pos': [main_pos[0] - 620, main_pos[1] + 298],
        'size': [300, 190],
        'flags': {},
        'order': order,
        'mode': 0,
        'showAdvanced': True,
        'inputs': [
            {
                'localized_name': '宽高比',
                'name': 'aspect_ratio',
                'type': 'COMBO',
                'widget': {'name': 'aspect_ratio'},
                'link': None,
            },
            {
                'localized_name': '百万像素',
                'name': 'megapixels',
                'type': 'FLOAT',
                'widget': {'name': 'megapixels'},
                'link': None,
            },
            {
                'localized_name': '倍数',
                'name': 'multiple',
                'type': 'INT',
                'widget': {'name': 'multiple'},
                'link': None,
            },
            {
                'localized_name': 'preview',
                'name': 'preview',
                'shape': 7,
                'type': 'RESOLUTION_PREVIEW',
                'widget': {'name': 'preview'},
                'link': None,
            },
        ],
        'outputs': [
            {
                'localized_name': '宽度',
                'name': 'width',
                'type': 'INT',
                'links': [],
            },
            {
                'localized_name': '高度',
                'name': 'height',
                'type': 'INT',
                'links': [],
            },
        ],
        'properties': {
            'cnr_id': 'comfy-core',
            'ver': '0.36.0',
            'Node name for S&R': 'ResolutionSelector',
        },
        'widgets_values': ['1:1 (Square)', 1, 8],
        'widgets_values_named': {
            'aspect_ratio': '1:1 (Square)',
            'megapixels': 1,
            'multiple': 8,
        },
    }


def main():
    with open(SRC, encoding='utf-8') as f:
        src_data = json.load(f)
    # 从源文件提取 ResolutionSelector 模板（仅用于核对，实际构造用 make_selector_node）
    for n in src_data['nodes']:
        if n.get('type') == 'ResolutionSelector':
            print('模板节点(源): id=%s ver=%s widgets=%s' % (n.get('id'), n['properties'].get('ver'), n.get('widgets_values')))
            break

    for fn, (main_id, w_idx, h_idx) in TARGETS.items():
        path = os.path.join(D, fn)
        data = load(path)
        # 备份
        bak = path + '.bak'
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
            print('已备份 ->', os.path.basename(bak))

        # 定位主节点
        main_node = None
        for n in data['nodes']:
            if n.get('id') == main_id:
                main_node = n
                break
        if main_node is None:
            print('!! %s 未找到主节点 %s，跳过' % (fn, main_id))
            continue

        # 校验目标输入存在且未占用
        w_inp = main_node['inputs'][w_idx]
        h_inp = main_node['inputs'][h_idx]
        assert 'width' in w_inp['name'] and 'height' in h_inp['name'], \
            '%s 输入索引不匹配: w=%s h=%s' % (fn, w_inp['name'], h_inp['name'])
        if w_inp.get('link') is not None or h_inp.get('link') is not None:
            print('!! %s width/height 已有链接，跳过' % fn)
            continue

        # 新节点与链接
        new_node_id = data['last_node_id'] + 1
        new_link_id = data['last_link_id'] + 1
        new_node = make_selector_node(new_node_id, main_node, main_node.get('order', 0))
        new_node['outputs'][0]['links'] = [new_link_id]
        new_node['outputs'][1]['links'] = [new_link_id + 1]

        link_w = [new_link_id, new_node_id, 0, main_id, w_idx, 'INT']
        link_h = [new_link_id + 1, new_node_id, 1, main_id, h_idx, 'INT']

        # 更新主节点输入
        w_inp['link'] = new_link_id
        h_inp['link'] = new_link_id + 1

        # 写入
        data['nodes'].append(new_node)
        data['links'].extend([link_w, link_h])
        data['last_node_id'] = new_node_id
        data['last_link_id'] = new_link_id + 1
        save(path, data)
        print('已应用 -> %s (新节点 id=%s, 链接 %s/%s -> 主节点 %s width[%s]/height[%s])'
              % (fn, new_node_id, new_link_id, new_link_id + 1, main_id, w_idx, h_idx))


if __name__ == '__main__':
    main()
