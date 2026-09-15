# Hand-lowering in-between test

Generated with the built-in image generator, preserving native RGBA transparency.
The main conversation animation is unchanged. Preview: `/assets/effendi-motion-demo.html`.
Playback: eight sequential frames at 110 ms, one shot with manual replay; no crossfade or randomness.

Reference: `frontend/images/ai-effendi/fallback/effendi-thinking-chair-day-b-8-aligned-transparent-v1.png`.
Raw: `frontend/images/ai-effendi/fallback/effendi-hand-lower-inbetweens-day-8-v1.png`.
Aligned: `frontend/images/ai-effendi/fallback/effendi-hand-lower-inbetweens-day-8-aligned-transparent-v1.png`.

## Final prompt

Use case: identity-preserve. Asset: eight-frame animation sprite sheet, 1536x1024, exactly four columns and two rows of equal 384x512 cells, reading order. Reference image is identity, chair, style and pose reference. Use ONLY its top-left cell as START pose and top-second cell as END pose. Create eight consecutive in-between frames of ONE action: the seated man's right hand (viewer-left) lowers smoothly from touching his chin to resting on the chair armrest. Frame 1 starts at chin; frames 2 through 7 progressively lower that hand with small evenly spaced natural changes of shoulder, elbow, wrist and fingers; frame 8 rests on armrest. Do NOT reproduce the reference's unrelated gestures. Lock the face, eyes looking forward, round glasses, moustache, black fez, black three-piece suit, tie, chain, white shirt, legs and other hand. Lock chair shape, camera, body position, scale, feet baseline and lighting across all eight cells. Full intact cartoon man plus entire walnut/green chair in every cell, identical screen coordinates, no body segmentation. Genuine transparent RGBA background; no checkerboard painted into image, no ground, no shadows outside character, no labels, no borders. High-quality smooth stylized 3D cartoon rendering matching reference. Single continuous action, not eight independent poses.
