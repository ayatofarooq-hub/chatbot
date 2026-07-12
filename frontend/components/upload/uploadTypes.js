export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];
export const ACCEPTED_MIME_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]);

export const UploadStatus = Object.freeze({
  QUEUED: "queued",
  UPLOADING: "uploading",
  UPLOADED: "uploaded",
  ERROR: "error",
});
