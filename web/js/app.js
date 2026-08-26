import * as THREE from "three";
import {
  PALETTE,
  addMeshFromGeometry,
  captureScreenshot,
  clearGroup,
  fitCamera,
  fitCameraToPieces,
  initScene,
  loadSTL,
  planePreview,
  resize,
  updatePlanePreview,
} from "./scene.js";
import { deleteModel, listModels, suggestConnector, uploadModel } from "./api.js";
import { OPERATIONS } from "./operations.js";
import { quoteCalc, loadConfig, saveConfig, formatCurrency, downloadPDF, downloadPNG, getDensity, calcWeight, calcTimeHours, formatTime } from "./quote.js";

const $ = (id) => document.getElementById(id);

window.addEventListener("error", (e) => {
  const el = document.getElementById("toast");
  if (el && !el.classList.contains("hidden")) return;
  console.error(e.error || e.message);
});

const state = {
  modelId: null,
  info: null,
  job: null,
  originalMesh: null,
  pieceMeshes: [],
  axis: "z",
};

const SESSION_KEY = "stlfiles.session.v1";
function readSession() { try { return JSON.parse(localStorage.getItem(SESSION_KEY)); } catch { return null; } }
function clearSession() { localStorage.removeItem(SESSION_KEY); }

function adoptForm(form) {
  if (!form) return;
  document.querySelector(`input[name="op"][value="${form.op}"]`).checked = true;
  document.querySelector(`input[name="mode"][value="${form.mode}"]`).checked = true;
  const half = form.mode === "half";
  $("field-axis").classList.toggle("hidden", !half);
  $("field-pos").classList.toggle("hidden", !half);
  $("field-parts").classList.toggle("hidden", half);
  state.axis = form.axis;
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("active", b.dataset.axis === form.axis);
  });
  $("pos-slider").value = form.pos;
  $("pos-val").value = `${form.pos}%`;
  $("parts-input").value = form.parts;
  $("conn-type").value = form.conn.type;
  $("conn-fields").classList.toggle("hidden", form.conn.type === "none");
  $("conn-dia").value = form.conn.dia;
  $("conn-depth").value = form.conn.depth;
  $("conn-clear").value = form.conn.clear;
  $("conn-count").value = form.conn.count;
  $("sup-angle").value = form.sup.angle;
  $("sup-tip").value = form.sup.tip;
  $("sup-contact").value = form.sup.contact;
  $("sup-spacing").value = form.sup.spacing;
  $("sup-gap").value = form.sup.gap;
  $("sup-base").value = form.sup.base;
  updateOperationUI();
}

async function restoreSession() {
  const s = readSession();
  if (!s?.modelId) return;
  try {
    const res = await fetch(`/api/models/${s.modelId}`);
    if (!res.ok) { clearSession(); return; }
    s.info = await res.json();
  } catch { clearSession(); return; }
  adoptForm(s.form);
  adoptModel(s.info);
  if (s.job?.pieces?.length) {
    state.job = s.job;
    try {
      const res = await fetch(`${s.job.pieces[0].file_url}/preview`, { method: "HEAD" });
      if (!res.ok) { state.job = null; persistSession(); return; }
    } catch { state.job = null; persistSession(); return; }
    renderResults(s.job);
  }
  toast("Sesión restaurada");
}

initScene($("c"));

function onResize() {
  const box = $("viewport").getBoundingClientRect();
  resize(box.width, box.height);
}
window.addEventListener("resize", onResize);
onResize();

let suggestTimer = null;

async function refreshSuggestion() {
  if (!state.modelId || currentOp() !== "cut" || $("conn-type").value === "none") return;
  const sug = await suggestConnector(state.modelId, {
    axis: state.axis,
    position: String(Number($("pos-slider").value) / 100),
    mode: currentMode(),
  });
  if (!sug) return;
  $("conn-dia").value = sug.diameter_mm;
  $("conn-depth").value = sug.depth_mm;
  $("conn-count").value = sug.count;
  const el = $("conn-suggest");
  el.textContent = `Sugerido (${sug.basis}): cara ${sug.face_mm[0]}×${sug.face_mm[1]} mm · `
    + `espesor mín. ${sug.thickness_mm} mm → ⌀${sug.diameter_mm} mm × prof. ${sug.depth_mm} mm × ${sug.count}`;
  el.hidden = false;
}

function scheduleSuggestion() {
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(refreshSuggestion, 300);
}

function updatePlanePreviewFromState() {
  const show = state.originalMesh && currentOp() === "cut" && currentMode() === "half";
  if (!show) {
    planePreview.visible = false;
    return;
  }
  const frac = Number($("pos-slider").value) / 100;
  updatePlanePreview(state.originalMesh.geometry, state.axis, frac);
}

let toastTimer = null;
function toast(msg, kind = "info") {
  const el = $("toast");
  el.textContent = msg;
  el.className = kind;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), kind === "error" ? 7000 : 3500);
}

function setLoading(on, msg = "Cargando…") {
  $("loading-msg").textContent = msg;
  $("loading").classList.toggle("hidden", !on);
}

function loadOriginal(url) {
  setLoading(true, "Cargando modelo…");
  loadSTL(
    url,
    (geo) => {
      clearGroup([state.originalMesh, ...state.pieceMeshes]);
      state.pieceMeshes = [];
      planePreview.visible = false;
      state.originalMesh = addMeshFromGeometry(geo, 0x7aa2ff, []);
      fitCamera(state.originalMesh);
      $("hud").classList.add("hidden");
      setLoading(false);
    },
    () => {
      setLoading(false);
      toast("No se pudo leer el STL desde el servidor", "error");
    }
  );
}

function adoptModel(info) {
  state.modelId = info.id;
  state.info = info;
  $("m-name").textContent = info.name;
  $("m-dims").textContent = `${info.dims_mm.map((d) => Math.round(d)).join(" × ")} mm`;
  $("m-vol").textContent = `${info.volume_cm3} cm³`;
  $("m-tris").textContent = info.triangles.toLocaleString("es");
  $("m-wat").textContent = info.watertight ? "sí ✓" : "no ⚠";
  $("m-wat").style.color = info.watertight ? "var(--ok)" : "var(--warn)";
  $("drop").querySelector("strong").textContent = `✓ ${info.name}`;
  $("model-card").classList.remove("hidden");
  $("btn-cut").disabled = false;
  $("btn-supports").disabled = false;
  $("results-card").classList.add("hidden");
  loadOriginal(`/api/models/${info.id}/preview`);
  refreshSuggestion();
  persistSession();
  recalcFromSTL();
}

async function upload(file) {
  setStatusSubiendo(true);
  try {
    const info = await uploadModel(file);
    adoptModel(info);
    toast(`Modelo cargado: ${info.name}`);
    refreshLibrary();
  } catch (err) {
    if (err.status === 409 && err.existing && confirm(`${err.existing.name} ya existe. ¿Reemplazarlo?`)) {
      try {
        const info = await uploadModel(file, true);
        adoptModel(info);
        toast(`Modelo reemplazado: ${info.name}`);
        refreshLibrary();
        return;
      } catch (e2) {
        toast(String(e2.message || e2), "error");
      }
    } else {
      toast(String(err.message || err), "error");
    }
  } finally {
    setStatusSubiendo(false);
  }
}

function setStatusSubiendo(on) {
  $("drop").querySelector("span").textContent = on
    ? "subiendo…"
    : "click para cambiar de archivo";
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

function currentOp() {
  return document.querySelector('input[name="op"]:checked').value;
}

function persistSession() {
  try {
    const form = {
      op: currentOp(), mode: currentMode(), axis: state.axis,
      pos: Number($("pos-slider").value),
      parts: Number($("parts-input").value),
      conn: {
        type: $("conn-type").value,
        dia: Number($("conn-dia").value),
        depth: Number($("conn-depth").value),
        clear: Number($("conn-clear").value),
        count: Number($("conn-count").value),
      },
      sup: {
        angle: Number($("sup-angle").value),
        tip: Number($("sup-tip").value),
        contact: Number($("sup-contact").value),
        spacing: Number($("sup-spacing").value),
        gap: Number($("sup-gap").value),
        base: Number($("sup-base").value),
      },
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      v: 1,
      modelId: state.modelId,
      info: state.info,
      job: state.job,
      form,
    }));
  } catch { /* quota/serialization */ }
}

function updateOperationUI() {
  const op = currentOp();
  const cutting = op === "cut";
  const supporting = op === "supports";
  const quoting = op === "quote";
  $("cut-controls").classList.toggle("hidden", !cutting);
  $("sup-controls").classList.toggle("hidden", !supporting);
  $("btn-cut").classList.toggle("hidden", quoting || supporting);
  $("quote-card").classList.toggle("hidden", !quoting);
  if (!quoting) {
    $("results-card").classList.toggle("hidden", !$("results-card").dataset.hasResults);
  } else {
    $("results-card").classList.add("hidden");
  }
  updatePlanePreviewFromState();
  if (cutting) refreshSuggestion();
  if (quoting) initQuote();
}

document.querySelectorAll('input[name="op"]').forEach((r) =>
  r.addEventListener("change", updateOperationUI)
);

document.querySelectorAll('input[name="mode"]').forEach((r) =>
  r.addEventListener("change", () => {
    const half = currentMode() === "half";
    $("field-axis").classList.toggle("hidden", !half);
    $("field-pos").classList.toggle("hidden", !half);
    $("field-parts").classList.toggle("hidden", half);
    updatePlanePreviewFromState();
    refreshSuggestion();
  })
);

document.querySelectorAll(".seg button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".seg button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.axis = b.dataset.axis;
    updatePlanePreviewFromState();
    refreshSuggestion();
  })
);

$("pos-slider").addEventListener("input", () => {
  $("pos-val").value = `${$("pos-slider").value}%`;
  updatePlanePreviewFromState();
  scheduleSuggestion();
});

$("conn-type").addEventListener("change", () => {
  $("conn-fields").classList.toggle("hidden", $("conn-type").value === "none");
  refreshSuggestion();
});

$("file-input").addEventListener("change", (e) => {
  if (e.target.files[0]) upload(e.target.files[0]);
});

const dropzone = $("drop");
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  const f = [...e.dataTransfer.files].find((f) => f.name.toLowerCase().endsWith(".stl"));
  if (f) upload(f);
});

$("btn-cut").addEventListener("click", async () => {
  const btn = $("btn-cut");
  btn.disabled = true;
  btn.textContent = "Cortando…";
  try {
    const params = OPERATIONS.cut.collectParams();
    const data = await OPERATIONS.cut.execute(state, params);
    state.job = data;
    renderResults(data);
    persistSession();
    toast(`${data.pieces.length} pieza${data.pieces.length > 1 ? "s" : ""} generada${data.pieces.length > 1 ? "s" : ""}`);
  } catch (err) {
    toast(String(err.message || err), "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Cortar modelo";
  }
});

$("btn-supports").addEventListener("click", async () => {
  const btn = $("btn-supports");
  btn.disabled = true;
  btn.textContent = "Generando…";
  try {
    const params = OPERATIONS.supports.collectParams();
    const data = await OPERATIONS.supports.execute(state, params);
    state.job = data;
    renderResults(data);
    persistSession();
    toast("STL con soportes listo para descargar");
  } catch (err) {
    toast(String(err.message || err), "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generar soportes";
  }
});

function renderResults(job) {
  $("results-card").dataset.hasResults = "1";
  $("results-title").textContent = job.pieces.length > 1 || currentOp() === "cut"
    ? "3 · Piezas"
    : "3 · Resultado";
  const list = $("results-list");
  list.innerHTML = "";
  job.pieces.forEach((p, i) => {
    const li = document.createElement("li");
    const dot = `<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#${PALETTE[i % PALETTE.length].toString(16).padStart(6, "0")};margin-right:6px"></span>`;
    li.innerHTML = `
      <div>
        <div class="p-name">${dot}${p.name}</div>
        <div class="p-meta">${p.dims_mm.map((d) => Math.round(d)).join("×")} mm · ${p.volume_cm3} cm³${p.watertight ? "" : " · ⚠ no estanca"}</div>
      </div>
      <a href="${p.file_url}" download="${p.name}">STL</a>`;
    list.appendChild(li);
  });

  const zipBtn = $("zip-btn");
  zipBtn.href = `/api/jobs/${job.job_id}/zip`;
  zipBtn.classList.remove("hidden");

  const warnBox = $("warnings");
  if (job.warnings.length) {
    warnBox.textContent = job.warnings.join("\n");
    warnBox.classList.remove("hidden");
  } else {
    warnBox.classList.add("hidden");
  }

  $("results-card").classList.remove("hidden");
  showPieces(job);
}

function showPieces(job) {
  clearGroup(state.pieceMeshes);
  if (state.originalMesh) state.originalMesh.visible = false;
  state.pieceMeshes = [];

  const globalCenter = new THREE.Vector3();
  const centers = [];
  const total = job.pieces.length;
  let ok = 0;
  let done = 0;

  function settle() {
    done++;
    if (done < total) return;
    setLoading(false);
    if (ok === total) {
      globalCenter.divideScalar(total);
      state.pieceMeshes.forEach((m, j) => {
        const d = centers[j].clone().sub(globalCenter);
        if (d.lengthSq() < 1e-6) d.set(0, 0, 1);
        m.userData.explodeDir = d.normalize();
      });
      applyExplode();
      fitCameraToPieces(state.pieceMeshes);
    }
  }

  setLoading(true, total > 1 ? `Cargando ${total} piezas…` : "Cargando pieza…");
  job.pieces.forEach((p, i) => {
    loadSTL(
      `${p.file_url}/preview`,
      (geo) => {
        addMeshFromGeometry(geo, PALETTE[i % PALETTE.length], state.pieceMeshes);
        centers[i] = geo.boundingBox.getCenter(new THREE.Vector3());
        globalCenter.add(centers[i]);
        ok++;
        settle();
      },
      () => {
        toast("No se pudo leer el STL desde el servidor", "error");
        settle();
      }
    );
  });

  $("hud").classList.remove("hidden");
  $("explode-box").classList.toggle("hidden", total < 2);
  $("btn-original").classList.remove("hidden");
}

function applyExplode() {
  const t = Number($("explode-slider").value);
  state.pieceMeshes.forEach((m) => {
    if (m.userData.explodeDir) m.position.copy(m.userData.explodeDir).multiplyScalar(t);
  });
}

$("explode-slider").addEventListener("input", applyExplode);

$("btn-original").addEventListener("click", () => {
  const showingPieces = state.pieceMeshes.some((m) => m.visible);
  if (showingPieces) {
    state.pieceMeshes.forEach((m) => (m.visible = false));
    if (state.originalMesh) state.originalMesh.visible = true;
    updatePlanePreviewFromState();
    $("btn-original").textContent = "Ver piezas";
    if (state.originalMesh) fitCamera(state.originalMesh);
  } else {
    if (state.originalMesh) state.originalMesh.visible = false;
    planePreview.visible = false;
    state.pieceMeshes.forEach((m) => (m.visible = true));
    $("btn-original").textContent = "Ver original";
    fitCameraToPieces(state.pieceMeshes);
  }
});

function renderLibrary(items) {
  const ul = $("lib-list");
  ul.innerHTML = "";
  items.forEach((m) => {
    const li = document.createElement("li");
    li.dataset.id = m.id;
    const dims = m.dims_mm ? m.dims_mm.map((d) => Math.round(d)).join("×") : "—";
    li.innerHTML = `
      <span class="lib-name">${m.name}</span>
      <span class="lib-meta">${dims} mm</span>
      <button class="lib-btn" data-act="load">Abrir</button>
      <button class="lib-btn del" data-act="del">✕</button>`;
    ul.appendChild(li);
  });
}

async function refreshLibrary() {
  const items = await listModels();
  renderLibrary(items);
}

$("lib-list").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const li = btn.closest("li");
  const id = li?.dataset.id;
  if (!id) return;

  if (btn.dataset.act === "load") {
    const items = await listModels();
    const info = items.find((m) => m.id === id);
    if (info) {
      adoptModel(info);
      toast(`Modelo cargado: ${info.name}`);
    }
  } else if (btn.dataset.act === "del") {
    const name = li.querySelector(".lib-name")?.textContent || id;
    if (!confirm(`¿Borrar "${name}"?`)) return;
    try {
      await deleteModel(id);
      toast(`"${name}" eliminado`);
      if (id === state.modelId) {
        clearGroup([state.originalMesh, ...state.pieceMeshes]);
        state.originalMesh = null;
        state.pieceMeshes = [];
        state.modelId = null;
        state.info = null;
        state.job = null;
        planePreview.visible = false;
        $("model-card").classList.add("hidden");
        $("results-card").classList.add("hidden");
        $("hud").classList.add("hidden");
        $("btn-cut").disabled = true;
        $("btn-supports").disabled = true;
        $("drop").querySelector("strong").textContent = "Subí tu .stl";
        localStorage.removeItem("stlfiles.session.v1");
      }
      refreshLibrary();
    } catch {
      toast("No se pudo borrar", "error");
    }
  }
});

let persistTimer = null;
document.addEventListener("input", () => {
  clearTimeout(persistTimer);
  persistTimer = setTimeout(persistSession, 300);
});
document.addEventListener("change", () => {
  clearTimeout(persistTimer);
  persistTimer = setTimeout(persistSession, 300);
});

/* --- Presupuesto --- */

function collectQuoteInput() {
  let image_base64 = "";
  try {
    image_base64 = captureScreenshot();
  } catch { /* ignore */ }
  return {
    hours: Number($("quote-hours").value) || 0,
    minutes: Number($("quote-minutes").value) || 0,
    grams: Number($("quote-grams").value) || 0,
    difficulty: Number($("quote-difficulty").value) || 1,
    model_name: state.info?.name || "",
    notes: "",
    dims_mm: state.info?.dims_mm || [],
    image_base64,
  };
}

function collectQuoteConfig() {
  return {
    machine_cost: Number($("q-cfg-machine").value) || 0,
    machine_life_hrs: Number($("q-cfg-life").value) || 1,
    electricity_kwh: Number($("q-cfg-kwh").value) || 0,
    power_watts: Number($("q-cfg-watts").value) || 0,
    maintenance_per_hr: Number($("q-cfg-maint").value) || 0,
    labor_per_hr: Number($("q-cfg-labor").value) || 0,
    filament_per_kg: Number($("q-cfg-filament").value) || 0,
    profit_pct: Number($("q-cfg-profit").value) || 0,
  };
}

function recalcFromSTL() {
  const isSTL = document.querySelector('input[name="quote-mode"]:checked')?.value === "stl";
  if (!isSTL || !state.info) return;
  const vol = state.info.volume_cm3 || 0;
  const weight = Math.round(calcWeight(vol) * 10) / 10;
  $("quote-stl-vol").value = vol;
  $("quote-stl-weight").value = weight;
  $("quote-grams").value = weight;
  const infill = Number($("q-infill").value) || 20;
  const layer = Number($("q-layer").value) || 0.2;
  const speed = Number($("q-speed").value) || 60;
  const hours = calcTimeHours(vol, infill, layer, speed);
  $("q-time").value = formatTime(hours);
  $("quote-hours").value = Math.floor(hours);
  $("quote-minutes").value = Math.round((hours - Math.floor(hours)) * 60);
  updateQuoteResults();
}

function updateQuoteResults() {
  const config = collectQuoteConfig();
  const input = collectQuoteInput();
  const r = quoteCalc(config, input);
  $("qr-time").textContent = formatCurrency(r.cost_time);
  $("qr-material").textContent = formatCurrency(r.cost_material);
  $("qr-subtotal").textContent = formatCurrency(r.subtotal);
  $("qr-diff").textContent = formatCurrency(r.extra_difficulty);
  $("qr-profit").textContent = formatCurrency(r.profit);
  $("qr-final").textContent = formatCurrency(r.final_price);
  $("qr-diff-row").style.display = r.extra_difficulty > 0 ? "" : "none";
  $("qr-profit-row").style.display = r.profit > 0 ? "" : "none";
}

function populateQuoteConfig(cfg) {
  $("q-cfg-machine").value = cfg.machine_cost;
  $("q-cfg-life").value = cfg.machine_life_hrs;
  $("q-cfg-kwh").value = cfg.electricity_kwh;
  $("q-cfg-watts").value = cfg.power_watts;
  $("q-cfg-maint").value = cfg.maintenance_per_hr;
  $("q-cfg-labor").value = cfg.labor_per_hr;
  $("q-cfg-filament").value = cfg.filament_per_kg;
  $("q-cfg-profit").value = cfg.profit_pct;
}

function initQuote() {
  const cfg = loadConfig();
  populateQuoteConfig(cfg);
  recalcFromSTL();
  updateQuoteResults();
}

document.querySelectorAll('input[name="quote-mode"]').forEach((r) =>
  r.addEventListener("change", () => {
    const stl = document.querySelector('input[name="quote-mode"]:checked').value === "stl";
    $("quote-stl-info").classList.toggle("hidden", !stl);
    $("quote-grams-field").classList.toggle("hidden", stl);
    if (stl && state.info) {
      $("quote-stl-model").textContent = `Modelo: ${state.info.name}`;
      recalcFromSTL();
    }
  })
);

$("q-material")?.addEventListener("change", () => {
  const isCustom = $("q-material").value === "0";
  $("q-density-custom-field").classList.toggle("hidden", !isCustom);
  recalcFromSTL();
  updateQuoteResults();
});

$("q-density")?.addEventListener("input", () => {
  recalcFromSTL();
  updateQuoteResults();
});

["q-infill", "q-layer", "q-speed"].forEach((id) => {
  $(id)?.addEventListener("input", recalcFromSTL);
});

["quote-hours", "quote-minutes", "quote-grams", "quote-difficulty",
 "q-cfg-machine", "q-cfg-life", "q-cfg-kwh", "q-cfg-watts",
 "q-cfg-maint", "q-cfg-labor", "q-cfg-filament", "q-cfg-profit"].forEach((id) => {
  $(id)?.addEventListener("input", updateQuoteResults);
});

$("quote-stl-weight")?.addEventListener("input", () => {
  $("quote-grams").value = $("quote-stl-weight").value;
  updateQuoteResults();
});

$("btn-cfg-save")?.addEventListener("click", () => {
  saveConfig(collectQuoteConfig());
  const msg = $("cfg-saved-msg");
  msg.textContent = "Guardado";
  setTimeout(() => { msg.textContent = ""; }, 2000);
});

$("btn-quote-pdf")?.addEventListener("click", async () => {
  try {
    await downloadPDF(collectQuoteConfig(), collectQuoteInput());
    toast("PDF descargado");
  } catch (err) {
    toast(String(err.message || err), "error");
  }
});

$("btn-quote-png")?.addEventListener("click", async () => {
  try {
    await downloadPNG(collectQuoteConfig(), collectQuoteInput());
    toast("PNG descargado");
  } catch (err) {
    toast(String(err.message || err), "error");
  }
});

refreshLibrary();
restoreSession();
