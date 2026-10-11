# 官方模板对齐快照：Z_image.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_z_image.json
- 当前工作流：Z_image.json

## 概览

`顶层类型 删=['9b9009e4-2d3d-445f-9be5-6063f465757e'] 加=['e8393e1e-0e30-4b22-a7c2-5745ffccc0e0']`

## 子图差异

- 子图0 新增节点 id=3 type=VAELoader
- 子图0 新增节点 id=4 type=CLIPTextEncode
- 子图0 新增节点 id=6 type=EmptySD3LatentImage
- 子图0 新增节点 id=7 type=KSampler
- 子图0 新增节点 id=8 type=VAEDecode
- 子图0 新增节点 id=11 type=CLIPLoader
- 子图0 新增节点 id=15 type=CLIPTextEncode
- 子图0 新增节点 id=19 type=LoraLoaderModelOnly
- 子图0 新增节点 id=20 type=LoraLoaderModelOnly
- 子图0 新增节点 id=21 type=LoraLoaderModelOnly
- 子图0 新增节点 id=22 type=LoraLoaderModelOnly
- 子图0 新增节点 id=23 type=LoraLoaderModelOnly
- 子图0 新增节点 id=24 type=LoraLoaderModelOnly
- 子图0 新增节点 id=52 type=Fast Groups Bypasser (rgthree)
- 子图0 新增节点 id=53 type=ImageScaleToTotalPixels
- 子图0 新增节点 id=54 type=PreviewImage
- 子图0 新增节点 id=56 type=ReservedVRAMSetter
- 子图0 新增节点 id=57 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=58 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=59 type=SeedVR2LoadDiTModel
- 子图0 删除节点 id=62 type=CLIPLoader
- 子图0 删除节点 id=63 type=VAELoader
- 子图0 id=65 type=VAEDecode widgets变:
  - 官方: []
  - 当前: ['Z-image-bf16\\z_image_bf16.safetensors', 'default']
- 子图0 id=66 type=UNETLoader widgets变:
  - 官方: ['z_image_bf16.safetensors', 'default']
  - 当前: ['input/Picture/', 965, 'increment', True, True, '*.txt', 'output/', False, 'default/batch_prompt_logs', False, False]
- 子图0 删除节点 id=67 type=CLIPTextEncode
- 子图0 删除节点 id=68 type=EmptySD3LatentImage
- 子图0 删除节点 id=69 type=KSampler
- 子图0 删除节点 id=70 type=ModelSamplingAuraFlow
- 子图0 删除节点 id=71 type=CLIPTextEncode
- 子图0 删除节点 id=87 type=MarkdownNote
