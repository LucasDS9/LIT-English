/* ==========================================================================
   LIT English — home.js
   Tela inicial do aluno: saudação + cards de LIT Points e Streak,
   consumindo GET /dashboard/metrics.
   ========================================================================== */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const welcomeTitleEl = document.getElementById("welcome-title");
const homeQuoteEl = document.getElementById("home-quote");
const homeQuoteAuthorEl = document.getElementById("home-quote-author");
const homeQuotePinyinEl = document.getElementById("home-quote-pinyin");
const homeTranslateBtn = document.getElementById("home-translate-btn");
const metricsRootEl = document.getElementById("home-metrics");

// Mesma regra do backend (ver student_language() em language.py): curso
// normal (access_type "padrao") é sempre inglês; Acesso Especial usa a
// target_language escolhida no cadastro (ex.: "italiano").
function studentLanguage(user) {
  if (user.target_language) {
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
    // Tradução para o português (botão de seta).
    pt: {
      welcome: (firstName) => `Bem-vindo, ${firstName}!`,
      quote: "Um investimento em conhecimento rende os melhores juros.",
      author: "Benjamin Franklin",
    },
  },
  italiano: {
    welcome: (firstName) => `Benvenuto, ${firstName}!`,
    quote: "La mente non è un vaso da riempire, ma un fuoco da accendere.",
    author: "Plutarco",
    // Tradução para o português (botão de seta).
    pt: {
      welcome: (firstName) => `Bem-vindo, ${firstName}!`,
      quote: "A mente não é um vaso a ser enchido, mas um fogo a ser aceso.",
      author: "Plutarco",
    },
  },
  frances: {
    welcome: (firstName) => `Bienvenue, ${firstName}!`,
    quote: "Savoir étant sublime, apprendre sera doux.",
    author: "Victor Hugo",
    // Tradução para o português (botão de seta).
    pt: {
      welcome: (firstName) => `Bem-vindo, ${firstName}!`,
      quote: "Sendo o saber sublime, aprender será doce.",
      author: "Victor Hugo",
    },
  },
  mandarim: {
    welcome: (firstName) => `欢迎, ${firstName}!`,
    quote: "千里之行，始于足下。",
    // Idiomas com outro alfabeto: a transcrição (pinyin) vai numa linha
    // própria, entre a frase e o autor.
    pinyin: "Qiān lǐ zhī xíng, shǐ yú zú xià.",
    author: "老子 (Laozi)",
    // Tradução para o português (botão de seta).
    pt: {
      welcome: (firstName) => `Bem-vindo, ${firstName}!`,
      quote: "A jornada de mil milhas começa com um único passo.",
      author: "老子 (Laozi)",
    },
  },
};

let homeShowingTranslation = false;
let homeCurrent = null;

function renderHomeContent() {
  if (!homeCurrent) return;
  const { content, firstName } = homeCurrent;
  const view = homeShowingTranslation ? content.pt : content;

  welcomeTitleEl.textContent = view.welcome(firstName);
  if (homeQuoteEl) homeQuoteEl.textContent = `\u201c${view.quote}\u201d`;
  // O pinyin só faz sentido junto da frase original; traduzido, some.
  const pinyin = homeShowingTranslation ? "" : (content.pinyin || "");
  if (homeQuotePinyinEl) {
    homeQuotePinyinEl.textContent = pinyin;
    homeQuotePinyinEl.hidden = !pinyin;
  }
  if (homeQuoteAuthorEl) homeQuoteAuthorEl.textContent = `\u2014 ${view.author}`;

  if (homeTranslateBtn) {
    homeTranslateBtn.classList.toggle("is-active", homeShowingTranslation);
    homeTranslateBtn.setAttribute("aria-pressed", String(homeShowingTranslation));
    const label = homeShowingTranslation ? "Ver no idioma original" : "Traduzir para português";
    homeTranslateBtn.setAttribute("aria-label", label);
    homeTranslateBtn.title = homeShowingTranslation ? "Original" : "Traduzir";
  }
}

function applyHomeContent(user, firstName) {
  const language = studentLanguage(user);
  homeCurrent = { content: HOME_CONTENT[language] || HOME_CONTENT.ingles, firstName };
  homeShowingTranslation = false;
  renderHomeContent();
}

homeTranslateBtn?.addEventListener("click", () => {
  homeShowingTranslation = !homeShowingTranslation;
  renderHomeContent();
});

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

  // Streak: dias seguidos com atividade, calculado pela API.
  setField("metric-streak", "value", metrics.streak.toLocaleString("pt-BR"));

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
  redirectToPriorityActivityIfNeeded(user);
}

init();
