# 官方模板对齐快照：flux2_klein_edit.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_flux2_klein_image_edit_9b_distilled.json
- 当前工作流：flux2_klein_edit.json

## 概览

`顶层类型 删=['MarkdownNote', 'SaveImage'] 加=['SaveImageAdvanced']`

## 子图差异

- 子图0 id=64 type=SamplerCustomAdvanced widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=65 type=VAEDecode widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=70 type=UNETLoader widgets变:
  - 官方: ['flux-2-klein-9b-fp8.safetensors', 'default']
  - 当前: ['FLUX-2-klein-9b-fp8\\DarkBeast-Klein9b-V2-BFS-FP8.safetensors', 'default']
- 子图0 id=82 type=ConditioningZeroOut widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=99 type=GetImageSize widgets变:
  - 官方: []
  - 当前: None
- 子图0 删除节点 id=123 type=ReferenceLatent
- 子图0 删除节点 id=124 type=VAEEncode
- 子图0 删除节点 id=125 type=ReferenceLatent
- 子图0 新增节点 id=151 type=ReferenceLatent
- 子图0 新增节点 id=152 type=ReferenceLatent
- 子图0 新增节点 id=153 type=VAEEncode
- 子图1 id=86 type=ConditioningZeroOut widgets变:
  - 官方: []
  - 当前: None
- 子图1 id=104 type=SamplerCustomAdvanced widgets变:
  - 官方: []
  - 当前: None
- 子图1 id=105 type=VAEDecode widgets变:
  - 官方: []
  - 当前: None
- 子图1 id=107 type=UNETLoader widgets变:
  - 官方: ['flux-2-klein-9b-fp8.safetensors', 'default']
  - 当前: ['FLUX-2-klein-9b-fp8\\DarkBeast-Klein9b-V2-BFS-FP8.safetensors', 'default']
- 子图1 id=114 type=GetImageSize widgets变:
  - 官方: []
  - 当前: None
- 子图1 删除节点 id=126 type=ReferenceLatent
- 子图1 删除节点 id=127 type=VAEEncode
- 子图1 删除节点 id=128 type=ReferenceLatent
- 子图1 id=129 type=ReferenceLatent widgets变:
  - 官方: []
  - 当前: None
- 子图1 id=130 type=VAEEncode widgets变:
  - 官方: []
  - 当前: None
- 子图1 id=131 type=ReferenceLatent widgets变:
  - 官方: []
  - 当前: None
- 子图1 新增节点 id=132 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=133 type=VAEEncode
- 子图1 新增节点 id=134 type=ReferenceLatent
- 子图1 新增节点 id=135 type=ReferenceLatent
- 子图1 新增节点 id=136 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=137 type=VAEEncode
- 子图1 新增节点 id=138 type=ReferenceLatent
- 子图1 新增节点 id=139 type=ReferenceLatent
- 子图1 新增节点 id=140 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=141 type=VAEEncode
- 子图1 新增节点 id=142 type=ReferenceLatent
- 子图1 新增节点 id=143 type=ReferenceLatent
- 子图1 新增节点 id=144 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=145 type=VAEEncode
- 子图1 新增节点 id=146 type=ReferenceLatent
- 子图1 新增节点 id=147 type=ReferenceLatent
- 子图1 新增节点 id=148 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=149 type=VAEEncode
- 子图1 新增节点 id=150 type=ReferenceLatent
- 子图1 新增节点 id=154 type=VAEEncode
- 子图1 新增节点 id=155 type=ReferenceLatent
- 子图1 新增节点 id=156 type=ReferenceLatent
- 子图1 新增节点 id=157 type=ReferenceLatent
- 子图1 新增节点 id=158 type=ImageScaleToTotalPixels
- 子图1 新增节点 id=159 type=VAEEncode
- 子图1 新增节点 id=160 type=ReferenceLatent
- 子图1 新增节点 id=161 type=ReferenceLatent
