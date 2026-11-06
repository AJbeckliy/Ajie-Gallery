import { app } from "../../scripts/app.js";

const assetURL = path => new URL(path, import.meta.url).href;
const css = `
.synrhg-dialog{padding:0;width:min(1100px,94vw);height:86vh;max-width:94vw;max-height:90vh;color:#eee;background:#1b1e26;border:1px solid #353c4b;border-radius:16px;box-shadow:0 20px 60px #0008;font-family:system-ui,"Microsoft YaHei",sans-serif;overflow:hidden}
.synrhg-dialog::backdrop{background:#080b15c9;backdrop-filter:blur(5px)}
.synrhg-body{height:100%;display:flex;flex-direction:column;min-height:0}
.synrhg-head{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:16px 20px;border-bottom:1px solid #353c4b}
.synrhg-title{font-size:16px;font-weight:600;margin:0;color:#fff}
.synrhg-search{flex:1;min-width:130px;border:1px solid #353c4b;background:#12141a;color:#eee;border-radius:9px;padding:10px;font:inherit;font-size:13px}
.synrhg-close,.synrhg-tab,.synrhg-retry{border:0;background:#292f3e;color:#ddd;border-radius:8px;padding:8px 12px;cursor:pointer;font:inherit;font-size:13px}
.synrhg-close{margin-left:auto;font-size:18px}
.synrhg-tabs{display:flex;flex-wrap:wrap;gap:8px;padding:12px 20px}
.synrhg-tab.on{background:#5b8cff;color:white}
.synrhg-note{padding:0 20px 10px;color:#aeb9cf;font-size:12px;line-height:1.5;margin:0}
.synrhg-grid{flex:1;min-height:0;overflow:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));grid-auto-rows:max-content;align-content:start;gap:14px;padding:6px 20px 20px}
.synrhg-card{cursor:pointer;padding:0;background:#232733;border:2px solid transparent;border-radius:12px;overflow:hidden;display:flex;flex-direction:column;align-self:start;min-width:0;color:#ddd;font:inherit;transition:transform .15s,box-shadow .15s}
.synrhg-card:hover{transform:translateY(-3px);box-shadow:0 8px 20px #0007}
.synrhg-card.sel{border-color:#5b8cff}
.synrhg-card img{width:100%;aspect-ratio:1;object-fit:contain;background:#12141a;display:block}
.synrhg-label{font-size:12.5px;line-height:1.4;padding:6px 8px 10px;text-align:center;overflow-wrap:anywhere}
.synrhg-code{font-size:11px;color:#9cbbff;text-align:center;padding:6px 8px 0;overflow-wrap:anywhere}
.synrhg-placeholder{width:100%;aspect-ratio:1;display:flex;align-items:center;justify-content:center;background:#12141a;font-size:13px;color:#aeb9cf}
.synrhg-empty{grid-column:1/-1;padding:50px 12px;text-align:center;color:#b1bbd0;font-size:13px}
.synrhg-dialog button:focus-visible,.synrhg-search:focus-visible{outline:2px solid #adc5ff;outline-offset:2px}
@media(max-width:520px){.synrhg-head{padding:12px;gap:8px}.synrhg-title{font-size:14px}.synrhg-search{order:3;flex-basis:100%}.synrhg-tabs{padding:10px 12px}.synrhg-grid{padding:4px 12px 16px;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.synrhg-note{padding:0 12px 8px}}
`;

function element(tag, className, text) {
  const value = document.createElement(tag);
  value.className = className;
  if (text) value.textContent = text;
  if (tag === "button") value.type = "button";
  return value;
}

function thumbnail(command) {
  const name = `${command.code}➕${command.zh_t || command.zh}`.replace(/[\\/:*?"<>|]/g, "_") + ".jpg";
  return assetURL(`thumbs/${encodeURIComponent(name)}`);
}

function matches(text, query) {
  return query.trim().toLowerCase().split(/\s+/).filter(Boolean).every(word => {
    if (text.includes(word)) return true;
    const target = word.replace(/^\//, "");
    let index = 0;
    for (const char of text) if (char === target[index]) index++;
    return index === target.length;
  });
}

async function openGallery(widget, node) {
  if (!widget || document.getElementById("synrhg-dialog")) return;
  if (!document.getElementById("synrhg-style")) {
    const style = element("style", "");
    style.id = "synrhg-style";
    style.textContent = css;
    document.head.append(style);
  }
  const dialog = element("dialog", "synrhg-dialog");
  dialog.id = "synrhg-dialog";
  dialog.setAttribute("aria-label", "元语提示画廊");
  const body = element("div", "synrhg-body");
  const head = element("div", "synrhg-head");
  const search = element("input", "synrhg-search");
  search.type = "search";
  search.placeholder = "搜索中文、英文指令或多个关键词…";
  search.setAttribute("aria-label", "搜索预设");
  const close = element("button", "synrhg-close", "×");
  close.setAttribute("aria-label", "关闭画廊");
  close.onclick = () => dialog.close();
  head.append(element("h2", "synrhg-title", "元语提示画廊"), search, close);
  const tabs = element("div", "synrhg-tabs");
  const grid = element("div", "synrhg-grid");
  const notice = element("p", "synrhg-note", "GPT-image2.5 · 选择预设后运行节点出图 · 生成消耗 RunningHub 钱包余额");
  grid.append(element("p", "synrhg-empty", "正在加载预设…"));
  body.append(head, tabs, notice, grid);
  dialog.append(body);
  document.body.append(dialog);
  const abort = new AbortController();
  dialog.addEventListener("close", () => { abort.abort(); dialog.remove(); }, { once: true });
  dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
  dialog.showModal();
  search.focus();
  try {
    const response = await fetch(assetURL("commands.json"), { signal: abort.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const commands = await response.json();
    if (!Array.isArray(commands) || !commands.length || commands.some(c => typeof c.zh !== "string" || typeof c.code !== "string")) {
      throw new Error("预设列表格式异常");
    }
    if (!dialog.isConnected) return;
    grid.replaceChildren();
    let category = "全部";
    const cards = [];
    const empty = element("p", "synrhg-empty", "没有找到匹配的预设");
    const filter = () => {
      let count = 0;
      for (const { card, command, text } of cards) {
        const visible = (category === "全部" || command.category === category) && matches(text, search.value);
        card.style.display = visible ? "" : "none";
        if (visible) count++;
      }
      empty.style.display = count ? "none" : "";
    };
    for (const name of ["全部", ...new Set(commands.map(c => c.category).filter(Boolean))]) {
      const tab = element("button", "synrhg-tab" + (name === category ? " on" : ""), name);
      tab.setAttribute("aria-pressed", String(name === category));
      tab.onclick = () => {
        category = name;
        for (const other of tabs.children) {
          other.classList.toggle("on", other === tab);
          other.setAttribute("aria-pressed", String(other === tab));
        }
        filter();
      };
      tabs.append(tab);
    }
    for (const command of commands) {
      const selected = widget.value === command.zh || widget.value === command.zh_t;
      const card = element("button", "synrhg-card" + (selected ? " sel" : ""));
      card.title = `${command.code} ${command.zh}`;
      card.setAttribute("aria-label", card.title);
      card.setAttribute("aria-pressed", String(selected));
      const image = element("img", "");
      image.loading = "lazy";
      image.src = thumbnail(command);
      image.alt = command.zh;
      image.onerror = () => image.replaceWith(element("span", "synrhg-placeholder", "暂无预览图"));
      card.append(image, element("span", "synrhg-code", command.code), element("span", "synrhg-label", command.zh));
      card.onclick = () => {
        widget.value = command.zh;
        widget.callback?.(command.zh);
        node.setDirtyCanvas(true, true);
        dialog.close();
      };
      cards.push({ card, command, text: [command.zh, command.zh_t || "", command.code].join(" ").toLowerCase() });
      grid.append(card);
    }
    grid.append(empty);
    search.oninput = filter;
    filter();
  } catch (error) {
    if (error.name === "AbortError" || !dialog.isConnected) return;
    const message = element("div", "synrhg-empty", `画廊加载失败：${error.message}。`);
    const retry = element("button", "synrhg-retry", "重试");
    retry.onclick = () => {
      dialog.addEventListener("close", () => openGallery(widget, node), { once: true });
      dialog.close();
    };
    message.append(document.createElement("br"), retry);
    grid.replaceChildren(message);
  }
}

app.registerExtension({
  name: "SynVow.RunningHub.PresetGallery",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "SynVowRHPresetGallery") return;
    const original = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = original?.apply(this, arguments);
      const preset = this.widgets?.find(widget => widget.name === "preset");
      this.addWidget("button", "🖼 打开元语提示画廊", null, () => openGallery(preset, this), { serialize: false });
      return result;
    };
  },
});
