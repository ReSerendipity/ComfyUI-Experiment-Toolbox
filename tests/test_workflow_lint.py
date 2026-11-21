# -*- coding: utf-8 -*-
"""workflow_lint.py 单元测试（标准库 unittest）。"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "01_工作流扁平化"))

import workflow_lint  # noqa: E402


def node(cls, **inputs):
    return {"class_type": cls, "inputs": inputs}


class TestLintApi(unittest.TestCase):
    def test_valid_order_is_dependency_first(self):
        api = {
            "3": node("SaveImage", images=["2", 0]),
            "2": node("VAEDecode", samples=["1", 0], vae=["9", 0]),
            "1": node("KSampler", model=["9", 0]),
            "9": node("CheckpointLoaderSimple", ckpt_name="a.safetensors"),
        }
        report = workflow_lint.lint_api(api)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["order"], ["9", "1", "2", "3"])

    def test_dangling_reference_is_error(self):
        report = workflow_lint.lint_api({"1": node("SaveImage", images=["404", 0])})
        self.assertFalse(report["ok"])
        self.assertIn("不存在的节点 404", report["errors"][0])

    def test_cycle_is_error_and_no_partial_order(self):
        api = {
            "1": node("A", x=["2", 0]),
            "2": node("B", x=["1", 0]),
            "3": node("C", x=["1", 0]),
        }
        report = workflow_lint.lint_api(api)
        self.assertFalse(report["ok"])
        self.assertIn("环或不可达依赖", report["errors"][0])
        self.assertEqual(report["order"], [])

    def test_self_reference_is_error(self):
        report = workflow_lint.lint_api({"1": node("A", x=["1", 0])})
        self.assertFalse(report["ok"])
        self.assertIn("自引用", report["errors"][0])

    def test_non_link_list_is_ignored(self):
        report = workflow_lint.lint_api({
            "1": node("A", text="not a link", values=[1, 2]),
            "2": node("B", model=["1", 0]),
        })
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["order"], ["1", "2"])

    def test_ui_workflow_is_rejected_with_hint(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "wf.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"nodes": [], "links": []}, f)
            report = workflow_lint.lint_file(path)
            self.assertFalse(report["ok"])
            self.assertIn("flatten.py", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
