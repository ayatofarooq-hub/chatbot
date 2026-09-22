import { applyLanguage, t } from "./i18n.js?v=20260916-kurdish";

const labels = {
  authFields: [
    ["login_enabled", "إلزام تسجيل الدخول", "checkbox"],
    ["remember_login", "تذكّر تسجيل الدخول", "checkbox"],
    ["session_timeout_minutes", "مدة الجلسة", "select", [15, 30, 60, 240, null]],
    ["password_min_length", "الحد الأدنى لطول كلمة المرور", "number"],
    ["require_numbers", "اشتراط رقم في كلمة المرور", "checkbox"],
    ["require_symbols", "اشتراط رمز خاص في كلمة المرور", "checkbox"],
    ["require_uppercase", "اشتراط حرف لاتيني كبير", "checkbox"],
  ],
  uploadFields: [
    ["max_file_count", "Maximum number of uploaded files", "number"],
    ["max_file_size_mb", "Maximum file size per file", "select", [5, 10, 20, 25]],
  ],
  fileSizeOptions: {
    5: "5 MB",
    10: "10 MB",
    20: "20 MB",
    25: "25 MB",
  },
  sessionOptions: {
    15: "15 دقيقة",
    30: "30 دقيقة",
    60: "ساعة واحدة",
    240: "4 ساعات",
    "": "بدون انتهاء",
  },
  roles: {
    super_admin: "مدير عام",
    admin: "مدير",
    viewer: "مراجع للقراءة فقط",
  },
  actions: {
    login_failed: "فشل تسجيل الدخول",
    login_success: "تم تسجيل الدخول",
    logout: "تسجيل الخروج",
    settings_updated: "تحديث الإعدادات",
    settings_reset: "إعادة ضبط الإعدادات",
    settings_imported: "استيراد الإعدادات",
    user_created: "إنشاء مستخدم",
    user_updated: "تحديث مستخدم",
    user_deactivated: "تعطيل مستخدم",
    user_password_reset: "إعادة تعيين كلمة المرور",
    classification_created: "إنشاء تصنيف",
    classification_updated: "تحديث تصنيف",
    classification_deleted: "حذف تصنيف",
    classification_reassigned: "إعادة إسناد تصنيف",
    index_rebuild_started: "بدء إعادة بناء الفهرس",
    admin_password_reset: "إعادة تعيين كلمة مرور المدير",
  },
  targets: {
    admin_user: "مستخدم",
    settings: "الإعدادات",
    classification: "تصنيف",
    search_index: "فهرس البحث",
  },
};

const errorMessages = [
  ["Request failed", "فشل الطلب."],
  ["Administrator authentication required.", "يلزم تسجيل دخول المسؤول."],
  ["Invalid administrator credentials.", "بيانات دخول المسؤول غير صحيحة."],
  ["Permission denied.", "ليست لديك صلاحية لتنفيذ هذا الإجراء."],
  ["Username is required.", "اسم المستخدم مطلوب."],
  ["Unsupported role.", "الدور المحدد غير مدعوم."],
  ["Username or email already exists.", "اسم المستخدم أو البريد الإلكتروني موجود مسبقاً."],
  ["At least one active super administrator is required.", "يجب أن يبقى مدير عام نشط واحد على الأقل."],
  ["You cannot deactivate your own account.", "لا يمكنك تعطيل حسابك الحالي."],
  ["Passwords do not match.", "كلمتا المرور غير متطابقتين."],
  ["Active user not found.", "لم يتم العثور على مستخدم نشط."],
  ["User not found.", "لم يتم العثور على المستخدم."],
  ["Arabic and English names are required.", "الاسم العربي والإنكليزي مطلوبان."],
  ["Classification was not found.", "لم يتم العثور على التصنيف."],
  ["No classifications are available to delete.", "لا توجد تصنيفات متاحة للحذف."],
];

function messageFor(message) {
  const found = errorMessages.find(([english]) => message.includes(english));
  if (found) return found[1];
  if (message.includes("Administrator password must contain")) {
    return message
      .replace("Administrator password must contain", "يجب أن تحتوي كلمة مرور المسؤول على")
      .replace("at least", "ما لا يقل عن")
      .replace("characters", "حرفاً")
      .replace("a number", "رقم")
      .replace("a symbol", "رمز خاص")
      .replace("an uppercase Latin letter", "حرف لاتيني كبير");
  }
  return message || "فشل الطلب.";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const problem = new Error(messageFor(payload.error?.detail || "Request failed"));
    problem.status = response.status;
    throw problem;
  }
  return payload;
}

export function createSettingsModule({ root, modalRoot, showToast, onAuthenticated = () => {} }) {
  let state;
  let dirty = false;
  let users = [];
  let roles = {};
  let ministries = [];
  let auditPage = 1;
  const auditPageSize = 5;
  const json = (method, body) => ({
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  function notify(message) {
    showToast(messageFor(message));
  }

  function applyAppearance() {
    applyLanguage("ar");
    // The automatic clock schedule and its manual toggle own the active theme.
    document.documentElement.dataset.scale = state.appearance.interface_scale;
    document.documentElement.dataset.primary = state.appearance.primary_color;
    const custom = state.appearance.primary_color === "custom" ? state.appearance.custom_primary_color : "";
    document.documentElement.style.setProperty("--custom-primary", custom || "#145a38");
  }

  function markDirty() {
    dirty = true;
    const banner = root.querySelector(".unsaved-banner");
    if (banner) banner.hidden = false;
  }

  function showLogin(loadSettingsAfterLogin = true) {
    modalRoot.innerHTML = `
      <div class="settings-modal-backdrop settings-login-backdrop">
        <form class="settings-modal settings-login-card" id="settings-login">
          <div class="settings-login-brand">
            <div class="settings-login-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M7.5 10V7.75a4.5 4.5 0 0 1 9 0V10"/>
                <rect x="5" y="10" width="14" height="10.5" rx="2.5"/>
                <path d="M12 14.25v2.25"/>
              </svg>
            </div>
            <div>
              <span>نظام إدارة القرارات</span>
              <h2>${t("login", "ar")}</h2>
            </div>
          </div>
          <p class="settings-login-intro">أدخل بيانات حسابك للوصول إلى النظام ومتابعة العمل.</p>
          <label class="settings-login-field">
            <span>${t("username", "ar")}</span>
            <span class="settings-login-input">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0"/></svg>
              <input name="username" required autocomplete="username" autofocus placeholder="أدخل اسم المستخدم">
            </span>
          </label>
          <label class="settings-login-field">
            <span>${t("password", "ar")}</span>
            <span class="settings-login-input">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10"/></svg>
              <input name="password" type="password" required autocomplete="current-password" placeholder="أدخل كلمة المرور">
              <button class="settings-password-toggle" type="button" aria-label="إظهار كلمة المرور">إظهار</button>
            </span>
          </label>
          <p class="field-error" role="alert"></p>
          <button class="primary-button settings-login-submit" type="submit">تسجيل الدخول</button>
          <p class="settings-login-note">الدخول مخصص للمستخدمين المخولين فقط</p>
        </form>
      </div>`;
    const form = modalRoot.querySelector("form");
    const password = form.elements.password;
    const toggle = form.querySelector(".settings-password-toggle");
    toggle.onclick = () => {
      const reveal = password.type === "password";
      password.type = reveal ? "text" : "password";
      toggle.textContent = reveal ? "إخفاء" : "إظهار";
      toggle.setAttribute("aria-label", reveal ? "إخفاء كلمة المرور" : "إظهار كلمة المرور");
    };
    form.onsubmit = async (event) => {
      event.preventDefault();
      const submit = event.currentTarget.querySelector(".settings-login-submit");
      submit.disabled = true;
      try {
        await api("/api/auth/login", json("POST", Object.fromEntries(new FormData(event.currentTarget))));
        await onAuthenticated();
        modalRoot.replaceChildren();
        if (loadSettingsAfterLogin) await load();
      } catch (error) {
        modalRoot.querySelector(".field-error").textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    };
  }

  function control(section, definition) {
    const [key, labelText, type = "text", options] = definition;
    const label = document.createElement("label");
    label.className = `settings-field ${type === "checkbox" ? "checkbox-field" : ""}`;
    const input = type === "select" ? document.createElement("select") : document.createElement("input");
    if (type !== "select") input.type = type;
    if (type === "number") {
      input.min = "1";
      input.step = "1";
    }
    if (type === "select") {
      options.forEach((value) => {
        const rawValue = value ?? "";
        input.add(new Option(labels.sessionOptions[String(rawValue)] || labels.fileSizeOptions[String(rawValue)] || String(value), rawValue));
      });
    }
    if (type === "checkbox") input.checked = Boolean(state[section][key]);
    else input.value = state[section][key] ?? "";
    label.append(input, Object.assign(document.createElement("span"), { textContent: labelText }));
    input.onchange = () => {
      const value = type === "checkbox"
        ? input.checked
        : type === "number"
          ? Number(input.value)
          : type === "select"
            ? options.find((option) => String(option ?? "") === input.value) ?? null
            : input.value || null;
      if (section === "authentication" && key === "login_enabled" && !value) {
        if (!confirm("تعطيل تسجيل الدخول يجعل النظام متاحاً لأي شخص يستطيع الوصول إلى الخادم. هل تريد المتابعة؟")) {
          input.checked = true;
          return;
        }
      }
      state[section][key] = value;
      markDirty();
    };
    return label;
  }

  function renderSecurity(grid) {
    const section = document.createElement("section");
    section.className = "settings-card full-width";
    section.innerHTML = `
      <h2>الوصول وسياسة كلمات المرور</h2>
      <p class="unsupported-note">تمت إزالة دخول الضيف. عند تفعيل تسجيل الدخول، لا يمكن استخدام المساعد أو الإعدادات إلا بعد تسجيل دخول مسؤول.</p>
      <div class="settings-fields"></div>`;
    const box = section.querySelector(".settings-fields");
    labels.authFields.forEach((definition) => box.append(control("authentication", definition)));
    grid.append(section);
  }

  function renderUploadSettings(grid) {
    const section = document.createElement("section");
    section.className = "settings-card full-width";
    section.innerHTML = `
      <h2>Upload Settings</h2>
      <p class="unsupported-note">These limits control the upload page message and client-side validation.</p>
      <div class="settings-fields"></div>`;
    const box = section.querySelector(".settings-fields");
    labels.uploadFields.forEach((definition) => box.append(control("upload", definition)));
    grid.append(section);
  }

  function roleLabel(role) {
    return labels.roles[role] || roles[role]?.label || role;
  }

  function roleOptions(selected) {
    const names = Object.keys(roles).length ? Object.keys(roles) : ["super_admin", "admin", "viewer"];
    return names.map((role) => `<option value="${escapeHtml(role)}" ${role === selected ? "selected" : ""}>${escapeHtml(roleLabel(role))}</option>`).join("");
  }

  function ministryOptions(selected) {
    return [
      `<option value="">بدون وزارة</option>`,
      ...ministries.map((ministry) => (
        `<option value="${escapeHtml(ministry)}" ${ministry === selected ? "selected" : ""}>${escapeHtml(ministry)}</option>`
      )),
    ].join("");
  }

  async function refreshUsers() {
    const body = root.querySelector("[data-users-body]");
    if (!body) return;
    try {
      const payload = await api("/api/settings/users");
      users = payload.items || [];
      roles = payload.roles || {};
      ministries = payload.ministries || [];
      body.innerHTML = users.map((user) => `
        <tr>
          <td>${escapeHtml(user.username)}</td>
          <td>${escapeHtml(user.display_name)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td>${escapeHtml(user.ministry || "")}</td>
          <td>${escapeHtml(roleLabel(user.role))}</td>
          <td>${user.is_active ? "نشط" : "معطل"}</td>
          <td class="settings-row-actions">
            <button type="button" data-edit-user="${user.id}">تعديل</button>
            <button type="button" data-reset-user="${user.id}">تغيير كلمة المرور</button>
            <button type="button" class="danger-button" data-delete-user="${user.id}" ${user.is_active ? "" : "disabled"}>تعطيل</button>
          </td>
        </tr>`).join("") || `<tr><td colspan="7">لا يوجد مستخدمون.</td></tr>`;
      body.querySelectorAll("[data-edit-user]").forEach((button) => {
        button.onclick = () => userForm(users.find((item) => item.id === Number(button.dataset.editUser)));
      });
      body.querySelectorAll("[data-reset-user]").forEach((button) => {
        button.onclick = () => passwordResetForm(Number(button.dataset.resetUser));
      });
      body.querySelectorAll("[data-delete-user]").forEach((button) => {
        button.onclick = () => deactivateUser(Number(button.dataset.deleteUser));
      });
    } catch (error) {
      body.innerHTML = `<tr><td colspan="7">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  async function refreshAudit(page = auditPage) {
    const body = root.querySelector("[data-audit-body]");
    const pagination = root.querySelector("[data-audit-pagination]");
    if (!body) return;
    try {
      const payload = await api(
        `/api/settings/audit-log?page=${page}&page_size=${auditPageSize}`,
      );
      const items = payload.items || [];
      auditPage = payload.page || 1;
      body.innerHTML = items.map((item) => `
        <tr>
          <td>${new Date(item.created_at).toLocaleString("ar-IQ")}</td>
          <td>${escapeHtml(item.actor_username)}</td>
          <td>${escapeHtml(labels.actions[item.action] || item.action)}</td>
          <td>${escapeHtml(labels.targets[item.target_type] || item.target_type || "")} ${escapeHtml(item.target_id)}</td>
        </tr>`).join("") || `<tr><td colspan="4">لا توجد أحداث تدقيق بعد.</td></tr>`;
      if (pagination) {
        const previous = pagination.querySelector("[data-audit-previous]");
        const next = pagination.querySelector("[data-audit-next]");
        pagination.querySelector("[data-audit-page]").textContent =
          `الصفحة ${auditPage} من ${payload.total_pages || 1} · ${payload.total || 0} سجل`;
        previous.disabled = auditPage <= 1;
        next.disabled = auditPage >= (payload.total_pages || 1);
      }
    } catch (error) {
      body.innerHTML = `<tr><td colspan="4">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  function userForm(item = {}) {
    const isEdit = Boolean(item?.id);
    modalRoot.innerHTML = `
      <div class="settings-modal-backdrop">
        <form class="settings-modal">
          <h2>${isEdit ? "تعديل مستخدم" : "إضافة مستخدم"}</h2>
          <label>اسم المستخدم<input name="username" required ${isEdit ? "disabled" : ""}></label>
          <label>الاسم الظاهر<input name="display_name"></label>
          <label>البريد الإلكتروني<input name="email" type="email"></label>
          <label>الوزارة<select name="ministry">${ministryOptions(item.ministry || "")}</select></label>
          <label>الدور<select name="role">${roleOptions(item.role || "viewer")}</select></label>
          <label><input name="is_active" type="checkbox"> نشط</label>
          ${isEdit ? "" : "<label>كلمة المرور الأولية<input name=\"password\" type=\"password\" required></label>"}
          <p class="field-error"></p>
          <button class="primary-button">حفظ</button>
          <button type="button" data-cancel>إلغاء</button>
        </form>
      </div>`;
    const form = modalRoot.querySelector("form");
    ["username", "display_name", "email", "ministry"].forEach((key) => {
      if (form.elements[key]) form.elements[key].value = item[key] || "";
    });
    form.elements.is_active.checked = item.is_active ?? true;
    form.querySelector("[data-cancel]").onclick = () => modalRoot.replaceChildren();
    form.onsubmit = async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      data.is_active = form.elements.is_active.checked;
      try {
        await api(isEdit ? `/api/settings/users/${item.id}` : "/api/settings/users", json(isEdit ? "PUT" : "POST", data));
        modalRoot.replaceChildren();
        notify(isEdit ? "تم تحديث المستخدم." : "تم إنشاء المستخدم.");
        await refreshUsers();
        await refreshAudit();
      } catch (error) {
        form.querySelector(".field-error").textContent = error.message;
      }
    };
  }

  function passwordResetForm(userId) {
    const user = users.find((item) => item.id === userId);
    modalRoot.innerHTML = `
      <div class="settings-modal-backdrop">
        <form class="settings-modal">
          <h2>تغيير كلمة المرور</h2>
          <p class="unsupported-note">${escapeHtml(user?.username || "المستخدم المحدد")}</p>
          <label>كلمة المرور الجديدة<input name="password" type="password" required></label>
          <label>تأكيد كلمة المرور<input name="confirmation" type="password" required></label>
          <p class="field-error"></p>
          <button class="primary-button">تغيير كلمة المرور</button>
          <button type="button" data-cancel>إلغاء</button>
        </form>
      </div>`;
    const form = modalRoot.querySelector("form");
    form.querySelector("[data-cancel]").onclick = () => modalRoot.replaceChildren();
    form.onsubmit = async (event) => {
      event.preventDefault();
      if (form.elements.password.value !== form.elements.confirmation.value) {
        form.querySelector(".field-error").textContent = "كلمتا المرور غير متطابقتين.";
        return;
      }
      try {
        await api(`/api/settings/users/${userId}/password`, json("POST", { password: form.elements.password.value }));
        modalRoot.replaceChildren();
        notify("تم تغيير كلمة المرور.");
        await refreshAudit();
      } catch (error) {
        form.querySelector(".field-error").textContent = error.message;
      }
    };
  }

  async function deactivateUser(userId) {
    const user = users.find((item) => item.id === userId);
    if (!confirm(`هل تريد تعطيل المستخدم "${user?.username || userId}"؟`)) return;
    try {
      await api(`/api/settings/users/${userId}`, { method: "DELETE" });
      notify("تم تعطيل المستخدم.");
      await refreshUsers();
      await refreshAudit();
    } catch (error) {
      notify(error.message);
    }
  }

  function renderUsers(grid) {
    const section = document.createElement("section");
    section.className = "settings-card full-width";
    section.innerHTML = `
      <div class="fine-card-header">
        <h2>إدارة المستخدمين</h2>
        <button type="button" class="primary-button" data-add-user>إضافة مستخدم</button>
      </div>
      <div class="settings-table-wrap">
        <table class="settings-table">
          <thead><tr><th>اسم المستخدم</th><th>الاسم</th><th>البريد</th><th>الوزارة</th><th>الدور</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
          <tbody data-users-body><tr><td colspan="7">جاري تحميل المستخدمين...</td></tr></tbody>
        </table>
      </div>`;
    grid.append(section);
    section.querySelector("[data-add-user]").onclick = () => userForm();
    refreshUsers();
  }

  function renderAuditLog(grid) {
    const section = document.createElement("section");
    section.className = "settings-card full-width";
    section.innerHTML = `
      <h2>سجل التدقيق</h2>
      <div class="settings-table-wrap">
        <table class="settings-table">
          <thead><tr><th>الوقت</th><th>الفاعل</th><th>الإجراء</th><th>الهدف</th></tr></thead>
          <tbody data-audit-body><tr><td colspan="4">جاري تحميل سجل التدقيق...</td></tr></tbody>
        </table>
      </div>
      <div class="audit-pagination" data-audit-pagination>
        <button type="button" data-audit-previous>السابق</button>
        <span data-audit-page>الصفحة 1</span>
        <button type="button" data-audit-next>التالي</button>
      </div>`;
    grid.append(section);
    section.querySelector("[data-audit-previous]").onclick = () => {
      if (auditPage > 1) refreshAudit(auditPage - 1);
    };
    section.querySelector("[data-audit-next]").onclick = () => {
      refreshAudit(auditPage + 1);
    };
    refreshAudit();
  }

  async function deleteClassificationPrompt() {
    const { items } = await api("/api/settings/classifications");
    if (!items.length) {
      notify("لا توجد تصنيفات متاحة للحذف.");
      return;
    }
    const value = prompt("أدخل رقم التصنيف أو اسمه العربي أو الإنكليزي لحذفه:");
    if (!value) return;
    const normalized = value.trim().toLowerCase();
    const item = items.find((candidate) => (
      String(candidate.id) === normalized
      || String(candidate.name_ar || "").trim().toLowerCase() === normalized
      || String(candidate.name_en || "").trim().toLowerCase() === normalized
    ));
    if (!item) {
      notify("لم يتم العثور على التصنيف.");
      return;
    }
    if (!confirm(`هل تريد حذف التصنيف "${item.name_ar || item.name_en}"؟`)) return;
    try {
      await api(`/api/settings/classifications/${item.id}`, { method: "DELETE" });
      notify("تم حذف التصنيف.");
    } catch (error) {
      notify(error.message);
    }
  }

  function classificationForm(item = {}) {
    modalRoot.innerHTML = `
      <div class="settings-modal-backdrop">
        <form class="settings-modal">
          <h2>${item.id ? "تعديل التصنيف" : "إضافة تصنيف"}</h2>
          <label>الاسم العربي<input name="name_ar" required></label>
          <label>الاسم الإنكليزي<input name="name_en" required></label>
          <label>الوصف<textarea name="description"></textarea></label>
          <label>الأيقونة<input name="icon_identifier"></label>
          <label>اللون<input name="color" type="color"></label>
          <label>الترتيب<input name="display_order" type="number"></label>
          <label><input name="enabled" type="checkbox"> مفعّل</label>
          <p class="field-error"></p>
          <button class="primary-button">حفظ</button>
          <button type="button" data-cancel>إلغاء</button>
        </form>
      </div>`;
    const form = modalRoot.querySelector("form");
    ["name_ar", "name_en", "description", "icon_identifier", "color", "display_order"].forEach((key) => {
      form.elements[key].value = item[key] ?? (key === "color" ? "#145a38" : "");
    });
    form.elements.enabled.checked = item.enabled ?? true;
    form.querySelector("[data-cancel]").onclick = () => modalRoot.replaceChildren();
    form.onsubmit = async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      data.enabled = form.elements.enabled.checked;
      data.display_order = Number(data.display_order);
      try {
        await api(item.id ? `/api/settings/classifications/${item.id}` : "/api/settings/classifications", json(item.id ? "PUT" : "POST", data));
        modalRoot.replaceChildren();
        notify("تم حفظ التصنيف.");
      } catch (error) {
        form.querySelector(".field-error").textContent = error.message;
      }
    };
  }

  function renderFineTuning(grid, language) {
    const section = document.createElement("section");
    section.className = "fine-tuning-stack full-width";
    section.innerHTML = `
      <section class="settings-card fine-card">
        <div class="fine-card-title"><span class="settings-card-icon" aria-hidden="true">&#9881;</span><h2>الضبط الدقيق</h2></div>
        <div class="fine-row"><span>النموذج الأساسي</span><select data-ft-model></select></div>
        <div class="fine-row"><span>حد التحقق</span><div class="range-control"><input data-ft-validation type="range" min="0" max="1" step="0.01"><strong data-ft-validation-label></strong></div></div>
      </section>
      <section class="settings-card fine-card">
        <div class="fine-card-header">
          <div class="fine-card-title"><span class="settings-card-icon" aria-hidden="true">&#9719;</span><h2>إعادة التدريب المجدولة</h2></div>
          <span class="run-status">مجدول</span>
        </div>
        <div class="fine-row"><span>وقت البدء</span><input data-ft-time type="time"></div>
        <button type="button" data-run-now>تشغيل الآن</button>
      </section>
      <section class="settings-card fine-card">
        <div class="fine-card-title"><span class="settings-card-icon" aria-hidden="true">&#8644;</span><h2>نمط التعلم</h2></div>
        <div class="segmented-control">
          <button type="button" data-mode="manual">يدوي</button>
          <button type="button" data-mode="automatic">تلقائي</button>
        </div>
        <p class="fine-help" data-mode-help></p>
      </section>
      <section class="settings-card fine-card">
        <div class="fine-card-header">
          <div class="fine-card-title"><span class="settings-card-icon" aria-hidden="true">&#9638;</span><h2>${t("classifications", language)}</h2></div>
          <div class="classification-actions"><button type="button" data-add>إضافة تصنيف</button><button type="button" class="danger-button" data-delete-category>حذف تصنيف</button></div>
        </div>
      </section>
      `;

    const modelSelect = section.querySelector("[data-ft-model]");
    [state.model.chat_model, "qwen2.5:3b", "qwen2.5:7b"].filter(Boolean).forEach((model) => {
      if (![...modelSelect.options].some((option) => option.value === model)) {
        modelSelect.add(new Option(model, model));
      }
    });
    modelSelect.value = state.model.chat_model;
    modelSelect.onchange = () => { state.model.chat_model = modelSelect.value; markDirty(); };

    const validation = section.querySelector("[data-ft-validation]");
    const validationLabel = section.querySelector("[data-ft-validation-label]");
    const updateValidationLabel = () => { validationLabel.textContent = `${Math.round(Number(validation.value) * 100)}%`; };
    validation.value = state.fine_tuning.validation_threshold;
    updateValidationLabel();
    validation.oninput = updateValidationLabel;
    validation.onchange = () => { state.fine_tuning.validation_threshold = Number(validation.value); markDirty(); };

    section.querySelector("[data-ft-time]").value = state.fine_tuning.scheduled_start_time || "02:00";
    section.querySelector("[data-ft-time]").onchange = (event) => {
      state.fine_tuning.scheduled_start_time = event.currentTarget.value;
      markDirty();
    };

    const modeButtons = section.querySelectorAll("[data-mode]");
    const help = section.querySelector("[data-mode-help]");
    const syncMode = () => {
      modeButtons.forEach((button) => button.classList.toggle("active", button.dataset.mode === state.fine_tuning.learning_mode));
      help.textContent = state.fine_tuning.learning_mode === "manual"
        ? "النمط اليدوي يضع البيانات الجديدة في انتظار مراجعة المسؤول قبل إدخالها في النموذج."
        : "النمط التلقائي يعتمد البيانات فقط عندما تتجاوز درجة الثقة الحد المحدد.";
    };
    modeButtons.forEach((button) => {
      button.onclick = () => {
        state.fine_tuning.learning_mode = button.dataset.mode;
        syncMode();
        markDirty();
      };
    });
    syncMode();

    section.querySelector("[data-run-now]").onclick = () => notify("مشغّل الضبط الدقيق اليدوي غير مربوط بواجهة API حالياً.");
    grid.append(section);
  }

  function render() {
    const language = "ar";
    root.innerHTML = `
      <header class="settings-header">
        <div><h1>الإعدادات</h1><p>إدارة النظام والمستخدمين وإعدادات التشغيل</p></div>
        <div><button data-reset>إعادة الضبط</button><button class="primary-button" data-save>حفظ التغييرات</button></div>
      </header>
      <div class="unsaved-banner" ${dirty ? "" : "hidden"}>لديك تغييرات غير محفوظة</div>
      <div class="settings-grid"></div>`;
    const grid = root.querySelector(".settings-grid");
    renderSecurity(grid);
    renderUploadSettings(grid);
    renderUsers(grid);
    renderAuditLog(grid);
    renderFineTuning(grid, language);

    root.querySelector("[data-save]").onclick = async () => {
      try {
        const body = {
          authentication: state.authentication,
          upload: state.upload,
          model: { chat_model: state.model.chat_model },
          fine_tuning: state.fine_tuning,
        };
        state = await api("/api/settings", json("PUT", body));
        dirty = false;
        applyAppearance();
        render();
        notify("تم حفظ الإعدادات بنجاح.");
      } catch (error) {
        notify(error.message);
      }
    };
    root.querySelector("[data-reset]").onclick = async () => {
      if (confirm("هل تريد إعادة الإعدادات إلى القيم الافتراضية؟")) {
        state = await api("/api/settings/reset", { method: "POST" });
        dirty = false;
        applyAppearance();
        render();
      }
    };
    root.querySelector("[data-add]").onclick = () => classificationForm();
    root.querySelector("[data-delete-category]").onclick = () => deleteClassificationPrompt();
  }

  async function load() {
    try {
      state = await api("/api/settings");
      applyAppearance();
      render();
    } catch (error) {
      if (error.status === 401) showLogin();
      else root.innerHTML = `<p class="settings-error">${escapeHtml(error.message)}</p>`;
    }
  }

  return {
    open: load,
    requireLogin() {
      showLogin(false);
    },
  };
}
