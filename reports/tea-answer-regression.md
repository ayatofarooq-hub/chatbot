# Tea decision answer regression

Investigated on 2026-10-18 using the question:

> ما هي الجهة الحكومية التي بادرت برفع الطلب للتعامل مع كميات الشاي الموقوفة والتالفة؟

## Evidence

The API selected one registered source, `قرار توصية الاقتصاد بشأن مادة الشاي الموقوف.docx`,
chunk `b7d64495e4ef-chunk-0`. The model received a 2,012-character context containing
both the retrieved text and the original JSON full text. The supporting sentence is:

> بناءً على ما عرضتـه وزارة التجارة بموجب كتابها المرقـــم بالعــــدد ( م.ر/5521 ) المـــؤرخ في 4/8/2024 .

With identical retrieval, prompts, temperature, context length, and answer-token
settings, changing only the chat model produced:

| Model | Answered requesting authority | Generation time |
| --- | --- | --- |
| qwen2.5:1.5b | مجلس الوزراء — incorrect | 3.98 seconds |
| qwen2.5:3b | وزارة التجارة — correct | 29.99 seconds |

The 1.5B run also reproduced the user's fallback suggestions about the date and
the ministry's role. The 3B run generated substantive suggestions from the decision.

## Cause and correction

The merge introduced `auto_select_model=True` as the default. Existing saved
settings contained `chat_model=qwen2.5:3b` and no automatic-selection flag. The
runtime treated that missing flag as enabled and replaced 3B with the hardware
recommendation, 1.5B on this installation. Reverting later test fixes did not
remove this earlier merge change. The answering prompts and generator did not
change between pre-merge main `e4e7ce7` and merge `86f7406`.

Automatic selection now requires explicit opt-in. Defaults, runtime resolution,
settings responses, and the settings UI preserve the configured model when the
flag is absent. Explicit automatic mode remains available.

No source text, embeddings, citation-registry records, retrieval rules, or prompts
were changed for this correction. No tea-specific answer rule was added. This
comparison diagnoses this regression; it does not establish accuracy for all
questions or either model.

The comparison can be repeated with:

```powershell
.\.venv\Scripts\python.exe reports/diagnose_tea_answer.py
```

This invokes both installed Ollama models and writes detailed local output to
`reports/tea-answer-comparison.json` without persisting chat history or settings.

## Verification after correction

- Six model-selection tests passed, including legacy settings with no automatic
  flag and continued support for explicit automatic mode.
- All 42 settings and grounded-answer tests passed.
- A new call through `app.api.answer_question()` with the actual runtime settings
  selected `qwen2.5:3b` and answered **وزارة التجارة**, with registered citations.
  No per-model override or test answer was injected into this call.
- The local server was restarted and `/health` returned `{"status":"ok"}`.
