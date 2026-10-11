# 官方模板对齐快照：Qwen_image.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_qwen_image.json
- 当前工作流：Qwen_image.json

## 概览

`顶层类型 删=['SaveImage', 'e5cfe5ba-2ae0-4bc4-869f-ab2228cb44d3'] 加=['ResolutionSelector', 'SaveImageAdvanced', 'c7300ca3-9504-4375-a665-c09529708304']`

## 子图差异

- 子图0 删除节点 id=3 type=KSampler
- 子图0 新增节点 id=4 type=CLIPTextEncode
- 子图0 id=6 type=CLIPTextEncode widgets变:
  - 官方: ['"A vibrant, warm neon-lit street scene in Hong Kong at the afternoon, with a mix of colorful Chinese and English signs
  - 当前: [1024, 1024, 1]
- 子图0 id=7 type=CLIPTextEncode widgets变:
  - 官方: ['']
  - 当前: [297796727043574, 'randomize', 50, 4, 'euler', 'simple', 1]
- 子图0 id=8 type=VAEDecode widgets变:
  - 官方: []
  - 当前: None
- 子图0 新增节点 id=15 type=CLIPTextEncode
- 子图0 删除节点 id=37 type=UNETLoader
- 子图0 删除节点 id=38 type=CLIPLoader
- 子图0 删除节点 id=39 type=VAELoader
- 子图0 新增节点 id=57 type=Fast Groups Bypasser (rgthree)
- 子图0 id=58 type=EmptySD3LatentImage widgets变:
  - 官方: [1328, 1328, 1]
  - 当前: ['lanczos', 0.1, 1]
- 子图0 新增节点 id=59 type=PreviewImage
- 子图0 新增节点 id=61 type=ReservedVRAMSetter
- 子图0 新增节点 id=62 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=63 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=64 type=SeedVR2LoadDiTModel
- 子图0 删除节点 id=66 type=ModelSamplingAuraFlow
- 子图0 新增节点 id=67 type=LoraLoaderModelOnly
- 子图0 新增节点 id=68 type=LoraLoaderModelOnly
- 子图0 新增节点 id=69 type=LoraLoaderModelOnly
- 子图0 新增节点 id=70 type=LoraLoaderModelOnly
- 子图0 新增节点 id=71 type=LoraLoaderModelOnly
- 子图0 新增节点 id=72 type=LoraLoaderModelOnly
- 子图0 删除节点 id=73 type=LoraLoaderModelOnly
- 子图0 新增节点 id=77 type=CLIPLoader
- 子图0 id=78 type=ComfySwitchNode widgets变:
  - 官方: [False]
  - 当前: ['Qwen（2512）（edit）(Krea2)\\qwen_image_vae.safetensors']
- 子图0 删除节点 id=79 type=PrimitiveInt
- 子图0 删除节点 id=81 type=PrimitiveFloat
- 子图0 删除节点 id=82 type=ComfySwitchNode
- 子图0 id=83 type=ComfySwitchNode widgets变:
  - 官方: [False]
  - 当前: ['Qwen-image-2512-nvfp4\\qwen-image-2512-nvfp4-Ultra.safetensors', 'default']
- 子图0 id=84 type=PrimitiveInt widgets变:
  - 官方: [20, 'fixed']
  - 当前: ['input/Picture/', 965, 'increment', True, True, '*.txt', 'output/', False, 'user/default/batch_prompt_logs', False, Fal
- 子图0 删除节点 id=85 type=PrimitiveFloat
- 子图0 删除节点 id=86 type=PrimitiveBoolean
- 子图0 删除节点 id=87 type=MarkdownNote
- 子图0 新增节点 id=92 type=ComfySwitchNode
- 子图0 新增节点 id=93 type=ComfySwitchNode
- 子图0 新增节点 id=94 type=ComfySwitchNode
- 子图0 新增节点 id=95 type=PrimitiveBoolean
- 子图0 新增节点 id=96 type=PrimitiveInt
- 子图0 新增节点 id=97 type=PrimitiveInt
- 子图0 新增节点 id=98 type=PrimitiveFloat
- 子图0 新增节点 id=99 type=PrimitiveFloat
