import { MAX_FILES, MAX_FILE_SIZE_BYTES } from "./uploadTypes.js";
import { formatFileSize } from "./uploadFormatters.js";

export function createUploadStats(stats) {
  const container = document.createElement("section");
  container.className = "upload-stats";
  container.setAttribute("aria-label", "إحصائيات الملفات المرفوعة");

  container.append(
    createStat("إجمالي حجم المرفوعات", formatFileSize(stats.totalSize)),
    createStat("أقصى حجم للملف الواحد", formatFileSize(MAX_FILE_SIZE_BYTES)),
    createStat("عدد الملفات", `${stats.count} / ${MAX_FILES}`),
    createStat("السعة المتبقية", `${Math.max(MAX_FILES - stats.count, 0)} ملفات`),
  );

  return container;
}

function createStat(label, value) {
  const card = document.createElement("div");
  card.className = "stat-card";

  const labelNode = document.createElement("span");
  labelNode.textContent = label;

  const valueNode = document.createElement("strong");
  valueNode.textContent = value;

  card.append(labelNode, valueNode);
  return card;
}
