# 官方模板对齐快照：Qwen_image_2_1_t2i.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_qwen_image_2_1_t2i.json
- 当前工作流：Qwen_image_2_1_t2i.json

## 概览

`顶层类型 删=[] 加=[]`

## 子图差异

- 子图0 id=458 type=KSampler widgets变:
  - 官方: [0, 'fixed', 25, 1, 'euler', 'simple', 1]
  - 当前: [0, 'randomize', 25, 1, 'euler', 'simple', 1]
- 子图0 新增节点 id=470 type=LoraLoaderModelOnly
- 子图0 id=471 type=TextGenerate widgets变:
  - 官方: ['', 4096, 'on', 1, 20, 0.95, 0, 1, 0, 1.5, True, True, 'auto']
  - 当前: ['None', 1]
- 子图0 id=472 type=PreviewAny widgets变:
  - 官方: []
  - 当前: ['None', 1]
- 子图0 id=473 type=CLIPLoader widgets变:
  - 官方: ['qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors', 'stable_diffusion', 'default']
  - 当前: ['None', 1]
- 子图0 id=474 type=ComfySwitchNode widgets变:
  - 官方: [False]
  - 当前: ['None', 1]
- 子图0 id=475 type=PrimitiveStringMultiline widgets变:
  - 官方: ['# Image Prompt Rewriting Expert\n\nYou turn a user\'s image request into one long English paragraph that describes the
  - 当前: ['None', 1]
- 子图0 新增节点 id=477 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=478 type=SeedVR2LoadDiTModel
- 子图0 新增节点 id=479 type=SeedVR2VideoUpscaler
- 子图0 id=480 type=QwenImage21Cache widgets变:
  - 官方: ['auto', 'default']
  - 当前: [0.6, 'auto', 1040532856441915, 'randomize', 0, False]
- 子图0 新增节点 id=481 type=BatchPromptReaderWithClip
- 子图0 新增节点 id=484 type=PreviewImage
