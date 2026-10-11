# 官方模板对齐快照：Qwen_image_2512.json

- 生成：2026-10-11 11:42:50
- 官方模板：image_qwen_Image_2512.json
- 当前工作流：Qwen_image_2512.json

## 概览

`顶层类型 删=['SaveImage', 'c3c58f7e-2004-43ae-8b06-a956294bf7f4'] 加=['ResolutionSelector', 'SaveImageAdvanced', 'c7300ca3-9504-4375-a665-c09529708304']`

## 子图差异

- 子图0 新增节点 id=3 type=VAELoader
- 子图0 新增节点 id=4 type=CLIPTextEncode
- 子图0 新增节点 id=6 type=EmptySD3LatentImage
- 子图0 新增节点 id=7 type=KSampler
- 子图0 新增节点 id=8 type=VAEDecode
- 子图0 新增节点 id=11 type=CLIPLoader
- 子图0 新增节点 id=15 type=CLIPTextEncode
- 子图0 新增节点 id=24 type=LoraLoaderModelOnly
- 子图0 新增节点 id=25 type=LoraLoaderModelOnly
- 子图0 新增节点 id=26 type=LoraLoaderModelOnly
- 子图0 新增节点 id=27 type=LoraLoaderModelOnly
- 子图0 新增节点 id=28 type=LoraLoaderModelOnly
- 子图0 新增节点 id=29 type=LoraLoaderModelOnly
- 子图0 新增节点 id=57 type=Fast Groups Bypasser (rgthree)
- 子图0 新增节点 id=58 type=ImageScaleToTotalPixels
- 子图0 新增节点 id=59 type=PreviewImage
- 子图0 新增节点 id=61 type=ReservedVRAMSetter
- 子图0 新增节点 id=62 type=SeedVR2LoadVAEModel
- 子图0 新增节点 id=63 type=SeedVR2VideoUpscaler
- 子图0 新增节点 id=64 type=SeedVR2LoadDiTModel
- 子图0 新增节点 id=76 type=UNETLoader
- 子图0 新增节点 id=77 type=BatchPromptReaderWithClip
- 子图0 新增节点 id=83 type=ComfySwitchNode
- 子图0 新增节点 id=84 type=ComfySwitchNode
- 子图0 新增节点 id=85 type=ComfySwitchNode
- 子图0 新增节点 id=86 type=PrimitiveBoolean
- 子图0 新增节点 id=87 type=PrimitiveInt
- 子图0 新增节点 id=88 type=PrimitiveInt
- 子图0 新增节点 id=89 type=PrimitiveFloat
- 子图0 新增节点 id=90 type=PrimitiveFloat
- 子图0 删除节点 id=218 type=PrimitiveFloat
- 子图0 删除节点 id=219 type=CLIPLoader
- 子图0 删除节点 id=220 type=VAELoader
- 子图0 删除节点 id=221 type=LoraLoaderModelOnly
- 子图0 删除节点 id=222 type=ModelSamplingAuraFlow
- 子图0 删除节点 id=223 type=PrimitiveFloat
- 子图0 删除节点 id=224 type=PrimitiveInt
- 子图0 删除节点 id=225 type=PrimitiveInt
- 子图0 删除节点 id=226 type=UNETLoader
- 子图0 删除节点 id=227 type=CLIPTextEncode
- 子图0 删除节点 id=228 type=CLIPTextEncode
- 子图0 删除节点 id=229 type=PrimitiveBoolean
- 子图0 删除节点 id=230 type=KSampler
- 子图0 删除节点 id=231 type=VAEDecode
- 子图0 删除节点 id=232 type=EmptySD3LatentImage
- 子图0 删除节点 id=233 type=ComfySwitchNode
- 子图0 删除节点 id=240 type=ComfySwitchNode
- 子图0 删除节点 id=243 type=ComfySwitchNode
