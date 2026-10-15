# -*- coding: utf-8 -*-
"""panel.py API 契约测试（标准库 unittest，2026-10-15，测试维度 P1-3）。

覆盖 Web 面板的 API 契约面（全部离线，不依赖 ComfyUI 服务）：
  build_api —— 扁平化后按组合覆盖 KSampler 参数（类型归一）+ 正向提示词注入；
  start_run —— 缺参 400 / 已在跑 409 两个同步分支；
  read_workflow_truth —— 运行时真值提取（①页数据源）。
使用测试内合成的扁平（非子图）工作流，tempfile 承载。
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "09_Web面板"))

import panel  # noqa: E402  （panel 自行注入 01 目录并 import flatten）


def flat_ksampler_workflow():
    """无子图的扁平工作流：UNETLoader→CLIPTextEncode→KSampler→VAEDecode→SaveImage。"""
    return {
        "nodes": [
            {"id": 1, "type": "UNETLoader", "mode": 0,
             "inputs": [{"name": "unet_name", "type": "COMBO", "widget": {"name": "unet_name"}}],
             "outputs": [{"name": "MODEL", "type": "MODEL", "links": [10]}],
             "widgets_values": ["model.safetensors"]},
            {"id": 2, "type": "CLIPLoader", "mode": 0,
             "inputs": [{"name": "clip_name", "type": "COMBO", "widget": {"name": "clip_name"}}],
             "outputs": [{"name": "CLIP", "type": "CLIP", "links": [11]}],
             "widgets_values": ["clip.safetensors"]},
            {"id": 3, "type": "CLIPTextEncode", "mode": 0,
             "inputs": [
                 {"name": "text", "type": "STRING", "widget": {"name": "text"}, "link": None},
                 {"name": "clip", "type": "CLIP", "link": 11}],
             "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [12, 13]}],
             "widgets_values": ["origin prompt"]},
            {"id": 4, "type": "KSampler", "mode": 0,
             "inputs": [
                 {"name": "seed", "type": "INT", "widget": {"name": "seed"}},
                 {"name": "steps", "type": "INT", "widget": {"name": "steps"}},
                 {"name": "cfg", "type": "FLOAT", "widget": {"name": "cfg"}},
                 {"name": "sampler_name", "type": "COMBO", "widget": {"name": "sampler_name"}},
                 {"name": "scheduler", "type": "COMBO", "widget": {"name": "scheduler"}},
                 {"name": "denoise", "type": "FLOAT", "widget": {"name": "denoise"}},
                 {"name": "model", "type": "MODEL", "link": 10},
                 {"name": "positive", "type": "CONDITIONING", "link": 12},
                 {"name": "negative", "type": "CONDITIONING", "link": 13}],
             "outputs": [{"name": "LATENT", "type": "LATENT", "links": [14]}],
             "widgets_values": [123, "fixed", 25, 1.0, "euler", "simple", 1.0]},
            {"id": 5, "type": "VAELoader", "mode": 0,
             "inputs": [{"name": "vae_name", "type": "COMBO", "widget": {"name": "vae_name"}}],
             "outputs": [{"name": "VAE", "type": "VAE", "links": [15]}],
             "widgets_values": ["vae.safetensors"]},
            {"id": 6, "type": "VAEDecode", "mode": 0,
             "inputs": [{"name": "samples", "type": "LATENT", "link": 14},
                        {"name": "vae", "type": "VAE", "link": 15}],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [16]}],
             "widgets_values": []},
            {"id": 7, "type": "SaveImage", "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 16},
                        {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}}],
             "outputs": [], "widgets_values": ["flat"]},
        ],
        "links": [
            [10, 1, 0, 4, 6, "MODEL"],
            [11, 2, 0, 3, 1, "CLIP"],
            [12, 3, 0, 4, 7, "CONDITIONING"],
            [13, 3, 0, 4, 8, "CONDITIONING"],
            [14, 4, 0, 6, 0, "LATENT"],
            [15, 5, 0, 6, 1, "VAE"],
            [16, 6, 0, 7, 0, "IMAGE"],
        ],
    }


class PanelApiTestBase(unittest.TestCase):
    def setUp(self):
        fd, self.wf_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self.wf_path, "w", encoding="utf-8") as f:
            json.dump(flat_ksampler_workflow(), f)

    def tearDown(self):
        os.remove(self.wf_path)


class TestBuildApi(PanelApiTestBase):
    def test_combo_overrides_types_and_prompt_injection(self):
        api, touched = panel.build_api(
            self.wf_path,
            {"name": "c", "sampler_name": "res_multistep", "scheduler": "simple",
             "steps": 20, "cfg": 2.5, "seed": 999},
            "NEW PROMPT", 999)
        ks = next(nd for nd in api.values() if nd["class_type"] == "KSampler")
        self.assertEqual(ks["inputs"]["sampler_name"], "res_multistep")
        self.assertEqual(ks["inputs"]["scheduler"], "simple")
        self.assertEqual(ks["inputs"]["steps"], 20)
        self.assertIsInstance(ks["inputs"]["steps"], int)
        self.assertEqual(ks["inputs"]["cfg"], 2.5)
        self.assertIsInstance(ks["inputs"]["cfg"], float)
        self.assertEqual(ks["inputs"]["seed"], 999)
        self.assertIsInstance(ks["inputs"]["seed"], int)
        self.assertEqual(sorted(set(touched)),
                         ["cfg", "sampler_name", "scheduler", "seed", "steps"])
        enc = next(nd for nd in api.values() if nd["class_type"] == "CLIPTextEncode")
        self.assertEqual(enc["inputs"]["text"], "NEW PROMPT")

    def test_empty_combo_keeps_original_values(self):
        api, touched = panel.build_api(self.wf_path, {"name": "c"}, "P2", 1)
        ks = next(nd for nd in api.values() if nd["class_type"] == "KSampler")
        self.assertEqual(ks["inputs"]["sampler_name"], "euler")
        self.assertEqual(ks["inputs"]["seed"], 123)
        self.assertEqual(touched, [])
        enc = next(nd for nd in api.values() if nd["class_type"] == "CLIPTextEncode")
        self.assertEqual(enc["inputs"]["text"], "P2")


class TestStartRun(unittest.TestCase):
    def test_missing_fields_returns_400(self):
        rc, body = panel.start_run({})
        self.assertEqual(rc, 400)
        for frag in ("未勾选任何工作流", "未添加任何组合", "提示词为空"):
            self.assertIn(frag, body["error"])

    def test_conflict_returns_409(self):
        old = panel.JOB["status"]
        panel.JOB["status"] = "running"
        try:
            rc, body = panel.start_run({})
            self.assertEqual(rc, 409)
            self.assertIn("已有跑测在进行中", body["error"])
        finally:
            panel.JOB["status"] = old


class TestReadWorkflowTruth(PanelApiTestBase):
    def test_truth_values_and_prompt_chars(self):
        truth = panel.read_workflow_truth(self.wf_path)
        self.assertEqual(truth["route"], "ksampler")
        self.assertEqual(truth["values"]["sampler_name"], "euler")
        self.assertEqual(truth["values"]["scheduler"], "simple")
        self.assertEqual(truth["values"]["steps"], 25)
        self.assertEqual(truth["values"]["seed"], 123)
        self.assertEqual(truth["prompt_chars"], len("origin prompt"))


if __name__ == "__main__":
    unittest.main()
