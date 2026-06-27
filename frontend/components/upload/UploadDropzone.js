import { MAX_FILES } from "./uploadTypes.js";

export function createUploadDropzone({ onFilesSelected }) {
  const label = document.createElement("label");
  label.className = "upload-dropzone";
  label.tabIndex = 0;
  label.setAttribute("role", "button");
  label.setAttribute("aria-label", "رفع ملفات القرار بصيغة PDF أو DOC أو DOCX");

  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.accept = ".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  const icon = document.createElement("span");
  icon.className = "upload-illustration";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "⇪";

  const title = document.createElement("strong");
  title.textContent = "اسحب الملفات هنا أو اضغط للتصفح";

  const subtitle = document.createElement("small");
  subtitle.textContent = "الصيغ المدعومة: PDF, DOC, DOCX";

  const hint = document.createElement("span");
  hint.className = "upload-hint";
  hint.textContent = `حتى ${MAX_FILES} ملفات، 100 ميغابايت لكل ملف`;

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
  };
}
