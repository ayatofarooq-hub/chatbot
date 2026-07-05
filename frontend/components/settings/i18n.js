const dictionary = {
  ar: {
    settings: "الإعدادات",
    save: "حفظ التغييرات",
    reset: "إعادة الضبط",
    login: "دخول المسؤول",
    username: "اسم المستخدم",
    password: "كلمة المرور",
    saved: "تم حفظ الإعدادات بنجاح.",
    unsaved: "لديك تغييرات غير محفوظة",
    classifications: "تصنيفات الوثائق القانونية",
    add: "إضافة",
    cancel: "إلغاء",
    export: "تصدير المحادثة",
    exportAs: "تصدير باسم",
    exportMarkdown: "تنسيق Markdown",
    exportText: "نص عادي",
    exporting: "جارٍ التصدير...",
    exportSuccess: "تم تصدير المحادثة بنجاح.",
    exportError: "فشل تصدير المحادثة.",
    exportEmpty: "لا توجد رسائل للتصدير.",
    filter: "تصفية",
  },
  en: {
    settings: "Settings",
    save: "Save changes",
    reset: "Reset",
    login: "Administrator login",
    username: "Username",
    password: "Password",
    saved: "Settings saved successfully.",
    unsaved: "You have unsaved changes",
    classifications: "Legal document classifications",
    add: "Add",
    cancel: "Cancel",
    export: "Export chat",
    exportAs: "Export as",
    exportMarkdown: "Markdown",
    exportText: "Plain text",
    exporting: "Exporting...",
    exportSuccess: "Chat exported successfully.",
    exportError: "Failed to export chat.",
    exportEmpty: "No messages to export.",
    filter: "Filter",
  },
};

export function t(key, language = document.documentElement.lang || "ar") {
  return dictionary[language]?.[key] || dictionary.ar[key] || dictionary.en[key] || key;
}

export function applyLanguage(language) {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  localStorage.setItem("legal-ui-language", language);
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n, language);
  });
}
