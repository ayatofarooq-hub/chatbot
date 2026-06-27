export function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 ميغابايت";
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} ميغابايت`;
}

export function formatUploadSpeed(bytesPerSecond) {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) return "0 ميغابايت/ث";
  return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} ميغابايت/ث`;
}

export function formatRemainingTime(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "أقل من ثانية";
  if (seconds < 60) return `${Math.ceil(seconds)} ثانية`;
  return `${Math.ceil(seconds / 60)} دقيقة`;
}

export function formatUploadDate(value) {
  return new Intl.DateTimeFormat("ar-IQ", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function fileExtension(fileName = "") {
  const index = fileName.lastIndexOf(".");
  return index >= 0 ? fileName.slice(index).toLowerCase() : "";
}

export function fileTypeLabel(fileName = "") {
  return fileExtension(fileName).replace(".", "").toUpperCase() || "FILE";
}
