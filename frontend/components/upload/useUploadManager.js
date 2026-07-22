import { createUploadDropzone } from "./UploadDropzone.js";
import { createUploadProgressCard, updateUploadProgressCard } from "./UploadProgressCard.js";
import { createUploadedFileCard } from "./UploadedFileCard.js";
import { createUploadStats } from "./UploadStats.js";
import {
  fetchUploadedFiles,
  fetchUploadSettings,
  removeUploadedFile,
  uploadFile,
} from "./uploadService.js?v=20260712-upload-settings";
import { DEFAULT_UPLOAD_CONFIG, normalizeUploadConfig } from "./uploadConfig.js?v=20260712-upload-settings";
import { UploadStatus } from "./uploadTypes.js?v=20260706-real-uploads";
import { validateFiles } from "./uploadValidation.js?v=20260712-upload-settings";

export function createUploadManager({
  dropzoneRoot,
  errorsRoot,
  listRoot,
  statsRoot,
  countRoot,
  capacityRoot,
  subtitleRoot,
  qualityCountRoot,
  qualityLabelRoot,
  showToast,
}) {
  const state = {
    files: [],
    cancelUploadById: new Map(),
    config: DEFAULT_UPLOAD_CONFIG,
    errors: [],
  };

  const dropzone = createUploadDropzone({
    config: state.config,
    onFilesSelected(files) {
      addFiles(files);
    },
  });

  dropzoneRoot.replaceChildren(dropzone.element);

  function addFiles(files) {
    const { validFiles, errors } = validateFiles(files, state.files.length, state.config);
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
      const { promise, cancel } = uploadFile(file, (progress) => {
        updateFile({ ...fileItem, ...progress, status: UploadStatus.UPLOADING });
      });
      state.cancelUploadById.set(fileItem.id, cancel);
      promise.then((uploaded) => {
        state.cancelUploadById.delete(fileItem.id);
        state.files = state.files.map((candidate) => (
          candidate.id === fileItem.id
            ? {
              ...candidate,
              id: uploaded.id,
              status: UploadStatus.UPLOADED,
              progress: 100,
              speedBytesPerSecond: 0,
              remainingSeconds: 0,
              uploadedAt: uploaded.uploaded_at,
              chunkCount: uploaded.chunk_count,
            }
            : candidate
        ));
        render();
        showToast(`Saved and indexed "${file.name}".`);
      }).catch((error) => {
        state.cancelUploadById.delete(fileItem.id);
        state.files = state.files.filter((candidate) => candidate.id !== fileItem.id);
        state.errors = [error.message];
        showToast(error.message);
        render();
      });
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

  async function deleteFile(fileId) {
    const card = listRoot.querySelector(`[data-file-id="${fileId}"]`);
    card?.classList.add("removing");
    try {
      await removeUploadedFile(fileId);
      state.cancelUploadById.get(fileId)?.();
      state.cancelUploadById.delete(fileId);
      state.files = state.files.filter((fileItem) => fileItem.id !== fileId);
      render();
      showToast("File moved to source library and remains searchable.");
    } catch (error) {
      card?.classList.remove("removing");
      showToast(error.message);
    }
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
    window.open(`/api/uploads/${encodeURIComponent(fileItem.id)}/download`, "_blank", "noopener,noreferrer");
  }

  function downloadFile(fileItem) {
    const link = document.createElement("a");
    link.href = `/api/uploads/${encodeURIComponent(fileItem.id)}/download`;
    link.download = fileItem.file.name;
    link.click();
  }

  function render() {
    const uploadingCount = state.files.filter((fileItem) => fileItem.status === UploadStatus.UPLOADING).length;
    const uploadedCount = state.files.filter((fileItem) => fileItem.status === UploadStatus.UPLOADED).length;
    const totalSize = state.files.reduce((sum, fileItem) => sum + fileItem.file.size, 0);
    const dropzoneState = state.errors.length ? "error" : uploadingCount ? "uploading" : uploadedCount ? "uploaded" : "empty";

    dropzone.setState(dropzoneState);
    renderErrors();
    renderFileList();
    statsRoot.replaceChildren(createUploadStats({ totalSize, count: state.files.length }, state.config));

    const maxFilesLabel = state.config.ready ? state.config.maxFiles : "...";
    countRoot.textContent = `${state.files.length} / ${maxFilesLabel}`;
    capacityRoot.textContent = `${state.files.length} / ${maxFilesLabel}`;
    if (subtitleRoot) subtitleRoot.textContent = state.config.ready
      ? `You can upload up to ${state.config.maxFiles} files.`
      : "Loading upload limits...";
    if (qualityCountRoot) qualityCountRoot.textContent = `${state.files.length}/${maxFilesLabel}`;
    if (qualityLabelRoot) qualityLabelRoot.textContent = uploadedCount
      ? `Uploaded ${uploadedCount} of ${maxFilesLabel} files`
      : "No uploaded files yet";
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
      empty.textContent = "No files have been uploaded yet.";
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

  fetchUploadSettings().then((settings) => {
    state.config = normalizeUploadConfig(settings);
    dropzone.setConfig(state.config);
    render();
  }).catch((error) => {
    state.errors = [error.message];
    render();
  });

  fetchUploadedFiles().then((items) => {
    state.files = items.map((item) => ({
      id: item.id,
      file: { name: item.name, size: item.size, type: "" },
      status: UploadStatus.UPLOADED,
      progress: 100,
      speedBytesPerSecond: 0,
      remainingSeconds: 0,
      uploadedAt: item.uploaded_at,
      chunkCount: item.chunk_count,
    }));
    render();
  }).catch((error) => {
    state.errors = [error.message];
    render();
  });

  return {
    getFiles() {
      return [...state.files];
    },
  };
}
