# 官方模板对齐快照：Z_image_turbo.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_z_image_turbo.json
- 当前工作流：Z_image_turbo.json

## 概览

`顶层类型 删=['SaveImage', 'f2fdebf6-dfaf-43b6-9eb2-7f70613cfdc1'] 加=['82388757-f3fe-445d-98b4-26314784fcba', 'ResolutionSelector', 'SaveImageAdvanced']`

## 子图差异

- 子图0 新增节点 id=1 type=UNETLoader
- 子图0 新增节点 id=2 type=CLIPLoader
- 子图0 id=3 type=KSampler widgets变:
  - 官方: [0, 'randomize', 8, 1, 'res_multistep', 'simple', 1]
  - 当前: ['FLUX-1-dev + Z-image-turbo\\ae.safetensors']
- 子图0 新增节点 id=4 type=EmptySD3LatentImage
- 子图0 新增节点 id=5 type=CLIPTextEncode
- 子图0 新增节点 id=6 type=CLIPTextEncode
- 子图0 新增节点 id=7 type=KSampler
- 子图0 id=8 type=VAEDecode widgets变:
  - 官方: []
  - 当前: [3, 'flow']
- 子图0 新增节点 id=9 type=VAEDecode
- 子图0 删除节点 id=11 type=ModelSamplingAuraFlow
- 子图0 删除节点 id=13 type=EmptySD3LatentImage
- 子图0 新增节点 id=16 type=LoraLoaderModelOnly
- 子图0 新增节点 id=17 type=LoraLoaderModelOnly
- 子图0 新增节点 id=18 type=LoraLoaderModelOnly
- 子图0 新增节点 id=19 type=LoraLoaderModelOnly
- 子图0 新增节点 id=20 type=LoraLoaderModelOnly
- 子图0 新增节点 id=21 type=LoraLoaderModelOnly
- 子图0 删除节点 id=27 type=CLIPTextEncode
- 子图0 删除节点 id=28 type=UNETLoader
- 子图0 删除节点 id=29 type=VAELoader
- 子图0 删除节点 id=30 type=CLIPLoader
- 子图0 删除节点 id=33 type=ConditioningZeroOut
- 子图0 新增节点 id=74 type=Fast Groups Bypasser (rgthree)
- 子图0 新增节点 id=75 type=ImageScaleToTotalPixels
- 子图0 新增节点 id=76 type=PreviewImage
- 子图0 新增节点 id=78 type=ReservedVRAMSetter
- 子图0 新增节点 id=79 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=80 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=81 type=SeedVR2LoadDiTModel
- 子图0 新增节点 id=103 type=BatchPromptReaderWithClip
- 子图0 新增节点 id=110 type=ConditioningZeroOut
