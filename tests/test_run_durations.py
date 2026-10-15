# -*- coding: utf-8 -*-
"""通用视频时长档位跑测器单元测试（E4，2026-10-16）。

覆盖：适配器加载（跳过 `_` 说明键）、两种帧数换算网格可插拔（H3 的 17k+5、
示例适配器的 8k+1）、档位元组展开。全部读仓内 adapters.json，不依赖本机 ComfyUI。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "03_受控跑测"))
sys.path.insert(0, os.path.join(ROOT, "01_工作流扁平化"))

import run_durations  # noqa: E402


class AdapterLoading(unittest.TestCase):
    def test_private_keys_are_not_adapters(self):
        """adapters.json 顶层有 `_comment` 说明键，不能当适配器返回。"""
        data = run_durations.load_adapters()
        self.assertIn("minimax_h3_t2v", data)
        self.assertTrue(all(isinstance(v, dict) for v in data.values()))
        self.assertTrue(all(not k.startswith("_") for k in data))

    def test_h3_adapter_shape(self):
        ad = run_durations.load_adapters()["minimax_h3_t2v"]
        self.assertEqual(ad["fps"], 24)
        self.assertEqual(ad["nodes"]["i2v"], 104)
        self.assertEqual(len(run_durations._combos(ad)), 5)
        # combos 必须是 5 元组（tag/duration/width/height/note）
        for c in run_durations._combos(ad):
            self.assertEqual(len(c), 5)


class FramesRule(unittest.TestCase):
    """帧数换算式必须可插拔：换模型只换规则，不换代码。"""

    def test_h3_grid_17k_plus_5(self):
        ad = run_durations.load_adapters()["minimax_h3_t2v"]
        # base = max(5, round(sec*24)); frames = base + (5 - base%17)%17
        for sec, want in ((5.0, 124), (8.0, 192), (10.0, 243), (11.0, 277), (15.0, 362)):
            self.assertEqual(run_durations.frames_for(ad, sec), want, "sec=%s" % sec)

    def test_demo_grid_8k_plus_1_at_16fps(self):
        """示例适配器：16fps、8k+1 网格、下限 9 帧 —— 与 H3 规则完全不同但同一套代码。"""
        ad = run_durations.load_adapters()["ltxv_demo"]
        # 2s -> base=32 -> 32+(1-0)%8=33 ; 5s -> base=80 -> 80+(1-0)%8=81
        self.assertEqual(run_durations.frames_for(ad, 2.0), 33)
        self.assertEqual(run_durations.frames_for(ad, 5.0), 81)
        # 极短时长受 min 下限保护：0.1s -> base=max(9, 2)=9 -> 9+(1-1)%8=9
        self.assertEqual(run_durations.frames_for(ad, 0.1), 9)

    def test_min_floor_applies(self):
        ad = {"fps": 24, "frames_rule": {"type": "grid", "k": 17, "offset": 5, "min": 5}}
        self.assertEqual(run_durations.frames_for(ad, 0.0), 5)


if __name__ == "__main__":
    unittest.main()
