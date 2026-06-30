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
