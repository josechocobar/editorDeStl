import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

export const PALETTE = [
  0x4f8cff, 0xff8c42, 0x41d18c, 0xc56cf0, 0xffd166, 0x4ecdc4, 0xff6b81, 0xa3a1fb,
];

export let camera;
export let renderer;
export let controls;
export let world;
export let planePreview;

const loader = new STLLoader();

export function initScene(canvas) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d0f12);

  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  camera.position.set(120, 90, 140);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  world = new THREE.Group();
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

  planePreview = new THREE.Mesh(
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

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  return scene;
}

export function resize(width, height) {
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

export function clearGroup(list) {
  for (const m of list) {
    if (!m) continue;
    world.remove(m);
    m.geometry.dispose();
    m.material.dispose();
  }
}

export function addMeshFromGeometry(geo, color, list) {
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

export function loadSTL(url, onLoad, onError) {
  loader.load(url, onLoad, undefined, (err) => {
    console.error("STLLoader:", err);
    if (onError) onError(err);
  });
}

function frameSphere(sphere) {
  if (!sphere.radius) return;
  const dist = (sphere.radius / Math.sin((camera.fov * Math.PI) / 360)) * 1.05;
  const dirV = new THREE.Vector3(1, 0.65, 1).normalize();
  camera.position.copy(sphere.center).addScaledVector(dirV, dist);
  camera.near = Math.max(dist / 100, 0.1);
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  controls.target.copy(sphere.center);
}

export function fitCamera(obj) {
  frameSphere(new THREE.Box3().setFromObject(obj).getBoundingSphere(new THREE.Sphere()));
}

export function fitCameraToPieces(meshes) {
  const box = new THREE.Box3();
  const tmp = new THREE.Box3();
  for (const m of meshes) {
    m.updateWorldMatrix(true, false);
    tmp.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld);
    box.union(tmp);
  }
  frameSphere(box.getBoundingSphere(new THREE.Sphere()));
}

export function updatePlanePreview(geometry, axis, frac) {
  if (!geometry) {
    planePreview.visible = false;
    return;
  }
  const box = geometry.boundingBox;
  const lo = box.min[axis];
  const span = box.max[axis] - lo;

  let w, h;
  if (axis === "x") {
    w = box.max.z - box.min.z;
    h = box.max.y - box.min.y;
  } else if (axis === "y") {
    w = box.max.x - box.min.x;
    h = box.max.z - box.min.z;
  } else {
    w = box.max.x - box.min.x;
    h = box.max.y - box.min.y;
  }
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
