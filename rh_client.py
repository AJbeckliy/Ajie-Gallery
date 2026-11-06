"""RunningHub GPT-image2.5 Economy: upload, submit once, poll and download."""

import io
import os
import re
import time
from urllib.parse import urlsplit

import numpy as np
import requests
import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from server import PromptServer
from comfy.model_management import throw_exception_if_processing_interrupted

BASE_URLS = ("https://www.runninghub.cn/openapi/v2", "https://www.runninghub.ai/openapi/v2")
STYLES = ("sunburst", "flare")
ASPECT_RATIOS = ("1:1", "3:2", "2:3", "5:4", "4:5", "16:9", "9:16", "21:9", "3:4", "4:3")
RESOLUTIONS = ("1K", "2K", "4K")
MAX_REFERENCE_IMAGES = 10  # Platform limit, including images inside connected batches.
MAX_REFERENCE_BYTES = 50 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
POLL_SECONDS = 5
POLL_TIMEOUT = 1800


class RHError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def resolve_credentials():
    key = getattr(PromptServer.instance, "shared_api_key", None)
    if not isinstance(key, str) or not key.strip() or key.strip() == "unknown":
        key = os.environ.get("RUNNINGHUB_API_KEY") or os.environ.get("RH_API_KEY", "")
    key = key.strip()
    if not key or key == "unknown":
        raise RHError("未获得 RunningHub 企业 API Key。平台请检查 shared_api_key 注入；本地请设置 RUNNINGHUB_API_KEY。")
    base_url = os.environ.get("RH_API_BASE_URL", BASE_URLS[0]).strip().rstrip("/")
    if base_url not in BASE_URLS:
        raise RHError("RH_API_BASE_URL 只支持 RunningHub 国内或国际站的 /openapi/v2 地址。")
    return key, base_url


def _safe_message(value, api_key):
    text = str(value or "未提供错误详情").replace(api_key, "[redacted]")
    return re.sub(r"https?://\S+", "[url]", text).replace("\n", " ")[:400]


def _body(data):
    return data["data"] if isinstance(data.get("data"), dict) else data


def _post(api_key, base_url, path, *, payload=None, files=None, query=False):
    throw_exception_if_processing_interrupted()
    try:
        with requests.post(
            f"{base_url}/{path}", headers={"Authorization": f"Bearer {api_key}"},
            json=payload, files=files, timeout=(10, 30) if query else (30, 180),
            allow_redirects=False,
        ) as response:
            status = response.status_code
            try:
                data = response.json()
            except ValueError:
                raise RHError(f"RunningHub 返回非 JSON 响应（HTTP {status}）。", query and (status == 200 or status >= 500)) from None
    except requests.RequestException as exc:
        raise RHError(f"RunningHub 网络请求失败（{type(exc).__name__}）。", query) from None
    if not isinstance(data, dict):
        raise RHError("RunningHub 响应格式异常。", query)
    if status != 200:
        message = _safe_message(data.get("errorMessage") or data.get("message") or data.get("msg"), api_key)
        raise RHError(f"RunningHub HTTP {status}：{message}", query and (status == 429 or status >= 500))
    for item in (data, _body(data)):
        code = item.get("errorCode") or item.get("error_code") or item.get("code")
        message = item.get("errorMessage") or item.get("error_message")
        if code not in (None, "", 0, "0") or message:
            detail = _safe_message(message or item.get("message") or item.get("msg"), api_key)
            raise RHError(f"RunningHub 接口失败（code={_safe_message(code, api_key)}）：{detail}")
    return _body(data)


def encode_references(images):
    count = sum(int(image.shape[0]) for image in images if image is not None)
    if count > MAX_REFERENCE_IMAGES:
        raise ValueError(f"GPT-image2.5 最多接收 {MAX_REFERENCE_IMAGES} 张参考图，当前批次共 {count} 张；请拆分批次。")
    encoded = []
    for image in images:
        if image is None:
            continue
        if image.ndim != 4 or image.shape[-1] not in (1, 3, 4) or image.shape[0] == 0:
            raise ValueError("参考图需要非空的 ComfyUI IMAGE（B,H,W,C）。")
        for frame in image:
            array = np.clip(frame.detach().cpu().numpy() * 255, 0, 255).astype(np.uint8)
            if array.shape[-1] == 1:
                array = array[..., 0]
            buffer = io.BytesIO()
            Image.fromarray(array).save(buffer, format="PNG")
            content = buffer.getvalue()
            if len(content) > MAX_REFERENCE_BYTES:
                raise ValueError("单张参考图 PNG 超过 RunningHub 的 50 MB 上限，请缩小图片后再试。")
            encoded.append(content)
    return encoded


def _check_url(value):
    if not isinstance(value, str) or urlsplit(value).scheme not in ("https", "http") or not urlsplit(value).netloc:
        raise RHError("RunningHub 未返回有效的图片地址。")
    return value


def upload_references(api_key, base_url, references):
    urls = []
    for index, content in enumerate(references, 1):
        data = _post(api_key, base_url, "media/upload/binary", files={
            "file": (f"gallery_ref_{index:02d}.png", content, "image/png"),
        })
        urls.append(_check_url(data.get("download_url")))
    return urls


def submit(api_key, base_url, prompt, style, aspect_ratio, resolution, image_urls):
    if style not in STYLES or aspect_ratio not in ASPECT_RATIOS or resolution not in RESOLUTIONS:
        raise ValueError("GPT-image2.5 模式、比例或分辨率无效，请重新选择节点参数。")
    mode = "image-to-image" if image_urls else "text-to-image"
    payload = {"prompt": prompt, "aspectRatio": aspect_ratio, "resolution": resolution.lower()}
    if image_urls:
        payload["imageUrls"] = image_urls
    try:
        data = _post(api_key, base_url, f"rhart-image-g-2.5/{style}/{mode}", payload=payload)
    except RHError as exc:
        raise RHError(f"{exc} 未自动重发生成请求；重新运行前请检查平台调用记录，避免重复扣费。") from None
    task_id = data.get("taskId") or data.get("task_id")
    if not isinstance(task_id, (str, int)) or not str(task_id).strip():
        raise RHError("提交未返回 taskId，未自动重试；请先检查平台调用记录。")
    return str(task_id)


def _sleep(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        throw_exception_if_processing_interrupted()
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))


def poll(api_key, base_url, task_id):
    deadline = time.monotonic() + POLL_TIMEOUT
    failures = 0
    while time.monotonic() < deadline:
        try:
            data = _post(api_key, base_url, "query", payload={"taskId": task_id}, query=True)
        except RHError as exc:
            failures += 1
            if not exc.retryable or failures >= 5:
                raise RHError(f"{exc} 查询停止，taskId={task_id}；请去平台调用记录查询，未重新生成。") from None
            _sleep(POLL_SECONDS)
            continue
        failures = 0
        status = str(data.get("status", "")).strip().upper()
        if status == "SUCCESS":
            results = data.get("results")
            if not isinstance(results, list) or not results:
                raise RHError(f"任务完成但没有图片结果，taskId={task_id}。")
            urls = []
            for result in results:
                if isinstance(result, dict):
                    url = result.get("url") or result.get("outputUrl")
                    if url:
                        urls.append(_check_url(url))
            if not urls:
                raise RHError(f"任务完成但未返回图片地址，taskId={task_id}。")
            return list(dict.fromkeys(urls))
        if status in ("FAILED", "CANCEL", "CANCELLED", "CANCELED"):
            detail = _safe_message(data.get("failedReason") or data.get("errorMessage") or data.get("message"), api_key)
            raise RHError(f"生成任务 {status}：{detail}；taskId={task_id}。")
        if status not in ("QUEUED", "RUNNING", "CREATE", "PENDING", "PROCESSING"):
            raise RHError(f"任务状态无法识别，taskId={task_id}；请查看平台调用记录。")
        _sleep(POLL_SECONDS)
    raise RHError(f"已等待 {POLL_TIMEOUT} 秒，停止查询；taskId={task_id}。平台任务可能仍在运行，请先查询调用记录。")


def download_images(urls):
    images = []
    for url in urls:
        throw_exception_if_processing_interrupted()
        buffer = io.BytesIO()
        try:
            # Do not send the enterprise API key to the result storage host.
            with requests.get(_check_url(url), stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(1024 * 1024):
                    throw_exception_if_processing_interrupted()
                    if buffer.tell() + len(chunk) > MAX_DOWNLOAD_BYTES:
                        raise RHError("结果图片超过 100 MB，请从平台调用记录下载原文件。")
                    buffer.write(chunk)
            buffer.seek(0)
            with Image.open(buffer) as source:
                rgb = ImageOps.exif_transpose(source).convert("RGB")
                images.append(torch.from_numpy(np.array(rgb).astype(np.float32) / 255.0).unsqueeze(0))
        except requests.RequestException as exc:
            raise RHError(f"结果图片下载失败（{type(exc).__name__}），请从平台调用记录获取已生成结果。") from None
        except (UnidentifiedImageError, OSError):
            raise RHError("结果无法解码为图片，请检查平台调用记录。") from None
    if not images:
        raise RHError("没有可下载的结果图片。")
    if any(image.shape[1:] != images[0].shape[1:] for image in images):
        raise RHError("平台返回的多张图片尺寸不同，无法合并为 IMAGE 批次；请从调用记录下载原图。")
    return torch.cat(images, dim=0)
