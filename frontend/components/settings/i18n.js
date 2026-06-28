const dictionary = {
  ar: {
    settings: "الإعدادات", save: "حفظ التغييرات", reset: "إعادة الضبط",
    login: "دخول المسؤول", username: "اسم المستخدم", password: "كلمة المرور",
    saved: "تم حفظ الإعدادات بنجاح", unsaved: "لديك تغييرات غير محفوظة",
    model: "الذكاء الاصطناعي وOllama", retrieval: "البحث ومعالجة الوثائق",
    authentication: "المصادقة والوصول", appearance: "اللغة والمظهر",
    upload: "إعدادات الرفع", notifications: "الإشعارات",
    backup: "النسخ الاحتياطي والاستعادة", classifications: "تصنيفات الوثائق القانونية",
    fineTuning: "الضبط الدقيق", notConfigured: "غير مهيأ",
    test: "اختبار الاتصال", rebuild: "إعادة بناء فهرس البحث",
    export: "تصدير JSON", import: "استيراد JSON", add: "إضافة تصنيف",
  },
  en: {
    settings: "Settings", save: "Save Changes", reset: "Reset",
    login: "Administrator login", username: "Username", password: "Password",
    saved: "Settings saved successfully.", unsaved: "You have unsaved changes",
    model: "AI and Ollama", retrieval: "Retrieval and document processing",
    authentication: "Authentication and access", appearance: "Language and appearance",
    upload: "Upload settings", notifications: "Notifications",
    backup: "Backup and restore", classifications: "Legal document classifications",
    fineTuning: "Fine-tuning", notConfigured: "Not configured",
    test: "Test connection", rebuild: "Rebuild search index",
    export: "Export JSON", import: "Import JSON", add: "Add classification",
  },
};

export function t(key, language = document.documentElement.lang || "ar") {
  return dictionary[language]?.[key] || dictionary.en[key] || key;
}

export function applyLanguage(language) {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  localStorage.setItem("legal-ui-language", language);
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n, language);
  });
}
