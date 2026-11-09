/* ==========================================================================
   BUSGO — Admin dashboard interactions & charts
   ========================================================================== */
(function () {
  "use strict";

  const onReady = (fn) => {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  };

  onReady(function () {
    const sidebar = document.getElementById("dashSidebar");
    const overlay = document.getElementById("dashOverlay");
    const toggle = document.getElementById("dashSidebarToggle");

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove("open");
      if (overlay) overlay.classList.remove("show");
    }
    if (toggle && sidebar) {
      toggle.addEventListener("click", () => {
        sidebar.classList.toggle("open");
        if (overlay) overlay.classList.toggle("show", sidebar.classList.contains("open"));
      });
    }
    if (overlay) overlay.addEventListener("click", closeSidebar);

    const chartsEl = document.getElementById("chartsData");
    if (!chartsEl || !window.Chart) return;

    let data;
    try {
      data = JSON.parse(chartsEl.textContent);
    } catch (err) {
      return;
    }

    const navy = "#081c36";
    const navySoft = "#12315f";
    const red = "#e63946";
    const gold = "#f4b400";
    const green = "#1f9d6b";
    const grid = "rgba(227, 235, 246, .8)";

    Chart.defaults.font.family = "'Inter', 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.color = "#5f7189";

    // Booking & revenue trend
    const trendCanvas = document.getElementById("trendChart");
    if (trendCanvas && data.trend) {
      new Chart(trendCanvas, {
        data: {
          labels: data.trend.labels,
          datasets: [
            {
              type: "bar",
              label: "Bookings",
              data: data.trend.bookings,
              backgroundColor: "rgba(18, 49, 95, .78)",
              borderRadius: 6,
              barThickness: 18,
              yAxisID: "y",
            },
            {
              type: "line",
              label: "Revenue (₹)",
              data: data.trend.revenue,
              borderColor: red,
              backgroundColor: "rgba(230, 57, 70, .12)",
              borderWidth: 2.5,
              pointBackgroundColor: red,
              pointRadius: 3,
              tension: 0.4,
              fill: true,
              yAxisID: "y1",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "top", align: "end", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: { backgroundColor: navy, padding: 10, cornerRadius: 8 },
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
            y: { beginAtZero: true, grid: { color: grid }, ticks: { precision: 0 } },
            y1: {
              beginAtZero: true,
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: { callback: (value) => "₹" + Number(value).toLocaleString("en-IN") },
            },
          },
        },
      });
    }

    // Status doughnut
    const statusCanvas = document.getElementById("statusChart");
    if (statusCanvas && data.status) {
      new Chart(statusCanvas, {
        type: "doughnut",
        data: {
          labels: data.status.labels,
          datasets: [
            {
              data: data.status.counts,
              backgroundColor: [gold, green, red, "#9aa9bb", "#343a40"],
              borderWidth: 3,
              borderColor: "#fff",
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          plugins: {
            legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, padding: 12 } },
            tooltip: { backgroundColor: navy, padding: 10, cornerRadius: 8 },
          },
        },
      });
    }

    // Monthly revenue
    const monthlyCanvas = document.getElementById("monthlyChart");
    if (monthlyCanvas && data.monthly) {
      new Chart(monthlyCanvas, {
        type: "line",
        data: {
          labels: data.monthly.labels,
          datasets: [
            {
              label: "Revenue (₹)",
              data: data.monthly.values,
              borderColor: green,
              backgroundColor: "rgba(31, 157, 107, .14)",
              borderWidth: 2.5,
              fill: true,
              tension: 0.38,
              pointBackgroundColor: "#fff",
              pointBorderColor: green,
              pointBorderWidth: 2,
              pointRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: navy,
              padding: 10,
              cornerRadius: 8,
              callbacks: {
                label: (ctx) => "Revenue: ₹" + Number(ctx.parsed.y).toLocaleString("en-IN"),
              },
            },
          },
          scales: {
            x: { grid: { display: false } },
            y: {
              beginAtZero: true,
              grid: { color: grid },
              ticks: { callback: (value) => "₹" + Number(value).toLocaleString("en-IN") },
            },
          },
        },
      });
    }

    // Top routes
    const routesCanvas = document.getElementById("routesChart");
    if (routesCanvas && data.routes) {
      new Chart(routesCanvas, {
        type: "bar",
        data: {
          labels: data.routes.labels,
          datasets: [
            {
              label: "Bookings",
              data: data.routes.counts,
              backgroundColor: ["#081c36", "#12315f", "#1a427a", "#e63946", "#f4b400"],
              borderRadius: 6,
              barThickness: 16,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { backgroundColor: navy, padding: 10, cornerRadius: 8 } },
          scales: {
            x: { beginAtZero: true, grid: { color: grid }, ticks: { precision: 0 } },
            y: { grid: { display: false } },
          },
        },
      });
    }
  });
})();
