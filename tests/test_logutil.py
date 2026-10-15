# -*- coding: utf-8 -*-
"""logutil.py 单元测试（标准库 unittest，2026-10-15，测试维度 P1-1）。

覆盖 append-only JSONL（唯一事实源）+ 合并视图重建 + 旧格式迁移三件套，
即 03 README「日志格式 v2」与 data-dictionary.md 的 schema_version 纪律。
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "03_受控跑测"))

import logutil  # noqa: E402


class TestAppendRecord(unittest.TestCase):
    def test_appends_one_line_per_record_with_schema_version(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "run.jsonl")
            logutil.append_record(p, {"label": "a", "ok": True})
            logutil.append_record(p, {"label": "b", "ok": False, "schema_version": 9})
            with open(p, encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["schema_version"], logutil.SCHEMA_VERSION)
            self.assertEqual(lines[1]["schema_version"], 9)  # 调用方显式指定则不覆盖


class TestRebuildConsolidated(unittest.TestCase):
    def test_same_key_keeps_latest(self):
        with tempfile.TemporaryDirectory() as td:
            jl = os.path.join(td, "run.jsonl")
            cj = os.path.join(td, "run.json")
            for rec in ({"k": "a", "v": 1}, {"k": "b", "v": 2}, {"k": "a", "v": 3}):
                logutil.append_record(jl, rec)
            rows = logutil.rebuild_consolidated(cj, jl, key=lambda r: r["k"])
            pairs = {(r["k"], r["v"]) for r in rows}
            self.assertEqual(pairs, {("a", 3), ("b", 2)})
            self.assertEqual(len(rows), 2)
            with open(cj, encoding="utf-8") as f:
                self.assertEqual({(r["k"], r["v"]) for r in json.load(f)}, pairs)


class TestMigrateLegacy(unittest.TestCase):
    def test_migrates_once_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            cj = os.path.join(td, "run.json")
            jl = os.path.join(td, "run.jsonl")
            with open(cj, "w", encoding="utf-8") as f:
                json.dump([{"label": "x"}, {"label": "y"}], f)
            logutil.migrate_legacy(cj, jl, key=lambda r: r["label"])
            with open(jl, encoding="utf-8") as f:
                self.assertEqual(len([x for x in f if x.strip()]), 2)
            # jsonl 已存在时再次 migrate 必须是 no-op（历史保全、不重复）
            logutil.migrate_legacy(cj, jl, key=lambda r: r["label"])
            with open(jl, encoding="utf-8") as f:
                self.assertEqual(len([x for x in f if x.strip()]), 2)

    def test_noop_when_no_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            jl = os.path.join(td, "run.jsonl")
            logutil.migrate_legacy(os.path.join(td, "missing.json"), jl, key=lambda r: r["k"])
            self.assertFalse(os.path.exists(jl))


if __name__ == "__main__":
    unittest.main()
