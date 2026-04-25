<template>
  <div ref="container" class="canvas-container"></div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";
import * as THREE from "three";
import GUI from "lil-gui";

type Params = {
  cantidad: number;
  velocidad: number;
};

const container = ref<HTMLDivElement | null>(null);

// Three core
let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let gui: GUI;

// Objetos
let boxes: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>[] = [];

// Params tipados
const params: Params = {
  cantidad: 15,
  velocidad: 0.03,
};

let animationId: number;

// 🔹 Función resize (tipada fuera para poder removerla bien)
function onResize() {
  if (!container.value) return;

  camera.aspect = container.value.clientWidth / container.value.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.value.clientWidth, container.value.clientHeight);
}

onMounted(() => {
  if (!container.value) return;

  // Escena
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x20252f);

  // Cámara
  camera = new THREE.PerspectiveCamera(
    75,
    container.value.clientWidth / container.value.clientHeight,
    0.1,
    1000,
  );
  camera.position.set(0, 5, 12);

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(container.value.clientWidth, container.value.clientHeight);
  container.value.appendChild(renderer.domElement);

  // Luces
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));

  const light: THREE.DirectionalLight = new THREE.DirectionalLight(0xffffff, 1);
  light.position.set(10, 10, 10);
  scene.add(light);

  // Suelo
  const floor: THREE.Mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(50, 50),
    new THREE.MeshStandardMaterial({ color: 0x555555 }),
  );
  floor.rotation.x = -Math.PI / 2;
  scene.add(floor);

  // Cinta
  const belt: THREE.Mesh = new THREE.Mesh(
    new THREE.BoxGeometry(20, 0.5, 2),
    new THREE.MeshStandardMaterial({ color: 0x222222 }),
  );
  belt.position.y = 0.25;
  scene.add(belt);

  const boxGeometry = new THREE.BoxGeometry(1, 1, 1);

  // Crear cajas
  function crearCajas(): void {
    boxes.forEach((b) => scene.remove(b));
    boxes = [];

    for (let i = 0; i < params.cantidad; i++) {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(`hsl(${Math.random() * 360},50%,50%)`),
      });

      const box: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial> = new THREE.Mesh(
        boxGeometry,
        material,
      );

      box.position.set(-8 + i * 1.5, 1, 0);
      scene.add(box);
      boxes.push(box);
    }
  }

  crearCajas();

  // GUI
  gui = new GUI();

  gui
    .add(params, "cantidad", 1, 50, 1)
    .name("Cajas")
    .onChange(() => crearCajas());

  gui.add(params, "velocidad", 0.001, 0.2, 0.001).name("Velocidad");

  // Animación
  const animate = (): void => {
    animationId = requestAnimationFrame(animate);

    boxes.forEach((box) => {
      box.position.x += params.velocidad;
      if (box.position.x > 10) box.position.x = -10;
    });

    renderer.render(scene, camera);
  };

  animate();

  // Resize
  window.addEventListener("resize", onResize);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId);
  gui.destroy();
  window.removeEventListener("resize", onResize);
});
</script>

<style scoped>
.canvas-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}
</style>
