/* ==========================================================================
   LIT English — home.js
   Tela inicial do aluno: saudação + métricas (Taxa de Acerto, Eficiência,
   LIT Points, Exercícios Feitos, Tempo de Texto, Flashcards), consumindo
   GET /dashboard/metrics.
   ========================================================================== */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const welcomeTitleEl = document.getElementById("welcome-title");
const metricsRootEl = document.getElementById("home-metrics");

document.getElementById("logout-btn").addEventListener("click", () => {
  const ok = window.confirm("Deseja sair da sua conta?");
  if (ok) Auth.logout();
});

// Injeta os ícones (SVG) de cada card de métrica.
function renderMetricIcons() {
  metricsRootEl.querySelectorAll("[data-icon]").forEach((el) => {
    const name = el.getAttribute("data-icon");
    if (Icons[name]) el.innerHTML = Icons[name];
  });
}

function setField(cardId, field, value) {
  const card = document.getElementById(cardId);
  if (!card) return;
  const el = card.querySelector(`[data-field="${field}"]`);
  if (el) el.textContent = value;
}

function renderMetrics(metrics) {
  // Taxa de acerto
  setField("metric-accuracy", "value", metrics.accuracy_rate);

  // Eficiência (performance) — exibida em porcentagem
  const performancePercent = metrics.performance_max
    ? Math.round((metrics.performance_points / metrics.performance_max) * 100)
    : 0;
  setField("metric-performance", "value", performancePercent);

  // LIT Points
  setField("metric-litpoints", "value", metrics.lit_points.toLocaleString("pt-BR"));

  // Exercícios feitos
  setField("metric-exercises", "today", metrics.exercises_today);
  setField("metric-exercises", "target", metrics.exercises_today_target);
  setField("metric-exercises", "total", metrics.exercises_total);

  // Tempo de texto
  setField("metric-reading", "value", metrics.reading_minutes);

  // Flashcards revisados
  setField("metric-flashcards", "value", metrics.flashcards_reviewed);

  metricsRootEl.querySelectorAll(".metric-card").forEach((card) => {
    card.classList.remove("is-loading");
  });
}

async function loadMetrics() {
  try {
    const metrics = await apiFetch("/dashboard/metrics");
    renderMetrics(metrics);
  } catch (err) {
    // Mantém os cards visíveis com "—" em vez de quebrar a tela inicial;
    // o aluno ainda vê a saudação normalmente.
    metricsRootEl.querySelectorAll(".metric-card").forEach((card) => {
      card.classList.remove("is-loading");
    });
  }
}

async function init() {
  if (!Auth.isLoggedIn()) {
    window.location.href = "index.html";
    return;
  }

  let user;
  try {
    user = await fetchCurrentUser();
  } catch (err) {
    Auth.clear();
    window.location.href = "index.html";
    return;
  }

  if (user.role === "professor") {
    window.location.href = "professor.html";
    return;
  }

  const firstName = (user.name || "").trim().split(/\s+/)[0] || user.name;

  studentNameEl.textContent = user.name;
  roleLabelEl.textContent = "ALUNO";
  welcomeTitleEl.textContent = `Bem-vindo, ${firstName}!`;

  renderMetricIcons();

  if (!user.is_approved) {
    // Conta ainda não aprovada: sem atividades registradas, não há métricas
    // pra buscar — evita uma chamada 403 desnecessária.
    metricsRootEl.querySelectorAll(".metric-card").forEach((card) => {
      card.classList.remove("is-loading");
    });
    return;
  }

  loadMetrics();
}

init();
