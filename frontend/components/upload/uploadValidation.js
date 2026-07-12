import {
  ACCEPTED_EXTENSIONS,
  ACCEPTED_MIME_TYPES,
} from "./uploadTypes.js?v=20260706-real-uploads";
import { uploadConfigToBytes } from "./uploadConfig.js?v=20260712-upload-settings";
import { fileExtension, formatFileSize } from "./uploadFormatters.js";

export function validateFiles(files, currentCount, config) {
  const errors = [];
  const validFiles = [];
  const maxFileSizeBytes = uploadConfigToBytes(config);

  if (!config.ready) {
    return { validFiles, errors: ["Upload settings are not loaded yet."] };
  }

  for (const file of files) {
    const extension = fileExtension(file.name);
    const hasAcceptedType = ACCEPTED_MIME_TYPES.has(file.type) || ACCEPTED_EXTENSIONS.includes(extension);

    if (!hasAcceptedType) {
      errors.push(`The file "${file.name}" is not supported. Available formats: PDF, DOCX, TXT.`);
      continue;
    }

    if (file.size > maxFileSizeBytes) {
      errors.push(`The file "${file.name}" is ${formatFileSize(file.size)} and exceeds the ${config.maxFileSizeMb} MB limit.`);
      continue;
    }

    if (currentCount + validFiles.length >= config.maxFiles) {
      errors.push(`You cannot upload more than ${config.maxFiles} files.`);
      continue;
    }

    validFiles.push(file);
  }

  return { validFiles, errors };
}
