(() => {
  const root = document.documentElement;
  const overrideKey = "iraqi-legal-theme-override";
  let boundaryTimer = 0;

  function scheduledTheme(date = new Date()) {
    const hour = date.getHours();
    return hour >= 16 || hour < 6 ? "dark" : "light";
  }

  function nextBoundary(date = new Date()) {
    const boundary = new Date(date);
    boundary.setSeconds(0, 0);
    if (date.getHours() < 6) {
      boundary.setHours(6, 0, 0, 0);
    } else if (date.getHours() < 16) {
      boundary.setHours(16, 0, 0, 0);
    } else {
      boundary.setDate(boundary.getDate() + 1);
      boundary.setHours(6, 0, 0, 0);
    }
    return boundary;
  }

  function readOverride(now = Date.now()) {
    try {
      const saved = JSON.parse(localStorage.getItem(overrideKey) || "null");
      if (saved && ["light", "dark"].includes(saved.theme) && saved.expiresAt > now) {
        return saved;
      }
      localStorage.removeItem(overrideKey);
    } catch (_error) {
      localStorage.removeItem(overrideKey);
    }
    return null;
  }

  function updateButton(theme) {
    const button = document.querySelector("#theme-toggle");
    if (!button) return;
    const isDark = theme === "dark";
    button.textContent = isDark ? "☀" : "☾";
    button.setAttribute("aria-label", isDark ? "تفعيل الوضع النهاري" : "تفعيل الوضع الليلي");
    button.title = isDark ? "الوضع النهاري" : "الوضع الليلي";
    button.setAttribute("aria-pressed", String(isDark));
  }

  function applyTheme() {
    const manual = readOverride();
    const theme = manual?.theme || scheduledTheme();
    root.dataset.theme = theme;
    root.dataset.themeSource = manual ? "manual" : "schedule";
    updateButton(theme);
  }

  function scheduleNextChange() {
    window.clearTimeout(boundaryTimer);
    const delay = Math.max(1000, nextBoundary().getTime() - Date.now() + 250);
    boundaryTimer = window.setTimeout(() => {
      localStorage.removeItem(overrideKey);
      applyTheme();
      scheduleNextChange();
    }, delay);
  }

  function toggleTheme() {
    const theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(overrideKey, JSON.stringify({
      theme,
      expiresAt: nextBoundary().getTime(),
    }));
    applyTheme();
  }

  applyTheme();
  scheduleNextChange();
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("#theme-toggle")?.addEventListener("click", toggleTheme);
    updateButton(root.dataset.theme);
  });
  window.addEventListener("storage", applyTheme);
  window.addEventListener("pagehide", () => window.clearTimeout(boundaryTimer), { once: true });
})();
