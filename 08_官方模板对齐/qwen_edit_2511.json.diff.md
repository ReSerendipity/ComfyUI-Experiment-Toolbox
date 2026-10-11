# 官方模板对齐快照：qwen_edit_2511.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_qwen_image_edit_2511.json
- 当前工作流：qwen_edit_2511.json

## 概览

`顶层类型 删=['MarkdownNote', 'SaveImage'] 加=['SaveImageAdvanced']`

## 子图差异

- 子图0 id=145 type=ModelSamplingAuraFlow widgets变:
  - 官方: [3.1]
  - 当前: [3.1, 'flow']
- 子图0 id=156 type=VAEEncode widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=158 type=VAEDecode widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=160 type=FluxKontextImageScale widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=161 type=UNETLoader widgets变:
  - 官方: ['qwen_image_edit_2511_fp8mixed.safetensors', 'default']
  - 当前: ['Qwen-Image-Edit-2511\\qwen_image_edit_2511_nvfp4.safetensors', 'default']
