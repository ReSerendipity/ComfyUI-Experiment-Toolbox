# -*- coding: utf-8 -*-
"""05 结构改造脚本共享的 dry-run 助手（2026-10-14，全默认关闭，不带参数时行为与旧版完全一致）。

改造脚本统一接入两个命令行开关：
  --dry-run     不落盘：跳过备份 copy2 与 makedirs，只打印「将修改的文件 + 将写入的结构 diff」；
                幂等守卫（[跳过] 判定）照常执行，读取照常。
  --target-dir  把脚本写死的目标目录（Image/Edit 工作流目录）重定向到样本目录，
                用于演练与验证；不传时保持原路径不变。

写工作流的脚本请沿用本模块三个收口点：guard_makedirs / guard_backup / write_json。
"""
import argparse
import difflib
import json
import os
import shutil

_OPTS = {"dry_run": False, "target_dir": None}


def parse_args(argv=None):
    """解析共享开关并写入全局状态；各改造脚本入口处调用一次。"""
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="默认关闭。开启后不落盘（不备份、不写入），只打印将修改的文件与结构 diff")
    ap.add_argument("--target-dir", default=None, metavar="DIR",
                    help="把脚本的目标工作流目录重定向到样本目录（演练/验证用）")
    args = ap.parse_args(argv)
    _OPTS["dry_run"] = bool(args.dry_run)
    _OPTS["target_dir"] = os.path.abspath(args.target_dir) if args.target_dir else None
    if _OPTS["dry_run"]:
        print("[dry-run] 已开启：不落盘，只输出计划（备份与写入均被跳过）")
    if _OPTS["target_dir"]:
        print("[target-dir] 目标目录重定向 -> %s" % _OPTS["target_dir"])
    return args


def is_dry_run():
    return _OPTS["dry_run"]


def get_target_dir():
    """返回当前 --target-dir （绝对路径）或未设置时 None。"""
    return _OPTS["target_dir"]


def resolve_target(original_dir):
    """有 --target-dir 且目录名匹配（basename 相同或原名含 Image/Edit）时用它替换。

    脚本里的原路径是本机历史绝对路径（如 aki-v3），换机后可能已不存在；
    此时只要给了 --target-dir 就直接采用，保证样本演练可用。
    """
    td = _OPTS["target_dir"]
    if not td:
        return original_dir
    base = os.path.basename(os.path.normpath(original_dir))
    if base and (base == os.path.basename(os.path.normpath(td))
                 or base in ("Image", "Edit")):
        return td
    if not os.path.isdir(original_dir):
        return td
    return original_dir


def detect_format(raw):
    """从原文件文本嗅探序列化格式（沿用各脚本原逻辑：缩进 + 分隔符空格）。"""
    indent = 2 if "\n  " in raw else None
    sep = (", ", ": ") if '", "' in raw else (",", ":")
    return indent, sep


def guard_makedirs(path):
    """dry-run 时不创建目录，只打印计划。"""
    if _OPTS["dry_run"]:
        print("[dry-run] 将跳过创建目录: %s" % path)
        return False
    os.makedirs(path, exist_ok=True)
    return True


def guard_backup(src, dst):
    """dry-run 时跳过备份 copy2（不产生任何写盘），只打印计划；否则照常备份。"""
    if _OPTS["dry_run"]:
        print("[dry-run] 将备份: %s -> %s" % (src, dst))
        return False
    shutil.copy2(src, dst)
    print("[备份] %s -> %s" % (src, dst))
    return True


def write_json(path, data, indent=None, sep=(",", ":"), max_diff_lines=40):
    """唯一的写盘收口：dry-run 时不落盘，打印结构 diff；非 dry-run 照常写入。

    diff 基线取自磁盘当前内容（读取原文，与旧版 read() 的嗅探一致），
    因此真实模式下幂等守卫未拦截、但内容实际无变化的文件也会提示「无结构变化」。
    """
    new_text = json.dumps(data, ensure_ascii=False, indent=indent, separators=sep)
    try:
        with open(path, encoding="utf-8") as f:
            old_text = f.read()
    except OSError:
        old_text = None

    if _OPTS["dry_run"]:
        if old_text == new_text:
            print("[dry-run] 无结构变化，将不写入: %s" % path)
        else:
            print("[dry-run] 将修改文件: %s" % path)
            _print_diff(old_text, new_text, path, max_diff_lines)
        return False

    if old_text == new_text:
        print("[无变化] %s 内容与将写入结果一致，跳过写入" % path)
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("[已写入] %s" % path)
    return True


def _print_diff(old_text, new_text, path, max_lines):
    """打印「将写入的结构差异」（JSON 按 indent=2 pretty 后做行级 unified diff）。"""
    old_lines = json.dumps(json.loads(old_text), ensure_ascii=False, indent=2).splitlines() \
        if old_text else []
    new_lines = json.dumps(json.loads(new_text), ensure_ascii=False, indent=2).splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                     fromfile="%s (当前)" % os.path.basename(path),
                                     tofile="%s (将写入)" % os.path.basename(path),
                                     lineterm=""))
    body = diff[2:] if len(diff) > 2 else diff
    truncated = len(body) > max_lines
    for line in body[:max_lines]:
        print("    " + line)
    if truncated:
        print("    ...（diff 共 %d 行，已截断，仅显示前 %d 行）" % (len(body), max_lines))
    elif not body:
        print("    （无行级差异，仅序列化格式/键序变化）")
