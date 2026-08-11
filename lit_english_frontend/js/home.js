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
const homeQuoteEl = document.getElementById("home-quote");
const homeQuoteAuthorEl = document.getElementById("home-quote-author");
const metricsRootEl = document.getElementById("home-metrics");

// Mesma regra do backend (ver student_language() em vocab_words.py): curso
// normal (access_type "padrao") é sempre inglês; Acesso Especial usa a
// target_language escolhida no cadastro (ex.: "italiano").
function studentLanguage(user) {
  if (user.access_type === "especial" && user.target_language) {
    return user.target_language.trim().toLowerCase();
  }
  return "ingles";
}

// Saudação e frase de abertura da Home, no idioma que o aluno está
// aprendendo (imersão) — cada idioma tem seu próprio texto de boas-vindas
// e citação inspiradora.
const HOME_CONTENT = {
  ingles: {
    welcome: (firstName) => `Welcome, ${firstName}!`,
    quote: "An investment in knowledge pays the best interest.",
    author: "Benjamin Franklin",
  },
  italiano: {
    welcome: (firstName) => `Benvenuto, ${firstName}!`,
    quote: "La mente non è un vaso da riempire, ma un fuoco da accendere.",
    author: "Plutarco",
  },
  frances: {
    welcome: (firstName) => `Bienvenue, ${firstName}!`,
    quote: "Savoir étant sublime, apprendre sera doux.",
    author: "Victor Hugo",
  },
};

function applyHomeContent(user, firstName) {
  const language = studentLanguage(user);
  const content = HOME_CONTENT[language] || HOME_CONTENT.ingles;

  welcomeTitleEl.textContent = content.welcome(firstName);
  if (homeQuoteEl) homeQuoteEl.textContent = `\u201c${content.quote}\u201d`;
  if (homeQuoteAuthorEl) homeQuoteAuthorEl.textContent = `\u2014 ${content.author}`;
}

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
    window.location.href = Auth.loginRedirectUrl();
    return;
  }

  let user;
  try {
    user = await fetchCurrentUser();
  } catch (err) {
    const redirectUrl = Auth.loginRedirectUrl();
    Auth.clear();
    window.location.href = redirectUrl;
    return;
  }

  if (user.role === "professor") {
    window.location.href = "professor.html";
    return;
  }

  const firstName = (user.name || "").trim().split(/\s+/)[0] || user.name;

  studentNameEl.textContent = user.name;
  roleLabelEl.textContent = "ALUNO";
  applyHomeContent(user, firstName);

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
