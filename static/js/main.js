/* ==========================================================================
   BUSGO — Global interactions
   ========================================================================== */
(function () {
  "use strict";

  const onReady = (fn) => {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  };

  onReady(function () {
    // Sticky header shadow
    const header = document.getElementById("siteHeader");
    const backTop = document.getElementById("backToTop");
    const onScroll = () => {
      const y = window.scrollY || window.pageYOffset;
      if (header) header.classList.toggle("scrolled", y > 12);
      if (backTop) backTop.classList.toggle("show", y > 500);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    if (backTop) {
      backTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    }

    // Auto-dismiss flash messages
    document.querySelectorAll(".alert.alert-dismissible").forEach((alert) => {
      window.setTimeout(() => {
        if (window.bootstrap && bootstrap.Alert) bootstrap.Alert.getOrCreateInstance(alert).close();
        else alert.remove();
      }, 8000);
    });

    // Scroll reveal
    const reveals = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
      );
      reveals.forEach((el) => observer.observe(el));
    } else {
      reveals.forEach((el) => el.classList.add("visible"));
    }

    // Animated counters
    const counters = document.querySelectorAll("[data-count]");
    if (counters.length && "IntersectionObserver" in window) {
      const counterObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const el = entry.target;
            const target = parseInt(el.dataset.count, 10) || 0;
            const suffix = el.dataset.suffix || "";
            const duration = 1200;
            const start = performance.now();
            const tick = (now) => {
              const progress = Math.min((now - start) / duration, 1);
              const eased = 1 - Math.pow(1 - progress, 3);
              el.textContent = Math.round(target * eased).toLocaleString("en-IN") + suffix;
              if (progress < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
            counterObserver.unobserve(el);
          });
        },
        { threshold: 0.4 }
      );
      counters.forEach((el) => counterObserver.observe(el));
    }

    // Password visibility toggles
    document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = document.querySelector(btn.dataset.togglePassword);
        if (!target) return;
        const showing = target.type === "text";
        target.type = showing ? "password" : "text";
        const icon = btn.querySelector("i");
        if (icon) {
          icon.classList.toggle("fa-eye", showing);
          icon.classList.toggle("fa-eye-slash", !showing);
        }
        btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      });
    });

    // Minimum date for journey pickers
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
      today.getDate()
    ).padStart(2, "0")}`;
    document.querySelectorAll('input[type="date"][data-min-today]').forEach((input) => {
      input.min = iso;
      if (!input.value) input.value = iso;
    });

    // Swap source / destination
    document.querySelectorAll("[data-swap]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const form = btn.closest("form");
        if (!form) return;
        const from = form.querySelector('[name="from"]');
        const to = form.querySelector('[name="to"]');
        if (!from || !to) return;
        const tmp = from.value;
        from.value = to.value;
        to.value = tmp;
        from.focus();
      });
    });

    // Copy offer codes
    document.querySelectorAll("[data-copy]").forEach((el) => {
      el.addEventListener("click", async (event) => {
        event.preventDefault();
        const code = el.dataset.copy;
        try {
          await navigator.clipboard.writeText(code);
          const original = el.innerHTML;
          el.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
          window.setTimeout(() => (el.innerHTML = original), 1800);
        } catch (err) {
          window.prompt("Copy this promo code:", code);
        }
      });
    });

    // Search filter panel toggle (mobile)
    const filterToggle = document.getElementById("filterToggle");
    const filterCard = document.getElementById("filterCard");
    if (filterToggle && filterCard) {
      filterToggle.addEventListener("click", () => filterCard.classList.toggle("show"));
    }

    // Auto submit selects
    document.querySelectorAll("[data-auto-submit]").forEach((el) => {
      el.addEventListener("change", () => {
        const form = el.closest("form");
        if (form) form.submit();
      });
    });

    // Print
    document.querySelectorAll("[data-print]").forEach((btn) => {
      btn.addEventListener("click", () => window.print());
    });

    // Confirm destructive actions
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
      });
    });

    // Bootstrap tooltips
    if (window.bootstrap && bootstrap.Tooltip) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
    }

    // Prevent accidental double submission of plain forms
    document.querySelectorAll("form[data-submit-once]").forEach((form) => {
      form.addEventListener("submit", () => {
        const btn = form.querySelector('button[type="submit"]');
        if (btn) {
          window.setTimeout(() => {
            btn.disabled = true;
            btn.classList.add("disabled");
          }, 10);
        }
      });
    });
  });
})();
