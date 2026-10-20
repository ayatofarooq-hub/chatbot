# Original Word files in the related-documents panel

Under **قرارات ووثائق ذات صلة → الوثائق الرسمية**, a cited Word source now
shows its filename and two actions:

- **فتح الوثيقة** opens an offline text/table preview inside the application.
- **تحميل Word** downloads the original `.docx` without conversion or modification.

The preview works in both the browser and desktop WebView2, without requiring
Microsoft Word or uploading the file to an external viewer. Images and original
Word formatting remain available in the downloadable original.

The controls also work for saved conversations containing the source filename.
They are shown after checking the original file's availability; missing originals
display **ملف Word الأصلي غير متوفر.**

The API requires the same login as the chatbot and checks the filename against
`citation_registry.json`. It resolves originals only inside the configured source
folders, refuses path traversal and ambiguous filenames, and does not expose a
general filesystem download endpoint:

- `GET /api/source-documents/{filename}`: availability and action URLs.
- `GET /api/source-documents/{filename}/preview`: escaped text/table HTML.
- `GET /api/source-documents/{filename}/download`: original Word attachment.

Source documents, generated indexes, model settings, retrieval, and answer
generation are unchanged.
