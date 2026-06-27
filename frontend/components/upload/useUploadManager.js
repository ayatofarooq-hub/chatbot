import { createUploadDropzone } from "./UploadDropzone.js";
import { createUploadProgressCard, updateUploadProgressCard } from "./UploadProgressCard.js";
import { createUploadedFileCard } from "./UploadedFileCard.js";
import { createUploadStats } from "./UploadStats.js";
import { simulateUpload } from "./uploadService.js";
import { MAX_FILES, UploadStatus } from "./uploadTypes.js";
import { validateFiles } from "./uploadValidation.js";

export function createUploadManager({
  dropzoneRoot,
  errorsRoot,
  listRoot,
  statsRoot,
  countRoot,
  capacityRoot,
  qualityCountRoot,
  qualityLabelRoot,
  showToast,
}) {
  const state = {
    files: [],
    cancelUploadById: new Map(),
    errors: [],
  };

  const dropzone = createUploadDropzone({
    onFilesSelected(files) {
      addFiles(files);
    },
  });

  dropzoneRoot.replaceChildren(dropzone.element);

  function addFiles(files) {
    const { validFiles, errors } = validateFiles(files, state.files.length, MAX_FILES);
    state.errors = errors;
    errors.forEach(showToast);

    validFiles.forEach((file) => {
      const fileItem = {
        id: crypto.randomUUID(),
        file,
        status: UploadStatus.UPLOADING,
        progress: 0,
        speedBytesPerSecond: 0,
        remainingSeconds: 0,
        uploadedAt: null,
      };

      state.files.push(fileItem);
      const cancel = simulateUpload(fileItem, updateFile, updateFile);
      state.cancelUploadById.set(fileItem.id, cancel);
    });

    render();
  }

  function updateFile(nextFile) {
    state.files = state.files.map((fileItem) =>
      fileItem.id === nextFile.id ? nextFile : fileItem,
    );
    if (nextFile.status === UploadStatus.UPLOADED) {
      state.cancelUploadById.delete(nextFile.id);
    }
    render();
  }

  function deleteFile(fileId) {
    const card = listRoot.querySelector(`[data-file-id="${fileId}"]`);
    card?.classList.add("removing");
    window.setTimeout(() => {
      state.cancelUploadById.get(fileId)?.();
      state.cancelUploadById.delete(fileId);
      state.files = state.files.filter((fileItem) => fileItem.id !== fileId);
      render();
    }, 150);
  }

  function moveFile(fileId, direction) {
    const index = state.files.findIndex((fileItem) => fileItem.id === fileId);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= state.files.length) return;
    const reordered = [...state.files];
    [reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]];
    state.files = reordered;
    render();
  }

  function previewFile(fileItem) {
    const url = URL.createObjectURL(fileItem.file);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
  }

  function downloadFile(fileItem) {
    const url = URL.createObjectURL(fileItem.file);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileItem.file.name;
    link.click();
    URL.revokeObjectURL(url);
  }

  function render() {
    const uploadingCount = state.files.filter((fileItem) => fileItem.status === UploadStatus.UPLOADING).length;
    const uploadedCount = state.files.filter((fileItem) => fileItem.status === UploadStatus.UPLOADED).length;
    const totalSize = state.files.reduce((sum, fileItem) => sum + fileItem.file.size, 0);
    const dropzoneState = state.errors.length ? "error" : uploadingCount ? "uploading" : uploadedCount ? "uploaded" : "empty";

    dropzone.setState(dropzoneState);
    renderErrors();
    renderFileList();
    statsRoot.replaceChildren(createUploadStats({ totalSize, count: state.files.length }));

    countRoot.textContent = `${state.files.length} / ${MAX_FILES}`;
    capacityRoot.textContent = `${state.files.length} / ${MAX_FILES}`;
    if (qualityCountRoot) qualityCountRoot.textContent = `${state.files.length}/${MAX_FILES}`;
    if (qualityLabelRoot) qualityLabelRoot.textContent = uploadedCount
      ? `تم رفع ${uploadedCount} من ${MAX_FILES} ملفات`
      : "لا توجد ملفات مرفوعة بعد";
  }

  function renderErrors() {
    errorsRoot.replaceChildren();
    state.errors.forEach((error) => {
      const alert = document.createElement("div");
      alert.className = "upload-alert";
      alert.textContent = error;
      errorsRoot.append(alert);
    });
  }

  function renderFileList() {
    if (!state.files.length) {
      listRoot.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty-panel";
      empty.textContent = "لم يتم رفع أي ملفات بعد.";
      listRoot.append(empty);
      return;
    }

    listRoot.querySelector(".empty-panel")?.remove();
    const activeIds = new Set(state.files.map((fileItem) => fileItem.id));
    listRoot.querySelectorAll("[data-file-id]").forEach((card) => {
      if (!activeIds.has(card.dataset.fileId)) card.remove();
    });

    state.files.forEach((fileItem) => {
      const existingCard = listRoot.querySelector(`[data-file-id="${fileItem.id}"]`);
      const existingStatus = existingCard?.dataset.status;

      if (existingCard && fileItem.status === UploadStatus.UPLOADING && existingStatus === UploadStatus.UPLOADING) {
        updateUploadProgressCard(existingCard, fileItem);
        listRoot.append(existingCard);
        return;
      }

      const card = fileItem.status === UploadStatus.UPLOADED
        ? createUploadedFileCard(fileItem, {
          onPreview: previewFile,
          onDownload: downloadFile,
          onDelete: deleteFile,
          onMoveUp: (fileId) => moveFile(fileId, -1),
          onMoveDown: (fileId) => moveFile(fileId, 1),
        })
        : createUploadProgressCard(fileItem);
      if (existingCard) {
        existingCard.replaceWith(card);
      } else {
        listRoot.append(card);
      }
    });
  }

  render();

  return {
    getFiles() {
      return [...state.files];
    },
  };
}
