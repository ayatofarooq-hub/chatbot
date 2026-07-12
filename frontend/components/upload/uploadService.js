export function uploadFile(file, onProgress) {
  const request = new XMLHttpRequest();
  const startedAt = performance.now();
  request.open("POST", "/api/uploads");
  request.withCredentials = true;

  const promise = new Promise((resolve, reject) => {
    request.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0.1);
      const speedBytesPerSecond = event.loaded / elapsedSeconds;
      onProgress({
        progress: Math.round((event.loaded / event.total) * 100),
        speedBytesPerSecond,
        remainingSeconds: speedBytesPerSecond
          ? (event.total - event.loaded) / speedBytesPerSecond
          : 0,
      });
    });
    request.addEventListener("load", () => {
      const payload = JSON.parse(request.responseText || "{}");
      if (request.status >= 200 && request.status < 300) resolve(payload);
      else reject(new Error(payload.detail || "فشل رفع الملف وفهرسته."));
    });
    request.addEventListener("error", () => reject(new Error("تعذر الاتصال بخادم الرفع.")));
    request.addEventListener("abort", () => reject(new Error("تم إلغاء رفع الملف.")));
  });

  const form = new FormData();
  form.append("file", file);
  request.send(form);
  return { promise, cancel: () => request.abort() };
}

export async function fetchUploadedFiles() {
  const response = await fetch("/api/uploads", { credentials: "same-origin" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "تعذر تحميل الملفات المرفوعة.");
  return payload.items || [];
}

export async function fetchUploadSettings() {
  const response = await fetch("/api/uploads/settings", { credentials: "same-origin" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "تعذر تحميل إعدادات الرفع.");
  return payload;
}

export async function removeUploadedFile(fileId) {
  const response = await fetch(`/api/uploads/${encodeURIComponent(fileId)}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "تعذر حذف الملف.");
}
