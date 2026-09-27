# -*- coding: utf-8 -*-
"""
将其他 6 个工作流全面对齐 Qwen_image_2_1_t2i.json（Text to Image 2.1 模板）：v2
修复：
  - 主节点新输入插入到 height 之后（h_idx+1），而非 width 之后
  - 新链接 slot 按 iface_order 动态计算（不硬编码）
  - 预处理：修复上一轮 RS 顶层链接 id 与子图内部链接 id 冲突
  - 最后统一 subgraph state.lastLinkId = 顶层 last_link_id
"""
import json
import os
import shutil
import uuid

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'

CONFIG = {
    'Flux.2_Klein-9B-Distilled.json': {
        'main_id': 64, 'w_idx': 4, 'h_idx': 5, 'kind': 'flux2',
        'interface_x': -0.955078125,
        'iface_order': ['positive_prompt', 'negative_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (8, 0, 'COMBO'), 'seed': (6, 0, 'INT'),
                    'clip': (2, 0, 'COMBO'), 'vae': (3, 0, 'COMBO')},
        'unet_link_id': 97,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'seed': 688501362745234,
                     'clip': 'FLUX.2-klein-9b\\qwen_3_8b_fp8mixed.safetensors',
                     'vae': 'FLUX.2-klein-9b\\flux2-vae.safetensors'},
        'save_prefix': 'Flux.2_Klein-9B-Distilled', 'space_sep': False,
    },
    'Qwen_image.json': {
        'main_id': 65, 'w_idx': 4, 'h_idx': 5, 'kind': 'ksampler',
        'interface_x': -0.955078125,
        'iface_order': ['positive_prompt', 'negative_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'scheduler_1', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (7, 7, 'COMBO'), 'scheduler': (7, 8, 'COMBO'), 'seed': (7, 4, 'INT'),
                    'clip': (77, 0, 'COMBO'), 'vae': (78, 0, 'COMBO')},
        'unet_link_id': 118,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'scheduler': 'sgm_uniform', 'seed': 297796727043574,
                     'clip': 'Qwen（2512）（edit）\\qwen_2.5_vl_7b_fp8_scaled.safetensors',
                     'vae': 'Qwen（2512）（edit）(Krea2)\\qwen_image_vae.safetensors'},
        'save_prefix': 'Qwen_image', 'space_sep': False,
    },
    'Qwen_image_2512.json': {
        'main_id': 65, 'w_idx': 4, 'h_idx': 5, 'kind': 'ksampler',
        'interface_x': -0.955078125,
        'iface_order': ['positive_prompt', 'negative_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'scheduler_1', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (7, 7, 'COMBO'), 'scheduler': (7, 8, 'COMBO'), 'seed': (7, 4, 'INT'),
                    'clip': (11, 0, 'COMBO'), 'vae': (3, 0, 'COMBO')},
        'unet_link_id': 100,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'scheduler': 'sgm_uniform', 'seed': 827975260547332,
                     'clip': 'Qwen（2512）（edit）\\qwen_2.5_vl_7b_fp8_scaled.safetensors',
                     'vae': 'Qwen（2512）（edit）(Krea2)\\qwen_image_vae.safetensors'},
        'save_prefix': 'Qwen_image_2512', 'space_sep': False,
    },
    'Z_image.json': {
        'main_id': 60, 'w_idx': 4, 'h_idx': 5, 'kind': 'ksampler',
        'interface_x': -0.955078125,
        'iface_order': ['positive_prompt', 'negative_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'scheduler_1', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (7, 7, 'COMBO'), 'scheduler': (7, 8, 'COMBO'), 'seed': (7, 4, 'INT'),
                    'clip': (11, 0, 'COMBO'), 'vae': (3, 0, 'COMBO')},
        'unet_link_id': 90,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'scheduler': 'sgm_uniform', 'seed': 234518742503160,
                     'clip': 'Z_image(turbo)\\qwen_3_4b_fp8_mixed.safetensors',
                     'vae': 'FLUX.1-dev(Z-image(turbo))\\ae.safetensors'},
        'save_prefix': 'Z_image', 'space_sep': True,
    },
    'Z_image_turbo.json': {
        'main_id': 82, 'w_idx': 4, 'h_idx': 5, 'kind': 'ksampler',
        'interface_x': -0.955078125,
        'iface_order': ['positive_prompt', 'negative_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'scheduler_1', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (7, 7, 'COMBO'), 'scheduler': (7, 8, 'COMBO'), 'seed': (7, 4, 'INT'),
                    'clip': (2, 0, 'COMBO'), 'vae': (3, 0, 'COMBO')},
        'unet_link_id': 130,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'scheduler': 'sgm_uniform', 'seed': 427805451282774,
                     'clip': 'Z-image-turbo\\qwen_3_4b_fp8_mixed.safetensors',
                     'vae': 'FLUX-1-dev + Z-image-turbo\\ae.safetensors'},
        'save_prefix': 'Z_image_turbo', 'space_sep': False,
    },
    'flux.1-dev.json': {
        'main_id': 132, 'w_idx': 3, 'h_idx': 4, 'kind': 'flux1',
        'interface_x': -5.35546875,
        'iface_order': ['positive_prompt', 'cfg', 'steps', 'width', 'height',
                        'scheduler', 'scheduler_1', 'seed', 'unet_name', 'clip_name', 'vae_name'],
        'targets': {'sampler': (16, 0, 'COMBO'), 'scheduler': (17, 1, 'COMBO'), 'seed': (25, 0, 'INT'),
                    'clip': (85, 0, 'COMBO'), 'vae': (10, 0, 'COMBO')},
        'unet_link_id': 301,
        'defaults': {'sampler': 'dpmpp_3m_sde_gpu', 'scheduler': 'sgm_uniform', 'seed': 912137899306657,
                     'clip': 'FLUX.1-dev\\clip_l.safetensors',
                     'vae': 'FLUX.1-dev(Z-image(turbo))\\ae.safetensors'},
        'save_prefix': 'flux.1-dev', 'space_sep': False,
    },
}

KEY_TO_IFACE = {'sampler': 'scheduler', 'scheduler': 'scheduler_1',
                'seed': 'seed', 'clip': 'clip_name', 'vae': 'vae_name'}


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(path, data, space_sep):
    sep = (', ', ': ') if space_sep else (',', ':')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, separators=sep))


def fix_rs_link_conflict(data, sg):
    """修复 RS 顶层链接 id 与子图内部链接 id 冲突（上一轮遗留）。"""
    sub_ids = {l['id'] for l in sg.get('links', [])}
    top_ids = {l[0] for l in data['links']}
    conflict = top_ids & sub_ids
    if not conflict:
        return False
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    all_ids = top_ids | sub_ids
    next_id = max(all_ids) + 1
    changed = {}
    for out in rs['outputs']:
        new_links = []
        for lid in out.get('links', []):
            if lid in sub_ids:
                new_id = next_id
                next_id += 1
                changed[lid] = new_id
                new_links.append(new_id)
            else:
                new_links.append(lid)
        out['links'] = new_links
    # 更新顶层 links 记录与目标节点 input.link
    for l in data['links']:
        if l[0] in changed:
            l[0] = changed[l[0]]
        # 目标 input 引用
        for n in data['nodes']:
            for inp in n.get('inputs', []):
                if inp.get('link') in changed:
                    inp['link'] = changed[inp['link']]
    # 更新 last_link_id
    if changed:
        data['last_link_id'] = max(max(l[0] for l in data['links']), next_id - 1)
    return bool(changed)


def new_iface(name, ltype, link_ids, pos, label=None):
    d = {'id': str(uuid.uuid4()), 'name': name, 'type': ltype, 'linkIds': link_ids, 'pos': pos}
    if label:
        d['label'] = label
    return d


def main():
    for fn, cfg in CONFIG.items():
        path = os.path.join(D, fn)
        data = load(path)
        sg = data['definitions']['subgraphs'][0]
        main_node = next(n for n in data['nodes'] if n.get('id') == cfg['main_id'])

        fixed = fix_rs_link_conflict(data, sg)
        if fixed:
            print('  [修复] %s RS 链接 id 冲突已重编' % fn)

        # 全局链接 id 分配（重新统计）
        all_link_ids = {l[0] for l in data['links']} | {l['id'] for l in sg.get('links', [])}
        next_lid = max(all_link_ids) + 1

        # ============ 1. 子图接口补齐 ============
        pos_x = cfg['interface_x']
        old_by_name = {i['name']: i for i in sg['inputs']}
        # 动态计算每个 key 的 slot
        slots = {}
        for key in ('sampler', 'scheduler', 'seed', 'clip', 'vae'):
            if key in cfg['targets']:
                slots[key] = cfg['iface_order'].index(KEY_TO_IFACE[key])

        new_link_ids = {}
        for key, slot in slots.items():
            tgt_id, tgt_slot, ltype = cfg['targets'][key]
            lid = next_lid
            next_lid += 1
            new_link_ids[key] = lid
            sg['links'].append({'id': lid, 'origin_id': -10, 'origin_slot': slot,
                                'target_id': tgt_id, 'target_slot': tgt_slot, 'type': ltype})
            tgt_node = next(n for n in sg['nodes'] if n.get('id') == tgt_id)
            tgt_node['inputs'][tgt_slot]['link'] = lid

        # 重建接口列表
        new_ifaces = []
        y = 154
        for name in cfg['iface_order']:
            if name in old_by_name:
                old = dict(old_by_name[name])
                old['pos'] = [pos_x, y]
                new_ifaces.append(old)
            else:
                if name == 'scheduler':
                    new_ifaces.append(new_iface('scheduler', 'COMBO', [new_link_ids['sampler']], [pos_x, y], label='sampler'))
                elif name == 'scheduler_1':
                    new_ifaces.append(new_iface('scheduler_1', 'COMBO', [new_link_ids['scheduler']], [pos_x, y], label='scheduler'))
                elif name == 'seed':
                    new_ifaces.append(new_iface('seed', 'INT', [new_link_ids['seed']], [pos_x, y]))
                elif name == 'clip_name':
                    new_ifaces.append(new_iface('clip_name', 'COMBO', [new_link_ids['clip']], [pos_x, y]))
                elif name == 'vae_name':
                    new_ifaces.append(new_iface('vae_name', 'COMBO', [new_link_ids['vae']], [pos_x, y]))
            y += 20
        sg['inputs'] = new_ifaces

        # unet_name 的 -10 链接 origin_slot 更新
        unet_new_slot = cfg['iface_order'].index('unet_name')
        for l in sg['links']:
            if l.get('origin_id') == -10 and l.get('id') == cfg['unet_link_id']:
                l['origin_slot'] = unet_new_slot

        # ============ 2. 顶层主节点 ============
        main_inputs = main_node['inputs']
        main_vals = list(main_node['widgets_values'])
        dfl = cfg['defaults']
        insert_at = cfg['h_idx'] + 1

        new_inputs_map = {}
        for key, iname in [('sampler', 'scheduler'), ('scheduler', 'scheduler_1'), ('seed', 'seed'),
                           ('clip', 'clip_name'), ('vae', 'vae_name')]:
            if key not in cfg['targets']:
                continue
            if key in ('sampler', 'scheduler'):
                lbl = 'sampler' if key == 'sampler' else 'scheduler'
                new_inputs_map[iname] = {'label': lbl, 'name': iname, 'type': 'COMBO',
                                         'widget': {'name': iname}, 'link': None}
            elif key == 'seed':
                new_inputs_map[iname] = {'name': iname, 'type': 'INT',
                                         'widget': {'name': iname}, 'link': None}
            else:
                new_inputs_map[iname] = {'name': iname, 'type': 'COMBO',
                                         'widget': {'name': iname}, 'link': None}

        mid_names = [KEY_TO_IFACE[k] for k in ('sampler', 'scheduler', 'seed') if k in cfg['targets']]
        tail_names = [KEY_TO_IFACE[k] for k in ('clip', 'vae')]

        main_node['inputs'] = main_inputs[:insert_at] + [new_inputs_map[n] for n in mid_names] \
                              + main_inputs[insert_at:] + [new_inputs_map[n] for n in tail_names]
        mid_vals = [dfl[k] for k in ('sampler', 'scheduler', 'seed') if k in cfg['targets']]
        tail_vals = [dfl['clip'], dfl['vae']]
        main_node['widgets_values'] = main_vals[:insert_at] + mid_vals + main_vals[insert_at:] + tail_vals
        main_node['size'] = [247.589453125, 473.9999843161845]

        # ============ 3. RS 位置 ============
        rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
        mpos = main_node.get('pos', [0, 0])
        rs['pos'] = [mpos[0] - 372, mpos[1] + 298]

        # ============ 4. 保存节点替换 ============
        main_outs = main_node['outputs']
        old_save = next(n for n in data['nodes'] if n.get('type') == 'SaveImage')
        prefix = old_save.get('widgets_values', [cfg['save_prefix']])[0]
        eses = next(n for n in data['nodes'] if n.get('type') == 'EsesImageCompare')
        remove_ids = {l[0] for l in data['links'] if l[3] == eses['id'] or l[1] == eses['id']}
        data['links'] = [l for l in data['links'] if l[0] not in remove_ids]
        data['nodes'] = [n for n in data['nodes']
                         if n.get('type') not in ('EsesImageCompare', 'SaveImage')]
        save_link_id = next_lid
        next_lid += 1
        main_outs[0]['links'] = [save_link_id]
        if len(main_outs) > 1:
            main_outs[1]['links'] = []
        save_node = {
            'id': data['last_node_id'] + 1, 'type': 'SaveImageAdvanced',
            'pos': [mpos[0] + 320, mpos[1] - 8], 'size': [850, 610],
            'flags': {}, 'order': 4, 'mode': 0,
            'inputs': [
                {'localized_name': '图像', 'name': 'images', 'type': 'IMAGE', 'link': save_link_id},
                {'localized_name': '文件名前缀', 'name': 'filename_prefix', 'type': 'STRING', 'widget': {'name': 'filename_prefix'}, 'link': None},
                {'localized_name': '格式', 'name': 'format', 'type': 'COMFY_DYNAMICCOMBO_V3', 'widget': {'name': 'format'}, 'link': None},
                {'localized_name': '位深度', 'name': 'format.bit_depth', 'type': 'COMBO', 'widget': {'name': 'format.bit_depth'}, 'link': None},
                {'localized_name': '输入色彩空间', 'name': 'format.input_color_space', 'type': 'COMBO', 'widget': {'name': 'format.input_color_space'}, 'link': None},
            ],
            'outputs': [{'localized_name': 'images', 'name': 'images', 'type': 'IMAGE', 'links': []}],
            'properties': {'cnr_id': 'comfy-core', 'ver': '0.36.0'},
            'widgets_values': [prefix, 'png', '8-bit', 'sRGB'],
            'widgets_values_named': {'filename_prefix': prefix, 'format': 'png',
                                     'format.bit_depth': '8-bit', 'format.input_color_space': 'sRGB'},
        }
        data['nodes'].append(save_node)
        data['links'].append([save_link_id, cfg['main_id'], 0, save_node['id'], 0, 'IMAGE'])

        data['last_node_id'] = save_node['id']
        data['last_link_id'] = next_lid - 1
        sg['state']['lastLinkId'] = data['last_link_id']

        save(path, data, cfg['space_sep'])
        print('[OK] %s: 接口=%d, 主节点inputs=%d, SaveImageAdvanced=%d, last_link_id=%d'
              % (fn, len(sg['inputs']), len(main_node['inputs']), save_node['id'], data['last_link_id']))


if __name__ == '__main__':
    main()
