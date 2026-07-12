import { uploadLimitText } from "./uploadConfig.js?v=20260712-upload-settings";

export function createUploadDropzone({ config, onFilesSelected }) {
  const label = document.createElement("label");
  label.className = "upload-dropzone";
  label.tabIndex = 0;
  label.setAttribute("role", "button");
  label.setAttribute("aria-label", "Upload PDF, DOCX, or TXT files");

  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.accept = ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

  const icon = document.createElement("span");
  icon.className = "upload-illustration";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "⇪";

  const title = document.createElement("strong");
  title.textContent = "Drop files here or browse";

  const subtitle = document.createElement("small");
  subtitle.textContent = "Supported formats: PDF, DOCX, TXT";

  const hint = document.createElement("span");
  hint.className = "upload-hint";
  hint.textContent = uploadLimitText(config);

  label.append(input, icon, title, subtitle, hint);

  const selectFiles = (files) => onFilesSelected(Array.from(files || []));

  input.addEventListener("change", () => {
    selectFiles(input.files);
    input.value = "";
  });

  label.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  label.addEventListener("dragover", (event) => {
    event.preventDefault();
    label.classList.add("dragging");
  });

  label.addEventListener("dragleave", () => {
    label.classList.remove("dragging");
  });

  label.addEventListener("drop", (event) => {
    event.preventDefault();
    label.classList.remove("dragging");
    selectFiles(event.dataTransfer.files);
  });

  return {
    element: label,
    setState(state) {
      label.classList.toggle("uploading", state === "uploading");
      label.classList.toggle("error", state === "error");
      label.setAttribute("data-state", state);
    },
    setConfig(nextConfig) {
      hint.textContent = uploadLimitText(nextConfig);
    },
  };
}
