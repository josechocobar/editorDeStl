import * as THREE from "three";
import {
  PALETTE,
  addMeshFromGeometry,
  clearGroup,
  fitCamera,
  fitCameraToPieces,
  initScene,
  loadSTL,
  planePreview,
  resize,
  updatePlanePreview,
} from "./scene.js";
import { cutModel, generateSupports, suggestConnector, uploadModel } from "./api.js";

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

initScene($("c"));

function onResize() {
  const box = $("viewport").getBoundingClientRect();
  resize(box.width, box.height);
}
window.addEventListener("resize", onResize);
onResize();

function loadOriginal(url) {
  loadSTL(
    url,
    (geo) => {
      clearGroup([state.originalMesh, ...state.pieceMeshes]);
      state.pieceMeshes = [];
      planePreview.visible = false;
      state.originalMesh = addMeshFromGeometry(geo, 0x7aa2ff, []);
      fitCamera(state.originalMesh);
      $("hud").classList.add("hidden");
    },
    () => toast("No se pudo leer el STL desde el servidor", "error")
  );
}

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

async function upload(file) {
  setStatusSubiendo(true);
  try {
    const info = await uploadModel(file);
    state.modelId = info.id;
    state.info = info;
    $("m-name").textContent = info.name;
    $("m-dims").textContent = `${info.dims_mm.map((d) => Math.round(d)).join(" × ")} mm`;
    $("m-vol").textContent = `${info.volume_cm3} cm³`;
    $("m-tris").textContent = info.triangles.toLocaleString("es");
    $("m-wat").textContent = info.watertight ? "sí ✓" : "no ⚠";
    $("m-wat").style.color = info.watertight ? "var(--ok)" : "var(--warn)";
    const dz = $("drop");
    dz.querySelector("strong").textContent = `✓ ${info.name}`;
    $("model-card").classList.remove("hidden");
    $("btn-cut").disabled = false;
    $("results-card").classList.add("hidden");
    loadOriginal(`/api/models/${info.id}/preview`);
    refreshSuggestion();
    toast(`Modelo cargado: ${info.name}`);
  } catch (err) {
    toast(String(err.message || err), "error");
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

function supportsPayload() {
  return {
    enabled: true,
    angle: Number($("sup-angle").value),
    tip_diameter: Number($("sup-tip").value),
    contact_diameter: Number($("sup-contact").value),
    spacing: Number($("sup-spacing").value),
    z_gap: Number($("sup-gap").value),
    base_thickness: Number($("sup-base").value),
  };
}

function updateOperationUI() {
  const cutting = currentOp() === "cut";
  $("cut-controls").classList.toggle("hidden", !cutting);
  $("sup-toggle-field").classList.toggle("hidden", !cutting);
  $("sup-fields").classList.toggle("hidden", cutting ? !$("sup-enabled").checked : false);
  $("btn-cut").textContent = cutting ? "Cortar modelo" : "Generar soportes";
  updatePlanePreviewFromState();
  if (cutting) refreshSuggestion();
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

$("sup-enabled").addEventListener("change", () => {
  updateOperationUI();
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
  const cutting = currentOp() === "cut";
  btn.disabled = true;
  btn.textContent = cutting ? "Cortando…" : "Generando soportes…";
  try {
    let data;
    if (cutting) {
      data = await cutModel({
        model_id: state.modelId,
        mode: currentMode(),
        axis: state.axis,
        position: Number($("pos-slider").value) / 100,
        parts: Number($("parts-input").value),
        connector: {
          type: $("conn-type").value,
          diameter: Number($("conn-dia").value),
          depth: Number($("conn-depth").value),
          clearance: Number($("conn-clear").value),
          count: Number($("conn-count").value),
        },
        supports: $("sup-enabled").checked ? supportsPayload() : null,
      });
    } else {
      data = await generateSupports(state.modelId, supportsPayload());
    }
    state.job = data;
    renderResults(data);
    toast(cutting
      ? `${data.pieces.length} piezas generadas`
      : "STL con soportes listo para descargar");
  } catch (err) {
    toast(String(err.message || err), "error");
  } finally {
    btn.disabled = false;
    btn.textContent = cutting ? "Cortar modelo" : "Generar soportes";
  }
});

function renderResults(job) {
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

  let loaded = 0;
  job.pieces.forEach((p, i) => {
    loadSTL(
      `${p.file_url}/preview`,
      (geo) => {
        addMeshFromGeometry(geo, PALETTE[i % PALETTE.length], state.pieceMeshes);
        centers[i] = geo.boundingBox.getCenter(new THREE.Vector3());
        globalCenter.add(centers[i]);
        loaded++;
        if (loaded === job.pieces.length) {
          globalCenter.divideScalar(job.pieces.length);
          state.pieceMeshes.forEach((m, j) => {
            const d = centers[j].clone().sub(globalCenter);
            if (d.lengthSq() < 1e-6) d.set(0, 0, 1);
            m.userData.explodeDir = d.normalize();
          });
          applyExplode();
          fitCameraToPieces(state.pieceMeshes);
        }
      },
      () => toast("No se pudo leer el STL desde el servidor", "error")
    );
  });

  $("hud").classList.remove("hidden");
  $("explode-box").classList.toggle("hidden", job.pieces.length < 2);
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
