# Effendi thinking animation

Generated with the built-in image generator, using the existing Effendi and chair
sprites as identity, clothing and pose references. Native RGBA alpha is retained;
the RGB day-B source requires checkerboard removal. No crossfade or randomness.

## Final prompt set

All prompts request an exact 4-column, 2-row sprite sheet, eight complete sequential
poses, transparent background, unchanged face, moustache, round glasses, chair,
camera, lighting, body scale and ground baseline.

- B: continue chin pose, lower hand, join hands, adjust glasses, lean forward,
  raise index finger with an insight, then relax onto armrests.
- C: glance sideways, return to center, contemplate while touching moustache,
  clasp hands, open one palm to weigh an idea, join fingertips, then settle.
- D: look upward, fingertips to temple, lower hand, lean back, cross a leg,
  adjust glasses, nod gently, then return to chin-thinking pose.
- Night B/C/D: reproduce the matching day gestures and chair exactly, replacing
  the suit/fez with the established bald, hatless Effendi in an ivory Iraqi home
  dishdasha and brown slippers.

## Final project assets

Under `frontend/images/ai-effendi/fallback/`:

- `effendi-thinking-chair-day-b-8-aligned-transparent-v1.png`
- `effendi-thinking-chair-day-c-8-aligned-transparent-v1.png`
- `effendi-thinking-chair-day-d-8-aligned-transparent-v1.png`
- `effendi-thinking-chair-night-b-8-aligned-transparent-v1.png`
- `effendi-thinking-chair-night-c-8-aligned-transparent-v1.png`
- `effendi-thinking-chair-night-d-8-aligned-transparent-v1.png`

Prepare from the saved source siblings with:

```powershell
python -m scripts.prepare_thinking_continuations
```

Playback in `frontend/effendi-flipbook.js`: eight intro frames at 210 ms each,
then 24 continuation frames at 350 ms each. The intro is not replayed. One full
continuation cycle is about 8.4 seconds; a finite frame set necessarily repeats
if thinking lasts longer. Changing theme preserves the current sequence position.
