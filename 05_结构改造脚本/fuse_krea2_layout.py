# -*- coding: utf-8 -*-
"""
第四轮改造：
A. krea2_turbo.json（K2）融合：5 个 LoRA 插槽(补成 6 个)、BatchPromptReaderWithClip、
   SeedVR2 超分(静止)、ReservedVRAMSetter 显存控制、SaveImage→SaveImageAdvanced、删 3 个注释
B. 2.1 删 2 个 MarkdownNote 注释
C. 8 个工作流顶层布局统一：主节点 (0,0)、RS (-380,310)、Save (330,-10)、尺寸统一
"""
import json, os, uuid, shutil

D = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image'

MAIN_POS = [0, 0]
RS_POS = [-380, 310]
SAVE_POS = [330, -10]
RS_SIZE = [300, 190]
SAVE_SIZE = [850, 610]

CUSTOM = ['Flux.2_Klein-9B-Distilled.json', 'Qwen_image.json', 'Qwen_image_2512.json',
          'Z_image.json', 'Z_image_turbo.json', 'flux.1-dev.json']

def read(fn):
    p = os.path.join(D, fn)
    with open(p, encoding='utf-8') as f:
        raw = f.read()
    indent = 2 if '\n  ' in raw else None
    sep = (', ', ': ') if '", "' in raw else (',', ':')
    return json.loads(raw), indent, sep

def write(fn, data, indent, sep):
    with open(os.path.join(D, fn), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, separators=sep)

def backup(fn, suffix):
    src = os.path.join(D, fn)
    dst = os.path.join(D, fn.replace('.json', suffix))
    shutil.copy2(src, dst)
    print('  备份:', os.path.basename(dst))

LORA_PROPS = {"cnr_id": "comfy-core", "ver": "0.18.1",
              "Node name for S&R": "LoraLoaderModelOnly",
              "Node name for S&amp;R": "LoraLoaderModelOnly"}
SEEDVR2_PROPS = {"cnr_id": "seedvr2_videoupscaler",
                 "ver": "912ab4a5da8bb3590c4659f8f19160a7bd88a656",
                 "ue_properties": {"widget_ue_connectable": {}, "input_ue_unconnectable": {}, "version": "7.5.1"}}

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

def make_batch_prompt(nid, x, y, order, clip_link):
    return {
        "id": nid, "type": "BatchPromptReaderWithClip",
        "pos": [x, y], "size": [305.75, 430], "flags": {}, "order": order, "mode": 0,
        "inputs": [
            {"localized_name": "clip", "name": "clip", "type": "CLIP", "link": clip_link},
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

def make_seedvr_vae(nid, x, y, order, out_link):
    return {
        "id": nid, "type": "SeedVR2LoadVAEModel",
        "pos": [x, y], "size": [302.65625, 422], "flags": {}, "order": order, "mode": 4,
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
        "outputs": [{"localized_name": "SEEDVR2_VAE", "name": "SEEDVR2_VAE", "type": "SEEDVR2_VAE", "links": [out_link]}],
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

def make_seedvr_dit(nid, x, y, order, out_link):
    return {
        "id": nid, "type": "SeedVR2LoadDiTModel",
        "pos": [x, y], "size": [304.125, 298], "flags": {}, "order": order, "mode": 4,
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
        "outputs": [{"localized_name": "SEEDVR2_DIT", "name": "SEEDVR2_DIT", "type": "SEEDVR2_DIT", "links": [out_link]}],
        "properties": dict(SEEDVR2_PROPS, **{"Node name for S&R": "SeedVR2LoadDiTModel"}),
        "widgets_values": ["seedvr2_ema_3b_fp16.safetensors", "cuda:0", 8, True, "cpu", True, "sdpa"],
        "widgets_values_named": {
            "model": "seedvr2_ema_3b_fp16.safetensors", "device": "cuda:0", "blocks_to_swap": 8,
            "swap_io_components": True, "offload_device": "cpu", "cache_model": True, "attention_mode": "sdpa"},
        "color": "#432", "bgcolor": "#653",
    }

def make_seedvr_upscaler(nid, x, y, order, img_link, dit_link, vae_link, out_link):
    return {
        "id": nid, "type": "SeedVR2VideoUpscaler",
        "pos": [x, y], "size": [333.40625, 604.71875], "flags": {}, "order": order, "mode": 4,
        "inputs": [
            {"localized_name": "image", "name": "image", "type": "IMAGE", "link": img_link},
            {"localized_name": "dit", "name": "dit", "type": "SEEDVR2_DIT", "link": dit_link},
            {"localized_name": "vae", "name": "vae", "type": "SEEDVR2_VAE", "link": vae_link},
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
        "outputs": [{"localized_name": "图像", "name": "IMAGE", "type": "IMAGE", "links": [out_link]}],
        "properties": dict(SEEDVR2_PROPS, **{"Node name for S&R": "SeedVR2VideoUpscaler"}),
        "widgets_values": [2602636128, "randomize", 2048, 0, 1, False, "lab", 0, 0, 0, 0, "cpu", False],
        "widgets_values_named": {
            "seed": 2602636128, "control_after_generate": "randomize", "resolution": 2048,
            "max_resolution": 0, "batch_size": 1, "uniform_batch_size": False, "color_correction": "lab",
            "temporal_overlap": 0, "prepend_frames": 0, "input_noise_scale": 0, "latent_noise_scale": 0,
            "offload_device": "cpu", "enable_debug": False},
        "color": "#432", "bgcolor": "#653",
    }

def make_rvs(nid, x, y, order, in_link, out_link):
    return {
        "id": nid, "type": "ReservedVRAMSetter",
        "pos": [x, y], "size": [285.78125, 278], "flags": {}, "order": order, "mode": 0,
        "inputs": [
            {"localized_name": "anything", "name": "anything", "shape": 7, "type": "*", "link": in_link},
            {"localized_name": "reserved", "name": "reserved", "type": "FLOAT", "widget": {"name": "reserved"}, "link": None},
            {"localized_name": "mode", "name": "mode", "type": "COMBO", "widget": {"name": "mode"}, "link": None},
            {"localized_name": "seed", "name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": None},
            {"localized_name": "auto_max_reserved", "name": "auto_max_reserved", "type": "FLOAT",
             "widget": {"name": "auto_max_reserved"}, "link": None},
            {"localized_name": "clean_gpu_before", "name": "clean_gpu_before", "type": "BOOLEAN",
             "widget": {"name": "clean_gpu_before"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "output", "name": "output", "type": "*", "links": [out_link]},
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


def fuse_krea2():
    fn = 'krea2_turbo.json'
    print('== 融合 K2 ==')
    backup(fn, '.pre_fusion.bak')
    data, indent, sep = read(fn)
    sg = data['definitions']['subgraphs'][0]
    nodes = sg['nodes']
    links = sg['links']

    # 改造：29 (15→22 slot1) → 15→51；43 (8→-20 slot0) → 8→60
    l29 = next(l for l in links if l['id'] == 29)
    l29['target_id'] = 51
    l29['target_slot'] = 0
    l43 = next(l for l in links if l['id'] == 43)
    l43['target_id'] = 60
    l43['target_slot'] = 0

    new_links = [
        {'id': 87, 'origin_id': 51, 'origin_slot': 0, 'target_id': 52, 'target_slot': 0, 'type': 'MODEL'},
        {'id': 88, 'origin_id': 52, 'origin_slot': 0, 'target_id': 53, 'target_slot': 0, 'type': 'MODEL'},
        {'id': 89, 'origin_id': 53, 'origin_slot': 0, 'target_id': 54, 'target_slot': 0, 'type': 'MODEL'},
        {'id': 90, 'origin_id': 54, 'origin_slot': 0, 'target_id': 55, 'target_slot': 0, 'type': 'MODEL'},
        {'id': 91, 'origin_id': 55, 'origin_slot': 0, 'target_id': 22, 'target_slot': 1, 'type': 'MODEL'},
        {'id': 92, 'origin_id': 11, 'origin_slot': 0, 'target_id': 56, 'target_slot': 0, 'type': 'CLIP'},
        {'id': 93, 'origin_id': 60, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'},
        {'id': 94, 'origin_id': 8, 'origin_slot': 0, 'target_id': 59, 'target_slot': 0, 'type': 'IMAGE'},
        {'id': 95, 'origin_id': 57, 'origin_slot': 0, 'target_id': 59, 'target_slot': 2, 'type': 'SEEDVR2_VAE'},
        {'id': 96, 'origin_id': 58, 'origin_slot': 0, 'target_id': 59, 'target_slot': 1, 'type': 'SEEDVR2_DIT'},
        {'id': 97, 'origin_id': 59, 'origin_slot': 0, 'target_id': -20, 'target_slot': 1, 'type': 'IMAGE'},
    ]
    links.extend(new_links)

    # 既有节点连接更新
    n22 = next(n for n in nodes if n['id'] == 22)
    n22['inputs'][1]['link'] = 91          # 开关 on_true ← L6
    n8 = next(n for n in nodes if n['id'] == 8)
    n8['outputs'][0]['links'] = [43, 94]   # VAEDecode → RVS + SeedVR2
    n11 = next(n for n in nodes if n['id'] == 11)
    n11['outputs'][0]['links'].append(92)  # CLIP → BatchPrompt

    # 新节点
    lora_ys = [130, 254, 378, 502, 626]
    chain_in = [29, 87, 88, 89, 90]
    chain_out = [87, 88, 89, 90, 91]
    new_nodes = []
    for i in range(5):
        nid = 51 + i
        new_nodes.append(make_lora(nid, 940, lora_ys[i], 20 + i, chain_in[i], chain_out[i]))
    new_nodes.append(make_batch_prompt(56, 450, 1220, 25, 92))
    new_nodes.append(make_seedvr_vae(57, 1240, -280, 26, 95))
    new_nodes.append(make_seedvr_dit(58, 1240, 170, 27, 96))
    new_nodes.append(make_seedvr_upscaler(59, 1570, -280, 28, 94, 96, 95, 97))
    new_nodes.append(make_rvs(60, 1570, 360, 29, 43, 93))
    nodes.extend(new_nodes)

    # 子图 outputs
    sg['outputs'][0]['linkIds'] = [93]
    sg['outputs'][0]['pos'] = [1950, 380]
    sg['outputs'].append({
        "id": str(uuid.uuid4()), "name": "IMAGE", "type": "IMAGE",
        "linkIds": [97], "localized_name": "IMAGE", "pos": [1950, 460]})

    # groups
    sg['groups'] = sg.get('groups', []) + [
        {"id": 10, "title": "LoRA 插槽", "bounding": [890, 80, 400, 710], "color": "#3f789e", "flags": {}},
        {"id": 11, "title": "批量提示词", "bounding": [400, 1170, 410, 530], "color": "#3f789e", "flags": {}},
        {"id": 12, "title": "放大 (SeedVR2)", "bounding": [1180, -330, 780, 850], "color": "#3f789e", "flags": {}},
        {"id": 13, "title": "显存控制", "bounding": [1520, 310, 390, 380], "color": "#3f789e", "flags": {}},
    ]

    # state
    sg['state']['lastNodeId'] = 60
    sg['state']['lastLinkId'] = 97
    sg['state']['lastGroupId'] = 13
    data['last_node_id'] = 60
    data['last_link_id'] = 97

    # 顶层：SaveImage → SaveImageAdvanced；主节点第二输出；删 MarkdownNote；布局统一
    data['nodes'] = [n for n in data['nodes'] if n.get('type') != 'MarkdownNote']
    save = next(n for n in data['nodes'] if n.get('type') == 'SaveImage')
    save.update({
        'type': 'SaveImageAdvanced', 'size': SAVE_SIZE, 'pos': SAVE_POS,
        'inputs': [
            {'localized_name': '图像', 'name': 'images', 'type': 'IMAGE', 'link': 44},
            {'localized_name': '文件名前缀', 'name': 'filename_prefix', 'type': 'STRING',
             'widget': {'name': 'filename_prefix'}, 'link': None},
            {'localized_name': '格式', 'name': 'format', 'type': 'COMFY_DYNAMICCOMBO_V3',
             'widget': {'name': 'format'}, 'link': None},
            {'localized_name': '位深度', 'name': 'format.bit_depth', 'type': 'COMBO',
             'widget': {'name': 'format.bit_depth'}, 'link': None},
            {'localized_name': '输入色彩空间', 'name': 'format.input_color_space', 'type': 'COMBO',
             'widget': {'name': 'format.input_color_space'}, 'link': None},
        ],
        'outputs': [{'localized_name': 'images', 'name': 'images', 'type': 'IMAGE', 'links': []}],
        'properties': {'cnr_id': 'comfy-core', 'ver': '0.36.0'},
        'widgets_values': ['Krea2_turbo', 'png', '8-bit', 'sRGB'],
        'widgets_values_named': {'filename_prefix': 'Krea2_turbo', 'format': 'png',
                                 'format.bit_depth': '8-bit', 'format.input_color_space': 'sRGB'},
    })
    main = next(n for n in data['nodes'] if n['id'] == 30)
    main['pos'] = MAIN_POS
    main['size'] = [248, 1010]
    main['outputs'].append({'localized_name': '图像', 'name': 'IMAGE', 'type': 'IMAGE', 'links': []})
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    rs['pos'] = RS_POS
    rs['size'] = RS_SIZE
    # order 重排：主、RS、Save
    for i, nid in enumerate([30, 49, save['id']]):
        next(n for n in data['nodes'] if n['id'] == nid)['order'] = i

    write(fn, data, indent, sep)
    print('  已写入', fn)


def layout_21():
    fn = 'Qwen_image_2_1_t2i.json'
    print('== 2.1 布局统一 + 删注释 ==')
    backup(fn, '.layout.bak')
    data, indent, sep = read(fn)
    data['nodes'] = [n for n in data['nodes'] if n.get('type') != 'MarkdownNote']
    main = next(n for n in data['nodes'] if n['id'] == 459)
    main['pos'] = MAIN_POS
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    rs['pos'] = RS_POS
    save = next(n for n in data['nodes'] if n.get('type') == 'SaveImageAdvanced')
    save['pos'] = SAVE_POS
    save['size'] = SAVE_SIZE
    for i, nid in enumerate([459, 13, save['id']]):
        next(n for n in data['nodes'] if n['id'] == nid)['order'] = i
    write(fn, data, indent, sep)
    print('  已写入', fn)


def layout_custom(fn, main_id):
    print('== 布局统一:', fn, '==')
    backup(fn, '.layout.bak')
    data, indent, sep = read(fn)
    main = next(n for n in data['nodes'] if n['id'] == main_id)
    main['pos'] = MAIN_POS
    main['size'] = [248, main['size'][1]]
    rs = next(n for n in data['nodes'] if n.get('type') == 'ResolutionSelector')
    rs['pos'] = RS_POS
    save = next(n for n in data['nodes'] if n.get('type') == 'SaveImageAdvanced')
    save['pos'] = SAVE_POS
    save['size'] = SAVE_SIZE
    write(fn, data, indent, sep)
    print('  已写入', fn)


if __name__ == '__main__':
    fuse_krea2()
    layout_21()
    mains = {'Flux.2_Klein-9B-Distilled.json': 64, 'Qwen_image.json': 65, 'Qwen_image_2512.json': 65,
             'Z_image.json': 60, 'Z_image_turbo.json': 82, 'flux.1-dev.json': 132}
    for f in CUSTOM:
        layout_custom(f, mains[f])
    print('全部完成')
