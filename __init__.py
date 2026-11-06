from .gallery import RHPresetGallery

NODE_CLASS_MAPPINGS = {"SynVowRHPresetGallery": RHPresetGallery}
NODE_DISPLAY_NAME_MAPPINGS = {"SynVowRHPresetGallery": "元语提示画廊 · GPT-image2.5 (RH)"}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
