export const MAX_FILES = 3;
export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx"];
export const ACCEPTED_MIME_TYPES = new Set([
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export const UploadStatus = Object.freeze({
  QUEUED: "queued",
  UPLOADING: "uploading",
  UPLOADED: "uploaded",
  ERROR: "error",
});
