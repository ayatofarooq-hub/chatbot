import {
  ACCEPTED_EXTENSIONS,
  ACCEPTED_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
} from "./uploadTypes.js";
import { fileExtension, formatFileSize } from "./uploadFormatters.js";

export function validateFiles(files, currentCount, maxFiles) {
  const errors = [];
  const validFiles = [];

  for (const file of files) {
    const extension = fileExtension(file.name);
    const hasAcceptedType = ACCEPTED_MIME_TYPES.has(file.type) || ACCEPTED_EXTENSIONS.includes(extension);

    if (!hasAcceptedType) {
      errors.push(`الملف "${file.name}" غير مدعوم. الصيغ المتاحة: PDF, DOC, DOCX.`);
      continue;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      errors.push(`الملف "${file.name}" حجمه ${formatFileSize(file.size)} ويتجاوز الحد الأقصى 100 ميغابايت.`);
      continue;
    }

    if (currentCount + validFiles.length >= maxFiles) {
      errors.push("لا يمكن رفع أكثر من 3 ملفات للقرار الواحد.");
      continue;
    }

    validFiles.push(file);
  }

  return { validFiles, errors };
}
