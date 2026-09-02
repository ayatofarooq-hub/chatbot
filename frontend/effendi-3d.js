import * as THREE from "three";
import { GLTFLoader } from "/assets/vendor/three/addons/loaders/GLTFLoader.js";
import { createAudioLipSync } from "/assets/components/avatar/useAudioLipSync.js";

const dock = document.querySelector("#ai-character");
const canvas = document.querySelector("#ai-effendi-3d");
const fallback = document.querySelector("#ai-character-fallback");
const loading = document.querySelector("#ai-character-loading");

if (dock && canvas && window.WebGLRenderingContext) {
  let renderer, scene, camera, model, mixer, currentAction, frameId;
  let visible = true;
  let disposed = false;
  let motionEnabled = localStorage.getItem("jalssa-avatar-motion") !== "false";
  let nextBlinkAt = performance.now() + 1800;
  let blinkStartedAt = 0;
  let lastInteractionAt = performance.now();
  const morphs = new Map();
  const actions = new Map();
  const clock = new THREE.Clock();
  const stateToClip = {
    idle: "Idle", listening: "Listening", thinking: "Thinking", talking: "Talking",
    greeting: "Greeting", success: "Success", error: "Error",
  };

  const setMorph = (name, value) => (morphs.get(name) || []).forEach(({ mesh, index }) => {
    mesh.morphTargetInfluences[index] = value;
  });
  const bindMorphs = (root) => root.traverse((node) => {
    if (!node.isMesh || !node.morphTargetDictionary) return;
    Object.entries(node.morphTargetDictionary).forEach(([name, index]) => {
      if (!morphs.has(name)) morphs.set(name, []);
      morphs.get(name).push({ mesh: node, index });
    });
  });

  const lipSync = createAudioLipSync({
    onFrame: ({ energy, jaw, viseme }) => {
      setMorph("JawOpen", jaw);
      setMorph("MouthClosed", Math.max(0, 0.22 - energy));
      const cycle = Math.floor(performance.now() / 130) % 3;
      setMorph("Viseme_AI", viseme === "AI" ? 0.7 : energy * (cycle === 0 ? 0.34 : 0.08));
      setMorph("Viseme_E", viseme === "E" ? 0.7 : energy * (cycle === 1 ? 0.28 : 0.05));
      setMorph("Viseme_O", viseme === "O" ? 0.7 : energy * (cycle === 2 ? 0.32 : 0.04));
    },
    onError: (error) => console.warn("Audio analysis unavailable; animation continues.", error),
  });

  function playState(state, fade = 0.34) {
    if (!mixer) return;
    const name = stateToClip[state] || "Idle";
    const next = actions.get(name) || actions.get("Idle");
    if (!next || next === currentAction) return;
    next.reset().setEffectiveTimeScale(motionEnabled ? 1 : 0.01).setEffectiveWeight(1);
    if (["Greeting", "Success", "Error"].includes(name)) {
      next.setLoop(THREE.LoopOnce, 1);
      next.clampWhenFinished = true;
    } else {
      next.setLoop(THREE.LoopRepeat, Infinity);
      next.clampWhenFinished = false;
    }
    next.play();
    if (currentAction) currentAction.crossFadeTo(next, fade, true);
    currentAction = next;
    lastInteractionAt = performance.now();
  }

  function resize() {
    if (!renderer || !camera) return;
    const width = Math.max(1, canvas.clientWidth);
    const height = Math.max(1, canvas.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function updateBlink(now) {
    if (!motionEnabled) { setMorph("BlinkLeft", 0); setMorph("BlinkRight", 0); return; }
    if (!blinkStartedAt && now >= nextBlinkAt) blinkStartedAt = now;
    if (!blinkStartedAt) return;
    const phase = (now - blinkStartedAt) / 145;
    const amount = phase < 0.45 ? phase / 0.45 : Math.max(0, (1 - phase) / 0.55);
    setMorph("BlinkLeft", Math.min(1, amount));
    setMorph("BlinkRight", Math.min(1, amount));
    if (phase >= 1) {
      blinkStartedAt = 0;
      nextBlinkAt = now + 2400 + Math.random() * 3100;
    }
  }

  function render() {
    if (disposed) return;
    if (visible && !document.hidden) {
      const delta = Math.min(clock.getDelta(), 0.05);
      if (mixer && motionEnabled) mixer.update(delta);
      const now = performance.now();
      updateBlink(now);
      if (model && motionEnabled && dock.dataset.state === "idle" && now - lastInteractionAt > 10000) {
        model.rotation.y = Math.sin((now - lastInteractionAt) / 3500) * 0.22;
      } else if (model) model.rotation.y = THREE.MathUtils.lerp(model.rotation.y, 0, 0.08);
      lipSync.sample(window.__effendiSpeechAudio?.currentTime || 0);
      renderer.render(scene, camera);
    } else clock.getDelta();
    frameId = requestAnimationFrame(render);
  }

  async function initialize() {
    try {
      const config = await fetch("/api/avatar/config").then((r) => r.ok ? r.json() : {}).catch(() => ({}));
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "high-performance" });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(Number(config.camera_fov) || 27, 1, 0.1, 100);
      camera.position.set(0, 4.3, Number(config.camera_distance) || 18.2);
      camera.lookAt(0, 4.2, 0);
      scene.add(new THREE.HemisphereLight(0xfff6e8, 0x254f3b, 2.5));
      const key = new THREE.DirectionalLight(0xffead0, 3.1);
      key.position.set(-4, 8, 7);
      scene.add(key);
      const fill = new THREE.DirectionalLight(0xc3ead7, 1.5);
      fill.position.set(5, 4, 4);
      scene.add(fill);
      resize();
      const gltf = await new GLTFLoader().loadAsync(config.model_url || "/assets/models/effendi-cartoon.glb");
      model = gltf.scene;
      bindMorphs(model);
      mixer = new THREE.AnimationMixer(model);
      gltf.animations.forEach((clip) => actions.set(clip.name, mixer.clipAction(clip)));
      mixer.addEventListener("finished", () => {
        if (["greeting", "success", "error"].includes(dock.dataset.state)) {
          dock.dataset.state = "idle";
          playState("idle");
        }
      });
      scene.add(model);
      dock.classList.add("ai-character-dock--three-ready");
      fallback?.setAttribute("hidden", "");
      loading?.setAttribute("hidden", "");
      playState(dock.dataset.state || "idle", 0);
      dock.dispatchEvent(new CustomEvent("avatar:loaded", { detail: { clips: [...actions.keys()], morphs: [...morphs.keys()] } }));
      render();
    } catch (error) {
      loading?.setAttribute("hidden", "");
      dock.classList.add("ai-character-dock--fallback");
      dock.dispatchEvent(new CustomEvent("avatar:error", { detail: { error } }));
      console.warn("The 3D Effendi could not load; showing the static portrait.", error);
    }
  }

  new MutationObserver(() => playState(dock.dataset.state || "idle")).observe(dock, { attributes: true, attributeFilter: ["data-state"] });
  new ResizeObserver(resize).observe(dock);
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { rootMargin: "100px" }).observe(dock);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) clock.start(); });
  window.addEventListener("avatar:speech-start", async ({ detail }) => {
    window.__effendiSpeechAudio = detail?.audio;
    await lipSync.attach(detail?.audio);
    playState("talking");
    dock.dispatchEvent(new CustomEvent("avatar:speaking-started"));
  });
  window.addEventListener("avatar:speech-stop", () => {
    lipSync.detach();
    window.__effendiSpeechAudio = null;
    setMorph("JawOpen", 0);
    dock.dispatchEvent(new CustomEvent("avatar:speaking-ended"));
  });
  window.addEventListener("avatar:volume", ({ detail }) => lipSync.setVolume(detail?.volume));
  window.addEventListener("avatar:motion", ({ detail }) => {
    motionEnabled = detail?.enabled !== false;
    if (currentAction) currentAction.timeScale = motionEnabled ? 1 : 0.01;
  });
  window.addEventListener("pagehide", async () => {
    disposed = true;
    cancelAnimationFrame(frameId);
    await lipSync.dispose();
    mixer?.stopAllAction();
    model?.traverse((node) => {
      node.geometry?.dispose?.();
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach((material) => {
        Object.values(material).forEach((value) => value?.isTexture && value.dispose());
        material.dispose();
      });
    });
    renderer?.dispose();
  }, { once: true });
  const lazy = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) { lazy.disconnect(); initialize(); }
  }, { rootMargin: "250px" });
  lazy.observe(dock);
} else if (dock) {
  loading?.setAttribute("hidden", "");
  dock.classList.add("ai-character-dock--fallback");
}
