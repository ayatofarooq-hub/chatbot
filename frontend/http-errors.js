export const HTTP_ERROR_MESSAGES = Object.freeze({
  400: "الطلب غير صحيح. يُرجى مراجعة البيانات المدخلة.",
  401: "يُرجى تسجيل الدخول للمتابعة.",
  403: "ليس لديك صلاحية لتنفيذ هذا الإجراء.",
  404: "العنصر المطلوب غير موجود.",
  408: "انتهت مهلة الطلب. يُرجى المحاولة مرة أخرى.",
  409: "تعذّر إكمال العملية بسبب تعارض في البيانات.",
  422: "بعض البيانات المدخلة غير صحيحة. يُرجى مراجعتها.",
  429: "أُرسلت طلبات كثيرة. يُرجى الانتظار قليلًا.",
  500: "حدث خطأ غير متوقع. يُرجى المحاولة لاحقًا.",
  502: "الخدمة غير متاحة مؤقتًا. يُرجى المحاولة لاحقًا.",
  503: "الخدمة غير متاحة حاليًا. يُرجى المحاولة لاحقًا.",
  504: "تأخرت استجابة الخادم. يُرجى المحاولة مرة أخرى.",
});

export function httpErrorMessage(status, payload = {}, fallback = "تعذّر إكمال الطلب.") {
  const mappedMessage = HTTP_ERROR_MESSAGES[Number(status)];
  if (mappedMessage) return mappedMessage;

  const detail = payload?.detail ?? payload?.error?.detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return fallback;
}
