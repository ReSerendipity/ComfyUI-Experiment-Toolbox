# flatten 版本对照（Picture/tools 版 vs 工具箱 01 版）

> 任务：只读对比两版 `flatten.py`，给出**行数/能力差异**、Picture 侧多处理的情况、
> 值得回合进工具箱的增强、以及接口兼容风险。
> **本次未修改任何 `flatten.py`**；全部结论由 AST + 文本 diff 得出（脚本见 §六）。
>
> 对照对象：
>
> | 记号 | 路径 | 大小 |
> |---|---|---|
> | **PICT** | `Picture/tools/flatten.py` | 10851 B |
> | **TBOX** | `TBOX/01_工作流扁平化/flatten.py` | 10785 B |

---

## 一、结论摘要（先看这段）

**两版核心算法零差异。** AST 逐函数比对：`flatten` / `_containers` / `_link` /
`add_node` / `nid` / `resolve` 六个函数体**全部完全相等**。

- 唯一的源码差异只有 3 行、集中在 `__main__` 默认工作流路径的解析方式，
  外加 1 行 `import pathlib`。
- **不存在**「Picture 版多处理的节点 / bypass / 子图情况」。源项目的
  `flatten.py` 就是从工具箱 `01` 拷过去的（见 §四谱系），方向与直觉相反。
- **「镜面 mirror 接线」不是 `flatten.py` 的能力**，两版都没有。它在源项目里
  属于**提示词文字层**的注入（详见 §五）。
- 值得回合进工具箱的只有 1 项（默认路径可移植性），建议幅度极小。

---

## 二、行数与体量

| 指标 | TBOX | PICT | 差 |
|---|---|---|---|
| 行数 | **244** | **246** | **+2** |
| 磁盘字节（CRLF） | 10785 | 10851 | +66 |
| 解码后字符数（LF 计） | 10541 | 10605 | +64 |
| 换行风格 | CRLF | CRLF | 同 |
| 顶层函数数 | 6 | 6 | 0 |
| 顶层 import 数 | 1（`json`） | 2（`json`, `pathlib`） | +1 |

---

## 三、具体差异清单

### 差异 1 — 行数与 import

```
 import json
+import pathlib
```

PICT 多一个 `pathlib` import（仅 `__main__` 用到，核心算法不依赖）。

### 差异 2 — `__main__` 默认工作流路径：硬编码绝对路径 vs 脚本相对定位

**TBOX（244 行附近）**：

```python
p = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\Image\Z_image_turbo.json"
```

**PICT（246 行附近）**：

```python
p = sys.argv[1] if len(sys.argv) > 1 else str(
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "user" / "default" / "workflows" / "Image" / "Z_image_turbo.json")
```

- TBOX 写死**具体用户目录**。换机器 / 换用户名 / 把工具箱挪位置，直接
  `FileNotFoundError`；而且这条路径写在**带引号的 raw string** 里。
- PICT 从 `__file__` 上溯 4 级拼相对路径。PICT 的 `flatten.py` 位于
  `<ComfyUI>/ComfyUI/input/Picture/tools/`，上溯 4 级 = `<ComfyUI>/ComfyUI/`，
  再拼 `user/default/workflows/Image/...` 正好命中。
- **注意**：这个相对推法是**绑定目录布局**的（PICT 的层级恰好是 4 级）。
  它解决的是"换机器"，不是"任意布局"。见 §五 建议 1。

### 差异 3 — 存在过一个更差的中间版本（环境变量未展开）

谱系里存在一版 `r"%USERPROFILE%\APP\..."`。`%USERPROFILE%` 是 **cmd 的环境变量
语法，Python 的 raw string 不会展开它**，直接 `open()` 必然 `FileNotFoundError`。
PICT 现行版正是把它换成脚本相对定位的那次修复。**这条不要"回合"**——
它是待修版本，不是增强。

### 差异 4 — 核心函数 AST 全等（6/6）

```
funcs picture = ['_containers', '_link', 'add_node', 'flatten', 'nid', 'resolve']
funcs toolbox = ['_containers', '_link', 'add_node', 'flatten', 'nid', 'resolve']
func_name_set_equal = True
  ast_equal _containers  True
  ast_equal _link        True
  ast_equal add_node     True
  ast_equal flatten      True
  ast_equal nid          True
  ast_equal resolve      True
```

含义：两版的**全部能力完全相同**，逐项列在 §三之二。

### 差异 5 — 能力矩阵逐项核对（两版一致，无一侧独有）

| 能力 | TBOX | PICT |
|---|---|---|
| 子图容器识别（UUID type，含 `-` 且长度 > 30） | ✅ | ✅ |
| 容器输入虚拟槽 `-10`，按 `target_slot` 对齐（不按名字） | ✅ | ✅ |
| 容器输出虚拟槽 `-20`，经 `outputs[].linkIds` 反查 | ✅ | ✅ |
| 容器 positional 值类型守卫（数值位收到非数值 → 保留原值 + 警告） | ✅ | ✅ |
| widget 占位语义（带 `widget` 标记即占位，已连线也占位，先填 widget 再用 links 覆盖） | ✅ | ✅ |
| `seed` 后控制模式字符串（`fixed`/`randomize`/`increment`/`decrement`）跳过 | ✅ | ✅ |
| `_meta.title` 透传 | ✅ | ✅ |
| `mode == 4` bypass **递归**透传（上限 64 防环，解析后再删节点） | ✅ | ✅ |
| `UNETLoader` → 采样节点 `model` 断链兜底 | ✅ | ✅ |
| 从 `Save*/Preview*` 反向可达性裁剪 | ✅ | ✅ |
| `overrides` 按 `class_type` 或原始数字 id 覆盖，回吐 `applied` 清单 | ✅ | ✅ |
| 警告打印（`[flatten 警告]` 前缀） | ✅ | ✅ |
| **子图嵌套子图**（子图里再套子图） | ❌ | ❌ |
| **条件分支 / 选择节点求值**（只展开静态连线，不算分支） | ❌ | ❌ |
| **图级校验**（必填输入是否齐、类型是否匹配） | ❌ | ❌ |
| **镜面 / 特殊接线** | ❌ | ❌ |

> 最后三行是**两版共同的缺口**，不是"PICT 多处理了什么"。它们是候选增强方向，
> 不是既有差异。

### 差异 6 — 调用面（说明为什么兼容性风险为零）

- `10_模型家族横评/bench_family.py` 用
  `import flatten as wf_flatten`（sys.path 注入 `01_工作流扁平化`），调用
  `wf_flatten.flatten(path, overrides=...)`，解包 `(api_prompt, applied)`。
- 两版的 `flatten(path, overrides=None) -> (api, applied)` 签名与返回结构**完全一致**。
- 因此：**把 PICT 的 `__main__` 回合到 TBOX，接口零风险**（`__main__` 根本不被 import 路径使用）。

---

## 四、谱系（哪个是祖先）

用 SHA256 追踪：

| 副本 | SHA256 前 16 | 说明 |
|---|---|---|
| `TBOX/01_工作流扁平化/flatten.py` | `A654D4D020DCC003` | 与源项目 2026-09-24 备份仅差 1 行路径写法 |
| `Picture/_archive/Picture_backup_20260924_batch1/tools/flatten.py` | `76BA94499DF821C6` | 差 `r"%USERPROFILE%\…"` vs `r"C:\Users\Doro\…"` |
| `Picture/tools/flatten.py` | `CC50F1B6A57FE302` | 换成 pathlib 相对定位 |
| `C:/Users/Doro/model_benchmark/scripts/wf_flatten.py` | `CC50F1B6A57FE302` | **与 PICT 逐字节相同**（横评自己的副本） |

**结论：工具箱 `01` 是祖先，源项目是下游拷贝。** 源项目 SOP 文档里也写着
"`flatten.py` 源自采样器实验工具包"，与此一致。

**副产品发现**：横评目录下的 `scripts/wf_flatten.py` 是 PICT 版的**逐字节副本**，
而 `bench_family.py` 实际 import 的是 `01_` 那版。两份并存容易误改，
建议（**本次不做**，属入口/架构调整，需指挥方决策）只保留一份来源。

---

## 五、值得回合进工具箱的增强

### 建议 1（唯一实质建议）：`__main__` 默认路径改为可配置 + 可移植

**函数/位置**：`flatten.py` 的 `if __name__ == "__main__":` 块（约 237–244 行）。

**建议做法**（按优先级）：

1. **最好**：删掉硬编码默认路径，改成**必填位置参数**，
   `sys.argv[1] if len(sys.argv) > 1 else sys.exit("用法: python flatten.py <workflow.json>")`。
   这是 CLI 的正确默认行为——猜路径必然在换机时失败。
2. 次选：`pathlib` + `parents[k]` 遍历向上找含 `user/default/workflows` 的祖先目录，
   命中即用，找不到再报错。这样与目录层级解耦（不像 PICT 那样写死"上溯 4 级"）。
3. 最次（仅当想保留"零参数直接跑"的便利）：加环境变量兜底
   `os.environ.get("COMFY_ROOT")`，并且**必须 `os.path.expandvars`**，
   否则会重复踩差异 3 的 `%VAR%` 未展开坑。

**收益**：换机器/换用户名不再 `FileNotFoundError`。**风险：零**——只动 `__main__`。

### 建议 2：把"类型守卫"与"bypass 递归上限"提到 docstring 顶部

两版已有实现（差异 5），但这些是**最容易被下游误改**的部分（PICT 版 docstring
就明写了"⚠️ 必须按 `target_slot` 对齐，不能用名字匹配"）。
建议在 TBOX 的 docstring 里把三条铁律（target_slot 对齐 / bypass 必须递归 /
类型守卫不硬塞）写成 checklist。**纯注释，零行为变化。**

### 建议 3（可选，属新能力不是回合）：子图嵌套支持

若将来出现"子图里再套子图"的工作流，当前实现会在第一层展开后留下未解析的
UUID 容器。**判据**：容器 `type` 找不到对应 `definitions.subgraphs[].id` 时，
现在会静默产生一个 `class_type = <uuid>` 的坏节点。
低成本加固：在组装 API 前检查 `class_type` 是否形如 UUID，是则**抛错并打印容器 id**，
而不是让它流到服务端。**这条是加固，不是回合**——两版都没做。

---

## 六、风险评估

| 风险项 | 结论 |
|---|---|
| 接口签名兼容 | ✅ 无风险。`flatten(path, overrides=None) -> (api, applied)` 两版一致 |
| `bench_family.py` 调用兼容 | ✅ 无风险。`import flatten` + 解包二元组，不碰 `__main__` |
| `discover_families.py` 调用兼容 | ✅ 无风险。该脚本不 import flatten（只做权重扫描/架构探针） |
| 只改 `__main__` 的回归面 | ✅ 极小。`__main__` 仅在直接 `python flatten.py` 时执行 |
| 改核心函数（若未来动 bypass / target_slot） | ⚠️ 高。必须用真实工作流重跑扁平化并**逐节点比对 inputs**，光比节点数不够 |
| `scripts/wf_flatten.py` 副本漂移 | ⚠️ 中。它是 PICT 版副本，与 `01_` 版并存；改 `01_` 不会自动同步它 |

**建议的最小验证动作**（若将来真要动核心）：对每个在用工作流跑一次
`flatten()`，把 `(class_type, inputs)` 全量 dump 成 JSON，before/after 做结构化 diff，
要求**节点集合与每个 inputs 完全一致**（允许的差异仅为 `filename_prefix` / `seed`）。

---

## 七、复现本文结论的方法（只读）

用 ComfyUI 自带 python 跑 AST + 文本 diff，不加载任何权重、不连 ComfyUI：

```python
import ast, difflib, io

A = r"<Picture>/tools/flatten.py"
B = r"<TBOX>/01_工作流扁平化/flatten.py"
sa, sb = io.open(A, encoding="utf-8").read(), io.open(B, encoding="utf-8").read()

def funcs(src):
    tree = ast.parse(src)
    return {n.name: ast.dump(ast.Module(body=n.body, type_ignores=[]))
            for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

fa, fb = funcs(sa), funcs(sb)
print(set(fa) == set(fb))                      # True
for k in sorted(set(fa) & set(fb)):
    print(k, fa[k] == fb[k])                   # 全部 True
for ln in difflib.unified_diff(sb.splitlines(), sa.splitlines(), n=1, lineterm=""):
    print(ln)
```

配套的哈希清单脚本（工具箱侧目录树逐文件 SHA256，改前/改后对账用）：

```python
import hashlib, json, os, sys
root, dest = sys.argv[1], sys.argv[2]
out = {}
for dp, dn, fns in os.walk(root):
    dn[:] = sorted(d for d in dn if d != "__pycache__")
    for fn in sorted(fns):
        if fn.endswith((".pyc", ".pyo")):
            continue
        p = os.path.join(dp, fn)
        out[os.path.relpath(p, root).replace("\\", "/")] = {
            "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
            "size": os.path.getsize(p)}
json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
```

---

## 八、「镜面 mirror 接线」到底在哪（澄清任务描述里的假设）

任务里提到「Picture 版多处理的节点/bypass/子图情况（如镜面 mirror 接线）」。
实测结论：**`flatten.py` 两版都不含任何镜面相关处理**（§三差异 5 最后一行）。

镜面相关代码在源项目里的真实位置是**提示词文字层**，不是图结构层：

| 脚本 | 层 | 作用 |
|---|---|---|
| `tools/batch8_mirror_inject.py` | 文字层 | 往镜面题材提示词里注入**可视实体句**（落地镜/穿衣镜/镜墙 + "镜中映出…"），带 `--dry-run`、变体轮换、注入防撞 |
| `tools/batch16_mirror_wiring_render.py` | 文字层 + 出图 | 用新引擎的「镜面·强化反射句」池生成 3 件 L1 镜面件做**出图验证**（不落盘改库） |

也就是说：镜面能力落在**素材池 + 注入器 + QC 门控**这条链上，
与 `flatten.py` 的图展开职责无关。工具箱 `01` 若要支持"镜面类提示词"，
需要的是提示词层的断言检查（见 `场景断言审计法.md` §七 的机位断言扩展），
**不是**改 `flatten.py`。