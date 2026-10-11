# 官方模板对齐快照：Flux.2_Klein-9B-Distilled.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_flux2_klein_text_to_image.json
- 当前工作流：Flux.2_Klein-9B-Distilled.json

## 概览

`顶层类型 删=['7b34ab90-36f9-45ba-a665-71d418f0df18', 'PrimitiveStringMultiline', 'SaveImage', 'a67caa28-5f85-4917-8396-36004960dd30'] 加=['95960805-4e0e-42ca-98ba-6cc695c33b66', 'ResolutionSelector', 'SaveImageAdvanced']`

## 子图差异

- 子图0 新增节点 id=2 type=CLIPLoader
- 子图0 新增节点 id=3 type=VAELoader
- 子图0 新增节点 id=4 type=CLIPTextEncode
- 子图0 新增节点 id=6 type=RandomNoise
- 子图0 新增节点 id=7 type=CFGGuider
- 子图0 新增节点 id=8 type=KSamplerSelect
- 子图0 新增节点 id=9 type=Flux2Scheduler
- 子图0 新增节点 id=10 type=EmptyFlux2LatentImage
- 子图0 新增节点 id=11 type=SamplerCustomAdvanced
- 子图0 新增节点 id=12 type=VAEDecode
- 子图0 新增节点 id=15 type=CLIPTextEncode
- 子图0 新增节点 id=16 type=LoraLoaderModelOnly
- 子图0 新增节点 id=17 type=LoraLoaderModelOnly
- 子图0 新增节点 id=18 type=LoraLoaderModelOnly
- 子图0 新增节点 id=19 type=LoraLoaderModelOnly
- 子图0 新增节点 id=20 type=LoraLoaderModelOnly
- 子图0 新增节点 id=21 type=LoraLoaderModelOnly
- 子图0 新增节点 id=56 type=Fast Groups Bypasser (rgthree)
- 子图0 新增节点 id=57 type=ImageScaleToTotalPixels
- 子图0 新增节点 id=58 type=PreviewImage
- 子图0 新增节点 id=60 type=ReservedVRAMSetter
- 子图0 id=61 type=KSamplerSelect widgets变:
  - 官方: ['euler']
  - 当前: ['ema_vae_fp16.safetensors', 'cuda:0', True, 1024, 512, True, 1024, 512, 'false', 'cpu', True]
- 子图0 id=62 type=Flux2Scheduler widgets变:
  - 官方: [20, 1024, 1024]
  - 当前: [3814601556, 'randomize', 2048, 0, 1, False, 'lab', 0, 0, 0, 0, 'cpu', False]
- 子图0 id=63 type=CFGGuider widgets变:
  - 官方: [5]
  - 当前: ['seedvr2_ema_3b_fp16.safetensors', 'cuda:0', 8, True, 'cpu', True, 'sdpa']
- 子图0 删除节点 id=64 type=SamplerCustomAdvanced
- 子图0 删除节点 id=65 type=VAEDecode
- 子图0 删除节点 id=66 type=EmptyFlux2LatentImage
- 子图0 删除节点 id=67 type=CLIPTextEncode
- 子图0 删除节点 id=68 type=PrimitiveInt
- 子图0 id=69 type=PrimitiveInt widgets变:
  - 官方: [1024, 'fixed']
  - 当前: ['FLUX.2-klein-9b-fp8\\DarkBeast-Klein9b-V2-BFS-FP8.safetensors', 'default']
- 子图0 id=70 type=UNETLoader widgets变:
  - 官方: ['flux-2-klein-base-4b.safetensors', 'default']
  - 当前: ['input/Picture/', 10, 'increment', True, False, '*.txt', 'output/', False, 'user/default/batch_prompt_logs', False, Fal
- 子图0 删除节点 id=71 type=CLIPLoader
- 子图0 删除节点 id=72 type=VAELoader
- 子图0 删除节点 id=73 type=RandomNoise
- 子图0 删除节点 id=74 type=CLIPTextEncode
- 子图0 新增节点 id=76 type=ConditioningZeroOut
