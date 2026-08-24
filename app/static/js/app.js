document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("themeToggle");
  const html = document.documentElement;

  if (toggle) {
    const applyIcon = (theme) => {
      toggle.innerHTML = theme === "dark"
        ? '<i class="bi bi-sun"></i>'
        : '<i class="bi bi-moon-stars"></i>';
    };
    applyIcon(html.getAttribute("data-bs-theme"));
    toggle.addEventListener("click", function () {
      const current = html.getAttribute("data-bs-theme");
      const next = current === "dark" ? "light" : "dark";
      html.setAttribute("data-bs-theme", next);
      applyIcon(next);
      try { localStorage.setItem("lt-theme", next); } catch (e) {}
    });
  }

  // Auto-dismiss alerts after 6 seconds
  document.querySelectorAll(".alert").forEach(function (alertEl) {
    setTimeout(function () {
      const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
      alert.close();
    }, 6000);
  });

  // Notification badge polling (works for both header bell and bottom-nav dot)
  const notifTargets = document.querySelectorAll("[data-notif-badge]");
  if (notifTargets.length) {
    function refreshNotifCount() {
      fetch("/api/notifications/unread-count")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          notifTargets.forEach(function (el) {
            if (data.count > 0) {
              el.textContent = data.count > 99 ? "99+" : data.count;
              el.classList.add("has-count");
              el.style.display = "flex";
            } else {
              el.classList.remove("has-count");
              el.style.display = "none";
            }
          });
        })
        .catch(function () {});
    }
    refreshNotifCount();
    let notifTimer = null;
    function scheduleNotif() {
      if (notifTimer) clearTimeout(notifTimer);
      notifTimer = setTimeout(function () {
        if (!document.hidden) refreshNotifCount();
        scheduleNotif();
      }, document.hidden ? 30000 : 30000);
    }
    scheduleNotif();
  }

  // Highlight the active bottom-nav item based on current path
  const bnItems = document.querySelectorAll(".bottom-nav .bn-item[data-path]");
  const path = window.location.pathname;
  bnItems.forEach(function (item) {
    const target = item.getAttribute("data-path");
    if (target === "/" ? path === "/" : path.startsWith(target)) {
      item.classList.add("active");
    }
  });

  initPwaInstall();
  registerServiceWorker();
});

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

// -------------------- PWA: service worker --------------------
function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function () {
      // Silently ignore — app works fully without offline support too.
    });
  });
}

// -------------------- PWA: "Add to Home Screen" prompt --------------------
function initPwaInstall() {
  const banner = document.getElementById("installBanner");
  if (!banner) return;
  const installBtn = document.getElementById("installBannerBtn");
  const dismissBtn = document.getElementById("installBannerDismiss");
  let deferredPrompt = null;

  try {
    if (localStorage.getItem("lt-install-dismissed") === "1") return;
  } catch (e) {}

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    banner.classList.add("show");
  });

  if (installBtn) {
    installBtn.addEventListener("click", function () {
      banner.classList.remove("show");
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () {
        deferredPrompt = null;
      });
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener("click", function () {
      banner.classList.remove("show");
      try { localStorage.setItem("lt-install-dismissed", "1"); } catch (e) {}
    });
  }

  window.addEventListener("appinstalled", function () {
    banner.classList.remove("show");
  });
}
