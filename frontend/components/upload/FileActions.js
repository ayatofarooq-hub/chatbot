export function createFileActions({ fileItem, onPreview, onDownload, onDelete, onMoveUp, onMoveDown }) {
  const actions = document.createElement("div");
  actions.className = "file-actions";
  actions.setAttribute("aria-label", `إجراءات الملف ${fileItem.file.name}`);

  const preview = createAction("معاينة", () => onPreview(fileItem));
  const download = createAction("تنزيل", () => onDownload(fileItem));
  const deleteButton = createAction("إلى المصادر", () => onDelete(fileItem.id));
  const moveUp = createAction("أعلى", () => onMoveUp(fileItem.id));
  const moveDown = createAction("أسفل", () => onMoveDown(fileItem.id));
  const moreWrapper = document.createElement("div");
  moreWrapper.className = "more-actions";

  const more = createAction("⋯", () => {
    const isOpen = menu.hidden;
    menu.hidden = !isOpen;
    more.setAttribute("aria-expanded", String(isOpen));
  }, "more-menu");
  more.title = "إجراءات إضافية";
  more.setAttribute("aria-label", "إجراءات إضافية");
  more.setAttribute("aria-haspopup", "menu");
  more.setAttribute("aria-expanded", "false");

  const menu = document.createElement("div");
  menu.className = "more-actions-menu";
  menu.setAttribute("role", "menu");
  menu.hidden = true;
  menu.append(
    createMenuAction("نسخ اسم الملف", () => navigator.clipboard?.writeText(fileItem.file.name)),
    createMenuAction(`النوع: ${fileItem.file.type || "غير معروف"}`, () => {}),
  );

  moreWrapper.append(more, menu);

  actions.append(preview, download, deleteButton, moveUp, moveDown, moreWrapper);
  return actions;
}

function createAction(label, onClick, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.className = className;
  button.addEventListener("click", onClick);
  return button;
}

function createMenuAction(label, onClick) {
  const button = createAction(label, onClick);
  button.setAttribute("role", "menuitem");
  return button;
}
