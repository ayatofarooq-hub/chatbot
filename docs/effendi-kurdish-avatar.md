# Kurdish Effendi prototype

Generated with the built-in image generator as an identity-preserving edit of the Arabic day idle sheet. Native RGBA transparency was preserved and all eight cells were aligned to a fixed 450-pixel character height and feet baseline.

- Raw sheet: `frontend/images/ai-effendi/fallback/effendi-kurdish-idle-8-v1.png`
- Aligned sheet: `frontend/images/ai-effendi/fallback/effendi-kurdish-idle-8-aligned-transparent-v1.png`
- Preview: `/assets/effendi-kurdish-preview.html`

The avatar is connected to the Arabic/Kurdish selector. Kurdish mode uses dedicated idle, talking, and seated-thinking sheets and identifies the character as **مُجيب**. Arabic keeps its existing day/night sheets.

- Talking sheet: `frontend/images/ai-effendi/fallback/effendi-kurdish-talking-8-aligned-transparent-v1.png`
- Thinking sheet: `frontend/images/ai-effendi/fallback/effendi-kurdish-thinking-chair-8-aligned-transparent-v1.png`

## Local Kurmanji voice

Kurdish mode uses `ku` (Kurdî/Kurmanji) and the local eSpeak-NG `ku` voice. Arabic continues to use Piper/Kareem. eSpeak expects Latin Kurmanji, so the answer request asks the local chat model for Latin letters and the TTS endpoint rejects Arabic-script Kurdish instead of returning silent audio.

The default executable is `C:\Program Files\eSpeak NG\espeak-ng.exe`. Set `ESPEAK_NG_PATH` if it is installed elsewhere, and optionally set `ESPEAK_KURDISH_VOICE` to override the voice name.

## Final prompt

Identity-preserving 4x2 transparent idle sprite sheet. Preserve Mujib's face, moustache, proportions, scale and stylized 3D-cartoon rendering. Replace only the fez and Western suit with dignified traditional Iraqi Kurdish men's clothing: a dark charcoal/olive shal u shapik outfit, loose pleated trousers, fitted traditional jacket and shirt, broad layered dark-maroon pishtwen sash, black-and-white patterned jamadani turban, and traditional dark leather shoes. Eight subtle sequential idle poses; fixed coordinates and feet baseline; genuine RGBA transparency; no text, scenery, weapons, flags, logos, extra limbs or unrelated gestures.

Talking and thinking prompts kept the same identity/clothing invariants. Talking uses eight sequential mouth shapes and restrained hand motion. Thinking seats مُجيب on a fixed walnut/green chair with round glasses and eight connected hand-to-chin poses. Both are 1536×1024 RGBA 4×2 sheets with fixed scale and baseline.
