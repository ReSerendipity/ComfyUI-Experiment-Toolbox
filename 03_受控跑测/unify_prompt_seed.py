# -*- coding: utf-8 -*-
"""
把 Qwen_image_2_1_t2i 的提示词与种子统一写入其余图像工作流文件（确保跨模型单一变量）。

依据（2026-09-23 查明）：
  - 容器节点 positional `widgets_values` 是运行时真值（前端 NamedValuesRestore 默认 false）
  - 同时同步 `widgets_values_named`，避免前端显示不一致
  - 只改「提示词 / 种子」两处；steps / cfg / 采样器 / 调度器 / 模型一律不动

特例：krea2_turbo 的容器把用户提示词暴露为 input 名 `value`、种子为 `seed_1`，
      且默认开启 LLM 提示词增强（`value_1` / prompt_enhance = True）——
      增强会把提示词改写掉，破坏单一变量，因此一并关掉（其余参数不动）。
"""
import json, os, sys, shutil, time

WF = r"%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows"
SRC = os.path.join(WF, "Image", "Qwen_image_2_1_t2i.json")

# rel_path: (prompt_input_name, seed_input_name, extra_overrides{name: value})
MAP = {
    "Image/Qwen_image.json":                  ("positive_prompt", "seed", {}),
    "Image/Qwen_image_2512.json":             ("positive_prompt", "seed", {}),
    "Image/Z_image.json":                     ("positive_prompt", "seed", {}),
    "Image/Z_image_turbo.json":               ("positive_prompt", "seed", {}),
    "Image/flux.1-dev.json":                  ("positive_prompt", "seed", {}),
    "Image/Flux.2_Klein-9B-Distilled.json":   ("positive_prompt", "seed", {}),
    "Image/krea2_turbo.json":                 ("value", "seed_1", {"value_1": False}),
}


def containers(w):
    return [n for n in w["nodes"]
            if isinstance(n.get("type"), str) and "-" in n["type"] and len(n["type"]) > 30]


def idx_of(c, name):
    for i, inp in enumerate(c["inputs"]):
        if inp.get("name") == name:
            return i
    return None


def check_wiring(c, sg_links):
    """确认容器的 prompt/seed 输入确实经 -10 虚拟槽注入到子图内部节点。"""
    return [l for l in sg_links if l.get("origin_id") == -10]


def read_src():
    w = json.load(open(SRC, encoding="utf-8"))
    c = containers(w)[0]
    nv = c["widgets_values_named"]
    return nv["prompt"], nv["seed"]


def main():
    apply_ = "--apply" in sys.argv
    prompt, seed = read_src()
    print(f"源 Qwen_image_2_1_t2i：提示词 {len(prompt)} 字符 / 种子 {seed}")
    print(f"模式：{'APPLY（写盘，逐个备份）' if apply_ else 'DRY-RUN（不写盘）'}\n")
    for rel, (pname, sname, extras) in MAP.items():
        path = os.path.join(WF, rel)
        if not os.path.exists(path):
            print(f"跳过（不存在）: {rel}\n"); continue
        w = json.load(open(path, encoding="utf-8"))
        conts = containers(w)
        if not conts:
            print(f"{rel}\n  ! 未找到子图容器，跳过\n"); continue
        sg = w.get("definitions", {}).get("subgraphs", [])
        sg_links = sg[0].get("links", []) if sg else []
        c = conts[0]
        pi, si = idx_of(c, pname), idx_of(c, sname)
        print(f"{rel}  (container {c['id']})")
        if pi is None or si is None:
            print(f"  ! 定位失败 prompt_idx={pi} seed_idx={si}，跳过\n"); continue
        pos = list(c.get("widgets_values") or [])
        nv = dict(c.get("widgets_values_named") or {})
        old_pos_p = pos[pi] if pi < len(pos) else None
        old_pos_s = pos[si] if si < len(pos) else None
        print(f"  定位：{pname}[{pi}] / {sname}[{si}]　（-10 注入链路 {len(check_wiring(c, sg_links))} 条）")
        print(f"  改前 positional：seed={old_pos_s}  prompt={len(str(old_pos_p))} 字符「{str(old_pos_p)[:34]}」")
        print(f"  改前 named     ：seed={nv.get(sname)}  prompt={len(str(nv.get(pname,'')))} 字符")
        if pi < len(pos):
            pos[pi] = prompt
        if si < len(pos):
            pos[si] = seed
        nv[pname] = prompt
        nv[sname] = seed
        for k, v in extras.items():
            j = idx_of(c, k)
            if j is not None and j < len(pos):
                print(f"  附带：{k}[{j}] {pos[j]} → {v}" + ("（关闭提示词增强，保证提示词不被改写）" if k == "value_1" else ""))
                pos[j] = v
            nv[k] = v
        c["widgets_values"] = pos
        c["widgets_values_named"] = nv
        if apply_:
            bak = path + ".bak-" + time.strftime("%Y%m%d_%H%M%S")
            shutil.copy2(path, bak)
            json.dump(w, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  ✔ 已写入（备份 {os.path.basename(bak)}）")
        print()


if __name__ == "__main__":
    main()
