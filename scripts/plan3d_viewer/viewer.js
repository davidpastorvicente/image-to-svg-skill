// Viewer for casa.glb. Bundled with three.js into viewer.bundle.js (see build.sh);
// plan3d.py inlines that bundle, the model and the scene data into <output>.html.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const S = window.SCENE;
const $ = (id) => document.getElementById(id);
$('title').textContent = S.title;
document.title = S.title;

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#dfe8f0');
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.05, 200);

const [bx0, bz0, bx1, bz1] = S.bounds;
const center = new THREE.Vector3((bx0 + bx1) / 2, 0, (bz0 + bz1) / 2);
const size = Math.max(bx1 - bx0, bz1 - bz0);

scene.add(new THREE.HemisphereLight(0xffffff, 0xd8cfc0, 1.8));
scene.add(new THREE.AmbientLight(0xffffff, 0.7));     // interiors are lit even under the ceiling
const sun = new THREE.DirectionalLight(0xfff4e0, 2.2);
sun.position.set(center.x - 8, 18, center.z + 6);
sun.target.position.copy(center);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -size, right: size, top: size, bottom: -size, near: 1, far: 60 });
sun.shadow.bias = -0.0005;
scene.add(sun, sun.target);

const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200),
  new THREE.MeshStandardMaterial({ color: '#cfd5c6', roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.03;
ground.receiveShadow = true;
scene.add(ground);

const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;

// ---------- model ----------
const parts = {};
const bytes = Uint8Array.from(atob(S.glb), (c) => c.charCodeAt(0));
new GLTFLoader().parse(bytes.buffer, '', (gltf) => {
  scene.add(gltf.scene);
  for (const n of ['walls', 'openings', 'ceiling', 'wardrobes', 'doors', 'windows', 'floors'])
    parts[n] = gltf.scene.getObjectByName(n);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const glass = o.material.transparent;
    o.castShadow = !glass;
    o.receiveShadow = true;
    if (glass) o.material.depthWrite = false;
  });
  parts.ceiling.traverse((o) => { if (o.isMesh) o.receiveShadow = false; });
  makeLabels();
  const [initial, room, heading] = decodeURIComponent(location.hash.slice(1)).split(':');  // #walk:cocina:90
  if (room) S.walk.start = room;
  if (heading) S.walk.heading = Number(heading);
  setMode(['model', 'plan', 'walk'].includes(initial) ? initial : 'model');
  renderer.setAnimationLoop(loop);
}, (err) => { document.body.textContent = 'Could not load the model: ' + err; });

// ---------- room labels on the floor ----------
const labels = new THREE.Group();
scene.add(labels);
function makeLabels() {
  const px = 64, m = S.labelSize / px;        // same text size as the plan
  for (const r of S.rooms) {
    const c = document.createElement('canvas');
    const g = c.getContext('2d');
    const bold = `bold ${px}px ${S.labelFont}`, regular = `${px}px ${S.labelFont}`;
    g.font = bold;
    const w = Math.max(g.measureText(r.name).width, 200) + 20;
    c.width = w; c.height = px * 2.6;
    g.textAlign = 'center';
    g.font = bold; g.fillStyle = '#111'; g.fillText(r.name, w / 2, px);
    g.font = regular; g.fillStyle = '#444'; g.fillText(r.area, w / 2, px * 2.2);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(c.width * m, c.height * m),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
    plane.rotation.x = -Math.PI / 2;
    const pivot = new THREE.Group();
    pivot.position.set(r.x, 0.02, r.z);
    if (r.rotated) pivot.rotation.y = Math.PI / 2;  // plan labels turned 90° (corridors)
    pivot.add(plane);
    labels.add(pivot);
    const op = document.createElement('option');
    op.value = r.id; op.textContent = r.name;
    $('go-to').append(op);
  }
}

// ---------- modes ----------
let mode = null;
const look = { yaw: 0, pitch: 0 };
const eye = S.heights.eye;

function setMode(m) {
  mode = m;
  document.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('active', b.dataset.mode === m));
  const walking = m === 'walk';
  orbit.enabled = !walking;
  $('crosshair').style.display = $('room').style.display = walking ? 'block' : 'none';
  $('show-ceiling').checked = walking;
  $('show-labels').checked = !walking;
  applyVisibility();
  camera.fov = walking ? 70 : m === 'plan' ? 30 : 45;
  camera.updateProjectionMatrix();
  if (m === 'model') {
    orbit.enableRotate = true;
    orbit.target.copy(center);
    const dir = new THREE.Vector3(-0.45, 0.95, 0.75).normalize();
    camera.position.copy(center).addScaledVector(dir, fitDistance() * 1.05);
  } else if (m === 'plan') {
    orbit.enableRotate = false;
    orbit.target.copy(center);
    camera.position.set(center.x, fitDistance(), center.z + 0.001);
  } else {
    const r = S.rooms.find((e) => e.id === S.walk.start) || S.rooms[0];
    goTo(r);
    look.yaw = -THREE.MathUtils.degToRad(S.walk.heading);
    look.pitch = 0;
  }
  orbit.update();
  $('help').innerHTML = walking
    ? 'WASD / arrows: walk · Shift: run<br>Click: look with the mouse (Esc releases)<br>or drag to look'
    : 'Drag: rotate · wheel: zoom<br>Right-click / two fingers: pan';
}
document.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));

// distance at which the whole plan fits the screen (with margin) at the current fov
function fitDistance() {
  const t = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  return 1.1 * Math.max((bz1 - bz0) / 2 / t, (bx1 - bx0) / 2 / (t * camera.aspect)) + S.heights.ceiling;
}

function applyVisibility() {
  parts.ceiling.visible = $('show-ceiling').checked;
  parts.doors.visible = $('show-doors').checked;
  labels.visible = $('show-labels').checked;
  labels.traverse((o) => {                   // top view: names over the walls
    if (o.isMesh) { o.material.depthTest = mode !== 'plan'; o.renderOrder = mode === 'plan' ? 10 : 0; }
  });
}
for (const id of ['show-ceiling', 'show-doors', 'show-labels'])
  $(id).addEventListener('change', applyVisibility);

function goTo(r) {
  if (mode === 'walk') {
    camera.position.set(r.x, eye, r.z);
  } else {
    const d = camera.position.clone().sub(orbit.target).setLength(mode === 'plan' ? 9 : 7);
    orbit.target.set(r.x, 0, r.z);
    camera.position.copy(orbit.target).add(d);
  }
}
$('go-to').addEventListener('change', (e) => {
  const r = S.rooms.find((x) => x.id === e.target.value);
  if (r) goTo(r);
  e.target.value = '';
  e.target.blur();
});

// ---------- walking ----------
const keys = new Set();
addEventListener('keydown', (e) => { keys.add(e.code); });
addEventListener('keyup', (e) => { keys.delete(e.code); });
addEventListener('blur', () => keys.clear());

const canvas = renderer.domElement;
let dragging = false;
canvas.addEventListener('click', () => {
  if (mode === 'walk' && document.pointerLockElement !== canvas) canvas.requestPointerLock?.();
});
canvas.addEventListener('pointerdown', () => { dragging = true; });
addEventListener('pointerup', () => { dragging = false; });
addEventListener('mousemove', (e) => {
  if (mode !== 'walk') return;
  const locked = document.pointerLockElement === canvas;
  if (!locked && !dragging) return;
  const k = locked ? 0.0022 : 0.005;
  look.yaw -= e.movementX * k;
  look.pitch = THREE.MathUtils.clamp(look.pitch - e.movementY * k, -1.4, 1.4);
});

const ray = new THREE.Raycaster();
const RADIUS = 0.25;
function solids() {
  const s = [parts.walls, parts.wardrobes, parts.windows];
  if (parts.doors.visible) s.push(parts.doors);
  return s;
}
function isFree(origin, dir, dist) {
  for (const h of [0.3, 1.2]) {
    ray.set(new THREE.Vector3(origin.x, h, origin.z), dir);
    ray.far = dist + RADIUS;
    if (ray.intersectObjects(solids(), true).length) return false;
  }
  return true;
}

const down = new THREE.Vector3(0, -1, 0);
function roomAt(p) {
  ray.set(new THREE.Vector3(p.x, 1, p.z), down);
  ray.far = 2;
  const hit = ray.intersectObject(parts.floors, true)[0];
  let o = hit?.object;
  while (o && !o.userData.name) o = o.parent;
  return o?.userData.name || '';
}

const clock = new THREE.Clock();
function loop() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (mode === 'walk') {
    camera.rotation.set(look.pitch, look.yaw, 0, 'YXZ');
    const forward = new THREE.Vector3(-Math.sin(look.yaw), 0, -Math.cos(look.yaw));
    const right = new THREE.Vector3(-forward.z, 0, forward.x);
    const move = new THREE.Vector3();
    if (keys.has('KeyW') || keys.has('ArrowUp')) move.add(forward);
    if (keys.has('KeyS') || keys.has('ArrowDown')) move.sub(forward);
    if (keys.has('KeyD') || keys.has('ArrowRight')) move.add(right);
    if (keys.has('KeyA') || keys.has('ArrowLeft')) move.sub(right);
    if (move.lengthSq()) {
      const v = S.walk.speed * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 2.5 : 1);
      move.normalize().multiplyScalar(v * dt);
      for (const axis of ['x', 'z']) {
        if (!move[axis]) continue;
        const dir = new THREE.Vector3(axis === 'x' ? Math.sign(move.x) : 0, 0, axis === 'z' ? Math.sign(move.z) : 0);
        if (isFree(camera.position, dir, Math.abs(move[axis]))) camera.position[axis] += move[axis];
      }
    }
    camera.position.y = eye;
    $('room').textContent = roomAt(camera.position) || 'Outside';
  } else {
    orbit.update();
  }
  renderer.render(scene, camera);
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
