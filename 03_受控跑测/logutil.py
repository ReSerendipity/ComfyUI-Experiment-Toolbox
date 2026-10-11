# -*- coding: utf-8 -*-
"""受控跑测增量日志工具：append-only JSONL（唯一事实源）+ 合并视图 JSON（兼容旧读取方）。

背景（NEXT 评估报告 P1-1/P1-2）：
  旧实现每次 json.dump 全量覆写同一日志文件，单模型/单组合补跑会把完整历史冲掉
  （07 样例中 model_test_log.json 曾因此只剩 3 条失败记录）。
v2 约定：
  - 每条记录 append 到 <log>.jsonl，永不覆写（唯一事实源）；
  - 合并视图 <log>.json 由 jsonl 重建，按 key 取「最新一条」，保持出现顺序，
    旧读取方（人工读 json / 脚本读 json）无需改动；
  - jsonl 不存在但 json 存在时，migrate_legacy() 把旧记录迁入 jsonl，历史保全。
字段约定：每条记录除业务字段外，含 ts（本地时间）/ seed / steps / cfg / py / comfy
（见 run_combos.py、run_models.py 落盘处）。

schema 版本（数据治理 R2 P1，2026-10-11）：
  - SCHEMA_VERSION = 2：v2 协议标记。append_record 对每条新记录写入 schema_version=2；
    旧记录（v2 上线前落盘）无该字段，读取方应使用 .get("schema_version") 容错。
    字段字典见同目录 data-dictionary.md（03 日志 / 07 样例 / 05 manifest 统一登记）。
"""
import json
import os

# 日志记录 schema 版本（v2 协议，2026-10-11 起显式打标；与 data-dictionary.md 保持一致）
SCHEMA_VERSION = 2


def append_record(jsonl_path, rec):
    """追加一条记录到 jsonl（文件不存在则创建，目录自动建）。

    每条记录写入前打上 schema_version 标记（setdefault：调用方未显式指定时补 v2），
    使历史记录可按版本识别；旧记录无此字段，读取方 .get() 容错。
    """
    d = os.path.dirname(jsonl_path)
    if d:
        os.makedirs(d, exist_ok=True)
    rec.setdefault("schema_version", SCHEMA_VERSION)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def rebuild_consolidated(json_path, jsonl_path, key):
    """由 jsonl 重建合并视图：同 key 取最后一次出现，顺序按 jsonl 首次出现。"""
    rows = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except FileNotFoundError:
        pass
    latest = {}
    for r in rows:
        latest[key(r)] = r
    cons = []
    for r in rows:                      # 同 key 重复时，只保留 latest 指向的那一条
        if latest.get(key(r)) is r:
            cons.append(r)
    if cons:
        d = os.path.dirname(json_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(cons, f, ensure_ascii=False, indent=1)
    return cons


def migrate_legacy(json_path, jsonl_path, key):
    """jsonl 不存在且旧合并视图 json 存在时，把旧记录迁入 jsonl（历史保全）。"""
    if os.path.exists(jsonl_path):
        return
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, encoding="utf-8") as f:
            legacy = json.load(f)
    except Exception:
        return
    for r in legacy:
        append_record(jsonl_path, r)
