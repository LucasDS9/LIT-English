/* ==========================================================================
   LIT English — home.js
   Tela inicial do aluno: saudação + cards de LIT Points e Streak,
   consumindo GET /dashboard/metrics.
   (Streak ainda não possui campo próprio no backend, então permanece em 0
   até que essa métrica seja implementada na API.)
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
  const iconEls = metricsRootEl.querySelectorAll("[data-icon]");
  for (let i = 0; i < iconEls.length; i++) {
    const el = iconEls[i];
    const iconName = el.getAttribute("data-icon");
    if (Icons[iconName]) el.innerHTML = Icons[iconName];
  }
}

function setField(cardId, field, value) {
  const card = document.getElementById(cardId);
  if (!card) return;
  const el = card.querySelector(`[data-field="${field}"]`);
  if (el) el.textContent = value;
}

function renderMetrics(metrics) {
  // LIT Points
  setField("metric-litpoints", "value", metrics.lit_points.toLocaleString("pt-BR"));

  // Streak: sem campo próprio na API ainda — mantém "0" (ver nota no topo do arquivo).

  metricsRootEl.querySelectorAll(".stat-card").forEach((card) => {
    card.classList.remove("is-loading");
  });
}

async function loadMetrics() {
  try {
    const metrics = await apiFetch("/dashboard/metrics");
    renderMetrics(metrics);
  } catch (err) {
    // Mantém os cards visíveis com "0" em vez de quebrar a tela inicial;
    // o aluno ainda vê a saudação normalmente.
    metricsRootEl.querySelectorAll(".stat-card").forEach((card) => {
      card.classList.remove("is-loading");
    });
  }
}

async function init() {
  if (!Auth.isLoggedIn()) {
    window.location.href = "login.html";
    return;
  }

  let user;
  try {
    user = await fetchCurrentUser();
  } catch (err) {
    Auth.clear();
    window.location.href = "login.html";
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
    metricsRootEl.querySelectorAll(".stat-card").forEach((card) => {
      card.classList.remove("is-loading");
    });
    return;
  }

  loadMetrics();
}

init();
