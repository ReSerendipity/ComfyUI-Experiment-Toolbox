# -*- coding: utf-8 -*-
"""flatten.py 单元测试（标准库 unittest，2026-10-15，测试维度 P1-1）。

覆盖 01 README「flatten.py 的核心规则」与模块 docstring 规则 1~5：
  规则2 容器输入按 target_slot 对齐注入 + positional 数组只装带 widget 标记的输入；
  规则3 容器输出 (-20) 映射；规则4 bypass(mode=4) 递归透传；规则5 可达性裁剪；
  overrides（按 class_type / 原始数字 id）；_link 的 int/str 类型归一。
全部使用测试内合成的最小工作流（tempfile），不依赖本机 ComfyUI 目录。
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "01_工作流扁平化"))

import flatten  # noqa: E402

SG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001"  # 满足 _containers：含 "-" 且长度 > 30


def container_workflow(widget_values=(512, 768)):
    """容器(输入 width/height 均带 widget) → 顶层 SaveImageAdvanced；子图内 EmptyImage 产 IMAGE。"""
    return {
        "nodes": [
            {"id": 1, "type": SG_ID, "mode": 0,
             "inputs": [
                 {"name": "width", "type": "INT", "widget": {"name": "width"}},
                 {"name": "height", "type": "INT", "widget": {"name": "height"}},
             ],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
             "widgets_values": list(widget_values)},
            {"id": 2, "type": "SaveImageAdvanced", "mode": 0,
             "inputs": [
                 {"name": "images", "type": "IMAGE", "link": 1},
                 {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}},
             ],
             "outputs": [], "widgets_values": ["demo"]},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        "definitions": {"subgraphs": [{
            "id": SG_ID,
            "inputs": [
                {"id": "i0", "name": "width", "type": "INT", "linkIds": [201], "widget": {"name": "width"}},
                {"id": "i1", "name": "height", "type": "INT", "linkIds": [202], "widget": {"name": "height"}},
            ],
            "outputs": [{"id": "o0", "name": "IMAGE", "type": "IMAGE", "linkIds": [101]}],
            "links": [
                {"id": 101, "origin_id": 10, "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "IMAGE"},
                {"id": 201, "origin_id": -10, "origin_slot": 0, "target_id": 10, "target_slot": 0, "type": "INT"},
                {"id": 202, "origin_id": -10, "origin_slot": 1, "target_id": 10, "target_slot": 1, "type": "INT"},
            ],
            "nodes": [{
                "id": 10, "type": "EmptyImage", "mode": 0,
                "inputs": [
                    {"name": "width", "type": "INT", "widget": {"name": "width"}},
                    {"name": "height", "type": "INT", "widget": {"name": "height"}},
                ],
                "widgets_values": [0, 0],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [101]}],
            }],
        }]},
    }


def write_wf(tmpdir, wf, name="wf.json"):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wf, f)
    return path


class TestContainerInjection(unittest.TestCase):
    def test_widget_input_injection_and_output_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            api, applied = flatten.flatten(write_wf(td, container_workflow()))
            node = api["1010"]
            self.assertEqual(node["class_type"], "EmptyImage")
            self.assertEqual(node["inputs"]["width"], 512)
            self.assertEqual(node["inputs"]["height"], 768)
            save = api["t2"]
            self.assertEqual(save["class_type"], "SaveImageAdvanced")
            self.assertEqual(save["inputs"]["images"], ["1010", 0])

    def test_positional_skips_non_widget_inputs(self):
        """规则2：positional 数组只对应带 widget 标记的输入（2026-10-15 修复的错位问题）。"""
        wf = container_workflow()
        sg = wf["definitions"]["subgraphs"][0]
        # 在 height 前插入一个无 widget 的 MASK 接口：positional 仍只装 2 个 widget 值；
        # height 的接口下标由 1 变 2，其 -10 链 origin_slot 必须同步为 2（接口下标对齐规则）
        sg["inputs"].insert(1, {"id": "im", "name": "mask", "type": "MASK", "linkIds": []})
        for l in sg["links"]:
            if l["id"] == 202:
                l["origin_slot"] = 2
        with tempfile.TemporaryDirectory() as td:
            api, _ = flatten.flatten(write_wf(td, wf))
            self.assertEqual(api["1010"]["inputs"]["width"], 512)
            self.assertEqual(api["1010"]["inputs"]["height"], 768)


class TestTypeGuard(unittest.TestCase):
    def test_non_numeric_into_numeric_input_keeps_original(self):
        """类型守卫：目标输入本为数值而容器给了字符串 → 保留节点原值并告警。"""
        with tempfile.TemporaryDirectory() as td:
            api, _ = flatten.flatten(write_wf(td, container_workflow((512, "model.safetensors"))))
            self.assertEqual(api["1010"]["inputs"]["width"], 512)
            self.assertEqual(api["1010"]["inputs"]["height"], 0)


class TestBypassAndPrune(unittest.TestCase):
    def test_bypass_passthrough_and_unreachable_pruned(self):
        wf = container_workflow()
        wf["nodes"].append(
            {"id": 3, "type": "ImageScale", "mode": 4,
             "inputs": [{"name": "image", "type": "IMAGE", "link": 1}],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}],
             "widgets_values": []})
        wf["nodes"].append(
            {"id": 4, "type": "EmptyLatentImage", "mode": 0,
             "inputs": [{"name": "width", "type": "INT", "widget": {"name": "width"}}],
             "outputs": [], "widgets_values": [512]})
        wf["links"] = [[1, 1, 0, 3, 0, "IMAGE"], [2, 3, 0, 2, 0, "IMAGE"]]
        with tempfile.TemporaryDirectory() as td:
            api, _ = flatten.flatten(write_wf(td, wf))
            self.assertNotIn("t3", api)          # bypass 节点被删除
            self.assertNotIn("t4", api)          # 不可达节点被裁剪（规则5）
            self.assertEqual(api["t2"]["inputs"]["images"], ["1010", 0])  # 透传到容器输出


class TestLinkTypeNormalization(unittest.TestCase):
    def test_string_ids_normalized(self):
        """_link 类型归一：子图 links 混用 str/int id 不再 str-vs-int 崩溃（2026-10-15 修复）。"""
        wf = container_workflow()
        sg = wf["definitions"]["subgraphs"][0]
        sg["links"] = [
            {"id": "101", "origin_id": "10", "origin_slot": "0", "target_id": "-20", "target_slot": "0"},
            {"id": "201", "origin_id": "-10", "origin_slot": "0", "target_id": "10", "target_slot": "0"},
            {"id": "202", "origin_id": "-10", "origin_slot": "1", "target_id": "10", "target_slot": "1"},
        ]
        with tempfile.TemporaryDirectory() as td:
            api, _ = flatten.flatten(write_wf(td, wf))
            self.assertEqual(api["1010"]["inputs"]["width"], 512)
            self.assertEqual(api["t2"]["inputs"]["images"], ["1010", 0])


class TestOverrides(unittest.TestCase):
    def test_override_by_class_type_and_by_old_id(self):
        with tempfile.TemporaryDirectory() as td:
            api, applied = flatten.flatten(
                write_wf(td, container_workflow(), "a.json"),
                overrides={"SaveImageAdvanced": {"filename_prefix": "over"}})
            self.assertEqual(api["t2"]["inputs"]["filename_prefix"], "over")
            self.assertTrue(applied)
        with tempfile.TemporaryDirectory() as td:
            api, applied = flatten.flatten(
                write_wf(td, container_workflow(), "b.json"),
                overrides={2: {"filename_prefix": "over2"}})
            self.assertEqual(api["t2"]["inputs"]["filename_prefix"], "over2")
            self.assertTrue(applied)


if __name__ == "__main__":
    unittest.main()
