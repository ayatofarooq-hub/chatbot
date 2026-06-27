import {
  fileTypeLabel,
  formatFileSize,
  formatRemainingTime,
  formatUploadSpeed,
} from "./uploadFormatters.js";

export function createUploadProgressCard(fileItem) {
  const card = document.createElement("article");
  card.className = "file-card";
  card.dataset.fileId = fileItem.id;
  card.dataset.status = fileItem.status;

  const icon = document.createElement("div");
  icon.className = `file-icon ${fileTypeLabel(fileItem.file.name).toLowerCase()}`;
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "📄";

  const main = document.createElement("div");
  main.className = "file-main";

  const titleRow = document.createElement("div");
  titleRow.className = "file-title-row";

  const name = document.createElement("strong");
  name.className = "file-name";
  name.textContent = fileItem.file.name;

  const status = document.createElement("span");
  status.className = "status-pill status-uploading";
  status.dataset.uploadStatus = "true";
  status.textContent = `جاري الرفع ${fileItem.progress}%`;

  titleRow.append(name, status);

  const meta = document.createElement("div");
  meta.className = "file-meta";
  meta.textContent = formatFileSize(fileItem.file.size);

  const progressTrack = document.createElement("progress");
  progressTrack.className = "progress-track";
  progressTrack.dataset.uploadProgress = "true";
  progressTrack.max = 100;
  progressTrack.value = fileItem.progress;
  progressTrack.setAttribute("aria-label", `نسبة رفع ${fileItem.file.name}`);

  const uploadMeta = document.createElement("div");
  uploadMeta.className = "progress-meta";
  uploadMeta.dataset.uploadMeta = "true";
  uploadMeta.append(
    createMeta(`السرعة: ${formatUploadSpeed(fileItem.speedBytesPerSecond)}`),
    createMeta(`المتبقي: ${formatRemainingTime(fileItem.remainingSeconds)}`),
  );

  main.append(titleRow, meta, progressTrack, uploadMeta);
  card.append(icon, main);
  return card;
}

export function updateUploadProgressCard(card, fileItem) {
  const status = card.querySelector("[data-upload-status]");
  const progress = card.querySelector("[data-upload-progress]");
  const meta = card.querySelector("[data-upload-meta]");

  card.dataset.status = fileItem.status;
  if (status) status.textContent = `جاري الرفع ${fileItem.progress}%`;
  if (progress) progress.value = fileItem.progress;
  if (meta) {
    meta.replaceChildren(
      createMeta(`السرعة: ${formatUploadSpeed(fileItem.speedBytesPerSecond)}`),
      createMeta(`المتبقي: ${formatRemainingTime(fileItem.remainingSeconds)}`),
    );
  }
}

function createMeta(text) {
  const span = document.createElement("span");
  span.textContent = text;
  return span;
}
