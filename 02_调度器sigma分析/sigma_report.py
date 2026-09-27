# -*- coding: utf-8 -*-
"""
离线验证：把 9 个调度器在 Qwen-Image 2.1 上的真实 sigma 曲线算出来，
量化「低噪声区步数分配」，把 karras 在 25 步下的失败根因从"推断"升级为"已验证"。
纯 CPU 计算，不生成任何图片。
"""
import os, sys, json
import torch

COMFY = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI"
sys.path.insert(0, COMFY)

import comfy.model_sampling as msmod
import comfy.samplers as S


class FakeCfg:
    # 取自 comfy/supported_models.py -> class QwenImage21.sampling_settings
    sampling_settings = {"multiplier": 1.0, "shift": 0.69}   # shift = mu @ 1024x1024


def build_ms():
    return msmod.ModelSamplingDiscreteFlow(FakeCfg())


def analyze(sig, steps):
    sig = [float(x) for x in sig]
    smax, smin = sig[0], sig[-1]
    d = [sig[i] - sig[i + 1] for i in range(len(sig) - 1)]     # 每步实际走的 sigma 距离
    tot = sum(d) or 1e-9
    # 低噪声区（细节打磨阶段）占用的步数与行程占比
    def frac(thr):
        n = sum(1 for i in range(len(d)) if sig[i] <= thr)
        return n, sum(d[i] for i in range(len(d)) if sig[i] <= thr) / tot
    n_lo_01, w_lo_01 = frac(0.1 * smax)
    n_lo_001, w_lo_001 = frac(0.01 * smax)
    return {
        "sigma_max": round(smax, 5),
        "sigma_min": round(smin, 8),
        "最后一步前 sigma": round(sig[-2], 6) if len(sig) > 1 else None,
        "步数>0.1σmax的": steps - n_lo_01,
        "步数≤0.1σmax的": n_lo_01,
        "低噪区行程占比(≤0.1σmax)": round(w_lo_01, 3),
        "步数≤0.01σmax的": n_lo_001,
        "低噪区行程占比(≤0.01σmax)": round(w_lo_001, 3),
        "首步Δ": round(d[0], 5),
        "末步Δ": round(d[-1], 6),
    }


def main():
    ms = build_ms()
    print("ModelSamplingDiscreteFlow  sigma_min=%.8f  sigma_max=%.5f  表长=%d  shift=%.2f"
          % (float(ms.sigma_min), float(ms.sigma_max), len(ms.sigmas), ms.shift))
    print()
    out = {}
    for steps in (25, 50):
        print("=" * 108)
        print(f"steps = {steps}")
        print("=" * 108)
        hdr = f"{'调度器':16s}{'σmax':>9s}{'σmin':>11s}{'末步前σ':>10s}{'≤0.1σmax步数':>13s}{'≤0.1σmax行程':>13s}{'≤0.01σmax步数':>14s}{'首步Δ':>9s}{'末步Δ':>10s}"
        print(hdr)
        out[steps] = {}
        for name in S.SCHEDULER_NAMES:
            sig = S.calculate_sigmas(ms, name, steps)
            r = analyze(sig, steps)
            out[steps][name] = r
            print(f"{name:16s}{r['sigma_max']:>9.5f}{r['sigma_min']:>11.8f}"
                  f"{str(r['最后一步前 sigma']):>10s}{r['步数≤0.1σmax的']:>13d}"
                  f"{r['低噪区行程占比(≤0.1σmax)']:>13.3f}{r['步数≤0.01σmax的']:>14d}"
                  f"{r['首步Δ']:>9.5f}{r['末步Δ']:>10.6f}")
        print()

    # karras 详细逐步
    for steps in (25, 50):
        sig = [float(x) for x in S.calculate_sigmas(ms, "karras", steps)]
        print(f"--- karras @ {steps} 步，逐步 sigma ---")
        print("  " + "  ".join(f"{s:.4f}" for s in sig[:8]) + " ... " +
              "  ".join(f"{s:.5f}" for s in sig[-8:]))
    print()
    for steps in (25, 50):
        sig = [float(x) for x in S.calculate_sigmas(ms, "simple", steps)]
        print(f"--- simple @ {steps} 步，逐步 sigma ---")
        print("  " + "  ".join(f"{s:.4f}" for s in sig[:8]) + " ... " +
              "  ".join(f"{s:.5f}" for s in sig[-8:]))

    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigma_schedules.json"),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已保存 sigma_schedules.json")


if __name__ == "__main__":
    main()
