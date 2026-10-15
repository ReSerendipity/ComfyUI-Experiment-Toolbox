# -*- coding: utf-8 -*-
"""修复 Z_image.json 写入格式：恢复带空格分隔、缩进格式（与 step3.bak 原格式一致）
   2026-10-14：接入 dry-run 开关（默认关闭）——--dry-run 不落盘，只打印将重排后的结构。"""
import os
import json
import dryrun

GLOBAL_D = os.path.expandvars(r'%USERPROFILE%\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image')
dryrun.parse_args()
D = dryrun.resolve_target(GLOBAL_D)
fn = 'Z_image.json'
p = D + '\\' + fn
bak = D + '\\Z_image.step3.bak'

# 从备份读取原始格式特征
raw_bak = open(bak, encoding='utf-8').read()
indent = 2 if '\n  ' in raw_bak else None
sep = (', ', ': ') if '", "' in raw_bak else (',', ':')
print('原始格式: indent=%s sep=%s' % (indent, sep))

# 重新序列化当前内容（内容已是改造后，仅格式重排）
data = json.load(open(p, encoding='utf-8'))
out = json.dumps(data, ensure_ascii=False, indent=indent, separators=sep)
if dryrun.is_dry_run():
    cur = open(p, encoding='utf-8').read()
    if cur == out:
        print('[dry-run] 无格式变化，将不写入: %s' % p)
    else:
        print('[dry-run] 将修改文件（仅重排格式）: %s' % p)
        import difflib
        diff = list(difflib.unified_diff(cur.splitlines(), out.splitlines(),
                                          fromfile=p + ' (当前)', tofile=p + ' (将写入)', lineterm=''))
        for line in diff[2:20]:
            print('    ' + line)
        if len(diff) > 22:
            print('    ...（diff 共 %d 行，已截断）' % (len(diff) - 2))
else:
    with open(p, 'w', encoding='utf-8') as f:
        f.write(out)

# 验证
new = open(p, encoding='utf-8').read()
print('修复后 head:', new[:60])
print('修复后 含空格分隔:', '", "' in new, '缩进:', '\n  ' in new)
print('字节数: %d (备份 %d)' % (len(new.encode('utf-8')), len(raw_bak.encode('utf-8'))))
