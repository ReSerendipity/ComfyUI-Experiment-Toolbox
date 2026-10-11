# 官方模板对齐快照：krea2_turbo.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_krea2_turbo_t2i.json
- 当前工作流：krea2_turbo.json

## 概览

`顶层类型 删=['SaveImage'] 加=['SaveImageAdvanced']`

## 子图差异

- 子图0 id=6 type=CLIPTextEncode widgets变:
  - 官方: ['A high-resolution, surreal digital illustration showing a human hand holding a martini glass. The image is overlaid wi
  - 当前: ['']
- 子图0 id=8 type=VAEDecode widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=13 type=ConditioningZeroOut widgets变:
  - 官方: []
  - 当前: None
- 子图0 id=16 type=TextGenerate widgets变:
  - 官方: ['', 512, 'on', 0.7, 64, 0.95, 0.05, 1.05, 0, 0, True, True]
  - 当前: ['', 512, 'on', 0.7, 64, 0.95, 0.05, 1.05, 0, 0, True, True, 'auto']
- 子图0 id=18 type=PrimitiveStringMultiline widgets变:
  - 官方: ['You are an expert prompt engineer for text-to-image models. Your task is to expand the user\'s prompt into a highly ef
  - 当前: ['You are an expert prompt engineer for text-to-image models. Your task is to expand the user\'s prompt into a highly ef
- 子图0 id=19 type=PrimitiveStringMultiline widgets变:
  - 官方: ['A high-resolution, surreal digital illustration showing a human hand holding a martini glass. The image is overlaid wi
  - 当前: ['']
- 子图0 新增节点 id=51 type=LoraLoaderModelOnly
- 子图0 新增节点 id=52 type=LoraLoaderModelOnly
- 子图0 新增节点 id=53 type=LoraLoaderModelOnly
- 子图0 新增节点 id=54 type=LoraLoaderModelOnly
- 子图0 新增节点 id=55 type=LoraLoaderModelOnly
- 子图0 新增节点 id=56 type=BatchPromptReaderWithClip
- 子图0 新增节点 id=57 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=58 type=SeedVR2LoadDiTModel
- 子图0 新增节点 id=59 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=60 type=ReservedVRAMSetter
- 子图0 新增节点 id=64 type=PreviewImage
