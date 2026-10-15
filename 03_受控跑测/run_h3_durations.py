# -*- coding: utf-8 -*-
"""
MiniMax H3 t2v 时长档位跑测 —— **薄壳**（E4 重构后，2026-10-16）
================================================================

历史：本文件原是 H3 专用的 291 行跑测器，帧数换算（17k+5）/ 档位矩阵 / 节点 ID /
隐藏参数补缺全部硬编码，换一个视频模型就要整份复制改写。

现在：**跑测引擎在 `run_durations.py`（与模型无关），本文件只做两件事**——
  1) 从 `adapters.json` 取出 `minimax_h3_t2v` 适配器；
  2) 把命令行原样转发给引擎。

命令行与重构前**完全兼容**（--dry-run / --only / --workflow / --te / --dit，
以及 E2 新增的 --no-auto-vram / --vram-budget / --start-tier / --max-downgrade），
重构前后 dry-run 输出逐字段一致（已回归验证）。

下方保留的常量仅供仍按旧名 import 的调用方使用，真实取值以 adapters.json 为准。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_durations  # noqa: E402   同轨互 import（Gate ⑥ 放行）

ADAPTER_NAME = "minimax_h3_t2v"


def _adapter():
    return run_durations.load_adapters()[ADAPTER_NAME]


# ── 兼容常量（旧调用方可能 import 这些名字；真值一律以 adapters.json 为准） ──
DEFAULT_WORKFLOW = os.path.expandvars(_adapter().get("workflow") or "")
COMBOS = run_durations._combos(_adapter())
TE = (_adapter().get("defaults") or {}).get("te")
DIT = (_adapter().get("defaults") or {}).get("dit")
NODE_I2V = (_adapter().get("nodes") or {}).get("i2v")
NODE_CLIP = (_adapter().get("nodes") or {}).get("clip")
NODE_UNET = (_adapter().get("nodes") or {}).get("unet")


def frames_for(seconds):
    """duration(秒) -> length(帧)：17k+5 网格 @24fps（转发给引擎的通用换算）。"""
    return run_durations.frames_for(_adapter(), seconds)


def main(argv=None):
    return run_durations.main(_adapter(), ADAPTER_NAME,
                              list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
