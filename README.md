

## Usage
```
usage:

Windows [Version 10.0.22631.3737]
(c) Microsoft Corporation. All rights reserved.

C:\Work\tom\Project\et_al>python
Python 3.12.4 (tags/v3.12.4:8e8a4ba, Jun  6 2024, 19:30:16) [MSC v.1940 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license" for more information.

>>> from enntest import exynos
>>> root = exynos()
>>> root.help()
>>> out = root.connect("sam", "Thunder$@88")
>>> root.devices()

* 사용할 디바이스와 명령어 설정하고 평가할 모델과 입력 바이너리, 골든 바이너리 위치 선택 그리고 옵션 설정
>>> device = "000012b58f246013"
>>> cmd = "EnnTest_v2_service"
>>> model = r"C:\Work\tom\Project\AI_Application_Servie_Team\ExynosTestTool\enntest\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore.nnc"
>>> input = r"C:\Work\tom\Project\AI_Application_Servie_Team\ExynosTestTool\enntest\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore_input_data.bin"
>>> gold = r"C:\Work\tom\Project\AI_Application_Servie_Team\ExynosTestTool\enntest\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore_golden_data.bin"
>>> option = "--profile summary --iter 3"
>>> result_file = root.analyze(device=device, exe_cmd=cmd, nnc_model=model, input_binary=input, golden_binary=gold, option=option)
>>> print(result_file)
>>> out = root.show(profile_file=result_file)
   
```
