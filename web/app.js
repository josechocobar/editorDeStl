import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const $ = (id) => document.getElementById(id);

const PALETTE = [0x4f8cff, 0xff8c42, 0x41d18c, 0xc56cf0, 0xffd166, 0x4ecdc4, 0xff6b81, 0xa3a1fb];

const state = {
  modelId: null,
  info: null,
  job: null,
  originalMesh: null,
  pieceMeshes: [],
  axis: "z",
};

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0f12);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
camera.position.set(120, 90, 140);

const renderer = new THREE.WebGLRenderer({ canvas: $("c"), antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const world = new THREE.Group();
world.rotation.x = -Math.PI / 2;
scene.add(world);

const grid = new THREE.GridHelper(400, 40, 0x2a2e37, 0x1c1f26);
scene.add(grid);

scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x30281f, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 1.6);
dir.position.set(150, 220, 120);
scene.add(dir);
const dir2 = new THREE.DirectionalLight(0xffffff, 0.5);
dir2.position.set(-140, -60, -160);
scene.add(dir2);

const planePreview = new THREE.Mesh(
  new THREE.PlaneGeometry(1, 1),
  new THREE.MeshBasicMaterial({
    color: 0xff5566,
    transparent: true,
    opacity: 0.28,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
);
planePreview.visible = false;
world.add(planePreview);

function resize() {
  const box = $("viewport").getBoundingClientRect();
  renderer.setSize(box.width, box.height, false);
  camera.aspect = box.width / box.height;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});

function fitCamera(obj) {
  const sphere = new THREE.Box3().setFromObject(obj).getBoundingSphere(new THREE.Sphere());
  if (!sphere.radius) return;
  const dist = (sphere.radius / Math.sin((camera.fov * Math.PI) / 360)) * 1.05;
  const dirV = new THREE.Vector3(1, 0.65, 1).normalize();
  camera.position.copy(sphere.center).addScaledVector(dirV, dist);
  camera.near = Math.max(dist / 100, 0.1);
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  controls.target.copy(sphere.center);
}

function clearGroup(list) {
  for (const m of list) {
    world.remove(m);
    m.geometry.dispose();
    m.material.dispose();
  }
}

const loader = new STLLoader();

function addMeshFromGeometry(geo, color, list) {
  geo.computeBoundingBox();
  const mat = new THREE.MeshStandardMaterial({
    color,
    flatShading: true,
    roughness: 0.55,
    metalness: 0.05,
  });
  const mesh = new THREE.Mesh(geo, mat);
  world.add(mesh);
  list.push(mesh);
  return mesh;
}

function loadOriginal(url) {
  loader.load(url, (geo) => {
    clearGroup([state.originalMesh, ...state.pieceMeshes]);
    state.pieceMeshes = [];
    planePreview.visible = false;
    state.originalMesh = addMeshFromGeometry(geo, 0x7aa2ff, []);
    fitCamera(state.originalMesh);
    updatePlanePreview();
    $("hud").classList.add("hidden");
  });
}

const AXIS_VEC = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };

function updatePlanePreview() {
  if (!state.originalMesh || currentMode() !== "half") {
    planePreview.visible = false;
    return;
  }
  const box = state.originalMesh.geometry.boundingBox;
  const axis = state.axis;
  const lo = box.min[axis];
  const span = box.max[axis] - lo;
  const frac = Number($("pos-slider").value) / 100;

  const others = axis === "x" ? ["y", "z"] : axis === "y" ? ["x", "z"] : ["x", "y"];
  const w = box.max[others[0]] - box.min[others[0]];
  const h = box.max[others[1]] - box.min[others[1]];
  planePreview.geometry.dispose();
  planePreview.geometry = new THREE.PlaneGeometry(w * 1.04, h * 1.04);

  planePreview.rotation.set(0, 0, 0);
  if (axis === "x") planePreview.rotation.y = Math.PI / 2;
  if (axis === "y") planePreview.rotation.x = -Math.PI / 2;

  const c = box.getCenter(new THREE.Vector3());
  planePreview.position.set(c.x, c.y, c.z);
  planePreview.position[axis] = lo + frac * span;
  planePreview.visible = true;
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
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/models", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "Error subiendo");
    const info = await res.json();
    state.modelId = info.id;
    state.info = info;
    $("m-name").textContent = info.name;
    $("m-dims").textContent = `${info.dims_mm.map((d) => Math.round(d)).join(" × ")} mm`;
    $("m-vol").textContent = `${info.volume_cm3} cm³`;
    $("m-tris").textContent = info.triangles.toLocaleString("es");
    $("m-wat").textContent = info.watertight ? "sí ✓" : "no ⚠";
    $("m-wat").style.color = info.watertight ? "var(--ok)" : "var(--warn)";
    $("model-card").classList.remove("hidden");
    $("btn-cut").disabled = false;
    $("results-card").classList.add("hidden");
    loadOriginal(`/api/models/${info.id}/file`);
    toast(`Modelo cargado: ${info.name}`);
  } catch (err) {
    toast(String(err.message || err), "error");
  } finally {
    setStatusSubiendo(false);
  }
}

function setStatusSubiendo(on) {
  $("drop").querySelector("span").textContent = on ? "subiendo…" : "click para elegir archivo";
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

document.querySelectorAll('input[name="mode"]').forEach((r) =>
  r.addEventListener("change", () => {
    const half = currentMode() === "half";
    $("field-axis").classList.toggle("hidden", !half);
    $("field-pos").classList.toggle("hidden", !half);
    $("field-parts").classList.toggle("hidden", half);
    updatePlanePreview();
  })
);

document.querySelectorAll(".seg button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".seg button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.axis = b.dataset.axis;
    updatePlanePreview();
  })
);

$("pos-slider").addEventListener("input", () => {
  $("pos-val").value = `${$("pos-slider").value}%`;
  updatePlanePreview();
});

$("conn-type").addEventListener("change", () => {
  $("conn-fields").classList.toggle("hidden", $("conn-type").value === "none");
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
    const body = {
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
    };
    const res = await fetch("/api/cut", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error cortando");
    state.job = data;
    renderResults(data);
    toast(`${data.pieces.length} piezas generadas`);
  } catch (err) {
    toast(String(err.message || err), "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Cortar modelo";
  }
});

function renderResults(job) {
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
      <a href="${p.file_url}" download>STL</a>`;
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
    loader.load(p.file_url, (geo) => {
      const mesh = addMeshFromGeometry(geo, PALETTE[i % PALETTE.length], state.pieceMeshes);
      const c = geo.boundingBox.getCenter(new THREE.Vector3());
      centers[i] = c;
      globalCenter.add(c);
      loaded++;
      if (loaded === job.pieces.length) {
        globalCenter.divideScalar(job.pieces.length);
        state.pieceMeshes.forEach((m, j) => {
          const d = centers[j].clone().sub(globalCenter);
          if (d.lengthSq() < 1e-6) d.set(0, 0, 1);
          m.userData.explodeDir = d.normalize();
        });
        applyExplode();
        fitCameraToPieces();
      }
    });
  });

  $("hud").classList.remove("hidden");
  $("explode-box").classList.remove("hidden");
  $("btn-original").classList.remove("hidden");
}

function fitCameraToPieces() {
  const g = new THREE.Group();
  state.pieceMeshes.forEach((m) => g.add(m));
  scene.add(g);
  fitCamera(g);
  scene.remove(g);
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
    planePreview.visible = currentMode() === "half";
    $("btn-original").textContent = "Ver piezas";
    if (state.originalMesh) fitCamera(state.originalMesh);
  } else {
    if (state.originalMesh) state.originalMesh.visible = false;
    planePreview.visible = false;
    state.pieceMeshes.forEach((m) => (m.visible = true));
    $("btn-original").textContent = "Ver original";
    fitCameraToPieces();
  }
});
