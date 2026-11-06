# Ajie Gallery

独立 ComfyUI 插件。保留原画廊的 200 个预设、缩略图、分类、简繁体/英文指令搜索和 8 路图片输入，使用 RunningHub GPT-image2.5 生图。无须安装 SynVow API 或 SynVow-prompt 插件。

首版不提供收藏，不读写用户收藏文件，不包含原插件的登录和余额界面。钱包扣费由 RunningHub 企业 API 处理。

## 安装

1. 在 ComfyUI 的 `custom_nodes` 目录执行 `git clone https://github.com/AJbeckliy/Ajie-Gallery.git`。
2. 进入 `Ajie-Gallery` 目录，在 ComfyUI Python 环境中运行 `python -m pip install -r requirements.txt`。PyTorch 使用 ComfyUI 已有环境，不单独安装。
3. 重启 ComfyUI 并刷新页面。
4. 添加 `SynVow/RunningHub → 元语提示画廊 · GPT-image2.5 (RH)`，输出 image 接“保存图像”或“预览图像”。

RunningHub 平台由技术人员安装、部署和适配；此包未自行发布到平台。

## v0.1.0 部署说明

RunningHub 平台上的实际出图和钱包扣费待验证。部署时请留意这三个已知行为：

- 平台用户 Key 缺失时，插件会尝试使用进程环境变量中的企业 Key。多用户部署请确保平台正确注入当前账户 Key，避免使用其他账户的钱包。
- ComfyUI 的缓存标识未区分账户。如果多个账户共享同一执行器，相同输入和 seed 可能复用上一账户的图片。多用户测试请使用按账户隔离的执行器和缓存。
- 查询任务遇到 HTTP 429 且返回空响应或 HTML 时会停止等待。请用已有 taskId 查看平台调用记录。

## 用法

- 点击“打开元语提示画廊”，搜索或选择预设。选卡片只修改预设，不发起生成。
- 有参考图时连接 `image_1` 至 `image_8`，按插口顺序作为参考；不接图时走文生图。
- 模型固定 GPT-image2.5 **Economy**；模式支持 `sunburst`（默认）和 `flare`，分辨率 1K/2K/4K。
- 接口支持的比例：1:1、3:2、2:3、5:4、4:5、16:9、9:16、21:9、3:4、4:3。默认 1:1。
- 每个插口可接 IMAGE 批次，合计不能超过平台接口上限 10 张。超过上限明确报错，不悄悄丢图。
- `seed` 仅用于让 ComfyUI 重新执行；接口不接收随机种子，不保证同 seed 重现。改变 seed 再运行会提交新任务并产生费用。
- 输出为标准 RGB `IMAGE` 和实际发送的预设短语 `STRING`。未增加 LLM 扩写，保持原有 `/指令 中文名称` 形式。
- Economy 接口没有质量、透明背景参数，首版不展示这些选项，也不自动切换到另一计费通道。

## 鉴权和请求

运行时优先读取 `PromptServer.instance.shared_api_key`。本地开发可通过进程环境变量 `RUNNINGHUB_API_KEY`（或 `RH_API_KEY`）提供企业 Key；不在工作流、前端或插件文件中填写密钥。

默认基址 `https://www.runninghub.cn/openapi/v2`，可用环境变量 `RH_API_BASE_URL` 切换到 `https://www.runninghub.ai/openapi/v2`。仅允许这两个官方地址。

1. 上传：`POST /media/upload/binary`，multipart 的 `file` 字段。
2. 文生图：`POST /rhart-image-g-2.5/{sunburst|flare}/text-to-image`。
3. 图生图：`POST /rhart-image-g-2.5/{sunburst|flare}/image-to-image`。
4. 查询：`POST /query`，JSON `{"taskId": "..."}`。
5. 下载 `results[].url` 或 `results[].outputUrl`，转换为 ComfyUI IMAGE。

生成请求只有 `prompt`、`aspectRatio`、小写 `resolution`；图生图额外传 `imageUrls`。上传和接口调用使用 Bearer 鉴权；下载结果不会附带企业 Key。TLS 证书校验保持开启。

生成提交不自动重试。查询最多等待 30 分钟，只针对网络错误、429/5xx 等查询故障做有限重试，不重新生成。任务提交后会打印 taskId；停止 ComfyUI 只停止本地等待，不代表取消平台任务或退款。超时、下载失败后先查平台调用记录，避免重新运行造成重复扣费。

## 前端接入

唯一节点 ID：`SynVowRHPresetGallery`。使用传统 `NODE_CLASS_MAPPINGS` 接口，匹配参考插件及 RunningHub 官方节点的加载方式。

`WEB_DIRECTORY=./web`。前端通过 `import.meta.url` 相对加载 `commands.json` 和 `thumbs/*.jpg`；没有自定义后端路由，也没有 `/preset_gallery/*` 路由冲突。请保留整个 web 目录、Unicode 文件名和原始大小写。

支持标准 ComfyUI 工作流编辑器。RunningHub AI 应用页面是否展示自定义画廊，由平台前端适配；即使不加载扩展 JS，后端仍有标准 preset 下拉框。旧 `PresetGallery` 工作流不会自动替换节点；请使用新节点及附带示例。

## 验证与交接

`python -m unittest discover -s tests -v` 执行无网络的模拟 API 回归。`examples` 提供可导入的文生图/图生图工作流及 API 格式示例，导入不会立即生成。

本地验证不等于 RunningHub 上线验收。上线后检查画廊资源、切换预设、1/8 张参考图、钱包扣费、实际成图和失败提示。原缩略图只作预设示意，不代表新接口复现效果。

接口来源（2026-11-05 核对）：

- [官方模型参数](https://github.com/HM-RunningHub/ComfyUI_RH_OpenAPI/blob/main/models_registry.json)，本包 references 保存了四个 GPT-image2.5 Economy 端点的快照。
- [官方鉴权实现](https://github.com/HM-RunningHub/ComfyUI_RH_OpenAPI/blob/main/core/api_key.py)
- [官方上传实现](https://github.com/HM-RunningHub/ComfyUI_RH_OpenAPI/blob/main/core/upload.py)
- [官方任务实现](https://github.com/HM-RunningHub/ComfyUI_RH_OpenAPI/blob/main/core/task.py)

预设及缩略图沿用用户原 SynVow 画廊资产；本包未对这些资产另行授予开源许可。分发范围由用户及平台确认。
