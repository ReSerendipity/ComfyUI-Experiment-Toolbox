# -*- coding: utf-8 -*-
"""diff 当前工作流 vs 官方模板，列出所有差异，并支持批量导出对照快照。

v2（2026-10-11，评估报告 P2-5）：
  - 覆盖 Edit 3 份 + Image 8 份（来源模板映射同 gen_workflows_manifest.py 的 SOURCE_MAP）
  - 新增 --export-dir：为每份工作流生成 `08_官方模板对齐/<工作流名>.diff.md` 快照
  - 路径常量统一 os.path.expandvars；逻辑包进 main()（import 无副作用）

用法：
  python diff_edit.py                          # 控制台复查（原行为，全部 11 对）
  python diff_edit.py --export-dir ../08_官方模板对齐   # 批量导出快照
  python diff_edit.py --templates <目录> --edit <目录> --image <目录>  # 覆盖默认路径
"""
import argparse
import datetime
import json
import os

T = os.path.expandvars(
    r"%USERPROFILE%\APP\ComfyUI-aki-v3\python\Lib\site-packages\comfyui_workflow_templates_json\templates")
E = os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Edit")
I = os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image")

PAIRS = [
    # (官方模板, 当前工作流, 类别)
    ('image_qwen_image_2_1_image_edit.json', 'qwen_2_1_edit.json', 'Edit'),
    ('image_qwen_image_edit_2511.json', 'qwen_edit_2511.json', 'Edit'),
    ('image_flux2_klein_image_edit_9b_distilled.json', 'flux2_klein_edit.json', 'Edit'),
    ('image_qwen_image_2_1_t2i.json', 'Qwen_image_2_1_t2i.json', 'Image'),
    ('image_krea2_turbo_t2i.json', 'krea2_turbo.json', 'Image'),
    ('image_flux2_klein_text_to_image.json', 'Flux.2_Klein-9B-Distilled.json', 'Image'),
    ('image_qwen_Image_2512.json', 'Qwen_image_2512.json', 'Image'),
    ('image_qwen_image.json', 'Qwen_image.json', 'Image'),
    ('image_z_image.json', 'Z_image.json', 'Image'),
    ('image_z_image_turbo.json', 'Z_image_turbo.json', 'Image'),
    ('flux_dev_full_text_to_image.json', 'flux.1-dev.json', 'Image'),
]


def _subgraphs(wf):
    return (wf.get('definitions') or {}).get('subgraphs', [])


def diff_pair(off, cur, tdir, cdir):
    """返回 (顶层差异字符串, 子图差异行列表)。"""
    a = json.load(open(os.path.join(tdir, off), encoding='utf-8'))
    b = json.load(open(os.path.join(cdir, cur), encoding='utf-8'))
    a_types = {n.get('type') for n in a.get('nodes', [])}
    b_types = {n.get('type') for n in b.get('nodes', [])}
    top = '顶层类型 删=%s 加=%s' % (sorted(a_types - b_types), sorted(b_types - a_types))
    lines = []
    subs = zip(_subgraphs(a), _subgraphs(b))
    for sgi, (sa, sb) in enumerate(subs):
        a_sub = {n['id']: n for n in sa.get('nodes', [])}
        b_sub = {n['id']: n for n in sb.get('nodes', [])}
        for nid in sorted(set(a_sub) | set(b_sub)):
            na = a_sub.get(nid)
            nb = b_sub.get(nid)
            if na is None:
                lines.append('- 子图%d 新增节点 id=%s type=%s' % (sgi, nid, nb.get('type')))
            elif nb is None:
                lines.append('- 子图%d 删除节点 id=%s type=%s' % (sgi, nid, na.get('type')))
            else:
                wa = na.get('widgets_values')
                wb = nb.get('widgets_values')
                if wa != wb:
                    lines.append('- 子图%d id=%s type=%s widgets变:' % (sgi, nid, na.get('type')))
                    lines.append('  - 官方: %s' % str(wa)[:120])
                    lines.append('  - 当前: %s' % str(wb)[:120])
    return top, lines


def build_report(off, cur, tdir, cdir, top, lines):
    out = ['# 官方模板对齐快照：%s' % cur, '',
           '- 生成：%s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           '- 官方模板：%s' % off,
           '- 当前工作流：%s' % cur, '',
           '## 概览', '', '`%s`' % top, '',
           '## 子图差异', '']
    out += lines if lines else ['（无节点增删，widgets 无变化）']
    out += ['']
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='diff 当前工作流 vs 官方模板（可批量导出快照）')
    ap.add_argument('--templates', default=T, help='官方模板目录')
    ap.add_argument('--edit', default=E, help='Edit 工作流目录')
    ap.add_argument('--image', default=I, help='Image 工作流目录')
    ap.add_argument('--export-dir', default=None, help='导出目录（每份工作流生成 <cur>.diff.md）')
    args = ap.parse_args()

    export_dir = args.export_dir
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
    exported = 0
    for off, cur, cat in PAIRS:
        print('====', cur, 'vs', off, '====')
        cdir = args.edit if cat == 'Edit' else args.image
        tp = os.path.join(args.templates, off)
        cp = os.path.join(cdir, cur)
        if not os.path.exists(tp):
            print('[警告] 模板缺失，跳过：', tp)
            continue
        if not os.path.exists(cp):
            print('[警告] 工作流缺失，跳过：', cp)
            continue
        try:
            top, lines = diff_pair(off, cur, args.templates, cdir)
        except Exception as e:
            print('[警告] 对比失败，跳过：', e)
            continue
        print('  ' + top)
        for ln in lines:
            print('  ' + ln)
        if export_dir:
            with open(os.path.join(export_dir, cur + '.diff.md'), 'w', encoding='utf-8') as f:
                f.write(build_report(off, cur, args.templates, cdir, top, lines))
            exported += 1
        print()
    if export_dir:
        print('已导出 %d 份对照快照 -> %s' % (exported, export_dir))


if __name__ == '__main__':
    main()
