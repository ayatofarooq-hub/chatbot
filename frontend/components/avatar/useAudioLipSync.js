/** CPU-friendly Web Audio energy lip sync for an HTMLAudioElement. */
export function createAudioLipSync({ onFrame, onError } = {}) {
  let context = null;
  let analyser = null;
  let source = null;
  let gain = null;
  let samples = null;
  let active = false;
  let smoothedEnergy = 0;
  let volume = 1;
  let visemeProvider = null;

  const reset = () => {
    smoothedEnergy = 0;
    onFrame?.({ energy: 0, jaw: 0, viseme: null });
  };

  async function attach(audio) {
    detach();
    if (!audio) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("Web Audio API is unavailable.");
      context ||= new AudioContextClass({ latencyHint: "interactive" });
      analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.56;
      gain = context.createGain();
      gain.gain.value = volume;
      source = context.createMediaElementSource(audio);
      source.connect(analyser);
      analyser.connect(gain);
      gain.connect(context.destination);
      samples = new Float32Array(analyser.fftSize);
      await context.resume();
      active = true;
    } catch (error) {
      detach();
      onError?.(error);
    }
  }

  function sample(audioTime = 0) {
    if (!active || !analyser || !samples) {
      smoothedEnergy *= 0.72;
      if (smoothedEnergy < 0.002) smoothedEnergy = 0;
      onFrame?.({ energy: smoothedEnergy, jaw: smoothedEnergy * 0.82, viseme: null });
      return smoothedEnergy;
    }
    analyser.getFloatTimeDomainData(samples);
    let sumSquares = 0;
    for (let index = 0; index < samples.length; index += 1) {
      sumSquares += samples[index] * samples[index];
    }
    const rms = Math.sqrt(sumSquares / samples.length);
    const noiseFloor = 0.018;
    const naturalCeiling = 0.16;
    const target = Math.max(0, Math.min(1, (rms - noiseFloor) / (naturalCeiling - noiseFloor)));
    const smoothing = target > smoothedEnergy ? 0.38 : 0.16;
    smoothedEnergy += (target - smoothedEnergy) * smoothing;
    if (smoothedEnergy < 0.018) smoothedEnergy = 0;
    const viseme = visemeProvider?.(audioTime) || null;
    onFrame?.({ energy: smoothedEnergy, jaw: Math.min(0.82, smoothedEnergy * 0.86), viseme });
    return smoothedEnergy;
  }

  function detach() {
    active = false;
    try { source?.disconnect(); } catch (_) { /* already disconnected */ }
    try { analyser?.disconnect(); } catch (_) { /* already disconnected */ }
    try { gain?.disconnect(); } catch (_) { /* already disconnected */ }
    source = null;
    analyser = null;
    gain = null;
    samples = null;
    reset();
  }

  function setVolume(nextVolume) {
    volume = Math.max(0, Math.min(1, Number(nextVolume) || 0));
    if (gain && context) gain.gain.setTargetAtTime(volume, context.currentTime, 0.02);
  }

  function setVisemeProvider(provider) {
    visemeProvider = typeof provider === "function" ? provider : null;
  }

  async function dispose() {
    detach();
    if (context && context.state !== "closed") await context.close();
    context = null;
  }

  return { attach, sample, detach, setVolume, setVisemeProvider, dispose };
}
