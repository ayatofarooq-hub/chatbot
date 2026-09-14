/** Deterministic whole-body animation: 8 complete images per state, no crossfade. */
const character = document.querySelector("#ai-character");
const flipbook = document.querySelector("#ai-character-fallback");
const landingFlipbook = document.querySelector("#landing-effendi");

if (character && flipbook) {
  const assetVersion = "20260907-night-effendi-v4";
  const assetSets = {
    day: {
      idle: `/assets/images/ai-effendi/fallback/effendi-idle-8-aligned-transparent-v1.png?v=${assetVersion}`,
      talking: `/assets/images/ai-effendi/fallback/effendi-talking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinking: `/assets/images/ai-effendi/fallback/effendi-thinking-8-aligned-transparent-v1.png?v=${assetVersion}`,
    },
    night: {
      idle: `/assets/images/ai-effendi/fallback/effendi-night-idle-8-aligned-transparent-v1.png?v=${assetVersion}`,
      talking: `/assets/images/ai-effendi/fallback/effendi-night-talking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinking: `/assets/images/ai-effendi/fallback/effendi-night-thinking-8-aligned-transparent-v1.png?v=${assetVersion}`,
    },
  };
  const stateAsset = {
    idle: "idle",
    listening: "thinking",
    thinking: "thinking",
    talking: "talking",
    greeting: "talking",
    success: "talking",
    error: "thinking",
  };
  const delays = {
    idle: 225,
    listening: 220,
    thinking: 235,
    talking: 160,
    greeting: 175,
    success: 185,
    error: 230,
  };
  const sequence = [0, 1, 2, 3, 4, 5, 6, 7];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let state = character.dataset.state || "idle";
  let frameIndex = 0;
  let lastFrameAt = 0;
  let animationFrame = 0;

  // Preload all three sheets so changing state never exposes a blank frame.
  Object.values(assetSets).flatMap((set) => Object.values(set)).forEach((source) => {
    const image = new Image();
    image.src = source;
  });

  function isNightMode() {
    return document.documentElement.dataset.theme === "dark";
  }

  function showFrame(frame) {
    const column = frame % 4;
    const row = Math.floor(frame / 4);
    const position = `${column * (100 / 3)}% ${row * 100}%`;
    flipbook.style.backgroundPosition = position;
    if (landingFlipbook) landingFlipbook.style.backgroundPosition = position;
  }

  function applyStateAsset() {
    const assetName = stateAsset[state] || "idle";
    const activeAssets = isNightMode() ? assetSets.night : assetSets.day;
    flipbook.style.backgroundImage = `url("${activeAssets[assetName]}")`;
    if (landingFlipbook) {
      landingFlipbook.style.backgroundImage = `url("${activeAssets.idle}")`;
    }
  }

  function animate(now) {
    if (reducedMotion.matches || document.hidden) {
      frameIndex = 0;
      showFrame(sequence[0]);
    } else if (now - lastFrameAt >= (delays[state] || delays.idle)) {
      showFrame(sequence[frameIndex]);
      frameIndex = (frameIndex + 1) % sequence.length;
      lastFrameAt = now;
    }
    animationFrame = requestAnimationFrame(animate);
  }

  new MutationObserver(() => {
    state = character.dataset.state || "idle";
    frameIndex = 0;
    lastFrameAt = 0;
    applyStateAsset();
    showFrame(0);
  }).observe(character, { attributes: true, attributeFilter: ["data-state"] });

  new MutationObserver(applyStateAsset).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  applyStateAsset();
  showFrame(0);
  animationFrame = requestAnimationFrame(animate);
  window.addEventListener("pagehide", () => {
    cancelAnimationFrame(animationFrame);
  }, { once: true });
}
