const AXIOXMEDIA_BRAND = "Axiox Media";
const AIO_WATERMARK = "axioxmedia";

const I18N = {
  zh: {
    appTitle: "风格抠图台",
    appSubtitle: "先抠底，再实时调风格，最后按尺寸导出 PNG",
    formTitle: "加工一张图",
    dropTitle: "把原图拖到这里",
    dropSub: "或点击选择 PNG / JPG / WEBP",
    cutLabel: "抠底方式",
    chromaColor: "色键",
    chromaStrength: "强度",
    styleKicker: "风格",
    presetLabel: "风格预设",
    fillLabel: "背景填充",
    fillTransparent: "保持透明",
    lutLabel: "全局颜色 / LUT",
    plateLabel: "底图 / 边框",
    platePick: "选择底图",
    plateOn: "启用底图",
    padOuter: "外 padding（图边距）",
    padInner: "内 padding（框与图标）",
    exportKicker: "导出",
    exportLabel: "导出尺寸",
    compress: "压缩 PNG",
    forceStretch: "强制拉升为正方形",
    forceHint: "勾选后可把 569×570 强行拉到 1024×1024，不再受原图长边限制。",
    runBtn: "开始抠底",
    saveBtn: "另存为 PNG",
    previewTitle: "结果预览",
    viewStyled: "风格结果",
    viewCut: "抠底件",
    viewSource: "原始图",
    previewEmpty: "还没有图片",
    needImage: "先放入一张原图",
    workingCut: "正在抠底…",
    workingStyle: "正在更新预览…",
    liveUpdating: "更新预览…",
    ready: "抠底完成，可调风格",
    saved: "已保存",
    plateReady: "底图已载入",
    noSavePath: "未选择保存路径",
    cutFirst: "先完成抠底",
    reloadBtn: "重新加载图片",
    idle: "就绪",
    error: "出错",
  },
  en: {
    appTitle: "Style Cut Desk",
    appSubtitle: "Cut first, tweak style live, then export a PNG",
    formTitle: "Process one image",
    dropTitle: "Drop the source image here",
    dropSub: "or click to pick PNG / JPG / WEBP",
    cutLabel: "Cutout mode",
    chromaColor: "Key color",
    chromaStrength: "Strength",
    styleKicker: "Style",
    presetLabel: "Style presets",
    fillLabel: "Background fill",
    fillTransparent: "Keep transparent",
    lutLabel: "Global color / LUT",
    plateLabel: "Plate / frame",
    platePick: "Choose plate",
    plateOn: "Enable plate",
    padOuter: "Outer padding (to canvas edge)",
    padInner: "Inner padding (frame to icon)",
    exportKicker: "Export",
    exportLabel: "Export size",
    compress: "Compress PNG",
    forceStretch: "Force stretch to square",
    forceHint: "On: a 569×570 source can be forced to 1024×1024, ignoring the source long side.",
    runBtn: "Remove background",
    saveBtn: "Save PNG as…",
    previewTitle: "Preview",
    viewStyled: "Styled",
    viewCut: "Cutout",
    viewSource: "Source",
    previewEmpty: "No image yet",
    needImage: "Drop a source image first",
    workingCut: "Removing background…",
    workingStyle: "Updating preview…",
    liveUpdating: "Updating…",
    ready: "Cutout ready — tweak style",
    saved: "Saved",
    plateReady: "Plate loaded",
    noSavePath: "No save path selected",
    cutFirst: "Finish the cutout first",
    reloadBtn: "Reload image",
    idle: "Ready",
    error: "Error",
  },
};

const state = {
  lang: "zh",
  jobId: "",
  presets: [],
  luts: [],
  preset: "white-stencil",
  cutMode: "auto",
  view: "source",
  hasCut: false,
  hasStyled: false,
  sizes: [],
  styleTimer: 0,
  styling: false,
  pendingStyle: false,
  statusKey: "idle",
  hintKey: "",
  hintExtra: "",
};

function detectUiLang() {
  const saved = localStorage.getItem("aio.uiLang") || localStorage.getItem("stylecut.lang");
  if (saved === "zh" || saved === "en") return saved;
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}

function persistUiLang(lang) {
  localStorage.setItem("aio.uiLang", lang);
  localStorage.setItem("stylecut.lang", lang);
}

function t(key) {
  return (I18N[state.lang] && I18N[state.lang][key]) || I18N.zh[key] || key;
}

function applyI18n() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-ui-lang]").forEach((btn) => {
    btn.classList.toggle("on", btn.getAttribute("data-ui-lang") === state.lang);
  });
  renderPresets();
  renderLuts();
  renderSizes();
  const preset = state.presets.find((p) => p.id === state.preset);
  if (preset) {
    document.getElementById("presetHint").textContent = state.lang === "zh" ? preset.hint_zh : preset.hint_en;
  }
  document.getElementById("statusChip").textContent = t(state.statusKey || "idle");
  const hintBits = [];
  if (state.hintKey) hintBits.push(t(state.hintKey));
  if (state.hintExtra) hintBits.push(state.hintExtra);
  document.getElementById("runHint").textContent = hintBits.join(" · ");
}

function setChip(key) {
  state.statusKey = key || "idle";
  document.getElementById("statusChip").textContent = t(state.statusKey);
}

function setHint(key, extra) {
  state.hintKey = key || "";
  state.hintExtra = extra || "";
  const bits = [];
  if (state.hintKey) bits.push(t(state.hintKey));
  if (state.hintExtra) bits.push(state.hintExtra);
  document.getElementById("runHint").textContent = bits.join(" · ");
}

function showProgress(on, label, percent) {
  const modal = document.getElementById("progressModal");
  modal.classList.toggle("hidden", !on);
  if (label) document.getElementById("progressLabel").textContent = label;
  if (typeof percent === "number") {
    document.getElementById("progressBar").style.width = `${Math.max(6, Math.min(100, percent))}%`;
  }
}

function setPostCutVisible(on) {
  document.getElementById("styleSection").classList.toggle("hidden", !on);
  document.getElementById("exportSection").classList.toggle("hidden", !on);
  document.getElementById("cutSection").classList.toggle("hidden", on);
  document.getElementById("reloadBtn").classList.toggle("hidden", !on);
}

function renderPresets() {
  const grid = document.getElementById("presetGrid");
  grid.innerHTML = "";
  state.presets.forEach((p) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preset" + (p.id === state.preset ? " on" : "");
    btn.textContent = state.lang === "zh" ? p.zh : p.en;
    btn.addEventListener("click", () => {
      state.preset = p.id;
      if (p.fill === "transparent") {
        document.getElementById("fillTransparent").checked = true;
      } else {
        document.getElementById("fillTransparent").checked = false;
        document.getElementById("fillColor").value = p.fill;
        document.getElementById("fillHex").value = p.fill;
      }
      applyI18n();
      queueStyle();
    });
    grid.appendChild(btn);
  });
}

function renderLuts() {
  const sel = document.getElementById("lutSelect");
  const current = sel.value || "none";
  sel.innerHTML = "";
  state.luts.forEach((lut) => {
    const opt = document.createElement("option");
    opt.value = lut.id;
    opt.textContent = state.lang === "zh" ? lut.zh : lut.en;
    sel.appendChild(opt);
  });
  sel.value = current;
}

function renderSizes() {
  const sel = document.getElementById("exportSize");
  const current = sel.value || "original";
  sel.innerHTML = "";
  const items = state.sizes.length ? state.sizes : [{ id: "original", label: "original" }];
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.id === "original"
      ? (state.lang === "zh" ? `原图 ${item.label}` : `Original ${item.label}`)
      : item.label;
    sel.appendChild(opt);
  });
  sel.value = items.some((i) => i.id === current) ? current : "original";
}

function currentFill() {
  if (document.getElementById("fillTransparent").checked) return "transparent";
  return document.getElementById("fillHex").value.trim() || "#000000";
}

function previewUrl() {
  if (!state.jobId) return "";
  const bust = Date.now();
  if (state.view === "source") return `/api/jobs/${state.jobId}/preview.png?layer=source&t=${bust}`;
  if (state.view === "cut") return `/api/jobs/${state.jobId}/preview.png?layer=cut&t=${bust}`;
  if (state.hasStyled) return `/api/jobs/${state.jobId}/styled.png?t=${bust}`;
  if (state.hasCut) return `/api/jobs/${state.jobId}/result.png?t=${bust}`;
  return `/api/jobs/${state.jobId}/preview.png?layer=source&t=${bust}`;
}

function refreshPreview() {
  const img = document.getElementById("previewImg");
  const empty = document.getElementById("previewEmpty");
  const url = previewUrl();
  if (!url) {
    img.hidden = true;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  img.hidden = false;
  img.src = url;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("#previewMode button").forEach((b) => {
    b.classList.toggle("on", b.getAttribute("data-view") === view);
  });
  refreshPreview();
}

async function refreshSizes() {
  if (!state.jobId) return;
  const force = document.getElementById("exportForce").checked;
  const res = await fetch(`/api/jobs/${state.jobId}/export-sizes?force=${force ? "true" : "false"}`);
  const data = await res.json();
  state.sizes = data.sizes || [];
  renderSizes();
}

async function ingestFile(file) {
  if (!file) return;
  const body = new FormData();
  body.append("file", file, file.name);
  showProgress(true, t("workingCut"), 8);
  const res = await fetch("/api/jobs/normalize", { method: "POST", body });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "normalize failed");
  state.jobId = data.id;
  state.hasCut = false;
  state.hasStyled = false;
  state.sizes = data.sizes || [];
  setPostCutVisible(false);
  document.getElementById("fileMeta").textContent = `${data.name} · ${data.width}×${data.height}`;
  renderSizes();
  setView("source");
  showProgress(false);
  setChip("idle");
}

async function runCutout() {
  if (!state.jobId) {
    setHint("needImage");
    return;
  }
  const runBtn = document.getElementById("runBtn");
  runBtn.disabled = true;
  try {
    showProgress(true, t("workingCut"), 20);
    const removeRes = await fetch(`/api/jobs/${state.jobId}/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: state.cutMode,
        color: document.getElementById("chromaHex").value || document.getElementById("chromaColor").value,
        strength: Number(document.getElementById("chromaStrength").value || 0.001),
      }),
    });
    const removeData = await removeRes.json();
    if (!removeRes.ok) throw new Error(removeData.detail || "remove failed");
    state.hasCut = true;
    setPostCutVisible(true);
    await refreshSizes();
    setView("cut");
    setHint("ready");
    setChip("ready");
    showProgress(false);
    await applyStyle(true);
  } catch (err) {
    setHint("error", String(err.message || err));
    setChip("error");
    showProgress(false);
  } finally {
    runBtn.disabled = false;
  }
}

function stylePayload() {
  return {
    preset: state.preset,
    fill: currentFill(),
    lut: document.getElementById("lutSelect").value || "none",
    lut_strength: Number(document.getElementById("lutStrength").value || 1),
    plate_enabled: document.getElementById("plateOn").checked,
    pad_outer: Number(document.getElementById("padOuter").value || 0),
    pad_inner: Number(document.getElementById("padInner").value || 0),
  };
}

async function applyStyle(immediate) {
  if (!state.jobId || !state.hasCut) return;
  if (state.styling) {
    state.pendingStyle = true;
    return;
  }
  state.styling = true;
  const pill = document.getElementById("livePill");
  pill.classList.remove("hidden");
  try {
    const styleRes = await fetch(`/api/jobs/${state.jobId}/style`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(stylePayload()),
    });
    const styleData = await styleRes.json();
    if (!styleRes.ok) throw new Error(styleData.detail || "style failed");
    state.hasStyled = true;
    if (immediate || state.view === "styled") setView("styled");
    else refreshPreview();
  } catch (err) {
    setHint("error", String(err.message || err));
  } finally {
    state.styling = false;
    pill.classList.add("hidden");
    if (state.pendingStyle) {
      state.pendingStyle = false;
      applyStyle(false);
    }
  }
}

function queueStyle() {
  if (!state.hasCut) return;
  window.clearTimeout(state.styleTimer);
  state.styleTimer = window.setTimeout(() => applyStyle(false), 220);
}

async function saveExport() {
  if (!state.jobId || (!state.hasStyled && !state.hasCut)) {
    setHint("cutFirst");
    return;
  }
  let path = "";
  try {
    const dlg = await fetch("/api/dialog/save?name=style-cut.png", { method: "POST" });
    const picked = await dlg.json();
    path = picked.path || "";
  } catch (_) {
    path = "";
  }
  if (!path) {
    setHint("noSavePath");
    return;
  }
  const res = await fetch(`/api/jobs/${state.jobId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path,
      size: document.getElementById("exportSize").value || "original",
      compress: document.getElementById("exportCompress").checked,
      force: document.getElementById("exportForce").checked,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    setHint("error", data.detail || "export failed");
    return;
  }
  setHint("saved", `${data.width}×${data.height} · ${data.path}`);
}

function syncChromaReadouts() {
  const hex = document.getElementById("chromaHex");
  const color = document.getElementById("chromaColor");
  const strength = document.getElementById("chromaStrength");
  document.getElementById("chromaStrengthVal").textContent = Number(strength.value).toFixed(3);
  document.getElementById("lutStrengthVal").textContent = Number(document.getElementById("lutStrength").value).toFixed(2);
  if (/^#?[0-9a-fA-F]{6}$/.test((hex.value || "").trim())) {
    const norm = hex.value.startsWith("#") ? hex.value : `#${hex.value}`;
    hex.value = norm.toLowerCase();
    color.value = norm;
  }
}

function reloadImage() {
  state.jobId = "";
  state.hasCut = false;
  state.hasStyled = false;
  state.sizes = [];
  setPostCutVisible(false);
  document.getElementById("fileInput").value = "";
  document.getElementById("fileMeta").textContent = t("dropSub");
  document.getElementById("previewImg").hidden = true;
  document.getElementById("previewEmpty").hidden = false;
  document.getElementById("plateMeta").textContent = "";
  document.getElementById("plateOn").checked = false;
  setChip("idle");
  setHint("");
  setView("source");
}

function bindLiveControls() {
  ["fillColor", "fillHex", "fillTransparent", "lutSelect", "lutStrength", "plateOn", "padOuter", "padInner"].forEach((id) => {
    const el = document.getElementById(id);
    const evt = el.type === "text" || el.type === "number" ? "change" : "input";
    el.addEventListener(evt, queueStyle);
    if (el.type === "checkbox") el.addEventListener("change", queueStyle);
  });
}

async function boot() {
  state.lang = detectUiLang();
  const defaults = await fetch("/api/defaults").then((r) => r.json());
  state.presets = defaults.presets || [];
  state.luts = defaults.luts || [];
  applyI18n();
  setChip("idle");
  setPostCutVisible(false);
  if (defaults.version) document.getElementById("appVersion").textContent = `v${String(defaults.version).replace(/^v/, "")}`;
  syncChromaReadouts();

  document.getElementById("uiLangSwitch").addEventListener("click", (ev) => {
    const lang = ev.target.getAttribute("data-ui-lang");
    if (!lang) return;
    state.lang = lang;
    persistUiLang(lang);
    applyI18n();
  });

  const drop = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  drop.addEventListener("click", () => fileInput.click());
  drop.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    drop.classList.add("over");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (ev) => {
    ev.preventDefault();
    drop.classList.remove("over");
    const file = ev.dataTransfer.files && ev.dataTransfer.files[0];
    ingestFile(file).catch((err) => setHint("error", String(err.message || err)));
  });
  fileInput.addEventListener("change", () => {
    ingestFile(fileInput.files[0]).catch((err) => setHint("error", String(err.message || err)));
  });

  document.getElementById("cutMode").addEventListener("click", (ev) => {
    const mode = ev.target.getAttribute("data-mode");
    if (!mode) return;
    state.cutMode = mode;
    document.querySelectorAll("#cutMode button").forEach((b) => {
      b.classList.toggle("on", b.getAttribute("data-mode") === mode);
    });
    document.getElementById("chromaRow").classList.toggle("hidden", mode !== "chroma");
    syncChromaReadouts();
  });

  document.getElementById("chromaColor").addEventListener("input", () => {
    document.getElementById("chromaHex").value = document.getElementById("chromaColor").value;
    syncChromaReadouts();
  });
  document.getElementById("chromaHex").addEventListener("change", syncChromaReadouts);
  document.getElementById("chromaStrength").addEventListener("input", syncChromaReadouts);
  document.getElementById("lutStrength").addEventListener("input", syncChromaReadouts);

  document.getElementById("fillColor").addEventListener("input", () => {
    document.getElementById("fillHex").value = document.getElementById("fillColor").value;
    document.getElementById("fillTransparent").checked = false;
  });
  document.getElementById("fillHex").addEventListener("change", () => {
    const hex = document.getElementById("fillHex").value.trim();
    if (/^#?[0-9a-fA-F]{6}$/.test(hex)) {
      document.getElementById("fillColor").value = hex.startsWith("#") ? hex : `#${hex}`;
    }
  });

  document.getElementById("plateBtn").addEventListener("click", () => {
    document.getElementById("plateInput").click();
  });
  document.getElementById("plateInput").addEventListener("change", async () => {
    const file = document.getElementById("plateInput").files[0];
    if (!file || !state.jobId) return;
    const body = new FormData();
    body.append("file", file, file.name);
    const res = await fetch(`/api/jobs/${state.jobId}/plate`, { method: "POST", body });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("plateMeta").textContent = data.detail || "plate failed";
      return;
    }
    document.getElementById("plateOn").checked = true;
    document.getElementById("plateMeta").textContent = `${t("plateReady")} · ${data.width}×${data.height}`;
    queueStyle();
  });

  document.getElementById("previewMode").addEventListener("click", (ev) => {
    const view = ev.target.getAttribute("data-view");
    if (!view) return;
    if (view === "cut" && !state.hasCut) return;
    if (view === "styled" && !state.hasStyled) return;
    setView(view);
  });

  document.getElementById("exportForce").addEventListener("change", () => {
    refreshSizes().catch(() => {});
  });

  bindLiveControls();
  document.getElementById("runBtn").addEventListener("click", runCutout);
  document.getElementById("reloadBtn").addEventListener("click", reloadImage);
  document.getElementById("saveBtn").addEventListener("click", saveExport);
}

boot().catch((err) => {
  setChip("error");
  setHint("error", String(err));
});
