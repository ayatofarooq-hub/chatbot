import { UploadStatus } from "./uploadTypes.js";

export function simulateUpload(fileItem, onProgress, onComplete) {
  const startedAt = performance.now();
  const duration = Math.max(1800, Math.min(9000, fileItem.file.size / 18000));

  const timer = window.setInterval(() => {
    const elapsed = performance.now() - startedAt;
    const progress = Math.min(100, Math.round((elapsed / duration) * 100));
    const uploadedBytes = fileItem.file.size * (progress / 100);
    const elapsedSeconds = Math.max(elapsed / 1000, 0.1);
    const speedBytesPerSecond = uploadedBytes / elapsedSeconds;
    const remainingBytes = Math.max(fileItem.file.size - uploadedBytes, 0);
    const remainingSeconds = speedBytesPerSecond > 0 ? remainingBytes / speedBytesPerSecond : 0;

    onProgress({
      ...fileItem,
      status: UploadStatus.UPLOADING,
      progress,
      speedBytesPerSecond,
      remainingSeconds,
    });

    if (progress >= 100) {
      window.clearInterval(timer);
      onComplete({
        ...fileItem,
        status: UploadStatus.UPLOADED,
        progress: 100,
        speedBytesPerSecond,
        remainingSeconds: 0,
        uploadedAt: new Date().toISOString(),
      });
    }
  }, 180);

  return () => window.clearInterval(timer);
}
