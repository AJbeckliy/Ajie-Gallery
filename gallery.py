import json
from pathlib import Path

from comfy.utils import ProgressBar

from . import rh_client as rh

with (Path(__file__).parent / "web" / "commands.json").open(encoding="utf-8") as handle:
    COMMANDS = json.load(handle)
PRESETS = [command["zh"] for command in COMMANDS]
PROMPTS = {command["zh"]: f'{command["code"]} {command["zh"]}' for command in COMMANDS}
PROMPTS.update({command["zh_t"]: PROMPTS[command["zh"]] for command in COMMANDS if command.get("zh_t")})


class RHPresetGallery:
    CATEGORY = "SynVow/RunningHub"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "prompt")
    FUNCTION = "run"
    DESCRIPTION = "选择元语预设，使用 RunningHub GPT-image2.5 生成图片。运行消耗当前账户钱包余额。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (PRESETS,),
                "gpt_style": (list(rh.STYLES), {"default": "sunburst"}),
                "resolution": (list(rh.RESOLUTIONS), {"default": "1K"}),
                "aspect_ratio": (list(rh.ASPECT_RATIOS), {"default": "1:1"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                                 "tooltip": "改变此值会重新执行并计费；仅控制 ComfyUI 缓存，不是模型的随机种子。"}),
            },
            "optional": {f"image_{i}": ("IMAGE",) for i in range(1, 9)},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, preset):
        return True if preset in PROMPTS else "未知预设，请在画廊重新选择。"

    def run(self, preset, gpt_style="sunburst", resolution="1K", aspect_ratio="1:1", seed=0,
            image_1=None, image_2=None, image_3=None, image_4=None,
            image_5=None, image_6=None, image_7=None, image_8=None):
        if preset not in PROMPTS:
            raise ValueError("未知预设，请在画廊重新选择。")
        if gpt_style not in rh.STYLES or resolution not in rh.RESOLUTIONS or aspect_ratio not in rh.ASPECT_RATIOS:
            raise ValueError("GPT-image2.5 模式、比例或分辨率无效。")
        api_key, base_url = rh.resolve_credentials()
        prompt = PROMPTS[preset]
        references = rh.encode_references((image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8))
        progress = ProgressBar(4)
        urls = rh.upload_references(api_key, base_url, references)
        progress.update(1)
        task_id = rh.submit(api_key, base_url, prompt, gpt_style, aspect_ratio, resolution, urls)
        print(f"[SynVow RH Gallery] 已提交 GPT-image2.5/{gpt_style}, taskId={task_id}")
        progress.update(1)
        try:
            urls = rh.poll(api_key, base_url, task_id)
            progress.update(1)
            image = rh.download_images(urls)
        except rh.RHError as exc:
            raise rh.RHError(f"{exc} [taskId={task_id}]") from None
        progress.update(1)
        return image, prompt
