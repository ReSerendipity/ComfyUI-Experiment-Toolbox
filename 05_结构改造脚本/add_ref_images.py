# -*- coding: utf-8 -*-
"""Qwen 2.1 加到10张, Qwen 2511 补到3张"""
import json, os

E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'

def load(p):
    raw = open(p, encoding='utf-8').read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    return json.loads(raw), indent, sep

def save(p, d, indent, sep):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=indent, separators=sep)

def new_loadimage(node_id, x, y, links, link_id):
    """构造一个 LoadImage 节点"""
    return {
        "id": node_id, "type": "LoadImage",
        "pos": [x, y], "size": [290, 110],
        "flags": {}, "order": node_id, "mode": 0,
        "inputs": [],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [link_id]},
            {"name": "MASK", "type": "MASK", "links": None}
        ],
        "properties": {"Node name for S&R": "LoadImage"},
        "widgets_values": ["example.png", "image"]
    }

# ============ Qwen 2.1: 2 -> 10 张 ============
print('=== Qwen 2.1 edit: 加 8 张 LoadImage ===')
p = os.path.join(E, 'qwen_2_1_edit.json')
d, indent, sep = load(p)

# 找当前最大 id 和 link id
max_nid = max(n['id'] for n in d['nodes'])
max_lid = max(l[0] for l in d['links'])
print('当前最大 node id=%d, link id=%d' % (max_nid, max_lid))

# 主节点 459
main = next(n for n in d['nodes'] if n['id']==459)
# images.image_3 ~ image_10 在 slot 16~23
# image_5 的接口名是 images.image_5_1（slot 18）
slot_map = {
    'images.image_3': 16, 'images.image_4': 17, 'images.image_5_1': 18,
    'images.image_6': 19, 'images.image_7': 20, 'images.image_8': 21,
    'images.image_9': 22, 'images.image_10': 23
}

new_nid = max_nid
new_lid = max_lid
for i, (name, slot) in enumerate(slot_map.items()):
    new_nid += 1
    new_lid += 1
    # LoadImage 位置：左列竖排，470 在 [−380,0]，475 在 [−380,150]
    x = -700
    y = i * 130  # 从 0 开始竖排
    li = new_loadimage(new_nid, x, y, None, new_lid)
    d['nodes'].append(li)
    # 连线: LoadImage 输出 -> 主节点 slot
    d['links'].append([new_lid, new_nid, 0, 459, slot, 'IMAGE'])
    # 主节点该 input 的 link 指向新 link
    main['inputs'][slot]['link'] = new_lid
    print('  加 LoadImage id=%d -> 主节点 slot=%d (%s), link=%d' % (new_nid, slot, name, new_lid))

save(p, d, indent, sep)
# 验证
d2, _, _ = load(p)
lds = [n for n in d2['nodes'] if n['type']=='LoadImage']
print('Qwen 2.1 LoadImage 数量: %d' % len(lds))

# ============ Qwen 2511: 2 -> 3 张 ============
print()
print('=== Qwen 2511 edit: 加 1 张 LoadImage ===')
p2 = os.path.join(E, 'qwen_edit_2511.json')
d2, indent2, sep2 = load(p2)
max_nid2 = max(n['id'] for n in d2['nodes'])
max_lid2 = max(l[0] for l in d2['links'])
new_nid2 = max_nid2 + 1
new_lid2 = max_lid2 + 1
li = new_loadimage(new_nid2, -380, 300, None, new_lid2)
d2['nodes'].append(li)
# 主节点 170 image3 在 slot 2
d2['links'].append([new_lid2, new_nid2, 0, 170, 2, 'IMAGE'])
main2 = next(n for n in d2['nodes'] if n['id']==170)
main2['inputs'][2]['link'] = new_lid2
print('  加 LoadImage id=%d -> 主节点 slot=2 (image3), link=%d' % (new_nid2, new_lid2))
save(p2, d2, indent2, sep2)
d3, _, _ = load(p2)
lds2 = [n for n in d3['nodes'] if n['type']=='LoadImage']
print('Qwen 2511 LoadImage 数量: %d' % len(lds2))
print('完成')
