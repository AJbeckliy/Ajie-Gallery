# 示例工作流

- `01-text-to-image.json`：拖入 ComfyUI 编辑器，选择预设后运行，输出接保存图像。
- `02-image-to-image.json`：拖入编辑器，先在“加载图像”节点上传自己的参考图。更多参考图可添加加载节点，接入 image_2 至 image_8。
- `03-text-to-image-api.json`：ComfyUI `/prompt` 的 API 格式图，用于平台集成；不是直接调用 RunningHub 标准模型的请求体。

导入不会自动生成。点击运行后会消耗 RunningHub 钱包余额。示例没有 API Key、用户图片或原插件登录信息。

同样输入可能命中 ComfyUI 缓存；要再次生成可更改 seed。seed 不会发送给模型接口。
