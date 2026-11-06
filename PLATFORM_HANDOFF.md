# RunningHub 技术交接 · v0.1.0

日期：2026-11-05。当前状态：独立插件已实现，本地验证完成，待平台部署与真实生图验收。

## 已确认范围

- 用户已确认企业 API 与运行用户绑定，费用扣其 RunningHub 钱包。插件不实现独立钱包、登录或账单系统。
- 仅 GPT-image2.5：默认 Economy / sunburst，可切换 flare。不包含 GPT-image2 或 LLM。
- 200 个原预设、200 张原缩略图、分类搜索、8 路参考图；无收藏功能，未来有账户存储接口再接。
- 保持原预设提示词，不引入扩写或额外模型调用。

## 平台部署

1. 安装整个目录，使用现有 ComfyUI Python 环境安装 requirements.txt；重新加载后端与前端扩展。
2. 节点类 ID `SynVowRHPresetGallery`，中文名称“元语提示画廊 · GPT-image2.5 (RH)”。不要映射成原插件的 `PresetGallery`，避免冲突。
3. 运行时提供 `PromptServer.instance.shared_api_key`。不需要用户在节点里填写 Key；插件不会把 Key 保存进工作流或发给前端。
4. 保留 `WEB_DIRECTORY` 下的 JS、JSON、缩略图资源。资源通过 JS 自身 URL 相对访问，支持代理前缀，无自定义后端路由。
5. 如果 AI 应用页面无法展示自定义弹窗，由平台适配；节点本身仍保留标准 preset 下拉输入。
6. 导入 examples/01-text-to-image.json 或 examples/02-image-to-image.json。图生图例需先上传用户图片。

请求契约及官方来源见 README.md 与 references/ 参数快照。界面没有质量、透明背景或 API Key 输入；请勿在平台映射中添加未被此端点支持的字段。

## 本地验证结果

| 检查 | 结果与范围 |
| --- | --- |
| Python 回归 | 21 项通过，模拟 HTTP，无真实模型请求 |
| 模型参数 | sunburst/flare × 文生图/图生图的 4 个请求体对照官方参数快照通过 |
| 参考图 | 8 插口上传顺序、10 张平台总上限、超限先报错通过 |
| 请求失败 | 缺 Key、企业权限/钱包错误、上传失败、提交超时不重试、查询暂时失败和有限重试通过 |
| 任务管理 | 成功/失败/取消/未知状态、30 分钟等待期限、中断传播、下载失败带 taskId 通过 |
| 图像解码 | 实际 PNG 编解码及 RGB float32 IMAGE 输出通过 |
| 原资产 | 200 个预设、200 张缩略图完整，缩略图逐张解码通过 |
| ComfyUI 本地 | 使用 H 盘现有 ComfyUI 的真实 load_custom_node 加载通过，web 目录登记通过；真实 validate_prompt 验证 API 示例通过，未执行图 |
| 编辑器示例 | 两个 JSON 工作流节点类型与连线一致性通过；尚未在 RunningHub 编辑器导入验证 |
| 浏览器 | 真实 Chromium + 最小 ComfyUI 宿主模拟页面，通过根路径/代理前缀加载、搜索分类、选择回填、手机宽度、关闭、加载失败重试、图片缺失占位 |
| 静态检查 | Ruff 与 JavaScript 语法检查通过 |

浏览器测试页面只模拟 ComfyUI 挂载接口，不等于完整编辑器或 RunningHub 平台验证。

## 上线后验收

1. 普通用户进入工作流，画廊能打开、预览图完整、选卡会修改 preset。
2. 不填 Key，文生图完成，查看实际钱包扣费及调用记录。
3. 分别以 1 张、8 张图片完成图生图，检查参考顺序与效果；切换 flare 和分辨率。
4. 核对图片保存与下载；对照原缩略图评估预设效果。短语可被原样发送不代表两个服务会生成相同结果。
5. 验证余额不足/鉴权异常显示可理解错误；停止本地等待后到平台调用记录检查任务状态。

生成提交不自动重试。停止等待、超时或下载失败不代表平台任务取消或退款；请先查 taskId，再决定是否重新运行。

## 复查命令

在插件目录、ComfyUI Python 环境执行：

```text
python -m unittest discover -s tests -v
python tests/check_comfy_registration.py <ComfyUI源码目录>
python -m ruff check __init__.py gallery.py rh_client.py tests
node --check web/gallery.js
node tests/browser_gallery.cjs <playwright-core目录> <Chromium可执行文件> <截图输出目录>
```

Ruff、Node、playwright-core、Chromium 仅用于开发验证，不是插件运行依赖。
