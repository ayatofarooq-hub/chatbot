import { uploadConfigToBytes } from "./uploadConfig.js?v=20260712-upload-settings";
import { formatFileSize } from "./uploadFormatters.js";

export function createUploadStats(stats, config) {
  const container = document.createElement("section");
  container.className = "upload-stats";
  container.setAttribute("aria-label", "Uploaded file statistics");

  container.append(
    createStat("Total upload size", formatFileSize(stats.totalSize)),
    createStat("Maximum size per file", config.ready ? formatFileSize(uploadConfigToBytes(config)) : "..."),
    createStat("Files", `${stats.count} / ${config.ready ? config.maxFiles : "..."}`),
    createStat("Remaining capacity", config.ready ? `${Math.max(config.maxFiles - stats.count, 0)} files` : "..."),
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
