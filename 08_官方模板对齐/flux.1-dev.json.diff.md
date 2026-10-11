# 官方模板对齐快照：flux.1-dev.json

- 生成：2026-10-11 11:42:50
- 官方模板：flux_dev_full_text_to_image.json
- 当前工作流：flux.1-dev.json

## 概览

`顶层类型 删=['2523c08d-4c99-4b73-910c-62c873f124db', 'SaveImage'] 加=['3b418416-21a0-44da-a0ed-2fc16b1f8d4c', 'ResolutionSelector', 'SaveImageAdvanced']`

## 子图差异

- 子图0 新增节点 id=6 type=CLIPTextEncode
- 子图0 新增节点 id=8 type=VAEDecode
- 子图0 新增节点 id=10 type=VAELoader
- 子图0 新增节点 id=13 type=SamplerCustomAdvanced
- 子图0 新增节点 id=16 type=KSamplerSelect
- 子图0 新增节点 id=17 type=BasicScheduler
- 子图0 新增节点 id=22 type=BasicGuider
- 子图0 新增节点 id=25 type=RandomNoise
- 子图0 新增节点 id=26 type=FluxGuidance
- 子图0 新增节点 id=30 type=ModelSamplingFlux
- 子图0 删除节点 id=45 type=VAELoader
- 子图0 删除节点 id=46 type=UNETLoader
- 子图0 删除节点 id=47 type=DualCLIPLoader
- 子图0 删除节点 id=48 type=EmptySD3LatentImage
- 子图0 删除节点 id=49 type=CLIPTextEncode
- 子图0 删除节点 id=50 type=KSampler
- 子图0 删除节点 id=51 type=VAEDecode
- 子图0 删除节点 id=52 type=ConditioningZeroOut
- 子图0 新增节点 id=55 type=EmptySD3LatentImage
- 子图0 新增节点 id=76 type=LoraLoaderModelOnly
- 子图0 新增节点 id=77 type=LoraLoaderModelOnly
- 子图0 新增节点 id=78 type=LoraLoaderModelOnly
- 子图0 新增节点 id=79 type=LoraLoaderModelOnly
- 子图0 新增节点 id=80 type=LoraLoaderModelOnly
- 子图0 新增节点 id=81 type=LoraLoaderModelOnly
- 子图0 新增节点 id=84 type=UNETLoader
- 子图0 新增节点 id=85 type=DualCLIPLoader
- 子图0 新增节点 id=94 type=ReservedVRAMSetter
- 子图0 新增节点 id=121 type=Fast Groups Bypasser (rgthree)
- 子图0 新增节点 id=125 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=126 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=127 type=SeedVR2LoadDiTModel
- 子图0 新增节点 id=130 type=ImageScaleToTotalPixels
- 子图0 新增节点 id=131 type=PreviewImage
- 子图0 新增节点 id=138 type=BatchPromptReaderWithClip
- 子图0 新增节点 id=142 type=ConditioningZeroOut
- 子图0 新增节点 id=143 type=CFGGuider
