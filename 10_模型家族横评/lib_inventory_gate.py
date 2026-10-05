# -*- coding: utf-8 -*-
"""
模型家族横评 P1 增强 · lib① 名册基线门禁（inventory gate）。

思路出处（只借鉴思路，不 import、不拷项目专属字段）
    Picture/tools/inventory_gate.py 的 docstring 与结构：把「批次开始前对账名册、
    发现静默漂移就停机」这条工程能力抽成一个纯函数库。本库与它的差别：
      · 不认识 SFW/NSFW/cos 三库、只认 root + globs（家族横评的对象是权重与产物树）；
      · 基线记 rel/size/sha256/mtime 四元组（对方的 roster 只记文件名列表 + md5 指纹，
        抓不到「同一文件名内容被换掉」这种静默漂移）；
      · check() 返回 report 字典并带 exit 语义，不自己写文件——落盘由调用方决定。

三种漂移态（三态即本库存在的理由）
    added   —— 基线里没有、现在多出来的（有人塞了文件/换目录）
    removed —— 基线里有、现在不见的（文件被删/被移走/盘符掉了）
    changed —— 两边同名同在，但 size 或 sha256 变了（权重被静默替换 = 最危险的一态）
    mtime_only 单独列出，不算漂移（只是被 touch 过），便于区分「重写了」与「读过」。

为什么必须有：discover_families 靠 SHA256 去重、analyze_family 按 ledger 记账，
三者都默认「磁盘上那份就是基线里那份」。一旦有人替换/删除权重，报告里的横向对比
会静默失真而不留任何痕迹。本库就是那道闸——批次开工前 check 一次，收工再 baseline。

零依赖（纯标准库）。不 import bench_family / discover_families / analyze_family，
故 import 本模块无任何副作用。

用法（必须用 ComfyUI 自带 python）：
    python lib_inventory_gate.py selftest --root "C:/.../ComfyUI/models/unet"
    python lib_inventory_gate.py build  --root <unet 根> --glob "*.safetensors" --out gate.json
    python lib_inventory_gate.py check  --baseline gate.json
    python lib_inventory_gate.py build --root <unet 根> --max-hash-mb 512   # 只哈希小文件
退出码：0 零漂移 / 1 有漂移（已列明细）/ 2 用法或 IO 错。
"""
import argparse
import fnmatch
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True

SCHEMA = "inventory-gate/1"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COMFY = r"C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI"

# ComfyUI 各 models/ 子目录都有的 0 字节占位文件，不是权重，进名册只会制造噪声。
# 另有下载中断残片与日志类垃圾。注意：本库只「记账」，删文件是人的事。
DEFAULT_IGNORE = (
    "put_unet_files_here",
    "*.tmp", "*.temp", "*.part", "*.partial", "*.crdownload", "*.download",
    "*.log", "*.bak", "*~",
    "thumbs.db", "desktop.ini", ".DS_Store",
    "__pycache__", "*.pyc", "*.pyo",
)
DEFAULT_IGNORE_DIRS = ("__pycache__", ".git", ".svn", ".cache")
CHUNK = 1 << 22  # 4 MiB，与 discover_families.sha256_of 同口径


class GateError(Exception):
    """用法/IO 错 → main() 映射为退出码 2。"""


# ── 小工具 ──────────────────────────────────────────────────────────────────
def _sha256_of(path, chunk=CHUNK):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def _norm_rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")


def _ignored(rel, base, patterns):
    if not patterns:
        return False
    for pat in patterns:
        pat = pat.replace("\\", "/")
        # basename 与整条 rel 都试一遍：目录级模式（如 "*/cache/*"）才有意义
        if fnmatch.fnmatchcase(base, pat) or fnmatch.fnmatchcase(rel, pat):
            return True
    return False


def _matched(rel, base, globs):
    if not globs:
        return True
    r, b, l = rel.lower(), base.lower(), [g.lower().replace("\\", "/") for g in globs]
    return any(fnmatch.fnmatchcase(r, g) or fnmatch.fnmatchcase(b, g) for g in l)


def _roster_digest(files):
    """名册指纹：按 rel 排序拼 "rel:size:sha256|mtime" 再 sha256。
    sha256 为 None（跳过 payload 哈希）时退化为用 size+mtime 占位，两次 build 必须同值。"""
    lines = []
    for rel in sorted(files):
        e = files[rel]
        lines.append("%s:%s:%s:%s" % (rel, e["size"], e.get("sha256"), e.get("mtime")))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# ── API ①：建基线 ──────────────────────────────────────────────────────────
def build_baseline(root, globs=("*",), ignore=DEFAULT_IGNORE,
                   ignore_dirs=DEFAULT_IGNORE_DIRS, recursive=True,
                   hash_limit_bytes=0, now=None):
    """扫 root 下的文件建名册基线（只读）。

    参数
        root              被扫目录，如 <comfy>/models/unet
        globs             白名单通配（对 basename 与 rel 同时匹配，大小写不敏感）
        ignore            黑名单通配，默认 DEFAULT_IGNORE（含 put_unet_files_here）
        ignore_dirs       整目录跳过的目录名，默认 DEFAULT_IGNORE_DIRS
        recursive         True 递归（unet 根目录按家族分子文件夹，必须递归）
        hash_limit_bytes  >0 时，超过此体积的文件只记 size+mtime、sha256=None
                          （单文件 17 GB 时全量哈希要几十秒，排查阶段可用它换速度；
                          注意：跳过哈希的文件其 changed 判定退化为 size+mtime）
    返回 dict（可直接 json.dump 落盘）
    """
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise GateError("找不到被扫目录：%s" % root)
    t0 = time.time()
    files = {}
    skipped_hash = []
    if recursive:
        walker = os.walk(root)
    else:
        walker = [(root, [], sorted(os.listdir(root)))]
    for r, ds, fs in walker:
        if recursive:
            ds[:] = sorted(d for d in ds if d not in ignore_dirs)
        for fn in sorted(fs):
            p = os.path.join(r, fn)
            if not os.path.isfile(p):
                continue
            rel = _norm_rel(p, root)
            if _ignored(rel, fn, ignore) or _matched(rel, fn, globs) is False:
                continue
            st = os.stat(p)
            if hash_limit_bytes and st.st_size > hash_limit_bytes:
                h = None
                skipped_hash.append(rel)
            else:
                h = _sha256_of(p)
            files[rel] = {
                "size": int(st.st_size),
                "sha256": h,
                "mtime": round(st.st_mtime, 3),
                "mtime_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                "hash_mode": "skipped" if h is None else "full",
            }
    total_bytes = sum(e["size"] for e in files.values())
    hashed_bytes = sum(e["size"] for e in files.values() if e["sha256"])
    base = {
        "schema": SCHEMA,
        "root": root,
        "globs": list(globs),
        "ignore": list(ignore),
        "ignore_dirs": list(ignore_dirs),
        "recursive": bool(recursive),
        "hash_limit_bytes": int(hash_limit_bytes),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S") if now is None else now,
        "count": len(files),
        "total_bytes": total_bytes,
        "hashed_bytes": hashed_bytes,
        "hash_skipped": sorted(skipped_hash),
        "digest": _roster_digest(files),
        "files": files,
        "elapsed_s": round(time.time() - t0, 1),
    }
    return base


# ── API ②：对账 ────────────────────────────────────────────────────────────
def check(baseline, root=None, globs=None, ignore=None, ignore_dirs=None,
          recursive=None, hash_limit_bytes=None):
    """拿基线与当前磁盘对账 → 三态漂移报告（只读，不写任何文件）。

    返回 dict：
        ok         bool  零漂移为 True
        exit_code  0=零漂移 1=有漂移（调用方直接 sys.exit(report["exit_code"])）
        counts     {added, removed, changed, mtime_only, count_base, count_cur}
        added      [rel]
        removed    [rel]
        changed    [{rel, fields, base:{...}, cur:{...}}]
        mtime_only [rel]                     只被 touch、内容未变 → 不算漂移
        digests    {base, cur}
    """
    if not isinstance(baseline, dict) or baseline.get("schema") != SCHEMA:
        raise GateError("不是本库的基线（schema=%r，应为 %r）"
                        % (baseline.get("schema") if isinstance(baseline, dict) else type(baseline),
                           SCHEMA))
    bfiles = baseline.get("files") or {}
    cur = build_baseline(
        root or baseline["root"],
        globs if globs is not None else baseline.get("globs") or ("*",),
        ignore if ignore is not None else baseline.get("ignore", DEFAULT_IGNORE),
        ignore_dirs if ignore_dirs is not None else baseline.get("ignore_dirs", DEFAULT_IGNORE_DIRS),
        baseline.get("recursive", True) if recursive is None else recursive,
        baseline.get("hash_limit_bytes", 0) if hash_limit_bytes is None else hash_limit_bytes,
    )
    cfiles = cur["files"]
    bset, cset = set(bfiles), set(cfiles)

    added = sorted(cset - bset)
    removed = sorted(bset - cset)
    changed, mtime_only = [], []
    for rel in sorted(bset & cset):
        b, c = bfiles[rel], cfiles[rel]
        fields = []
        if b.get("size") != c.get("size"):
            fields.append("size")
        if b.get("sha256") and c.get("sha256"):
            if b["sha256"] != c["sha256"]:
                fields.append("sha256")
        elif b.get("hash_mode") == "skipped" or c.get("hash_mode") == "skipped":
            # 两边都跳过了 payload 哈希（或只有一边跳）→ 只能按 mtime 判，此时算 changed
            if b.get("mtime") != c.get("mtime"):
                fields.append("mtime(size_mtime_fallback)")
        if fields:
            changed.append({"rel": rel, "fields": fields,
                            "base": {k: b.get(k) for k in ("size", "sha256", "mtime")},
                            "cur": {k: c.get(k) for k in ("size", "sha256", "mtime")}})
        elif b.get("mtime") != c.get("mtime"):
            mtime_only.append(rel)

    drift = bool(added or removed or changed)
    report = {
        "ok": not drift,
        "exit_code": 0 if not drift else 1,
        "root": cur["root"],
        "globs": cur["globs"],
        "hash_limit_bytes": cur["hash_limit_bytes"],
        "counts": {
            "count_base": len(bfiles), "count_cur": len(cfiles),
            "added": len(added), "removed": len(removed),
            "changed": len(changed), "mtime_only": len(mtime_only),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "mtime_only": mtime_only,
        "digests": {"base": baseline.get("digest"), "cur": cur["digest"]},
        "digest_match": baseline.get("digest") == cur["digest"],
        "elapsed_s": cur["elapsed_s"],
    }
    return report


def format_report(report, limit=15):
    """把 report 渲染成给人看的多行文本（纯函数，不打印）。"""
    c = report["counts"]
    L = ["名册门禁  root=%s  globs=%s%s"
         % (report["root"], ",".join(report["globs"]),
            ("  (大文件只记 size+mtime)" if report["hash_limit_bytes"] else "")),
         "  基线 %d 个 / 当前 %d 个   指纹 base=%s cur=%s  %s"
         % (c["count_base"], c["count_cur"], (report["digests"]["base"] or "?")[:16],
            (report["digests"]["cur"] or "?")[:16],
            "一致" if report["digest_match"] else "不一致"),
         "  三态漂移：新增 %d / 消失 %d / 变更 %d   （只被 touch %d，不算漂移）"
         % (c["added"], c["removed"], c["changed"], c["mtime_only"])]
    for x in report["added"][:limit]:
        L.append("    [新增] " + x)
    if len(report["added"]) > limit:
        L.append("    [新增] …共 %d 条" % c["added"])
    for x in report["removed"][:limit]:
        L.append("    [消失] " + x)
    if len(report["removed"]) > limit:
        L.append("    [消失] …共 %d 条" % c["removed"])
    for ch in report["changed"][:limit]:
        L.append("    [变更] %s  %s  base=%s cur=%s"
                 % (ch["rel"], ",".join(ch["fields"]),
                    ch["base"].get("sha256", "-")[:12], ch["cur"].get("sha256", "-")[:12]))
    if len(report["changed"]) > limit:
        L.append("    [变更] …共 %d 条" % c["changed"])
    L.append("  结论：" + ("零漂移 ✅（exit 0）" if report["ok"]
                        else "检测到静默漂移 ⚠（exit 1）；确认合法改动后重建基线再继续"))
    return "\n".join(L)


# ── API ③：基线落盘/读盘（只给调用方用；本模块自身不会在自测里写工作区）────────
def save_baseline(path, baseline):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=1, sort_keys=True)
    return path


def load_baseline(path):
    if not os.path.isfile(path):
        raise GateError("基线文件不存在：%s" % path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── __main__ ───────────────────────────────────────────────────────────────
def _selftest_synthetic():
    """合成目录：把 added/removed/changed 三态与 ignore 逻辑各打一次。"""
    import shutil
    import tempfile
    td = tempfile.mkdtemp(prefix="invgate_")
    steps = []
    try:
        os.makedirs(os.path.join(td, "sub"))
        open(os.path.join(td, "put_unet_files_here"), "w").close()
        open(os.path.join(td, "a.txt"), "w").write("alpha")
        open(os.path.join(td, "sub", "b.bin"), "wb").write(b"bravo")
        open(os.path.join(td, "junk.tmp"), "w").write("noise")

        b0 = build_baseline(td, globs=("*",))
        steps.append(("build#1 count=%d digest=%s" % (b0["count"], b0["digest"][:12]),
                      b0["count"] == 2))  # put_unet_files_here + junk.tmp 被 ignore 掉

        r0 = check(b0)
        steps.append(("check 零漂移 exit=%d added=%d removed=%d changed=%d"
                      % (r0["exit_code"], r0["counts"]["added"],
                         r0["counts"]["removed"], r0["counts"]["changed"]),
                      r0["ok"] and r0["exit_code"] == 0))

        open(os.path.join(td, "a.txt"), "w").write("alpha-REPLACED")   # 同名换内容
        os.remove(os.path.join(td, "sub", "b.bin"))                   # 消失
        open(os.path.join(td, "c.txt"), "w").write("charlie")          # 新增
        os.utime(os.path.join(td, "c.txt"), (0, 0))                   # 极端 mtime 也不该误报
        r1 = check(b0)
        ok1 = (r1["counts"]["added"] == 1 and r1["counts"]["removed"] == 1
               and r1["counts"]["changed"] == 1 and r1["exit_code"] == 1
               and r1["added"] == ["c.txt"] and r1["removed"] == ["sub/b.bin"]
               and r1["changed"][0]["rel"] == "a.txt")
        steps.append(("check 三态 added=%d removed=%d changed=%d exit=%d"
                      % (r1["counts"]["added"], r1["counts"]["removed"],
                         r1["counts"]["changed"], r1["exit_code"]), ok1))

        open(os.path.join(td, "a.txt"), "w").write("alpha")            # 改回原内容
        r2 = check(b0)
        steps.append(("改回原内容后 changed=%d（mtime 变了但内容同 → 不算漂移）"
                      % r2["counts"]["changed"], r2["counts"]["changed"] == 0))

        b2 = build_baseline(td)
        r3 = check(b2)
        steps.append(("重建基线后 check 零漂移 exit=%d" % r3["exit_code"], r3["ok"]))
    finally:
        shutil.rmtree(td, ignore_errors=True)
    return steps


def _selftest_real(root, globs, hash_limit_bytes):
    """对真实 unet 根目录 build → check，期望零漂移。"""
    out = []
    if not os.path.isdir(root):
        out.append(("真实目录不存在，跳过：%s" % root, None))
        return out, False
    t0 = time.time()
    b = build_baseline(root, globs=globs, hash_limit_bytes=hash_limit_bytes)
    out.append(("build  count=%d  total=%.1f GB  已哈希 payload=%.1f GB  跳过=%d  %.1fs"
                % (b["count"], b["total_bytes"] / 2**30, b["hashed_bytes"] / 2**30,
                   len(b["hash_skipped"]), b["elapsed_s"]), True))
    for rel in b["hash_skipped"][:5]:
        out.append(("    跳过哈希：%s" % rel, None))
    if b["hash_skipped"]:
        out.append(("    …共 %d 个大文件（其 changed 判定按 size+mtime）"
                    % len(b["hash_skipped"]), None))
    for rel in list(b["files"])[:12]:
        e = b["files"][rel]
        out.append(("    %-58s %10.1f MB  %s" % (rel[:58], e["size"] / 2**20,
                                                (e["sha256"] or "(skip)")[:16]), None))
    if len(b["files"]) > 12:
        out.append(("    …共 %d 个文件" % b["count"], None))
    r = check(b)
    ok = r["ok"] and r["exit_code"] == 0 and r["digest_match"]
    out.append(("check  基线 %d / 当前 %d   added=%d removed=%d changed=%d mtime_only=%d"
                % (r["counts"]["count_base"], r["counts"]["count_cur"],
                   r["counts"]["added"], r["counts"]["removed"],
                   r["counts"]["changed"], r["counts"]["mtime_only"]), ok))
    out.append(("check  exit=%d  %s" % (r["exit_code"], "零漂移 ✅" if ok else "有漂移 ⚠"), ok))
    out.append(("build+check 合计 %.1fs" % (time.time() - t0), None))
    return out, ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="名册基线门禁（纯函数库）")
    ap.add_argument("mode", choices=("build", "check", "selftest"))
    ap.add_argument("--root", default=os.path.join(DEFAULT_COMFY, "models", "unet"))
    ap.add_argument("--baseline", default=None, help="check 模式读哪个基线 json")
    ap.add_argument("--out", default=None, help="build 模式的落盘路径")
    ap.add_argument("--glob", nargs="*", default=["*"])
    ap.add_argument("--ignore", nargs="*", default=None, help="覆盖默认黑名单")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--max-hash-mb", type=float, default=0,
                    help=">0 时超过该体积的文件只记 size+mtime（sha256=null）")
    ap.add_argument("--limit", type=int, default=15, help="明细打印上限")
    a = ap.parse_args(argv)
    hlb = int(a.max_hash_mb * 2**20)

    try:
        if a.mode == "build":
            b = build_baseline(a.root, globs=tuple(a.glob),
                               ignore=tuple(a.ignore) if a.ignore else DEFAULT_IGNORE,
                               recursive=not a.no_recursive, hash_limit_bytes=hlb)
            print("基线已建立  count=%d  total=%.2f GB  digest=%s"
                  % (b["count"], b["total_bytes"] / 2**30, b["digest"]))
            print("耗时 %.1fs%s" % (b["elapsed_s"],
                                   ("  跳过哈希 %d 个大文件" % len(b["hash_skipped"]))
                                   if b["hash_skipped"] else ""))
            if a.out:
                save_baseline(a.out, b)
                print("已写出：%s" % a.out)
            return 0

        if a.mode == "check":
            path = a.baseline or os.path.join(HERE, "gate_baseline.json")
            r = check(load_baseline(path))
            print(format_report(r, a.limit))
            return r["exit_code"]

        # selftest
        print("=" * 78)
        print("  lib_inventory_gate 自测")
        print("=" * 78)
        print("\n[A] 合成目录三态演练（临时目录，已清理）")
        syn = _selftest_synthetic()
        for msg, ok in syn:
            print("  %-4s %s" % ("OK" if ok else ("FAIL" if ok is False else "--"), msg))
        print("\n[B] 真实 unet 根目录 build → check（期望零漂移）")
        print("  root=%s" % a.root)
        rows, ok_real = _selftest_real(a.root, tuple(a.glob), hlb)
        for msg, ok in rows:
            print("  %-4s %s" % ("OK" if ok else ("FAIL" if ok is False else "--"), msg))
        syn_ok = all(ok is not False for _, ok in syn)
        print("\n结论：合成=%s 真实=%s" % ("PASS" if syn_ok else "FAIL",
                                          "PASS" if ok_real else "FAIL"))
        return 0 if (syn_ok and ok_real) else 1
    except GateError as e:
        print("[x] %s" % e)
        return 2
    except OSError as e:
        print("[x] IO 错：%s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())