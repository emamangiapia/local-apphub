/* Appearance preference, stored only in this browser and applied before paint. */
(function () {
  "use strict";
  var preferenceKey = "local-apphub-theme";
  var theme = "retro";
  try {
    if (localStorage.getItem(preferenceKey) === "liquid") theme = "liquid";
  } catch (_) { /* Private browsing may disable local storage. */ }

  function applyTheme(choice, save) {
    theme = choice === "liquid" ? "liquid" : "retro";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === "liquid" ? "light" : "dark";
    var themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute("content", theme === "liquid" ? "#e8effa" : "#11142a");
    if (save) {
      try { localStorage.setItem(preferenceKey, theme); }
      catch (_) { /* The choice still works for this page. */ }
    }
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      var selected = button.dataset.themeChoice === theme;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("selected", selected);
    });
  }

  applyTheme(theme, false);
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        applyTheme(button.dataset.themeChoice, true);
      });
    });
    applyTheme(theme, false);
  });
})();
