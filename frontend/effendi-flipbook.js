/** Whole-body animation with a one-shot intro and 24 sequential thinking frames. */
const character = document.querySelector("#ai-character");
const flipbook = document.querySelector("#ai-character-fallback");
const landingFlipbook = document.querySelector("#landing-effendi");

if (character && flipbook) {
  const assetVersion = "20260916-mujib-kurdish-v8";
  const assetSets = {
    day: {
      idle: `/assets/images/ai-effendi/fallback/effendi-idle-8-aligned-transparent-v1.png?v=${assetVersion}`,
      talking: `/assets/images/ai-effendi/fallback/effendi-talking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      listening: `/assets/images/ai-effendi/fallback/effendi-thinking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinking: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-day-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingB: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-day-b-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingC: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-day-c-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingD: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-day-d-8-aligned-transparent-v1.png?v=${assetVersion}`,
    },
    night: {
      idle: `/assets/images/ai-effendi/fallback/effendi-night-idle-8-aligned-transparent-v1.png?v=${assetVersion}`,
      talking: `/assets/images/ai-effendi/fallback/effendi-night-talking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      listening: `/assets/images/ai-effendi/fallback/effendi-night-thinking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinking: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-night-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingB: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-night-b-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingC: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-night-c-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingD: `/assets/images/ai-effendi/fallback/effendi-thinking-chair-night-d-8-aligned-transparent-v1.png?v=${assetVersion}`,
    },
    kurdish: {
      idle: `/assets/images/ai-effendi/fallback/effendi-kurdish-idle-8-aligned-transparent-v1.png?v=${assetVersion}`,
      talking: `/assets/images/ai-effendi/fallback/effendi-kurdish-talking-8-aligned-transparent-v1.png?v=${assetVersion}`,
      listening: `/assets/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinking: `/assets/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingB: `/assets/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingC: `/assets/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png?v=${assetVersion}`,
      thinkingD: `/assets/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png?v=${assetVersion}`,
    },
  };
  const stateAsset = {
    idle: "idle",
    listening: "listening",
    thinking: "thinking",
    talking: "talking",
    greeting: "talking",
    success: "talking",
    error: "listening",
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
  const thinkingTimeline = ["thinking", "thinkingB", "thinkingC", "thinkingD"]
    .flatMap((asset, sheet) => sequence.map((frame) => ({
      asset,
      frame,
      delay: sheet === 0 ? 210 : 350,
    })));
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let state = character.dataset.state || "idle";
  let frameIndex = 0;
  let lastFrameAt = 0;
  let animationFrame = 0;
  let thinkingPosition = 0;
  let shownThinkingPosition = 0;

  // Preload every sheet so sequential sheet changes never expose a blank frame.
  Object.values(assetSets).flatMap((set) => Object.values(set)).forEach((source) => {
    const image = new Image();
    image.src = source;
  });

  function isNightMode() {
    return document.documentElement.dataset.theme === "dark";
  }

  function activeAssetSet() {
    if (["ku", "ckb"].includes(document.documentElement.dataset.language)) return assetSets.kurdish;
    return isNightMode() ? assetSets.night : assetSets.day;
  }

  function framePosition(frame) {
    const column = frame % 4;
    const row = Math.floor(frame / 4);
    return `${column * (100 / 3)}% ${row * 100}%`;
  }

  function showFrame(frame) {
    const position = framePosition(frame);
    flipbook.style.backgroundPosition = position;
    if (landingFlipbook) landingFlipbook.style.backgroundPosition = position;
  }

  function applyStateAsset() {
    const assetName = state === "thinking"
      ? thinkingTimeline[shownThinkingPosition].asset
      : stateAsset[state] || "idle";
    const activeAssets = activeAssetSet();
    flipbook.style.backgroundImage = `url("${activeAssets[assetName]}")`;
    if (landingFlipbook) {
      landingFlipbook.style.backgroundImage = `url("${activeAssets.idle}")`;
    }
  }

  function showThinkingFrame(position) {
    shownThinkingPosition = position;
    applyStateAsset();
    flipbook.style.backgroundPosition = framePosition(thinkingTimeline[position].frame);
  }

  function animate(now) {
    if (!document.hidden) {
      if (reducedMotion.matches) {
        if (state === "thinking") showThinkingFrame(thinkingTimeline.length - 1);
        else showFrame(0);
      } else if (state === "thinking") {
        if (now - lastFrameAt >= thinkingTimeline[shownThinkingPosition].delay) {
          showThinkingFrame(thinkingPosition);
          thinkingPosition += 1;
          // Repeat only the 24 seated continuations, never the sitting/glasses intro.
          if (thinkingPosition >= thinkingTimeline.length) thinkingPosition = 8;
          lastFrameAt = now;
        }
      } else if (now - lastFrameAt >= (delays[state] || delays.idle)) {
        showFrame(sequence[frameIndex]);
        frameIndex = (frameIndex + 1) % sequence.length;
        lastFrameAt = now;
      }
    }
    animationFrame = requestAnimationFrame(animate);
  }

  new MutationObserver(() => {
    state = character.dataset.state || "idle";
    frameIndex = 0;
    thinkingPosition = 0;
    shownThinkingPosition = 0;
    lastFrameAt = 0;
    applyStateAsset();
    showFrame(0);
  }).observe(character, { attributes: true, attributeFilter: ["data-state"] });

  new MutationObserver(applyStateAsset).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "data-language"],
  });
  applyStateAsset();
  showFrame(0);
  animationFrame = requestAnimationFrame(animate);
  window.addEventListener("pagehide", () => {
    cancelAnimationFrame(animationFrame);
  }, { once: true });
}
