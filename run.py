# -*- coding: utf-8 -*-
"""
ComfyUI 实验与改造工具箱 · 根目录统一入口
==========================================

本文件是整个工具箱的**唯一入口**，负责：
  1) 把各子目录加入 import 路径（脚本之间靠同目录 import 互调，见根 README 第四节）；
  2) 强制 UTF-8 输出，避免 GBK 控制台打印中文报 UnicodeEncodeError；
  3) 以子进程方式调用目标脚本——保持每个脚本「像单独运行一样」，不改动它们内部的 __file__ 逻辑。

为什么脚本本体不搬到根目录：`09_Web面板/panel.py` 靠 `__file__` 反推 TOOLBOX 并读同目录
`index.html`，`03_受控跑测/run_models.py` 裸 `import flatten` 依赖 PYTHONPATH——搬运会直接破坏它们。
入口层放根目录、脚本留在编号目录，是唯一两全的做法。

用法（必须用 ComfyUI 自带 python，因为 σ 计算要 import comfy.*、分析要 numpy/Pillow）：

    python run.py                 # 等价于 list
    python run.py list            # 列出所有入口
    python run.py panel           # ★ 启动 Web 面板（浏览器 http://127.0.0.1:8189）
    python run.py sigma           # 参数轨① 多模型 σ 风险矩阵（纯离线，不跑图）
    python run.py unify           # 参数轨② 统一提示词与种子（dry-run）
    python run.py unify --apply   #           同上，真正写盘（自动备份）
    python run.py models          # 参数轨③ 跨模型受控跑测（需 ComfyUI 在 8188）
    python run.py analyze         # 参数轨④ 结果分析（指标 + 拼版）
    python run.py pipeline        # ①→②→③→④ 顺序跑完（②默认 dry-run，加 --apply 才写盘）
    python run.py flatten [wf]    # 单工作流扁平化 / 查看运行时真值（参数透传）

Windows 用户可直接双击 `start.bat`（启动面板）或用 `run.bat <子命令>`，免记 python 路径。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 需要加入 import 路径的子目录（脚本之间靠同目录 import 互调）
IMPORT_DIRS = [
    "01_工作流扁平化",
    "02_调度器sigma分析",
    "03_受控跑测",
    "04_结果分析",
]

# 入口表：子命令 -> (说明, 相对脚本路径)
ENTRIES = {
    "panel":   ("★ 启动 Web 面板（浏览器 http://127.0.0.1:8189）", "09_Web面板/panel.py"),
    "sigma":   ("参数轨① 多模型 σ 风险矩阵（纯离线，不跑图）", "02_调度器sigma分析/sigma_matrix.py"),
    "unify":   ("参数轨② 统一提示词与种子（默认 dry-run，加 --apply 才写盘）", "03_受控跑测/unify_prompt_seed.py"),
    "models":  ("参数轨③ 跨模型统一变量跑测（需 ComfyUI 已在 8188）", "03_受控跑测/run_models.py"),
    "analyze": ("参数轨④ 结果分析：指标 + 拼版 + 相似度", "04_结果分析/analyze_models.py"),
    "flatten": ("单工作流扁平化 / 查看运行时真值（参数透传）", "01_工作流扁平化/flatten.py"),
}

# pipeline 的顺序（参数轨四步）
PIPELINE = ["sigma", "unify", "models", "analyze"]


def build_env():
    """构造子进程环境：补齐 PYTHONPATH，强制 UTF-8。"""
    env = os.environ.copy()
    extra = [os.path.join(ROOT, d) for d in IMPORT_DIRS]
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(extra + ([old] if old else []))
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def script_path(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        sys.exit("[x] 找不到脚本：%s" % path)
    return path


def run(rel, args):
    """以子进程方式运行目标脚本，返回退出码。"""
    path = script_path(rel)
    shown = os.path.relpath(path, ROOT).replace("\\", "/")
    print("\n[run] %s%s" % (shown, (" " + " ".join(args)) if args else ""), flush=True)
    return subprocess.call([sys.executable, path] + list(args),
                           cwd=os.path.dirname(path), env=build_env())


def show_list():
    width = max(len(k) for k in ENTRIES)
    print("ComfyUI 实验与改造工具箱 · 可用入口\n")
    for key, (desc, _) in ENTRIES.items():
        print("  %-*s  %s" % (width, key, desc))
    print("  %-*s  %s" % (width, "pipeline", "①→②→③→④ 顺序跑完（可加 --apply 让②写盘）"))
    print("  %-*s  %s" % (width, "list", "显示本清单"))
    print("\n示例：  python run.py panel         启动面板")
    print("        python run.py unify --apply 统一提示词与种子（写盘）")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("list", "-h", "--help", "help"):
        show_list()
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd == "pipeline":
        for step in PIPELINE:
            args = rest if step == "unify" else []
            rc = run(ENTRIES[step][1], args)
            if rc != 0:
                print("\n[!] 步骤 %s 失败（exit=%d），流水线中断" % (step, rc))
                return rc
        print("\n[ok] 参数轨 4 步全部完成")
        return 0

    if cmd not in ENTRIES:
        print("[x] 未知入口：%s\n" % cmd)
        show_list()
        return 2

    return run(ENTRIES[cmd][1], rest)


if __name__ == "__main__":
    sys.exit(main())
