"""Use an existing ComfyUI installation to load and validate, without execution.

Usage: python tests/check_comfy_registration.py /path/to/ComfyUI
"""

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
comfy_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(comfy_root))
sys.argv = ["gallery-registration-check", "--cpu"]

import nodes  # noqa: E402
import execution  # noqa: E402


async def check():
    assert await nodes.load_custom_node(str(ROOT)), "Plugin failed to load"
    node = nodes.NODE_CLASS_MAPPINGS["SynVowRHPresetGallery"]
    assert len(node.INPUT_TYPES()["required"]["preset"][0]) == 200
    assert len(node.INPUT_TYPES()["optional"]) == 8
    assert node.RETURN_TYPES == ("IMAGE", "STRING")
    assert nodes.EXTENSION_WEB_DIRS[ROOT.name] == str(ROOT / "web")
    workflow = json.loads((ROOT / "examples" / "03-text-to-image-api.json").read_text(encoding="utf-8"))
    result = await execution.validate_prompt("gallery-offline-validation", workflow, None)
    assert result[0], result
    for path in sorted((ROOT / "examples").glob("0[12]-*.json")):
        graph = json.loads(path.read_text(encoding="utf-8"))
        graph_nodes = {item["id"]: item for item in graph["nodes"]}
        for item in graph_nodes.values():
            assert item["type"] in nodes.NODE_CLASS_MAPPINGS, item["type"]
        for link_id, source, output, target, input_index, dtype in graph["links"]:
            assert link_id in graph_nodes[source]["outputs"][output]["links"]
            assert graph_nodes[target]["inputs"][input_index]["link"] == link_id
            assert graph_nodes[target]["inputs"][input_index]["type"] == dtype
    print("PASS: actual ComfyUI node loading, web directory registration, 200 presets, 8 image inputs")
    print("PASS: actual ComfyUI API prompt validation; both editor workflow links checked")
    print("No prompt submitted; no model requests or wallet charges.")


if __name__ == "__main__":
    asyncio.run(check())
