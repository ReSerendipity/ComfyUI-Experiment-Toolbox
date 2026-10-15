# -*- coding: utf-8 -*-
"""生成 11 份工作流的溯源清单（NEXT 评估报告 P2-4）。

对 ComfyUI 用户工作流目录（Image 8 份 + Edit 3 份）逐个计算
MD5 / 大小 / 修改时间 / 备份文件清单 / 来源官方模板（含模板 MD5），
输出本目录 workflows_manifest.json，供产物版本溯源与改造前后校验。

用法：
  python gen_workflows_manifest.py                     # 按 README 约定根目录（ComfyUI-aki-v3.2）
  python gen_workflows_manifest.py --root <绝对路径>    # 指定实际根目录（本机为 aki-v3.2）
  python gen_workflows_manifest.py --templates <绝对路径>  # 官方模板目录（默认按约定路径）

约束：只读外部原件，绝不写入 ComfyUI 目录；模板缺失时 source_md5=null 并打印警告，不硬失败。
"""
import argparse
import datetime
import hashlib
import json
import os

DEFAULT_ROOT = os.path.expandvars(
    r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI\user\default\workflows")
DEFAULT_TEMPLATES = os.path.expandvars(
    r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\python\Lib\site-packages\comfyui_workflow_templates_json\templates")

# 来源模板映射（官方模板名 -> 工作流名），Image 部分取自 06 文档§一 权威表，Edit 部分取自 05 README 四节
SOURCE_MAP = [
    ("Image", "image_qwen_image_2_1_t2i.json", "Qwen_image_2_1_t2i.json"),
    ("Image", "image_krea2_turbo_t2i.json", "krea2_turbo.json"),
    ("Image", "image_flux2_klein_text_to_image.json", "Flux.2_Klein-9B-Distilled.json"),
    ("Image", "image_qwen_Image_2512.json", "Qwen_image_2512.json"),
    ("Image", "image_qwen_image.json", "Qwen_image.json"),
    ("Image", "image_z_image.json", "Z_image.json"),
    ("Image", "image_z_image_turbo.json", "Z_image_turbo.json"),
    ("Image", "flux_dev_full_text_to_image.json", "flux.1-dev.json"),
    ("Edit", "image_qwen_image_2_1_image_edit.json", "qwen_2_1_edit.json"),
    ("Edit", "image_qwen_image_edit_2511.json", "qwen_edit_2511.json"),
    ("Edit", "image_flux2_klein_image_edit_9b_distilled.json", "flux2_klein_edit.json"),
]


def md5_of(path, chunk=1 << 22):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def list_backups(cat_dir, bak_dir, name):
    """收集工作流同名备份：类别目录下 <name>.bak* 与 新建文件夹 下同名条目。"""
    out = []
    try:
        out += [f for f in os.listdir(cat_dir) if f.startswith(name) and f != name]
    except OSError:
        pass
    try:
        base = name[:-5]  # 去掉 .json
        out += [os.path.join("新建文件夹", f) for f in os.listdir(bak_dir) if f.startswith(base)]
    except OSError:
        pass
    return sorted(out)


def depersonalize(p):
    """输出路径脱敏：本机主目录改写为 %USERPROFILE% 形态（公开仓红线，2026-10-15）。"""
    home = os.path.expandvars(r"%USERPROFILE%")
    if home and home != "%USERPROFILE%" and p and p.startswith(home):
        return "%USERPROFILE%" + p[len(home):]
    return p


def main():
    ap = argparse.ArgumentParser(description="生成 11 份工作流溯源清单（只读外部原件）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="ComfyUI user/default/workflows 绝对路径")
    ap.add_argument("--templates", default=DEFAULT_TEMPLATES, help="官方模板目录绝对路径")
    args = ap.parse_args()
    root = args.root
    bak_dir = os.path.join(root, "Image", "新建文件夹")

    entries = []
    missing = []
    for cat, tpl, wf in SOURCE_MAP:
        cat_dir = os.path.join(root, cat)
        path = os.path.join(cat_dir, wf)
        if not os.path.exists(path):
            missing.append(os.path.join(cat, wf))
            continue
        st = os.stat(path)
        src_md5 = None
        src_path = os.path.join(args.templates, tpl)
        if os.path.exists(src_path):
            src_md5 = md5_of(src_path)
        else:
            print("[警告] 官方模板未找到：%s（source_md5=null）" % tpl)
        entries.append({
            "category": cat,
            "file": wf,
            "path": depersonalize(path),
            "md5": md5_of(path),
            "size": st.st_size,
            "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "source_template": tpl,
            "source_md5": src_md5,
            "backups": list_backups(cat_dir, bak_dir, wf),
        })

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows_manifest.json")
    manifest = {
        "meta": {
            "generator": "gen_workflows_manifest.py",
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "root": depersonalize(root),
            "templates_dir": depersonalize(args.templates),
            "note": "快照型溯源清单：工作流原件在仓库外（只读），本清单为仓库内审计记录",
        },
        "workflows": entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("已生成 %s：%d 条" % (out_path, len(entries)))
    if missing:
        print("[警告] 以下工作流不存在于 %s：%s" % (root, missing))


if __name__ == "__main__":
    main()
