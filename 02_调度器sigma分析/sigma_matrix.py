# -*- coding: utf-8 -*-
"""
多模型调度器 σ 适配对照表（纯离线计算，不跑图）

⚠️ 关键更正：flow 系模型（Qwen-Image / Krea2 / FLUX / FLUX2）走的是
   ModelType.FLUX -> ModelSamplingFlux（σ 表 10000 点，σ=flux_time_shift(mu,1,t)），
   不是 ModelSamplingDiscreteFlow（那是 ModelType.FLOW，如 Z-Image / Lumina2）。
   两者 σ 表长度与 σ_min 都不同，必须用各自的类算。
"""
import os, sys, json
import torch

COMFY = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI"
sys.path.insert(0, COMFY)

import comfy.model_base as MB
import comfy.model_sampling as MS
import comfy.samplers as S
import comfy.supported_models as SM

ModelType = MB.ModelType


class Cfg:
    def __init__(self, settings):
        self.sampling_settings = settings


# 模型预设：(显示名, supported_models 类, model_type, 官方 steps, 官方 sampler/scheduler)
MODELS = [
    ("Qwen-Image 2.1",        "QwenImage21", ModelType.FLUX, 25, "euler + simple"),
    ("Qwen-Image 2512",       "QwenImage",   ModelType.FLUX, 50, "euler + simple"),
    ("Krea2-turbo",           "Krea2",       ModelType.FLUX,  8, "euler + simple"),
    ("Z-Image (原生)",         "ZImage",      ModelType.FLOW, 25, "res_multistep + simple"),
    ("Z-Image-Turbo",         "ZImage",      ModelType.FLOW,  8, "res_multistep + simple"),
    ("FLUX.1-dev",            "Flux",        ModelType.FLUX, 20, "euler + simple"),
    ("FLUX.2 Klein",          "Flux2",       ModelType.FLUX,  4, "euler + Flux2Scheduler"),
]


def build_ms(cls_name, mtype):
    cls = getattr(SM, cls_name)
    cfg = Cfg(dict(getattr(cls, "sampling_settings")))
    return MB.model_sampling(cfg, mtype), cfg.sampling_settings


def metrics(sig, steps):
    sig = [float(x) for x in sig]
    smax = sig[0]
    d = [sig[i] - sig[i + 1] for i in range(len(sig) - 1)]
    hi = sum(1 for i in range(len(d)) if sig[i] > 0.5 * smax)
    lo = sum(1 for i in range(len(d)) if sig[i] <= 0.1 * smax)
    return {
        "smax": smax,
        "smin": sig[-1] if len(sig) > 1 else None,
        "table_min": sig[-2] if len(sig) > 1 else None,
        "hi_steps": hi,
        "lo_steps": lo,
        "first_d": d[0],
        "first_d_pct": d[0] / smax * 100,
        "last_sigma": sig[-2] if len(sig) > 1 else None,
    }


def verdict(m, steps):
    """按第七节判据给风险等级：高危 / 注意 / 安全"""
    if m["first_d_pct"] > 15 or m["hi_steps"] <= max(1, steps * 0.15):
        return "高危"
    if m["first_d_pct"] > 9 or m["hi_steps"] <= max(2, steps * 0.25):
        return "注意"
    return "安全"


def main():
    report = {}
    for name, cls_name, mtype, steps, official in MODELS:
        ms, settings = build_ms(cls_name, mtype)
        tbl = len(ms.sigmas)
        smax = float(ms.sigma_max); smin = float(ms.sigma_min)
        print("=" * 104)
        print(f"【{name}】 class={cls_name}  model_type={mtype.name}  settings={settings}")
        print(f"  model_sampling={type(ms).__name__}  σ表={tbl} 点  σ范围=[{smin:.6f}, {smax:.6f}]  官方 {steps} 步 / {official}")
        print("=" * 104)
        hdr = f"{'调度器':17s}{'首步Δσ':>9s}{'首步Δσ%':>9s}{'σ>0.5σmax步':>12s}{'≤0.1σmax步':>11s}{'末步前σ':>11s}  风险"
        print(hdr)
        report[name] = {"class": cls_name, "ms": type(ms).__name__, "steps": steps,
                        "official": official, "scheds": {}}
        for sc in S.SCHEDULER_NAMES:
            sig = S.calculate_sigmas(ms, sc, steps)
            m = metrics(sig, steps)
            v = verdict(m, steps)
            report[name]["scheds"][sc] = {
                "first_d": round(m["first_d"], 4), "first_d_pct": round(m["first_d_pct"], 2),
                "hi_steps": m["hi_steps"], "lo_steps": m["lo_steps"],
                "last_sigma": round(m["last_sigma"], 6), "risk": v}
            print(f"{sc:17s}{m['first_d']:>9.4f}{m['first_d_pct']:>8.1f}%{m['hi_steps']:>12d}"
                  f"{m['lo_steps']:>11d}{m['last_sigma']:>11.6f}  {v}")
        print()

    print("=" * 104)
    print("汇总：各模型应避开的调度器（高危）")
    print("=" * 104)
    for name, r in report.items():
        bad = [k for k, v in r["scheds"].items() if v["risk"] == "高危"]
        warn = [k for k, v in r["scheds"].items() if v["risk"] == "注意"]
        ok = [k for k, v in r["scheds"].items() if v["risk"] == "安全"]
        print(f"{name:20s} ({r['steps']:>2d}步, 官方 {r['official']})")
        print(f"    ⛔ 高危: {', '.join(bad) if bad else '无'}")
        print(f"    ⚠️ 注意: {', '.join(warn) if warn else '无'}")
        print(f"    ✅ 安全: {', '.join(ok)}")
        print()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigma_model_matrix.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已保存", out)


if __name__ == "__main__":
    main()
