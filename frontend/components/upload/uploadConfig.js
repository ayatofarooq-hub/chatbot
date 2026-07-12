export const DEFAULT_UPLOAD_CONFIG = Object.freeze({
  maxFiles: null,
  maxFileSizeMb: null,
  ready: false,
});

export function normalizeUploadConfig(settings = {}) {
  const maxFiles = Number(settings.max_file_count ?? settings.maxFiles);
  const maxFileSizeMb = Number(settings.max_file_size_mb ?? settings.maxFileSizeMb);

  if (!Number.isInteger(maxFiles) || maxFiles <= 0 || !Number.isInteger(maxFileSizeMb) || maxFileSizeMb <= 0) {
    return DEFAULT_UPLOAD_CONFIG;
  }

  return { maxFiles, maxFileSizeMb, ready: true };
}

export function uploadConfigToBytes(config) {
  if (!config.ready) return 0;
  return config.maxFileSizeMb * 1024 * 1024;
}

export function uploadLimitText(config) {
  if (!config.ready) return "Loading upload limits...";
  return `Maximum ${config.maxFiles} files, up to ${config.maxFileSizeMb} MB each.`;
}
