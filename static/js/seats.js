/* ==========================================================================
   BUSGO — Interactive seat selection
   ========================================================================== */
(function () {
  "use strict";

  const root = document.getElementById("seatSelection");
  if (!root) return;

  const maxSeats = parseInt(root.dataset.maxSeats, 10) || 6;
  const feePerSeat = parseFloat(root.dataset.fee) || 0;
  const gstPercent = parseFloat(root.dataset.gst) || 0;
  const totalSeats = parseInt(root.dataset.totalCount, 10) || 0;
  const bookedSeats = parseInt(root.dataset.bookedCount, 10) || 0;
  const preselectedIds = (root.dataset.preselect || "").split(",").filter(Boolean);

  const form = document.getElementById("seatForm");
  const hiddenWrap = document.getElementById("seatHiddenInputs");
  const chipsWrap = document.getElementById("selectedSeatChips");
  const errorBox = document.getElementById("seatError");
  const continueBtn = document.getElementById("continueBtn");
  const seatCountEls = document.querySelectorAll("[data-selected-count]");
  const subtotalEls = document.querySelectorAll("[data-subtotal]");
  const feeEls = document.querySelectorAll("[data-fee]");
  const gstEls = document.querySelectorAll("[data-gst]");
  const totalEls = document.querySelectorAll("[data-total]");
  const availableEls = document.querySelectorAll("[data-available-count]");
  const bookedEls = document.querySelectorAll("[data-booked-count]");

  const selected = new Map();
  const inr = (value) =>
    "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.classList.add("show");
  }
  function hideError() {
    if (errorBox) errorBox.classList.remove("show");
  }

  function recalc() {
    let subtotal = 0;
    selected.forEach((seat) => (subtotal += seat.price));
    const count = selected.size;
    const fee = feePerSeat * count;
    const gst = Math.round(subtotal * (gstPercent / 100) * 100) / 100;
    const total = subtotal + fee + gst;

    seatCountEls.forEach((el) => (el.textContent = count));
    subtotalEls.forEach((el) => (el.textContent = inr(subtotal)));
    feeEls.forEach((el) => (el.textContent = inr(fee)));
    gstEls.forEach((el) => (el.textContent = inr(gst)));
    totalEls.forEach((el) => (el.textContent = inr(total)));

    availableEls.forEach((el) => {
      el.textContent = Math.max(totalSeats - bookedSeats - count, 0);
    });
    bookedEls.forEach((el) => (el.textContent = bookedSeats));

    if (continueBtn) {
      continueBtn.disabled = count === 0;
      continueBtn.classList.toggle("disabled", count === 0);
    }

    renderChips();
    renderHidden();
  }

  function renderChips() {
    if (!chipsWrap) return;
    if (selected.size === 0) {
      chipsWrap.innerHTML = '<span class="empty-selection">No seats selected yet — pick your favourites from the map.</span>';
      return;
    }
    chipsWrap.innerHTML = "";
    selected.forEach((seat) => {
      const chip = document.createElement("span");
      chip.className = "selected-seat-chip";
      chip.innerHTML = `${seat.number} <button type="button" aria-label="Remove seat ${seat.number}"><i class="fa-solid fa-xmark"></i></button>`;
      chip.querySelector("button").addEventListener("click", () => {
        seat.el.classList.remove("selected");
        seat.el.setAttribute("aria-pressed", "false");
        selected.delete(seat.id);
        hideError();
        recalc();
      });
      chipsWrap.appendChild(chip);
    });
  }

  function renderHidden() {
    if (!hiddenWrap) return;
    hiddenWrap.innerHTML = "";
    selected.forEach((seat) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "seat_ids";
      input.value = seat.id;
      hiddenWrap.appendChild(input);
    });
  }

  function addSeat(btn) {
    const id = btn.dataset.seatId;
    if (selected.has(id) || btn.disabled || btn.classList.contains("booked")) return;
    if (selected.size >= maxSeats) {
      showError(`You can select a maximum of ${maxSeats} seats per booking.`);
      return;
    }
    selected.set(id, {
      id,
      number: btn.dataset.number,
      price: parseFloat(btn.dataset.price) || 0,
      el: btn,
    });
    btn.classList.add("selected");
    btn.setAttribute("aria-pressed", "true");
    hideError();
  }

  document.querySelectorAll(".seat[data-seat-id]").forEach((btn) => {
    if (btn.disabled || btn.classList.contains("booked") || btn.classList.contains("blocked")) return;
    btn.addEventListener("click", () => {
      const id = btn.dataset.seatId;
      if (selected.has(id)) {
        selected.delete(id);
        btn.classList.remove("selected");
        btn.setAttribute("aria-pressed", "false");
        hideError();
        recalc();
        return;
      }
      addSeat(btn);
      recalc();
    });
  });

  // Restore seats after the traveller used "Back to seats".
  preselectedIds.forEach((id) => {
    const btn = document.querySelector(`.seat[data-seat-id="${id}"]`);
    if (btn) addSeat(btn);
  });

  // Deck tabs
  document.querySelectorAll("[data-deck-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const deck = tab.dataset.deckTab;
      document.querySelectorAll("[data-deck-tab]").forEach((t) => t.classList.toggle("active", t === tab));
      document.querySelectorAll("[data-deck-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.deckPanel === deck);
      });
    });
  });

  if (form) {
    form.addEventListener("submit", (event) => {
      if (selected.size === 0) {
        event.preventDefault();
        showError("Please select at least one seat before continuing.");
        return;
      }
      const btn = continueBtn;
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Holding seats...';
      }
    });
  }

  recalc();
})();
