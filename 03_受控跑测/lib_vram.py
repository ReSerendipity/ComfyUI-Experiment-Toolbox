# -*- coding: utf-8 -*-
"""
显存预算探测与档位自适应（E2 · 2026-10-16）
==========================================

解决的问题（2026-10-14 实测踩坑）：视频跑测的时长-分辨率边界此前是**人工标定**的
一张死表，跑超了就 OOM（10s/11s/15s 峰值 12.15~12.24GB > 11.91GB 可用），
只能靠人发现、人改参数、人重跑。本库把这条链路自动化：

  sniff()          → 探测当前可用显存（nvidia-smi，无则明确降级）
  start_tier()      → 按时长 + 预算推荐起始分辨率档
  is_oom()          → 从 ComfyUI 报错文本里识别 OOM（不是所有 exec_error 都是 OOM）
  downgrade_chain() → 从起始档到底档的降档链（OOM 时逐档退）

边界：
  - 纯 stdlib，nvidia-smi 走 subprocess；探测不到不伪装成功，返回 ok=False 让调用方
    「按预算兜底」而不是「按 0 显存跑」；
  - 阈值常量集中在顶部，换卡只改常量不改逻辑；
  - 本库不提交任何任务，只做决策（跑测器负责执行与重试）。

用法：
  python lib_vram.py --selftest      # 无 GPU 也能跑的纯逻辑自检（CI 可纳）
  python lib_vram.py                 # 打印本机显存快照 + 各时长推荐档
"""
import os
import re
import shutil
import subprocess

# ---------------- 常量（换显卡只改这里） ----------------
# 分辨率阶梯：下标越大越省显存。2026-10-14 在 12GB 可用显存上实测标定的 H3 边界。
LADDER = [(1344, 768), (1152, 640), (960, 544)]

# 时长 → 起始档下标：≤8s 顶档可跑；≤10s 需降一档；更长需降到底档
DURATION_TIER = [(8.0, 0), (10.0, 1)]

BUDGET_REF_GIB = 11.91   # 标定上述阶梯时的可用显存（RTX 5070 Ti Laptop 实测）
GB_PER_TIER = 1.0        # 启发式：可用显存每比基准少 1GB，起始档再降一档

# OOM 特征（ComfyUI 报错文本）：必须足够宽以覆盖 torch/ations 各种措辞，
# 又不能宽到把「required_input_missing」这类真·参数错也当成 OOM 去降档。
OOM_PAT = re.compile(
    r"out of memory|OutOfMemoryError|allocation failed|"
    r"CUDA error:\s*out of memory|not enough memory|"
    r"failed to allocate|OOM", re.I)


# ---------------- 显存探测 ----------------
def sniff():
    """探测可用显存（MiB）。返回 {'ok':True,...} 或 {'ok':False,'error':...}。

    无 nvidia-smi（CI runner / 非 N 卡）时返回 ok=False，由调用方决定兜底策略——
    刻意不做「假装探测到」以免把降档决策建立在假数据上。
    """
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"ok": False, "error": "nvidia_smi_not_found"}
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "nvidia_smi_failed:%s" % type(e).__name__}
    if out.returncode != 0:
        return {"ok": False,
                "error": (out.stderr.decode("utf-8", "replace").strip() or "nonzero")[:120]}
    try:
        line = out.stdout.decode("utf-8", "replace").strip().splitlines()[0]
        used, total = (int(float(x)) for x in line.split(",")[:2])
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "parse_failed:%s" % type(e).__name__}
    return {"ok": True, "used_mib": used, "total_mib": total,
            "free_mib": max(0, total - used), "free_gib": round(max(0, total - used) / 1024.0, 2)}


def effective_budget(snap=None, override=None):
    """返回用于决策的预算（GiB）。override 优先；探测不到时返回 None（调用方走保守档）。"""
    if override:
        return float(override)
    snap = snap if snap is not None else sniff()
    if not snap.get("ok"):
        return None
    return snap["free_gib"]


# ---------------- 档位决策 ----------------
def base_tier(duration):
    """时长 → 阶梯基准下标（不显存修正）。"""
    for limit, tier in DURATION_TIER:
        if duration <= limit:
            return tier
    return len(LADDER) - 1


def start_tier(duration, budget_gib=None):
    """时长 + 预算 → 起始档下标。

    预算为 None（探测不到）时保守取「基准档 +1」：宁可先跑小分辨率成功，
    也不要在不明显存上盲目冲顶档（OOM 的代价是几分钟白跑）。

    ⚠ 使用注意（2026-10-16 实测）：ComfyUI 跑完一轮后**不会释放已加载权重**
    （本机实测跑完 10s 后 nvidia-smi 显示仍占用 8.9GB，free 只剩 3.25GiB）。
    此时按 live 预算选档会把 5s 这种本来能跑 1344×768 的档位也降到底档，
    属于静默降质。所以跑测器默认走 `calibrated`（按标定表选档，不看实时占用），
    实时探测只在显式 `--vram-mode live` 时生效；真 OOM 由降档重试兜底。
    """
    t = base_tier(duration)
    if budget_gib is None:
        return min(t + 1, len(LADDER) - 1)
    deficit = BUDGET_REF_GIB - float(budget_gib)
    if deficit > 0:
        t += int(deficit // GB_PER_TIER)
    return max(0, min(t, len(LADDER) - 1))


def tier_wh(idx):
    """档位下标 → (width, height)；越界自动夹到底档/顶档。"""
    idx = max(0, min(int(idx), len(LADDER) - 1))
    return LADDER[idx]


def downgrade_chain(duration, budget_gib=None, start=None):
    """从起始档到底档的完整降档链，返回 [(w,h), ...]；起始档即底档时只有一项。"""
    s = start_tier(duration, budget_gib) if start is None else int(start)
    s = max(0, min(s, len(LADDER) - 1))
    return [LADDER[i] for i in range(s, len(LADDER))]


def is_oom(text):
    """报错文本是否为 OOM。区分对待：参数错不该触发降档。"""
    return bool(text) and bool(OOM_PAT.search(str(text)))


# ---------------- 无 GPU 自检（CI 可纳） ----------------
def _selftest():
    """纯逻辑自检（不碰 GPU），返回 [(msg, ok)]。"""
    steps = []

    # ① 起始档随时长单调不升（时长越长档位下标越大 = 分辨率越小）
    tiers = [start_tier(d, BUDGET_REF_GIB) for d in (5, 8, 10, 11, 15)]
    mono = all(tiers[i] <= tiers[i + 1] for i in range(len(tiers) - 1))
    steps.append(("起始档随时长单调不升：%s" % tiers, mono))
    # 与 2026-10-14 实测边界表逐档对齐（本机 11.91GB 预算下的已知可用分辨率）
    want = [(1344, 768), (1344, 768), (1152, 640), (960, 544), (960, 544)]
    got = [tier_wh(start_tier(d, BUDGET_REF_GIB)) for d in (5, 8, 10, 11, 15)]
    steps.append(("11.91GB 预算下时长→分辨率与实测边界表一致：%s" % (got,), got == want))

    # ② 显存变少必须降档（6GB 小卡不能冲 1344×768 的 15s）
    small = [tier_wh(start_tier(d, 6.0)) for d in (5, 15)]
    steps.append(("6GB 预算下全部落到底档：%s" % (small,),
                  all(w == LADDER[-1][0] for w, _ in small)))

    # ③ 探测不到显存时保守降一档（不盲冲顶档）
    unk = tier_wh(start_tier(5, None))
    steps.append(("预算未知时保守降一档（5s → %s）" % (unk,), unk == LADDER[1]))

    # ④ OOM 识别：命中真 OOM、不误伤参数错
    oom_cases = ["CUDA out of memory. Tried to allocate 2.00 GiB",
                 "torch.OutOfMemoryError: Allocation failed",
                 "Not enough memory!"]
    non_cases = ["Value not in list: vae_name", "Required input is missing: strength",
                 "Prompt outputs failed validation"]
    ok_oom = all(is_oom(t) for t in oom_cases)
    ok_non = not any(is_oom(t) for t in non_cases)
    steps.append(("OOM 文本全部命中", ok_oom))
    steps.append(("参数错/校验错不被误判为 OOM", ok_non))

    # ⑤ 降档链：长度正确、末项必为底档
    chain = downgrade_chain(15, BUDGET_REF_GIB)
    steps.append(("15s 降档链 %s 末项为底档" % (chain,), chain[-1] == LADDER[-1]))
    return steps


def main(argv=None):
    import json
    import sys
    args = set(argv or sys.argv[1:])
    if "--json" in args:
        """给 09 面板的机器可读输出：显存快照 + 阶梯 + 各时长推荐档。"""
        snap = sniff()
        free = snap.get("free_gib")
        tiers = {}
        for d in (5, 8, 10, 11, 15):
            t = start_tier(d, free)
            tiers[str(d)] = {"tier": t, "wh": list(tier_wh(t)),
                             "chain": [list(x) for x in downgrade_chain(d, free)]}
        print(json.dumps({"ok": snap.get("ok", False), "used_mib": snap.get("used_mib"),
                          "total_mib": snap.get("total_mib"), "free_gib": free,
                          "error": snap.get("error"), "ladder": [list(x) for x in LADDER],
                          "tiers": tiers}, ensure_ascii=False))
        return 0
    if "--selftest" in args:
        bad = 0
        for msg, ok in _selftest():
            print(("OK   " if ok else "FAIL ") + msg)
            if not ok:
                bad += 1
        return 1 if bad else 0
    snap = sniff()
    print("sniff:", snap)
    if snap.get("ok"):
        print("free  : %.2f GiB" % snap["free_gib"])
        for d in (5, 8, 10, 11, 15):
            t = start_tier(d, snap["free_gib"])
            print("  %2ds -> tier%d %s   降档链 %s" % (d, t, tier_wh(t), downgrade_chain(d, snap["free_gib"])))
    else:
        print("[SKIP] 无 nvidia-smi，改用保守档：")
        for d in (5, 8, 10, 11, 15):
            t = start_tier(d, None)
            print("  %2ds -> tier%d %s" % (d, t, tier_wh(t)))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
