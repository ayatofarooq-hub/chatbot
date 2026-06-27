import { createFileActions } from "./FileActions.js";
import { fileTypeLabel, formatFileSize, formatUploadDate } from "./uploadFormatters.js";

export function createUploadedFileCard(fileItem, actions) {
  const card = document.createElement("article");
  card.className = "file-card";
  card.dataset.fileId = fileItem.id;
  card.dataset.status = fileItem.status;

  const type = fileTypeLabel(fileItem.file.name).toLowerCase();
  const icon = document.createElement("div");
  icon.className = `file-icon ${type}`;
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
  status.className = "status-pill status-uploaded";
  status.textContent = "✓ تم الرفع";

  titleRow.append(name, status);

  const meta = document.createElement("div");
  meta.className = "uploaded-meta";
  meta.textContent = `${formatFileSize(fileItem.file.size)} · ${formatUploadDate(fileItem.uploadedAt)}`;

  main.append(titleRow, meta);
  card.append(icon, main, createFileActions({ fileItem, ...actions }));
  return card;
}
