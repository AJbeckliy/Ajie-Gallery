"""Offline contract tests; no real API key, network access or paid generation."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class Interrupted(Exception):
    pass


server = types.ModuleType("server")
server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(shared_api_key="test-platform-key"))
comfy = types.ModuleType("comfy")
utils = types.ModuleType("comfy.utils")
utils.ProgressBar = Mock()
management = types.ModuleType("comfy.model_management")
management.throw_exception_if_processing_interrupted = Mock()
with patch.dict(sys.modules, {"server": server, "comfy": comfy, "comfy.utils": utils, "comfy.model_management": management}):
    spec = importlib.util.spec_from_file_location("synrh_gallery_tests", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
gallery = package.gallery
rh = gallery.rh


def response(data=None, status=200, content=None):
    result = Mock(status_code=status)
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.json.return_value = data
    result.iter_content.return_value = [content] if content is not None else []
    return result


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (7, 5), (255, 64, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        server.PromptServer.instance.shared_api_key = "test-platform-key"
        management.throw_exception_if_processing_interrupted.reset_mock(side_effect=True)
        self.network = patch.object(requests, "post", side_effect=AssertionError("Unexpected network"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.get_network = patch.object(requests, "get", side_effect=AssertionError("Unexpected download"))
        self.get_network.start()
        self.addCleanup(self.get_network.stop)

    def test_package_loads_without_original_plugin(self):
        self.assertEqual(list(package.NODE_CLASS_MAPPINGS), ["SynVowRHPresetGallery"])
        self.assertEqual(package.WEB_DIRECTORY, "./web")
        schema = gallery.RHPresetGallery.INPUT_TYPES()
        self.assertEqual(list(schema["optional"]), [f"image_{i}" for i in range(1, 9)])
        self.assertNotIn("api_key", schema["required"])
        self.assertNotIn("quality", schema["required"])

    def test_all_200_thumbnails_exist_and_decode(self):
        self.assertEqual(len(gallery.COMMANDS), 200)
        self.assertEqual(len(set(gallery.PRESETS)), 200)
        for command in gallery.COMMANDS:
            name = f'{command["code"]}➕{command.get("zh_t") or command["zh"]}'
            for char in '\\/:*?"<>|':
                name = name.replace(char, "_")
            with Image.open(ROOT / "web" / "thumbs" / (name + ".jpg")) as image:
                image.verify()

    def test_traditional_preset_resolves_to_same_prompt(self):
        for command in gallery.COMMANDS:
            self.assertTrue(gallery.RHPresetGallery.VALIDATE_INPUTS(command["zh"]))
            if command.get("zh_t"):
                self.assertEqual(gallery.PROMPTS[command["zh_t"]], gallery.PROMPTS[command["zh"]])

    def test_platform_key_wins_and_environment_is_fallback(self):
        os.environ["RUNNINGHUB_API_KEY"] = "test-local-key"
        self.assertEqual(rh.resolve_credentials()[0], "test-platform-key")
        server.PromptServer.instance.shared_api_key = "unknown"
        self.assertEqual(rh.resolve_credentials()[0], "test-local-key")

    def test_missing_key_fails_before_upload(self):
        server.PromptServer.instance.shared_api_key = ""
        with self.assertRaisesRegex(rh.RHError, "未获得"):
            gallery.RHPresetGallery().run(gallery.PRESETS[0], image_1=torch.zeros((1, 4, 4, 3)))
        requests.post.assert_not_called()

    def test_custom_host_rejected_before_key_sent(self):
        os.environ["RH_API_BASE_URL"] = "https://example.com/openapi/v2"
        with self.assertRaisesRegex(rh.RHError, "只支持"):
            rh.resolve_credentials()
        requests.post.assert_not_called()

    def test_invalid_preset_or_parameters_cannot_generate(self):
        for kwargs in ({"preset": "missing"}, {"preset": gallery.PRESETS[0], "gpt_style": "../../other"},
                       {"preset": gallery.PRESETS[0], "resolution": "8K"}):
            with self.assertRaises(ValueError):
                gallery.RHPresetGallery().run(**kwargs)
        requests.post.assert_not_called()

    def test_all_four_payloads_match_official_registry(self):
        registry = json.loads((ROOT / "references" / "runninghub-gpt-image-2.5-20261105.json").read_text(encoding="utf-8-sig"))
        endpoints = {item["endpoint"]: item for item in registry}
        for style in rh.STYLES:
            for image_urls in ([], ["https://assets.example/ref.png"]):
                with patch.object(requests, "post", return_value=response({"taskId": "task-1"})) as post:
                    rh.submit("test-key", rh.BASE_URLS[0], "prompt", style, "1:1", "2K", image_urls)
                endpoint = post.call_args.args[0].split("/openapi/v2/")[1]
                params = {p["fieldKey"]: p for p in endpoints[endpoint]["params"]}
                payload = post.call_args.kwargs["json"]
                self.assertTrue(set(payload) <= set(params))
                self.assertEqual(payload["resolution"], "2k")
                self.assertNotIn("seed", payload)
                for key, options in (("aspectRatio", rh.ASPECT_RATIOS), ("resolution", [r.lower() for r in rh.RESOLUTIONS])):
                    self.assertTrue(set(options) <= {v["value"] for v in params[key]["options"]})

    def test_text_to_image_full_flow(self):
        with patch.object(requests, "post", side_effect=[response({"taskId": "task-text"}),
                response({"status": "SUCCESS", "results": [{"url": "https://assets.example/result.png"}]})]) as post, \
                patch.object(requests, "get", return_value=response(content=png())) as get:
            output, prompt = gallery.RHPresetGallery().run(gallery.PRESETS[0], seed=42)
        self.assertEqual(tuple(output.shape), (1, 5, 7, 3))
        self.assertEqual(output.dtype, torch.float32)
        self.assertAlmostEqual(output[0, 0, 0, 1].item(), 64 / 255, places=6)
        self.assertEqual(prompt, gallery.PROMPTS[gallery.PRESETS[0]])
        self.assertEqual(post.call_count, 2)
        self.assertNotIn("headers", get.call_args.kwargs)
        self.assertTrue(all(call.kwargs.get("verify", True) for call in post.call_args_list))

    def test_eight_image_inputs_keep_order_and_use_edit_endpoint(self):
        references = {f"image_{i}": torch.full((1, 4, 4, 3), i / 10) for i in range(1, 9)}
        responses = [response({"code": 0, "data": {"download_url": f"https://assets.example/ref{i}.png"}}) for i in range(1, 9)]
        responses += [response({"data": {"taskId": "task-edit"}}), response({"data": {
            "status": "SUCCESS", "results": [{"outputUrl": "https://assets.example/result.png"}]}})]
        with patch.object(requests, "post", side_effect=responses) as post, patch.object(requests, "get", return_value=response(content=png())):
            gallery.RHPresetGallery().run(gallery.PRESETS[0], gpt_style="flare", **references)
        self.assertEqual(post.call_count, 10)
        submit_call = post.call_args_list[8]
        self.assertTrue(submit_call.args[0].endswith("/flare/image-to-image"))
        self.assertEqual(submit_call.kwargs["json"]["imageUrls"], [f"https://assets.example/ref{i}.png" for i in range(1, 9)])
        for i, call in enumerate(post.call_args_list[:8], 1):
            with Image.open(io.BytesIO(call.kwargs["files"]["file"][1])) as image:
                self.assertEqual(image.getpixel((0, 0)), (int(i / 10 * 255),) * 3)

    def test_batch_limit_checked_before_any_upload(self):
        self.assertEqual(len(rh.encode_references([torch.zeros((10, 2, 2, 3))])), 10)
        with self.assertRaisesRegex(ValueError, "11"):
            gallery.RHPresetGallery().run(gallery.PRESETS[0], image_1=torch.zeros((11, 2, 2, 3)))
        requests.post.assert_not_called()

    def test_submit_timeout_never_retries(self):
        with patch.object(requests, "post", side_effect=requests.Timeout("secret should not appear")) as post:
            with self.assertRaisesRegex(rh.RHError, "未自动重发") as error:
                rh.submit("test-key", rh.BASE_URLS[0], "p", "sunburst", "1:1", "1K", [])
        self.assertNotIn("secret", str(error.exception))
        self.assertEqual(post.call_count, 1)

    def test_wallet_error_stops_without_retry_or_key_leak(self):
        with patch.object(requests, "post", return_value=response({"errorCode": "1014", "errorMessage": "balance test-key https://example.com/secret"})) as post:
            with self.assertRaises(rh.RHError) as error:
                rh.submit("test-key", rh.BASE_URLS[0], "p", "sunburst", "1:1", "1K", [])
        self.assertNotIn("test-key", str(error.exception))
        self.assertNotIn("example.com", str(error.exception))
        self.assertIn("1014", str(error.exception))
        self.assertEqual(post.call_count, 1)

    def test_upload_failure_does_not_submit_generation(self):
        with patch.object(requests, "post", return_value=response({"code": 1014, "message": "upload denied"})) as post:
            with self.assertRaises(rh.RHError):
                gallery.RHPresetGallery().run(gallery.PRESETS[0], image_1=torch.zeros((1, 2, 2, 3)))
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith("/media/upload/binary"))

    def test_poll_recovers_transient_errors_without_resubmit(self):
        with patch.object(requests, "post", side_effect=[requests.Timeout(), response({"message": "busy"}, status=503),
                response({"status": "RUNNING"}), response({"status": "SUCCESS", "results": [{"url": "https://example.com/a.png"}]})]) as post, \
                patch.object(rh, "_sleep"):
            self.assertEqual(rh.poll("test-key", rh.BASE_URLS[0], "task-poll"), ["https://example.com/a.png"])
        self.assertTrue(all(call.args[0].endswith("/query") for call in post.call_args_list))

    def test_poll_auth_error_not_retried(self):
        with patch.object(requests, "post", return_value=response({"message": "unauthorized"}, status=401)) as post:
            with self.assertRaisesRegex(rh.RHError, "task-auth"):
                rh.poll("test-key", rh.BASE_URLS[0], "task-auth")
        self.assertEqual(post.call_count, 1)

    def test_poll_has_bounded_network_retries(self):
        with patch.object(requests, "post", side_effect=requests.Timeout()) as post, patch.object(rh, "_sleep"):
            with self.assertRaisesRegex(rh.RHError, "task-net"):
                rh.poll("test-key", rh.BASE_URLS[0], "task-net")
        self.assertEqual(post.call_count, 5)

    def test_poll_failed_cancelled_unknown_and_empty_results(self):
        for data in ({"status": "FAILED"}, {"status": "CANCEL"}, {"status": "UNKNOWN"},
                     {"status": "SUCCESS", "results": []}, {"status": "SUCCESS", "results": [{"text": "no image"}]}):
            with patch.object(requests, "post", return_value=response(data)) as post:
                with self.assertRaisesRegex(rh.RHError, "task-fail"):
                    rh.poll("test-key", rh.BASE_URLS[0], "task-fail")
            self.assertEqual(post.call_count, 1)

    def test_poll_timeout_preserves_task_id(self):
        with patch.object(rh, "POLL_TIMEOUT", 0):
            with self.assertRaisesRegex(rh.RHError, "task-slow"):
                rh.poll("test-key", rh.BASE_URLS[0], "task-slow")
        requests.post.assert_not_called()

    def test_interrupt_propagates_without_retry(self):
        management.throw_exception_if_processing_interrupted.side_effect = Interrupted()
        with self.assertRaises(Interrupted):
            rh.poll("test-key", rh.BASE_URLS[0], "task-stop")
        with self.assertRaises(Interrupted):
            rh._sleep(1)
        requests.post.assert_not_called()

    def test_bad_download_keeps_task_id_at_node_boundary(self):
        with patch.object(requests, "post", side_effect=[response({"taskId": "task-download"}),
                response({"status": "SUCCESS", "results": [{"url": "https://example.com/a.png"}]})]), \
                patch.object(requests, "get", return_value=response(content=b"not an image")):
            with self.assertRaisesRegex(rh.RHError, "task-download"):
                gallery.RHPresetGallery().run(gallery.PRESETS[0])


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
