#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 Prompt-Library 产出的版式化提示词直接送进 ComfyUI 渲染。

用途：Prompt-Library 负责"提示词"（骨架 + 显式文字 + 词库配料），
本脚本负责"照单出图"，两边通过 `layout_<type>.txt` 这一层解耦。

前置：
  1) ComfyUI 已在本机 8188 运行；
  2) 先生成提示词（在 Prompt-Library 仓库内）：
       python tools/batch_runner_v4.py --mode layout --layout-type all \
              --folder output/版式化

用法：
  python layout_from_library.py --src <提示词目录> [选项]

  --src DIR         layout_*.txt 所在目录（必填）
  --types LIST      all（默认）或 tarot,dossier,...
  --copy-to DIR     把渲染结果另存一份到该目录（便于比对）
  --seed N          基础种子（默认 20261104，按类型序号递增）
  --steps N         采样步数（默认 30）
  --cfg F           CFG（默认 4.0）
  --out FILE        结果清单 JSON
  --no-probe        跳过三件套自检
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import layout_runner as R          # noqa: E402
import layout_types as T           # noqa: E402

SERVER = R.SERVER


def parse_types(expr):
    if not expr or expr == 'all':
        return list(T.TYPES)
    return [x.strip() for x in expr.split(',') if x.strip()]


def load_prompts(src, types):
    out = []
    for pt in types:
        p = os.path.join(src, 'layout_%s.txt' % pt)
        if not os.path.exists(p):
            print('[miss] %s（跳过）' % p, flush=True)
            continue
        text = open(p, encoding='utf-8').read().strip()
        if not text:
            print('[empty] %s（跳过）' % p, flush=True)
            continue
        out.append((pt, text))
    return out


def fetch_image(img, dest_dir):
    """按 /view 取回落盘（SaveImage 同时会写 ComfyUI 自身 output）。"""
    q = urllib.parse.urlencode({
        'filename': img['filename'],
        'subfolder': img.get('subfolder', ''),
        'type': img.get('type', 'output'),
    })
    with urllib.request.urlopen('%s/view?%s' % (SERVER, q), timeout=60) as r:
        data = r.read()
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, img['filename'])
    with open(path, 'wb') as f:
        f.write(data)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True, help='layout_*.txt 目录')
    ap.add_argument('--types', default='all', help='all 或逗号分隔类型')
    ap.add_argument('--copy-to', default='', help='渲染结果另存目录')
    ap.add_argument('--seed', type=int, default=20261104)
    ap.add_argument('--steps', type=int, default=30)
    ap.add_argument('--cfg', type=float, default=4.0)
    ap.add_argument('--timeout', type=int, default=1800)
    ap.add_argument('--out', default='', help='结果清单 JSON 路径')
    ap.add_argument('--no-probe', action='store_true')
    args = ap.parse_args(argv)

    if not args.no_probe:
        bad = R.probe()
        if bad:
            print('[probe] 缺失：%s —— 先修模型名再渲染' % ', '.join(bad))
            return 1

    prompts = load_prompts(args.src, parse_types(args.types))
    if not prompts:
        print('[fatal] 未找到任何 layout_*.txt；先跑 batch_runner --mode layout')
        return 2

    results = []
    for i, (pt, text) in enumerate(prompts):
        w, h = T.TYPES[pt]['size']
        rec = {
            'name': 'lib_%s' % pt,
            'prompt': text,
            'width': w, 'height': h,
            'seed': args.seed + i,
            'steps': args.steps,
            'cfg': args.cfg,
        }
        imgs = R.run(rec, timeout_s=args.timeout)
        saved = []
        if imgs and args.copy_to:
            for img in imgs:
                try:
                    saved.append(fetch_image(img, args.copy_to))
                except Exception as e:          # 取回失败不影响渲染本身
                    print('[warn] 取回失败 %s: %s' % (img.get('filename'), e), flush=True)
        results.append({
            'type': pt, 'label': T.TYPES[pt].get('label', pt),
            'size': [w, h], 'seed': rec['seed'],
            'images': imgs or [], 'saved': saved,
            'chars': len(text),
        })

    ok = sum(1 for r in results if r['images'])
    print('\n[summary] %d/%d 成功' % (ok, len(results)))
    for r in results:
        print('  %-12s %-8s %5dx%-5d %s' % (
            r['type'], r['label'], r['size'][0], r['size'][1],
            'OK' if r['images'] else 'FAIL'))

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print('[out] %s' % args.out)
    return 0 if ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
