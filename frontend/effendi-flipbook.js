/**
 * Smooth whole-body flipbook animation.
 * Every source frame contains the complete character; no body part is layered.
 */
const character = document.querySelector("#ai-character");
const flipbook = document.querySelector("#ai-character-fallback");

if (character && flipbook) {
  const layers = [
    flipbook.querySelector(".ai-character-frame--a"),
    flipbook.querySelector(".ai-character-frame--b"),
  ].filter(Boolean);
  const rows = {
    idle: 0,
    listening: 2,
    thinking: 2,
    talking: 1,
    greeting: 1,
    success: 1,
    error: 2,
  };
  const timing = {
    idle: [300, 510],
    listening: [245, 390],
    thinking: [250, 410],
    talking: [135, 235],
    greeting: [155, 250],
    success: [180, 280],
    error: [260, 410],
  };
  const phraseLengths = {
    idle: [7, 13],
    listening: [8, 15],
    thinking: [10, 18],
    talking: [12, 24],
    greeting: [8, 12],
    success: [7, 11],
    error: [8, 13],
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let state = character.dataset.state || "idle";
  let activeLayer = 0;
  let lastColumn = 0;
  let phrase = [];
  let timer = 0;
  let driftFrame = 0;
  let stateStartedAt = performance.now();
  const usedPhrases = new Set();

  const randomBetween = ([minimum, maximum]) => minimum + Math.random() * (maximum - minimum);

  function setCell(layer, column, row) {
    layer.style.backgroundPosition = `${column * (100 / 3)}% ${row * 50}%`;
  }

  function createUniquePhrase() {
    const [minimum, maximum] = phraseLengths[state] || phraseLengths.idle;
    const length = Math.floor(minimum + Math.random() * (maximum - minimum + 1));
    let candidate;
    let signature;
    let attempts = 0;
    do {
      candidate = [];
      let previous = lastColumn;
      for (let index = 0; index < length; index += 1) {
        const choices = [0, 1, 2, 3].filter((value) => value !== previous);
        let next = choices[Math.floor(Math.random() * choices.length)];
        // Returning through a neutral pose keeps large hand gestures coherent.
        if (state === "talking" && index % 3 === 2) next = 0;
        if ((state === "thinking" || state === "listening") && index % 4 === 3) next = 1;
        candidate.push(next);
        previous = next;
      }
      signature = `${state}:${candidate.join("")}`;
      attempts += 1;
    } while (usedPhrases.has(signature) && attempts < 40);
    usedPhrases.add(signature);
    return candidate;
  }

  function transitionTo(column) {
    const row = rows[state] ?? 0;
    const nextLayer = activeLayer === 0 ? 1 : 0;
    const current = layers[activeLayer];
    const next = layers[nextLayer];
    if (!current || !next) return;
    setCell(next, column, row);
    next.style.opacity = "0";
    // Force the initial transparent paint before starting the crossfade.
    void next.offsetWidth;
    next.style.opacity = "1";
    current.style.opacity = "0";
    activeLayer = nextLayer;
    lastColumn = column;
  }

  function scheduleNextFrame() {
    window.clearTimeout(timer);
    if (reducedMotion.matches) {
      setCell(layers[activeLayer], 0, rows[state] ?? 0);
      return;
    }
    if (document.hidden) {
      timer = window.setTimeout(scheduleNextFrame, 500);
      return;
    }
    if (!phrase.length) phrase = createUniquePhrase();
    transitionTo(phrase.shift());
    const baseDelay = randomBetween(timing[state] || timing.idle);
    // Occasional short holds remove the mechanical metronome effect.
    const hold = Math.random() < 0.13 ? randomBetween([90, 260]) : 0;
    timer = window.setTimeout(scheduleNextFrame, baseDelay + hold);
  }

  function animateDrift(now) {
    if (!reducedMotion.matches && !document.hidden) {
      const elapsed = (now - stateStartedAt) / 1000;
      const intensity = state === "talking" ? 1 : state === "thinking" ? 0.72 : 0.48;
      // Incommensurate periods prevent the whole-body motion from visibly looping at 30 seconds.
      const x = (Math.sin(elapsed * 2.17) * 0.8 + Math.sin(elapsed * 0.73) * 0.45) * intensity;
      const y = (Math.sin(elapsed * 2.91) * 0.85 + Math.sin(elapsed * 0.47) * 0.5) * intensity;
      const turn = (Math.sin(elapsed * 0.83) * 0.18 + Math.sin(elapsed * 0.31) * 0.1) * intensity;
      const scale = 1 + (Math.sin(elapsed * 1.37) * 0.0025 + Math.sin(elapsed * 0.59) * 0.0015) * intensity;
      flipbook.style.setProperty("--avatar-x", `${x.toFixed(3)}px`);
      flipbook.style.setProperty("--avatar-y", `${y.toFixed(3)}px`);
      flipbook.style.setProperty("--avatar-turn", `${turn.toFixed(3)}deg`);
      flipbook.style.setProperty("--avatar-scale", scale.toFixed(5));
    }
    driftFrame = requestAnimationFrame(animateDrift);
  }

  function changeState() {
    const nextState = character.dataset.state || "idle";
    if (nextState === state) return;
    state = nextState;
    phrase = [];
    usedPhrases.clear();
    stateStartedAt = performance.now();
    window.clearTimeout(timer);
    scheduleNextFrame();
  }

  new MutationObserver(changeState).observe(character, {
    attributes: true,
    attributeFilter: ["data-state"],
  });
  reducedMotion.addEventListener?.("change", scheduleNextFrame);
  setCell(layers[0], 0, rows[state] ?? 0);
  scheduleNextFrame();
  driftFrame = requestAnimationFrame(animateDrift);

  window.addEventListener("pagehide", () => {
    window.clearTimeout(timer);
    cancelAnimationFrame(driftFrame);
  }, { once: true });
}
