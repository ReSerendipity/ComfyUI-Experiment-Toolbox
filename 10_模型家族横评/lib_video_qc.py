# -*- coding: utf-8 -*-
"""
视频质检库 vqc（E1 · 2026-10-16）
================================

为什么需要：工具箱视频侧此前只有「跑」（h3dur / fbench 视频档位），没有「检」。
本库对标 fiqc（lib_image_qc_enh.py，纯像素统计不做内容判断），做视频三层只读质检：

  L1 容器层（ffprobe JSON）
     时长 / 帧率 / 宽高 / 视频编码 / pix_fmt / 音频轨（编码 + 采样率 + 声道）
  L2 帧层（ffmpeg 抽帧 → gray rawvideo，纯 stdlib 消费字节，不落帧文件）
     黑帧 / 冻结帧 / 过曝帧
  L3 时序层（相邻帧差）
     MAD 均值 / p95 / max → 抖动与突变检测，无需光流等重依赖

设计红线（与全仓一致）：
  - 零 pip 依赖：ffmpeg / ffprobe 走 subprocess + shutil.which 探测；本机缺则明确
    SKIP（不把环境差异伪装成通过，也不在无 ffmpeg 的 runner 上误杀 CI）；
  - 只读不出片：抽帧走管道 `-f rawvideo -`，全程不写任何帧文件；
  - 无本机绝对路径：路径一律运行时展开（AGENTS.md 公开仓红线）；
  - 依赖方向：本模块零 toolbox import（Gate ⑥：10 轨只准 import 01，本库不 import）。

用法：
  python lib_video_qc.py --selftest                       # 合成三态自检（good / 黑帧 / 无音轨）
  python lib_video_qc.py --root <视频目录> [--pattern "*.mp4"]
  python lib_video_qc.py --file a.mp4 --expect-fps 24 --expect-audio
  python lib_video_qc.py --root <dir> --json vqc.json     # 结果落盘
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------- 默认阈值（改这里不改逻辑） ----------------
DEFAULT_CFG = {
    "max_frames": 60,        # 每个视频最多抽多少帧参与统计（抽帧均匀间隔）
    "frame_width": 320,      # 抽帧缩放宽度（等比定高，偶数），只做亮度统计够用
    "black_mean": 4.0,       # 帧均值 < 该值判黑帧（0-255）
    "over_mean": 250.0,      # 帧均值 > 该值判过曝帧
    "freeze_diff": 0.5,      # 与上一帧的 MAD < 该值判冻结帧
    # 阈值标定说明（2026-10-16，用本机 7 段已知正常的 H3 实产视频回归标定）：
    #   正常片的相邻帧差 p95 落在 22.5~119.6 区间（慢镜头 22.5、快镜头 119.6），
    #   故抖动阈值必须高于 120 才不会把正常内容误判；150 用于捕捉「整幅闪烁/跳变」。
    "jitter_p95": 150.0,     # 相邻帧差 p95 > 该值判极端抖动（warn）
    "bad_black_ratio": 0.20,  # 黑帧占比超过 → bad
    # 正常片的静止段占比最高到 0.31（11s 慢镜头），故冻结阈值取 0.60：
    # 只有「大半段不动」才算真冻结，慢镜头不误伤。
    "bad_freeze_ratio": 0.60,
    "fps_tol": 0.5,          # 帧率绝对容差
    "dur_tol": 0.5,          # 时长绝对容差（秒），仅在给期望值时生效
}

VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".avi", ".gif")

# 默认扫描根：与 fiqc / lib_ledger_verify 同口径（运行时展开，不写死本机绝对路径）。
# 全链 `run.py full` 里 vqc 不带 --root 时靠它兜底。
DEFAULT_ROOT = os.path.join(
    os.path.expandvars(r"%USERPROFILE%\APP\ComfyUI-aki-v3.2\ComfyUI"), "output")


def _which(exe):
    """探测 ffmpeg/ffprobe；返回 None 表示本机没有（调用方按需 SKIP）。"""
    return shutil.which(exe)


def _jsonable(obj):
    """把 numpy/bytes 之类不可序列化对象压成 JSON 友好形态（本库纯 stdlib，兜底用）。"""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, bool, int, float)) or obj is None:
        return obj
    return str(obj)


def depersonalize(p):
    """输出路径脱敏：本机主目录改写为 %USERPROFILE% 形态。

    沿用 lib_inventory_gate.depersonalize 的同款口径（公开仓红线，2026-10-15）：
    本报告会带 --json 落盘到 07_样例输出与数据/，那里是 tracked 目录，
    Gate ⑤ 会扫描 .json 里的字面本机绝对路径，不脱敏会直接把 CI 打红。
    兼容混合分隔符（正斜杠形态的输入路径，2026-10-16 修）。
    """
    home = os.path.expandvars(r"%USERPROFILE%")
    if not (home and home != "%USERPROFILE%" and p):
        return p
    if p.replace("/", "\\").startswith(home.replace("/", "\\")):
        return "%USERPROFILE%" + p[len(home):]
    return p


def _pct(sorted_vals, p):
    """线性插值分位数；空列表返回 None。"""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    idx = p * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


# ---------------- L1 容器层：ffprobe ----------------
def probe(path, ffprobe=None):
    """返回容器层元信息；ffprobe 缺失或失败时返回 {'ok': False, 'error': ...}。"""
    ffprobe = ffprobe or _which("ffprobe")
    if not ffprobe:
        return {"ok": False, "error": "ffprobe_not_found"}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "ffprobe_failed:%s" % type(e).__name__}
    if out.returncode != 0:
        return {"ok": False,
                "error": (out.stderr.decode("utf-8", "replace").strip() or "ffprobe_nonzero")[:200]}
    try:
        data = json.loads(out.stdout.decode("utf-8", "replace"))
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "ffprobe_json:%s" % type(e).__name__}

    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {}) or {}

    def _fps(stream):
        r = (stream or {}).get("avg_frame_rate") or (stream or {}).get("r_frame_rate") or "0/0"
        try:
            num, den = str(r).split("/")
            return float(num) / float(den) if float(den) else None
        except Exception:                                    # noqa: BLE001
            return None

    meta = {
        "ok": True,
        "duration": _fnum(fmt.get("duration")),
        "size_bytes": _fnum(fmt.get("size")),
        "bit_rate": _fnum(fmt.get("bit_rate")),
        "format_name": fmt.get("format_name"),
        "has_video": v is not None,
        "codec": (v or {}).get("codec_name"),
        "pix_fmt": (v or {}).get("pix_fmt"),
        "width": (v or {}).get("width"),
        "height": (v or {}).get("height"),
        "fps": _fps(v),
        "nb_frames": _fnum((v or {}).get("nb_frames")),
        "has_audio": a is not None,
        "audio_codec": (a or {}).get("codec_name"),
        "audio_sample_rate": _fnum((a or {}).get("sample_rate")),
        "audio_channels": (a or {}).get("channels"),
    }
    if not meta["has_video"]:
        meta["ok"] = False
        meta["error"] = "no_video_stream"
    return meta


def _fnum(x):
    try:
        f = float(x)
        return int(f) if f.is_integer() and abs(f) < 1e15 else f
    except Exception:                                        # noqa: BLE001
        return None


# ---------------- L2/L3 帧层与时序层：ffmpeg 抽帧 → gray rawvideo ----------------
def _extract_gray(path, meta, cfg, ffmpeg):
    """抽帧为灰度原始流，返回 (frames[bytes], w, h)；失败返回 (None, 0, 0)。"""
    w, h = meta.get("width"), meta.get("height")
    if not w or not h:
        return None, 0, 0
    dur = meta.get("duration") or 0.0
    fps = meta.get("fps") or 25.0
    total = int(dur * fps) if dur and fps else 0
    # 均匀抽样：按目标帧数反推采样 fps，保证长视频也能覆盖全程
    if total > cfg["max_frames"] and dur > 0:
        sample = max(0.2, cfg["max_frames"] / float(dur))
    else:
        sample = fps if fps > 0 else 25.0

    tw = int(cfg["frame_width"])
    th = max(2, int(round(tw * float(h) / float(w))))
    if th % 2:
        th += 1
    vf = "fps=%.4f,scale=%d:%d,format=gray" % (sample, tw, th)
    try:
        out = subprocess.run(
            [ffmpeg, "-v", "error", "-i", path, "-vf", vf,
             "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except Exception:                                        # noqa: BLE001
        return None, 0, 0
    if out.returncode != 0:
        return None, 0, 0
    raw = out.stdout
    fs = tw * th
    n = len(raw) // fs
    if n == 0:
        return None, 0, 0
    return [raw[i * fs:(i + 1) * fs] for i in range(n)], tw, th


def _mean(buf, stride=3):
    """灰度帧均值（0-255）；stride 抽样加速，统计目的足够。"""
    if not buf:
        return 0.0
    s = buf[::stride]
    return sum(s) / float(len(s))


def _mad(a, b, stride=3):
    """相邻帧平均绝对差（0-255）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    sa, sb = a[::stride], b[::stride]
    total = 0
    for x, y in zip(sa, sb):
        total += (x - y) if x >= y else (y - x)
    return total / float(len(sa))


def frame_stats(path, meta, cfg, ffmpeg=None):
    """L2 黑/冻结/过曝 + L3 抖动；返回统计字典或 {'ok': False, 'error': ...}。"""
    ffmpeg = ffmpeg or _which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "error": "ffmpeg_not_found"}
    frames, tw, th = _extract_gray(path, meta, cfg, ffmpeg)
    if frames is None:
        return {"ok": False, "error": "extract_failed"}
    means = [_mean(f) for f in frames]
    diffs = [_mad(frames[i - 1], frames[i]) for i in range(1, len(frames))]

    n = len(frames)
    black = sum(1 for m in means if m < cfg["black_mean"])
    over = sum(1 for m in means if m > cfg["over_mean"])
    frozen = sum(1 for d in diffs if d < cfg["freeze_diff"])
    nd = max(1, len(diffs))
    sd = sorted(diffs)
    return {
        "ok": True,
        "frames_sampled": n,
        "frame_size": "%dx%d" % (tw, th),
        "luma_mean": round(sum(means) / n, 3),
        "luma_min": round(min(means), 3),
        "luma_max": round(max(means), 3),
        "black_frames": black,
        "over_frames": over,
        "freeze_frames": frozen,
        "black_ratio": round(black / float(n), 4),
        "over_ratio": round(over / float(n), 4),
        "freeze_ratio": round(frozen / float(nd), 4),
        "motion_mean": round(sum(diffs) / nd, 3) if diffs else 0.0,
        "motion_p95": round(_pct(sd, 0.95), 3) if sd else 0.0,
        "motion_max": round(sd[-1], 3) if sd else 0.0,
    }


# ---------------- 单文件分析 ----------------
def analyze(path, cfg=None, expect=None):
    """单视频质检：返回 row（含 verdict / flags / 三层指标）。"""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    cfg = merged                      # 阈值以默认值为底、用调用方覆盖项补齐
    expect = expect or {}
    row = {"file": os.path.basename(path), "path": path, "ok": True, "flags": []}

    meta = probe(path)
    row["meta"] = meta
    if not meta.get("ok"):
        row["ok"] = False
        row["error"] = meta.get("error")
        row["verdict"] = "failed"
        return row

    # L1 维度校验（仅在给出期望值时判定，未给则只记录）
    if expect.get("fps") and meta.get("fps"):
        if abs(meta["fps"] - float(expect["fps"])) > cfg["fps_tol"]:
            row["flags"].append("fps_mismatch")
    if expect.get("duration") and meta.get("duration"):
        if abs(meta["duration"] - float(expect["duration"])) > cfg["dur_tol"]:
            row["flags"].append("duration_mismatch")
    if expect.get("width") and meta.get("width"):
        if int(meta["width"]) != int(expect["width"]):
            row["flags"].append("width_mismatch")
    if expect.get("height") and meta.get("height"):
        if int(meta["height"]) != int(expect["height"]):
            row["flags"].append("height_mismatch")
    if expect.get("audio") and not meta.get("has_audio"):
        row["flags"].append("no_audio")
    if expect.get("audio_sample_rate") and meta.get("audio_sample_rate"):
        if abs(meta["audio_sample_rate"] - float(expect["audio_sample_rate"])) > 1:
            row["flags"].append("audio_rate_mismatch")
    # 无视频轨/无音频轨（未声明期望也做客观记录：无视频轨是硬错）
    if not meta.get("has_video"):
        row["flags"].append("no_video_stream")

    # L2/L3
    st = frame_stats(path, meta, cfg)
    row["frames"] = st
    if st.get("ok"):
        if st["black_ratio"] > cfg["bad_black_ratio"]:
            row["flags"].append("black_frame")
        elif st["black_frames"] > 0:
            row["flags"].append("black_frame_sparse")
        if st["freeze_ratio"] > cfg["bad_freeze_ratio"]:
            row["flags"].append("freeze_frame")
        elif st["freeze_frames"] > 0:
            row["flags"].append("freeze_frame_sparse")
        if st["over_ratio"] > cfg["bad_black_ratio"]:
            row["flags"].append("overexposed")
        if st["motion_p95"] > cfg["jitter_p95"]:
            row["flags"].append("high_jitter")
    else:
        row["flags"].append("frames_probe_skipped")

    # 判定：failed > bad > warn > ok
    #   hard  占比级硬错（整段黑/整段不动/整段过曝/没音轨/没视频轨）
    #   soft  客观不符期望（帧率/时长/尺寸/采样率）+ 极端抖动
    #   info  零星帧级现象（只记录，不影响判定——正常片开头常有一两帧暗帧）
    hard = {"no_video_stream", "no_audio", "black_frame", "freeze_frame", "overexposed"}
    soft = {"fps_mismatch", "duration_mismatch", "width_mismatch", "height_mismatch",
            "audio_rate_mismatch", "high_jitter", "frames_probe_skipped"}
    f = set(row["flags"])
    row["info"] = sorted(f & {"black_frame_sparse", "freeze_frame_sparse"})
    if f & hard:
        row["verdict"] = "bad"
    elif f & soft:
        row["verdict"] = "warn"
    else:
        row["verdict"] = "ok"
    return row


def analyze_dir(root, cfg=None, pattern=None, recursive=True, limit=0, expect=None):
    """目录级质检：返回 report（含 rows / verdict / flag_count / aggregate）。"""
    if not os.path.isdir(root):
        return {"ok": False, "error": "not_a_dir", "root": os.path.abspath(root)}
    files = []
    if recursive:
        for dirpath, _dn, names in os.walk(root):
            for n in sorted(names):
                if n.lower().endswith(VIDEO_EXT):
                    files.append(os.path.join(dirpath, n))
    else:
        for n in sorted(os.listdir(root)):
            p = os.path.join(root, n)
            if os.path.isfile(p) and n.lower().endswith(VIDEO_EXT):
                files.append(p)
    if limit and len(files) > limit:
        files = files[:limit]

    rows = [analyze(p, cfg, expect) for p in files]
    verdict = {"ok": 0, "warn": 0, "bad": 0, "failed": 0}
    flag_count = {}
    for r in rows:
        verdict[r["verdict"]] = verdict.get(r["verdict"], 0) + 1
        for f in r["flags"]:
            flag_count[f] = flag_count.get(f, 0) + 1
    return {"ok": True, "root": os.path.abspath(root), "scanned": len(files),
            "analyzed": sum(1 for r in rows if r["ok"]), "verdict": verdict,
            "flag_count": flag_count, "rows": rows}


# ---------------- 合成三态自检（CI 用） ----------------
def _gen_video(path, ffmpeg, source, with_audio=True, dur=2):
    """用 ffmpeg lavfi 合成一段 2 秒 320x180@24fps 的测试视频。

    source 是**完整滤镜串**（不是滤镜名）：各 lavfi 源的参数名不统一
    （testsrc/mandelbrot 用 size/rate，color 用 s/r），只有整串传入才不会拼错。
    """
    cmd = [ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", source]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=%d" % dur]
        cmd += ["-c:a", "aac", "-shortest"]
    else:
        cmd += ["-an"]
    # 时长统一用 -t 控制：并非所有 lavfi 源都支持 duration=（mandelbrot 就没有），
    # 写在源串里会报 "Option not found"。
    cmd += ["-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", path]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    return r.returncode == 0, (r.stderr.decode("utf-8", "replace").strip()[-200:])


def _selftest_synthetic():
    """合成三态自检，返回 [(msg, ok)]；无 ffmpeg/ffprobe 时返回单条 SKIP（不算失败）。"""
    ffmpeg, ffprobe = _which("ffmpeg"), _which("ffprobe")
    if not (ffmpeg and ffprobe):
        return [("ffmpeg/ffprobe 缺失 → 视频质检自检跳过（CI runner 无 ffmpeg 属可接受降级）", None)]
    steps = []
    tmp = tempfile.mkdtemp(prefix="vqc_selftest_")
    try:
        # 注意：good 用 mandelbrot（持续缩放、全画面有运动）而非 testsrc——
        # testsrc 的整帧灰度均值几乎恒定（实测 MAD≈0.45），会被冻结判定误伤，
        # 用它当「正常片」样本属于样本本身不合格。
        cases = [
            ("good", "mandelbrot=size=320x180:rate=24", True, [],
             "正常片：无黑帧/无冻结/有音轨"),
            ("black", "color=c=black:s=320x180:r=24:d=2", True, ["black_frame"],
             "必须命中黑帧"),
            ("silent", "mandelbrot=size=320x180:rate=24", False, ["no_audio"],
             "必须命中无音轨（期望有音轨，实际无）"),
        ]
        for name, src, audio, want_flags, note in cases:
            p = os.path.join(tmp, "%s.mp4" % name)
            made, err = _gen_video(p, ffmpeg, src, audio)
            if not made:
                steps.append(("合成样本 %s 失败：%s" % (name, err), False))
                continue
            # 三个用例一律「期望有音轨」：silent 用例正是靠这个期望值触发 no_audio
            row = analyze(p, None, {"fps": 24, "audio": True})
            got = set(row["flags"])
            miss = [f for f in want_flags if f not in got]
            if miss:
                steps.append(("样本 %s（%s）未命中 %s，实际 flags=%s"
                              % (name, note, miss, sorted(got)), False))
            elif name == "good" and got & {"black_frame", "freeze_frame", "no_audio"}:
                steps.append(("样本 good 不应命中黑帧/冻结/无音轨，实际 flags=%s" % sorted(got), False))
            else:
                steps.append(("样本 %s：%s → flags=%s verdict=%s"
                              % (name, note, sorted(got) or "无", row["verdict"]), True))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return steps


# ---------------- CLI ----------------
def _fmt(report):
    if not report.get("ok"):
        return "[ERR] %s: %s" % (report.get("error"), report.get("root"))
    lines = ["root    : %s" % report["root"],
             "scanned : %d   analyzed: %d" % (report["scanned"], report["analyzed"]),
             "verdict : %s" % report["verdict"],
             "",
             "%-34s %-8s %-9s %-7s %-7s %-8s %-8s %s" %
             ("file", "verdict", "dur(s)", "fps", "WxH", "audio", "motion", "flags")]
    for r in report["rows"]:
        m = r.get("meta") or {}
        f = r.get("frames") or {}
        audio = ("%s/%skHz/%sch" % (m.get("audio_codec"),
                                    (m.get("audio_sample_rate") or 0) / 1000.0,
                                    m.get("audio_channels"))) if m.get("has_audio") else "-"
        lines.append("%-34s %-8s %-9s %-7s %-7s %-8s %-8s %s" % (
            (r["file"] or "")[:34], r["verdict"],
            m.get("duration"), m.get("fps"),
            "%sx%s" % (m.get("width"), m.get("height")) if m.get("width") else "-",
            audio, f.get("motion_p95"), ",".join(r["flags"]) or "-"))
    if report["flag_count"]:
        lines.append("")
        lines.append("flags   : %s" % report["flag_count"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="视频质检库（ffprobe 容器层 + 抽帧层 + 时序层，只读）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="视频目录（默认 ComfyUI output）")
    ap.add_argument("--file", default=None, help="只分析单个文件")
    ap.add_argument("--pattern", default=None, help="已废弃：按扩展名自动识别，保留以兼容调用方")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="最多分析几个，0=全量")
    ap.add_argument("--json", default=None, help="结果写到此 JSON")
    ap.add_argument("--expect-fps", type=float, default=None)
    ap.add_argument("--expect-duration", type=float, default=None)
    ap.add_argument("--expect-width", type=int, default=None)
    ap.add_argument("--expect-height", type=int, default=None)
    ap.add_argument("--expect-audio", action="store_true", help="要求必须有音轨")
    ap.add_argument("--expect-audio-rate", type=float, default=None, help="期望采样率 Hz")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--selftest", action="store_true", help="合成三态自检（good/黑帧/无音轨）")
    a = ap.parse_args(argv)

    if a.selftest:
        steps = _selftest_synthetic()
        bad = 0
        for msg, ok in steps:
            print(("SKIP " if ok is None else ("OK   " if ok else "FAIL ")) + msg)
            if ok is False:
                bad += 1
        return 1 if bad else 0

    cfg = dict(DEFAULT_CFG)
    if a.max_frames:
        cfg["max_frames"] = a.max_frames
    expect = {}
    for k, v in (("fps", a.expect_fps), ("duration", a.expect_duration),
                 ("width", a.expect_width), ("height", a.expect_height),
                 ("audio", a.expect_audio), ("audio_sample_rate", a.expect_audio_rate)):
        if v:
            expect[k] = v

    if a.file:
        row = analyze(a.file, cfg, expect)
        rep = {"ok": row["ok"], "root": os.path.abspath(a.file), "scanned": 1,
               "analyzed": 1 if row["ok"] else 0,
               "verdict": {row["verdict"]: 1},
               "flag_count": {f: 1 for f in row["flags"]}, "rows": [row]}
        print(_fmt(rep))
        verdict_out = row["verdict"]
    elif a.root:
        rep = analyze_dir(a.root, cfg, None, not a.no_recursive, a.limit, expect)
        print(_fmt(rep))
        verdict_out = None
    else:
        ap.error("需要 --root / --file / --selftest 之一")

    if a.json:
        # 落盘前脱敏：报告的 root / 每个 row 的 path 都可能是本机绝对路径
        rep_out = _jsonable(rep)
        if isinstance(rep_out.get("root"), str):
            rep_out["root"] = depersonalize(rep_out["root"])
        for row in rep_out.get("rows", []):
            if isinstance(row.get("path"), str):
                row["path"] = depersonalize(row["path"])
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep_out, fh, ensure_ascii=False, indent=1)
        print("json ->", os.path.abspath(a.json))
    if verdict_out == "bad":
        return 2
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
