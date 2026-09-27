# -*- coding: utf-8 -*-
"""Flux.2 子图1 加 6 张参考图 (image_2 ~ image_7), 凑满 8 张"""
import json, os, uuid, copy

E = r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit'
p = os.path.join(E, 'flux2_klein_edit.json')
raw = open(p, encoding='utf-8').read()
indent = 2 if '\n  ' in raw else None
sep = (', ', ': ') if '", "' in raw else (',', ':')
d = json.loads(raw)

sg = d['definitions']['subgraphs'][1]
main92 = next(n for n in d['nodes'] if n['id']==92)

# 当前最大 id 和 link
max_nid = max(n['id'] for n in sg['nodes'])
max_lid = max(l['id'] for l in sg['links'])
print('子图1 当前最大 node id=%d, link id=%d' % (max_nid, max_lid))

# VAELoader id=110 (vae 输出)
vae_loader_id = 110
# 当前 conditioning 链尾: pos=131.0 -> 103.1(link 211), neg=129.0 -> 103.2(link 212)
# 改: 131.0 -> 新图3 pos.conditioning, 129.0 -> 新图3 neg.conditioning
# 最后一张图 pos.0 -> 103.1, neg.0 -> 103.2

# 6 张图配置: image_2 ~ image_7
NEW_IMGS = 6
new_nid = max_nid  # 200 起
new_lid = max_lid  # 221 起

# 模板节点结构（从现有复制再改 id/pos/links）
def make_img_scale(nid, link_in, x, y):
    return {
        "id": nid, "type": "ImageScaleToTotalPixels",
        "pos": [x, y], "size": [270, 140],
        "flags": {}, "order": nid, "mode": 0,
        "inputs": [
            {"localized_name":"图像","name":"image","type":"IMAGE","link":link_in},
            {"localized_name":"缩放算法","name":"upscale_method","type":"COMBO","widget":{"name":"upscale_method"},"link":None},
            {"localized_name":"像素数量","name":"megapixels","type":"FLOAT","widget":{"name":"megapixels"},"link":None},
            {"localized_name":"分辨率步数","name":"resolution_steps","type":"INT","widget":{"name":"resolution_steps"},"link":None}
        ],
        "outputs": [{"localized_name":"图像","name":"IMAGE","type":"IMAGE","links":[]}],
        "properties": {"cnr_id":"comfy-core","ver":"0.8.2","Node name for S&R":"ImageScaleToTotalPixels","enableTabs":False,"tabWidth":65,"tabXOffset":10,"hasSecondTab":False,"secondTabText":"Send Back","secondTabOffset":80,"secondTabWidth":65,"ue_properties":{"widget_ue_connectable":{},"version":"7.7","input_ue_unconnectable":{}}},
        "widgets_values": ["lanczos", 1, 1],
        "widgets_values_named": {"upscale_method":"lanczos","megapixels":1,"resolution_steps":1}
    }

def make_vae_encode(nid, px_link, vae_link, x, y):
    return {
        "id": nid, "type": "VAEEncode",
        "pos": [x, y], "size": [230, 100],
        "flags": {"collapsed": False}, "order": nid, "mode": 0,
        "inputs": [
            {"localized_name":"像素","name":"pixels","type":"IMAGE","link":px_link},
            {"localized_name":"vae","name":"vae","type":"VAE","link":vae_link}
        ],
        "outputs": [{"localized_name":"Latent","name":"LATENT","type":"LATENT","links":[]}],
        "properties": {"cnr_id":"comfy-core","ver":"0.8.2","Node name for S&R":"VAEEncode","enableTabs":False,"tabWidth":65,"tabXOffset":10,"hasSecondTab":False,"secondTabText":"Send Back","secondTabOffset":80,"secondTabWidth":65,"ue_properties":{"widget_ue_connectable":{},"version":"7.7","input_ue_unconnectable":{}}}
    }

def make_ref_latent(nid, cond_link, latent_link, x, y):
    return {
        "id": nid, "type": "ReferenceLatent",
        "pos": [x, y], "size": [230, 100],
        "flags": {"collapsed": False}, "order": nid, "mode": 0,
        "inputs": [
            {"localized_name":"条件","name":"conditioning","type":"CONDITIONING","link":cond_link},
            {"localized_name":"Latent","name":"latent","shape":7,"type":"LATENT","link":latent_link}
        ],
        "outputs": [{"localized_name":"条件","name":"CONDITIONING","type":"CONDITIONING","links":[]}],
        "properties": {"cnr_id":"comfy-core","ver":"0.8.2","Node name for S&R":"ReferenceLatent","enableTabs":False,"tabWidth":65,"tabXOffset":10,"hasSecondTab":False,"secondTabText":"Send Back","secondTabOffset":80,"secondTabWidth":65,"ue_properties":{"widget_ue_connectable":{},"version":"7.7","input_ue_unconnectable":{}}}
    }

# 当前 conditioning 链尾
prev_pos_node = 131  # 它的输出 -> CFGGuider.positive
prev_neg_node = 129  # 它的输出 -> CFGGuider.negative

# 先把 CFGGuider(103) 的 positive/negative 输入暂存
cfg = next(n for n in sg['nodes'] if n['id']==103)
old_pos_link = cfg['inputs'][1]['link']  # 211
old_neg_link = cfg['inputs'][2]['link']  # 212
print('当前 CFGGuider pos link=%s, neg link=%s' % (old_pos_link, old_neg_link))

# 逐张图加
for k in range(NEW_IMGS):
    img_idx = k + 2  # image_2, image_3, ...
    new_nid += 1; scale_id = new_nid
    new_nid += 1; ve_id = new_nid
    new_nid += 1; rl_pos_id = new_nid
    new_nid += 1; rl_neg_id = new_nid

    y = 1020 + (k+1)*180  # 竖向排

    # 1. 新子图接口 image_{k+2}
    iface_name = 'image_%d' % (k+1) if k>0 else 'image_2'
    iface_name = 'image_%d' % (k+1)  # image_2..image_7
    iface_label = 'reference_image%d' % (k+3)
    # -10 输入桩 link: origin_id=-10, origin_slot=新接口在 inputs 数组的位置
    new_lid += 1; link_branch = new_lid  # 子图接口 -> ImageScaleToPixels.image
    new_lid += 1; link_px2vae = new_lid  # ImageScale -> VAEEncode.pixels
    new_lid += 1; link_vae2ve = new_lid  # VAELoader -> VAEEncode.vae
    new_lid += 1; link_lat2pos = new_lid  # VAEEncode.latent -> pos ReferenceLatent.latent
    new_lid += 1; link_lat2neg = new_lid  # VAEEncode.latent -> neg ReferenceLatent.latent
    new_lid += 1; link_pos_cond = new_lid  # 前一张 pos.0 -> 新 pos.conditioning
    new_lid += 1; link_neg_cond = new_lid  # 前一张 neg.0 -> 新 neg.conditioning

    # 子图接口 slot：当前 inputs 数组长度
    new_slot = len(sg['inputs'])  # 新接口在末尾
    new_iface = {
        "id": str(uuid.uuid4()),
        "name": iface_name,
        "type": "IMAGE",
        "linkIds": [link_branch],
        "label": iface_label,
        "pos": [-607, 720 + k*20]
    }
    sg['inputs'].append(new_iface)

    # 子图内部 -10 -> ImageScaleToPixels.image
    sg['links'].append({'id':link_branch, 'origin_id':-10, 'origin_slot':new_slot, 'target_id':scale_id, 'target_slot':0, 'type':'IMAGE'})
    # ImageScale -> VAEEncode.pixels
    sg['links'].append({'id':link_px2vae, 'origin_id':scale_id, 'origin_slot':0, 'target_id':ve_id, 'target_slot':0, 'type':'IMAGE'})
    # VAELoader -> VAEEncode.vae
    sg['links'].append({'id':link_vae2ve, 'origin_id':vae_loader_id, 'origin_slot':0, 'target_id':ve_id, 'target_slot':1, 'type':'VAE'})
    # VAEEncode.latent -> pos RefLatent.latent
    sg['links'].append({'id':link_lat2pos, 'origin_id':ve_id, 'origin_slot':0, 'target_id':rl_pos_id, 'target_slot':1, 'type':'LATENT'})
    # VAEEncode.latent -> neg RefLatent.latent
    sg['links'].append({'id':link_lat2neg, 'origin_id':ve_id, 'origin_slot':0, 'target_id':rl_neg_id, 'target_slot':1, 'type':'LATENT'})
    # 前一张 pos.0 -> 新 pos.conditioning
    sg['links'].append({'id':link_pos_cond, 'origin_id':prev_pos_node, 'origin_slot':0, 'target_id':rl_pos_id, 'target_slot':0, 'type':'CONDITIONING'})
    # 前一张 neg.0 -> 新 neg.conditioning
    sg['links'].append({'id':link_neg_cond, 'origin_id':prev_neg_node, 'origin_slot':0, 'target_id':rl_neg_id, 'target_slot':0, 'type':'CONDITIONING'})

    # 新节点
    sg['nodes'].append(make_img_scale(scale_id, link_branch, -450, y))
    sg['nodes'].append(make_vae_encode(ve_id, link_px2vae, link_vae2ve, -130, y))
    sg['nodes'].append(make_ref_latent(rl_pos_id, link_pos_cond, link_lat2pos, 190, y))
    sg['nodes'].append(make_ref_latent(rl_neg_id, link_neg_cond, link_lat2neg, 190, y+120))

    # 更新前一张输出 links 数组（把原来指向 CFGGuider 的 link 改成指向新节点）
    prev_pos_node_obj = next(n for n in sg['nodes'] if n['id']==prev_pos_node)
    # 实际上前一张输出 links 最后一个就是指向 CFGGuider 的，改成新 link
    # 找到它
    for ol in prev_pos_node_obj['outputs'][0]['links']:
        if ol == old_pos_link:
            prev_pos_node_obj['outputs'][0]['links'].remove(ol)
    prev_pos_node_obj['outputs'][0]['links'].append(link_pos_cond)

    prev_neg_node_obj = next(n for n in sg['nodes'] if n['id']==prev_neg_node)
    for ol in prev_neg_node_obj['outputs'][0]['links']:
        if ol == old_neg_link:
            prev_neg_node_obj['outputs'][0]['links'].remove(ol)
    prev_neg_node_obj['outputs'][0]['links'].append(link_neg_cond)

    # 更新 CFGGuider 的 pos/neg link：如果是最后一张，直接指向新节点
    if k == NEW_IMGS - 1:
        cfg['inputs'][1]['link'] = link_pos_cond
        cfg['inputs'][2]['link'] = link_neg_cond
        # 删除旧的 211/212 link
        sg['links'] = [l for l in sg['links'] if l['id'] not in (old_pos_link, old_neg_link)]
        print('  最后一张: pos=%d.0 -> CFGGuider.positive, neg=%d.0 -> CFGGuider.negative' % (rl_pos_id, rl_neg_id))
    else:
        old_pos_link = link_pos_cond
        old_neg_link = link_neg_cond
        prev_pos_node = rl_pos_id
        prev_neg_node = rl_neg_id
        print('  图%d: scale=%d ve=%d pos=%d neg=%d' % (img_idx, scale_id, ve_id, rl_pos_id, rl_neg_id))

# 顶层主节点 92 inputs 加 image_2~image_7
top_max_nid = max(n['id'] for n in d['nodes'])
top_max_lid = max(l[0] for l in d['links'])
print()
print('顶层最大 node id=%d, link id=%d' % (top_max_nid, top_max_lid))

# 顶层 LoadImage 位置
for k in range(NEW_IMGS):
    top_max_nid += 1
    top_max_lid += 1
    lid = top_max_lid
    nid = top_max_nid
    # 主节点 92 inputs 加
    main92['inputs'].append({
        "label": "reference_image%d" % (k+3),
        "name": "image_%d" % (k+1),
        "type": "IMAGE",
        "link": lid
    })
    # 新 LoadImage
    li = {
        "id": nid, "type": "LoadImage",
        "pos": [-700, 850 + k*130], "size": [290, 110],
        "flags": {}, "order": nid, "mode": 0,
        "inputs": [],
        "outputs": [
            {"name":"IMAGE","type":"IMAGE","links":[lid]},
            {"name":"MASK","type":"MASK","links":None}
        ],
        "properties": {"Node name for S&R":"LoadImage"},
        "widgets_values": ["example.png", "image"]
    }
    d['nodes'].append(li)
    # 顶层 link: LoadImage -> 主节点 92 新 slot
    new_slot_top = len(main92['inputs']) - 1
    d['links'].append([lid, nid, 0, 92, new_slot_top, 'IMAGE'])
    print('  顶层 LoadImage id=%d -> 主节点 92 slot=%d, link=%d' % (nid, new_slot_top, lid))

with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=indent, separators=sep)

# 验证
d2 = json.load(open(p, encoding='utf-8'))
lds = [n for n in d2['nodes'] if n['type']=='LoadImage']
print()
print('Flux.2 顶层 LoadImage 数量: %d' % len(lds))
print('完成')
