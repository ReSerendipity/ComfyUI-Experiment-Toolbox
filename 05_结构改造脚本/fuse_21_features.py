# -*- coding: utf-8 -*-
"""
第三轮融合改造：
A. Qwen_image_2_1_t2i.json（2.1 官方模板）融合 6 个自定义工作流的长处：
   - 6 个 LoraLoaderModelOnly 插槽（mode=4 静止，默认不加载）
   - BatchPromptReaderWithClip 批量提示词（与手动 prompt 并存，默认不接采样器，手动 prompt 生效）
   - SeedVR2 超分链（LoadVAE + LoadDiT + VideoUpscaler，mode=4 静止默认不触发）
   - ReservedVRAMSetter 显存控制（mode=0，接 VAEDecode 后透传原图）
   - 子图双输出：输出0=原图(经显存控制)、输出1=超分(静止备用)
   - 顶层 SaveImageAdvanced 连主节点输出0（原图）
B. 6 个自定义工作流：SeedVR2 超分节点全部设为静止(mode=4)，顶层保存节点改连原图输出(输出1)
"""
import json, os, uuid, shutil

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'

CUSTOM = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
          'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']

def read(fn):
    p = os.path.join(D, fn)
    with open(p, encoding='utf-8') as f:
        raw = f.read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if "', '" in raw else (',', ':')
    return json.loads(raw), indent, sep

def write(fn, data, indent, sep):
    p = os.path.join(D, fn)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

def backup(fn, suffix):
    src = os.path.join(D, fn)
    dst = os.path.join(D, fn.replace('.json', suffix))
    shutil.copy2(src, dst)
    print('  备份:', os.path.basename(dst))


# ============ 新链接（682-694） ============
NEW_LINKS = [
    {'id': 682, 'origin_id': 470, 'origin_slot': 0, 'target_id': 471, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 683, 'origin_id': 471, 'origin_slot': 0, 'target_id': 472, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 684, 'origin_id': 472, 'origin_slot': 0, 'target_id': 473, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 685, 'origin_id': 473, 'origin_slot': 0, 'target_id': 474, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 686, 'origin_id': 474, 'origin_slot': 0, 'target_id': 475, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 687, 'origin_id': 475, 'origin_slot': 0, 'target_id': 458, 'target_slot': 0, 'type': 'MODEL'},
    {'id': 688, 'origin_id': 453, 'origin_slot': 0, 'target_id': 476, 'target_slot': 0, 'type': 'CLIP'},
    {'id': 689, 'origin_id': 457, 'origin_slot': 0, 'target_id': 480, 'target_slot': 0, 'type': 'IMAGE'},
    {'id': 690, 'origin_id': 480, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'},
    {'id': 691, 'origin_id': 457, 'origin_slot': 0, 'target_id': 479, 'target_slot': 0, 'type': 'IMAGE'},
    {'id': 692, 'origin_id': 477, 'origin_slot': 0, 'target_id': 479, 'target_slot': 2, 'type': 'SEEDVR2_VAE'},
    {'id': 693, 'origin_id': 478, 'origin_slot': 0, 'target_id': 479, 'target_slot': 1, 'type': 'SEEDVR2_DIT'},
    {'id': 694, 'origin_id': 479, 'origin_slot': 0, 'target_id': -20, 'target_slot': 1, 'type': 'IMAGE'},
]

LORA_PROPS = {"cnr_id": "comfy-core", "ver": "0.18.1",
              "Node name for S&R": "LoraLoaderModelOnly",
              "Node name for S&amp;R": "LoraLoaderModelOnly"}

def make_lora(nid, x, y, order, model_link, out_link):
    return {
        "id": nid, "type": "LoraLoaderModelOnly",
        "pos": [x, y], "size": [300, 114], "flags": {}, "order": order, "mode": 4,
        "inputs": [
            {"localized_name": "模型", "name": "model", "type": "MODEL", "link": model_link},
            {"localized_name": "LoRA名称", "name": "lora_name", "type": "COMBO",
             "widget": {"name": "lora_name"}, "link": None},
            {"localized_name": "模型强度", "name": "strength_model", "type": "FLOAT",
             "widget": {"name": "strength_model"}, "link": None},
        ],
        "outputs": [{"localized_name": "模型", "name": "MODEL", "type": "MODEL", "links": [out_link]}],
        "properties": LORA_PROPS,
        "widgets_values": ["None", 1],
        "widgets_values_named": {"lora_name": "None", "strength_model": 1},
        "color": "#223", "bgcolor": "#335",
    }

def make_batch_prompt():
    return {
        "id": 476, "type": "BatchPromptReaderWithClip",
        "pos": [300, 1180], "size": [305.75, 430], "flags": {}, "order": 13, "mode": 0,
        "inputs": [
            {"localized_name": "clip", "name": "clip", "type": "CLIP", "link": 688},
            {"localized_name": "folder_path", "name": "folder_path", "type": "STRING",
             "widget": {"name": "folder_path"}, "link": None},
            {"localized_name": "current_number", "name": "current_number", "type": "INT",
             "widget": {"name": "current_number"}, "link": None},
            {"localized_name": "recursive", "name": "recursive", "type": "BOOLEAN",
             "widget": {"name": "recursive"}, "link": None},
            {"localized_name": "reverse_order", "name": "reverse_order", "type": "BOOLEAN",
             "widget": {"name": "reverse_order"}, "link": None},
            {"localized_name": "file_pattern", "name": "file_pattern", "type": "STRING",
             "widget": {"name": "file_pattern"}, "link": None},
            {"localized_name": "output_folder", "name": "output_folder", "type": "STRING",
             "widget": {"name": "output_folder"}, "link": None},
            {"localized_name": "enable_logging", "name": "enable_logging", "type": "BOOLEAN",
             "widget": {"name": "enable_logging"}, "link": None},
            {"localized_name": "log_folder", "name": "log_folder", "type": "STRING",
             "widget": {"name": "log_folder"}, "link": None},
            {"localized_name": "clear_log_on_start", "name": "clear_log_on_start", "type": "BOOLEAN",
             "widget": {"name": "clear_log_on_start"}, "link": None},
            {"localized_name": "skip_exists", "name": "skip_exists", "type": "BOOLEAN", "shape": 7,
             "widget": {"name": "skip_exists"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "conditioning", "name": "conditioning", "type": "CONDITIONING", "links": None},
            {"localized_name": "filename", "name": "filename", "type": "STRING", "links": None},
            {"localized_name": "index", "name": "index", "type": "INT", "links": None},
            {"localized_name": "total_count", "name": "total_count", "type": "INT", "links": None},
        ],
        "properties": {"aux_id": "ReSerendipity/ComfyUI-BatchPromptLoader",
                       "ver": "e1ee38bc4bc302776f5a262431d17d5941baa16e",
                       "Node name for S&R": "BatchPromptReaderWithClip"},
        "widgets_values": ["input/Picture", 0, "increment", True, True, "*.txt", "output/",
                           False, "user/default/batch_prompt_logs", False, False],
        "widgets_values_named": {
            "folder_path": "input/Picture", "current_number": 0, "control_after_generate": "increment",
            "recursive": True, "reverse_order": True, "file_pattern": "*.txt", "output_folder": "output/",
            "enable_logging": False, "log_folder": "user/default/batch_prompt_logs",
            "clear_log_on_start": False, "skip_exists": False},
    }

SEEDVR2_PROPS = {"cnr_id": "seedvr2_videoupscaler",
                 "ver": "912ab4a5da8bb3590c4659f8f19160a7bd88a656",
                 "ue_properties": {"widget_ue_connectable": {}, "input_ue_unconnectable": {}, "version": "7.5.1"}}

def make_seedvr_vae():
    return {
        "id": 477, "type": "SeedVR2LoadVAEModel",
        "pos": [1900, 350], "size": [302.65625, 422], "flags": {}, "order": 14, "mode": 4,
        "inputs": [
            {"localized_name": "torch_compile_args", "name": "torch_compile_args", "shape": 7,
             "type": "TORCH_COMPILE_ARGS", "link": None},
            {"localized_name": "model", "name": "model", "type": "COMBO", "widget": {"name": "model"}, "link": None},
            {"localized_name": "device", "name": "device", "type": "COMBO", "widget": {"name": "device"}, "link": None},
            {"localized_name": "encode_tiled", "name": "encode_tiled", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "encode_tiled"}, "link": None},
            {"localized_name": "encode_tile_size", "name": "encode_tile_size", "shape": 7, "type": "INT",
             "widget": {"name": "encode_tile_size"}, "link": None},
            {"localized_name": "encode_tile_overlap", "name": "encode_tile_overlap", "shape": 7, "type": "INT",
             "widget": {"name": "encode_tile_overlap"}, "link": None},
            {"localized_name": "decode_tiled", "name": "decode_tiled", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "decode_tiled"}, "link": None},
            {"localized_name": "decode_tile_size", "name": "decode_tile_size", "shape": 7, "type": "INT",
             "widget": {"name": "decode_tile_size"}, "link": None},
            {"localized_name": "decode_tile_overlap", "name": "decode_tile_overlap", "shape": 7, "type": "INT",
             "widget": {"name": "decode_tile_overlap"}, "link": None},
            {"localized_name": "tile_debug", "name": "tile_debug", "shape": 7, "type": "COMBO",
             "widget": {"name": "tile_debug"}, "link": None},
            {"localized_name": "offload_device", "name": "offload_device", "shape": 7, "type": "COMBO",
             "widget": {"name": "offload_device"}, "link": None},
            {"localized_name": "cache_model", "name": "cache_model", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "cache_model"}, "link": None},
        ],
        "outputs": [{"localized_name": "SEEDVR2_VAE", "name": "SEEDVR2_VAE", "type": "SEEDVR2_VAE", "links": [692]}],
        "properties": dict(SEEDVR2_PROPS, **{"Node name for S&R": "SeedVR2LoadVAEModel"}),
        "widgets_values": ["ema_vae_fp16.safetensors", "cuda:0", True, 1024, 512, True, 1024, 512,
                           "false", "cpu", True],
        "widgets_values_named": {
            "model": "ema_vae_fp16.safetensors", "device": "cuda:0", "encode_tiled": True,
            "encode_tile_size": 1024, "encode_tile_overlap": 512, "decode_tiled": True,
            "decode_tile_size": 1024, "decode_tile_overlap": 512, "tile_debug": "false",
            "offload_device": "cpu", "cache_model": True},
        "color": "#432", "bgcolor": "#653",
    }

def make_seedvr_dit():
    return {
        "id": 478, "type": "SeedVR2LoadDiTModel",
        "pos": [1900, 800], "size": [304.125, 298], "flags": {}, "order": 15, "mode": 4,
        "inputs": [
            {"localized_name": "torch_compile_args", "name": "torch_compile_args", "shape": 7,
             "type": "TORCH_COMPILE_ARGS", "link": None},
            {"localized_name": "model", "name": "model", "type": "COMBO", "widget": {"name": "model"}, "link": None},
            {"localized_name": "device", "name": "device", "type": "COMBO", "widget": {"name": "device"}, "link": None},
            {"localized_name": "blocks_to_swap", "name": "blocks_to_swap", "shape": 7, "type": "INT",
             "widget": {"name": "blocks_to_swap"}, "link": None},
            {"localized_name": "swap_io_components", "name": "swap_io_components", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "swap_io_components"}, "link": None},
            {"localized_name": "offload_device", "name": "offload_device", "shape": 7, "type": "COMBO",
             "widget": {"name": "offload_device"}, "link": None},
            {"localized_name": "cache_model", "name": "cache_model", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "cache_model"}, "link": None},
            {"localized_name": "attention_mode", "name": "attention_mode", "shape": 7, "type": "COMBO",
             "widget": {"name": "attention_mode"}, "link": None},
        ],
        "outputs": [{"localized_name": "SEEDVR2_DIT", "name": "SEEDVR2_DIT", "type": "SEEDVR2_DIT", "links": [693]}],
        "properties": dict(SEEDVR2_PROPS, **{"Node name for S&R": "SeedVR2LoadDiTModel"}),
        "widgets_values": ["seedvr2_ema_3b_fp16.safetensors", "cuda:0", 8, True, "cpu", True, "sdpa"],
        "widgets_values_named": {
            "model": "seedvr2_ema_3b_fp16.safetensors", "device": "cuda:0", "blocks_to_swap": 8,
            "swap_io_components": True, "offload_device": "cpu", "cache_model": True, "attention_mode": "sdpa"},
        "color": "#432", "bgcolor": "#653",
    }

def make_seedvr_upscaler():
    return {
        "id": 479, "type": "SeedVR2VideoUpscaler",
        "pos": [2250, 400], "size": [333.40625, 604.71875], "flags": {}, "order": 16, "mode": 4,
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "IMAGE", "link": 691},
            {"localized_name": "dit", "name": "dit", "type": "SEEDVR2_DIT", "link": 693},
            {"localized_name": "vae", "name": "vae", "type": "SEEDVR2_VAE", "link": 692},
            {"localized_name": "seed", "name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": None},
            {"localized_name": "resolution", "name": "resolution", "type": "INT", "widget": {"name": "resolution"}, "link": None},
            {"localized_name": "max_resolution", "name": "max_resolution", "type": "INT", "widget": {"name": "max_resolution"}, "link": None},
            {"localized_name": "batch_size", "name": "batch_size", "type": "INT", "widget": {"name": "batch_size"}, "link": None},
            {"localized_name": "uniform_batch_size", "name": "uniform_batch_size", "type": "BOOLEAN",
             "widget": {"name": "uniform_batch_size"}, "link": None},
            {"localized_name": "color_correction", "name": "color_correction", "type": "COMBO",
             "widget": {"name": "color_correction"}, "link": None},
            {"localized_name": "temporal_overlap", "name": "temporal_overlap", "shape": 7, "type": "INT",
             "widget": {"name": "temporal_overlap"}, "link": None},
            {"localized_name": "prepend_frames", "name": "prepend_frames", "shape": 7, "type": "INT",
             "widget": {"name": "prepend_frames"}, "link": None},
            {"localized_name": "input_noise_scale", "name": "input_noise_scale", "shape": 7, "type": "FLOAT",
             "widget": {"name": "input_noise_scale"}, "link": None},
            {"localized_name": "latent_noise_scale", "name": "latent_noise_scale", "shape": 7, "type": "FLOAT",
             "widget": {"name": "latent_noise_scale"}, "link": None},
            {"localized_name": "offload_device", "name": "offload_device", "shape": 7, "type": "COMBO",
             "widget": {"name": "offload_device"}, "link": None},
            {"localized_name": "enable_debug", "name": "enable_debug", "shape": 7, "type": "BOOLEAN",
             "widget": {"name": "enable_debug"}, "link": None},
        ],
        "outputs": [{"localized_name": "图像", "name": "IMAGE", "type": "IMAGE", "links": [694]}],
        "properties": dict(SEEDVR2_PROPS, **{"Node name for S&R": "SeedVR2VideoUpscaler"}),
        "widgets_values": [2602636128, "randomize", 2048, 0, 1, False, "lab", 0, 0, 0, 0, "cpu", False],
        "widgets_values_named": {
            "seed": 2602636128, "control_after_generate": "randomize", "resolution": 2048,
            "max_resolution": 0, "batch_size": 1, "uniform_batch_size": False, "color_correction": "lab",
            "temporal_overlap": 0, "prepend_frames": 0, "input_noise_scale": 0, "latent_noise_scale": 0,
            "offload_device": "cpu", "enable_debug": False},
        "color": "#432", "bgcolor": "#653",
    }

def make_rvs():
    return {
        "id": 480, "type": "ReservedVRAMSetter",
        "pos": [2250, 1060], "size": [285.78125, 278], "flags": {}, "order": 17, "mode": 0,
        "inputs": [
            {"localized_name": "anything", "name": "anything", "shape": 7, "type": "*", "link": 689},
            {"localized_name": "reserved", "name": "reserved", "type": "FLOAT", "widget": {"name": "reserved"}, "link": None},
            {"localized_name": "mode", "name": "mode", "type": "COMBO", "widget": {"name": "mode"}, "link": None},
            {"localized_name": "seed", "name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": None},
            {"localized_name": "auto_max_reserved", "name": "auto_max_reserved", "type": "FLOAT",
             "widget": {"name": "auto_max_reserved"}, "link": None},
            {"localized_name": "clean_gpu_before", "name": "clean_gpu_before", "type": "BOOLEAN",
             "widget": {"name": "clean_gpu_before"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "output", "name": "output", "type": "*", "links": [690]},
            {"localized_name": "SEED", "name": "SEED", "type": "INT", "links": None},
            {"localized_name": "Reserved(GB)", "name": "Reserved(GB)", "type": "FLOAT", "links": None},
        ],
        "properties": {"cnr_id": "reservedvram", "ver": "1e5757db878ef05ac4ac8f169ddfdbeb4b53dfaa",
                       "Node name for S&R": "ReservedVRAMSetter"},
        "widgets_values": [0.6, "auto", 400260848591703, "randomize", 0, False],
        "widgets_values_named": {
            "reserved": 0.6, "mode": "auto", "seed": 400260848591703,
            "control_after_generate": "randomize", "auto_max_reserved": 0, "clean_gpu_before": False},
        "color": "#223", "bgcolor": "#335",
    }


def fuse_21():
    fn = 'Qwen_image_2_1_t2i.json'
    print('== 融合 2.1 ==')
    backup(fn, '.pre_fusion.bak')
    data, indent, sep = read(fn)
    sg = data['definitions']['subgraphs'][0]
    nodes = sg['nodes']
    links = sg['links']

    # 1) 改造 675：451→458 改为 451→470（接入 LoRA 链）
    l675 = next(l for l in links if l['id'] == 675)
    l675['target_id'] = 470
    l675['target_slot'] = 0

    # 2) 追加新链接；删除被替代的 650（VAEDecode 直连 -20，改走 RVS/SeedVR2 链）
    links.extend(NEW_LINKS)
    links[:] = [l for l in links if l['id'] != 650]

    # 3) 调整既有节点连接
    n458 = next(n for n in nodes if n['id'] == 458)
    n458['inputs'][0]['link'] = 687                       # KSampler.model ← L6
    n453 = next(n for n in nodes if n['id'] == 453)
    n453['outputs'][0]['links'] = [647, 688]              # CLIP → TextEncode + BatchPrompt
    n457 = next(n for n in nodes if n['id'] == 457)
    n457['outputs'][0]['links'] = [689, 691]              # VAEDecode → RVS + SeedVR2

    # 4) 新节点
    lora_ys = [1200, 1324, 1448, 1572, 1696, 1820]
    chain = [None, 675, 682, 683, 684, 685, 686]          # 470 的输入=675(改造后)
    new_nodes = []
    for i, nid in enumerate(range(470, 476)):
        out_link = 682 + i
        new_nodes.append(make_lora(nid, 990, lora_ys[i], 7 + i, chain[i + 1], out_link))
    new_nodes.append(make_batch_prompt())
    new_nodes.append(make_seedvr_vae())
    new_nodes.append(make_seedvr_dit())
    new_nodes.append(make_seedvr_upscaler())
    new_nodes.append(make_rvs())
    nodes.extend(new_nodes)

    # 5) 子图 outputs：0=原图(RVS)，1=超分(SeedVR2)
    sg['outputs'][0]['linkIds'] = [690]
    sg['outputs'][0]['pos'] = [2650, 560]
    sg['outputs'].append({
        "id": str(uuid.uuid4()), "name": "IMAGE", "type": "IMAGE",
        "linkIds": [694], "localized_name": "IMAGE", "pos": [2650, 640]})

    # 6) groups
    sg['groups'] = sg.get('groups', []) + [
        {"id": 38, "title": "LoRA 插槽", "bounding": [940, 1150, 400, 830], "color": "#3f789e", "flags": {}},
        {"id": 39, "title": "批量提示词", "bounding": [250, 1130, 410, 530], "color": "#3f789e", "flags": {}},
        {"id": 40, "title": "放大 (SeedVR2)", "bounding": [1850, 300, 790, 850], "color": "#3f789e", "flags": {}},
        {"id": 41, "title": "显存控制", "bounding": [2200, 1000, 390, 380], "color": "#3f789e", "flags": {}},
    ]

    # 7) state
    sg['state']['lastNodeId'] = 480
    sg['state']['lastLinkId'] = 694
    sg['state']['lastGroupId'] = 41
    data['last_node_id'] = 480
    data['last_link_id'] = 694

    # 8) 顶层主节点：第二个 IMAGE 输出；尺寸拉高
    main = next(n for n in data['nodes'] if n['id'] == 459)
    main['outputs'].append({'localized_name': '图像', 'name': 'IMAGE', 'type': 'IMAGE', 'links': []})
    main['size'] = [main['size'][0], main['size'][1] + 60]

    write(fn, data, indent, sep)
    print('  已写入', fn)


def mute_custom(fn):
    print('== 静止超分:', fn, '==')
    backup(fn, '.step3.bak')
    data, indent, sep = read(fn)
    sg = data['definitions']['subgraphs'][0]

    # 1) SeedVR2 相关节点 mode=4
    for n in sg['nodes']:
        if 'SeedVR2' in n.get('type', ''):
            n['mode'] = 4

    # 2) 顶层 SaveImageAdvanced 改连主节点输出1（原图）
    for l in data['links']:
        if len(l) >= 6 and l[5] == 'IMAGE':
            dst = [n for n in data['nodes'] if n['id'] == l[3]]
            if dst and dst[0].get('type') == 'SaveImageAdvanced':
                link_id, src_id = l[0], l[1]
                l[2] = 1
                main = next(n for n in data['nodes'] if n['id'] == src_id)
                for o in main.get('outputs', []):
                    if o.get('links'):
                        o['links'] = []
                img_outs = [o for o in main.get('outputs', []) if o.get('type') == 'IMAGE']
                if len(img_outs) >= 2:
                    img_outs[1]['links'] = [link_id]
                else:
                    main['outputs'][1]['links'] = [link_id]
                print('  保存节点 %s 改连主节点输出1(原图)，链接 %s' % (dst[0]['id'], link_id))
                break

    write(fn, data, indent, sep)
    print('  已写入', fn)


if __name__ == '__main__':
    fuse_21()
    for f in CUSTOM:
        mute_custom(f)
    print('全部完成')
