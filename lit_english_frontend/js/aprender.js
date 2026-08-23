/* LIT English — Aprender */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const toastEl = document.getElementById("toast");
const frontHintEl = document.getElementById("front-hint");
const frontInput = document.getElementById("flashcard-front");
const frontCounter = document.getElementById("front-counter");
const descriptionInput = document.getElementById("flashcard-description");
const descriptionCounter = document.getElementById("description-counter");
const form = document.getElementById("flashcard-form");
const errorBox = document.getElementById("form-error");
const createBtn = document.getElementById("create-flashcard-btn");

const onboardingEl = document.getElementById("learn-onboarding");
const previewEl = document.getElementById("learn-preview");
const receivedEl = document.getElementById("learn-received");
const createViewEl = document.getElementById("learn-create-view");
const exampleGridEl = document.getElementById("example-cards-grid");
const receivedGridEl = document.getElementById("received-cards-grid");
const startExamplesBtn = document.getElementById("start-examples-btn");
const createOwnBtn = document.getElementById("create-own-btn");
const seeExamplesBtn = document.getElementById("see-examples-btn");
const previewBackBtn = document.getElementById("preview-back-btn");
const addOwnAfterReceiveBtn = document.getElementById("add-own-after-receive-btn");
const receiveExamplesBtn = document.getElementById("receive-examples-btn");
const createTopbarEl = document.getElementById("create-topbar");
const createBackBtn = document.getElementById("create-back-btn");

const LANGUAGE_NAMES = {
  pt: "português", "pt-br": "português", portugues: "português", português: "português",
  en: "inglês", ingles: "inglês", inglês: "inglês",
  it: "italiano", italiano: "italiano",
  fr: "francês", frances: "francês", francês: "francês",
  es: "espanhol", espanhol: "espanhol",
  de: "alemão", alemao: "alemão", alemão: "alemão",
};

const TARGET_GREETING_EXAMPLES = {
  ingles: "Hello",
  italiano: "Ciao",
  frances: "Bonjour",
  espanhol: "Hola",
  alemão: "Hallo",
};

function languageLabel(value, fallback) {
  const key = String(value || "").trim().toLowerCase();
  return LANGUAGE_NAMES[key] || fallback;
}

function getNativeLanguage(user) {
  return user?.native_language || "pt";
}

function getTargetLanguage(user) {
  return user?.target_language || "ingles";
}

function updateFrontHint(user) {
  const nativeLabel = languageLabel(getNativeLanguage(user), "português");
  const targetLabel = languageLabel(getTargetLanguage(user), "inglês");
  const targetKey = getTargetKey(user);
  const greeting = TARGET_GREETING_EXAMPLES[targetKey] || "Hello";

  frontHintEl.textContent = `Digite a palavra, frase ou expressão em ${nativeLabel} ou ${targetLabel}. O flashcard será salvo em ${targetLabel}.`;
  frontInput.placeholder = `Ex: ${greeting}`;
  descriptionInput.placeholder = `Ex: É como falamos 'oi' de forma informal, ex: ${greeting}.`;
}

let toastTimer = null;
function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2600);
}

function updateCounter(input, counter, max = 200) {
  counter.textContent = `${input.value.length}/${max}`;
}

frontInput.addEventListener("input", () => updateCounter(frontInput, frontCounter));
descriptionInput.addEventListener("input", () => updateCounter(descriptionInput, descriptionCounter, 300));

document.getElementById("logout-btn").addEventListener("click", () => {
  if (window.confirm("Deseja sair da sua conta?")) Auth.logout();
});

// ---------------------------------------------------------------------------
// Primeiro acesso ao Aprender
// ---------------------------------------------------------------------------
// Esta lista é o ponto único para os cards iniciais. Quando você me enviar a
// lista definitiva, basta substituir os itens abaixo — o fluxo e o design não
// precisam ser alterados.
const STARTER_CARDS_BY_LANGUAGE = {};

let currentUser = null;
let currentStarterCards = [];

function onboardingKey(user) {
  return `lit_learn_start_${user.id}`;
}

function savedCardsKey(user) {
  return `lit_saved_starter_cards_${user.id}`;
}

function getTargetKey(user) {
  const raw = String(getTargetLanguage(user) || "ingles").trim().toLowerCase();
  return raw === "italiano" || raw === "it" ? "italiano"
    : raw === "frances" || raw === "francês" || raw === "fr" ? "frances"
    : raw === "espanhol" || raw === "es" ? "espanhol"
    : raw === "alemão" || raw === "alemao" || raw === "de" ? "alemão"
    : "ingles";
}

function firstName(fullName) {
  const trimmed = String(fullName || "").trim();
  return trimmed ? trimmed.split(/\s+/)[0] : "";
}

function nationalityValues(user) {
  const defaults = {
    nationality: "Brazilian",
    nacionalidade: "Brasileiro",
    nazionalità: "Brasiliano",
    nationalité: "Brésilien",
  };
  const custom = String(user?.nationality || "").trim();
  if (!custom || Object.values(defaults).some(v => v.toLowerCase() === custom.toLowerCase())) {
    return defaults;
  }
  return Object.fromEntries(Object.keys(defaults).map(key => [key, custom]));
}

function targetLanguageLabels(user) {
  const target = getTargetKey(user);
  const labels = {
    ingles: { language: "English", idioma: "inglês", lingua: "inglese", langue: "anglais" },
    italiano: { language: "Italian", idioma: "italiano", lingua: "italiano", langue: "italien" },
    frances: { language: "French", idioma: "francês", lingua: "francese", langue: "français" },
  };
  return labels[target] || labels.ingles;
}

function placeholderValues(user) {
  const age = user?.age != null ? String(user.age) : "";
  return {
    name: firstName(user?.name),
    nome: firstName(user?.name),
    nom: firstName(user?.name),
    age,
    idade: age,
    "età": age,
    "âge": age,
    ...nationalityValues(user),
    ...targetLanguageLabels(user),
  };
}

function applyUserPlaceholders(text, user) {
  const values = placeholderValues(user);
  return String(text ?? "").replace(/<([^<>]+)>/g, (match, token) => {
    const key = String(token).trim().toLowerCase();
    return values[key] ? values[key] : match;
  });
}

function personalizeStarterCard(card, user) {
  return {
    ...card,
    front: applyUserPlaceholders(card.front, user),
    back: applyUserPlaceholders(card.back, user),
    description: card.description ? applyUserPlaceholders(card.description, user) : card.description,
  };
}

function personalizeStarterCards(cards, user) {
  return (Array.isArray(cards) ? cards : []).map(card => personalizeStarterCard(card, user));
}

async function getStarterCards(user) {
  const language = getTargetKey(user);
  const cacheKey = `lit_starter_catalog_${language}`;
  try {
    const cards = await apiFetch(`/flashcards/starter/catalog?language=${encodeURIComponent(language)}`);
    const normalized = personalizeStarterCards(Array.isArray(cards) ? cards : [], user);
    STARTER_CARDS_BY_LANGUAGE[language] = normalized;
    return normalized;
  } catch (err) {
    const cached = STARTER_CARDS_BY_LANGUAGE[language];
    if (cached) return cached.map(card => ({ ...card }));
    try {
      const local = JSON.parse(localStorage.getItem(cacheKey) || "[]");
      if (Array.isArray(local)) return local.map(card => ({ ...card }));
    } catch {}
    throw err;
  }
}

function markOnboardingDone(user, mode) {
  localStorage.setItem(onboardingKey(user), mode);
}

function getOnboardingMode(user) {
  return localStorage.getItem(onboardingKey(user));
}

function bookmarkIcon(saved) {
  return saved
    ? `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.2 3.5h11.6c.9 0 1.7.8 1.7 1.7v15.3c0 .5-.6.8-1 .5L12 17.4l-6.5 3.6c-.4.2-1-.1-1-.5V5.2c0-.9.8-1.7 1.7-1.7Z"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.2 3.5h11.6c.9 0 1.7.8 1.7 1.7v15.3c0 .5-.6.8-1 .5L12 17.4l-6.5 3.6c-.4.2-1-.1-1-.5V5.2c0-.9.8-1.7 1.7-1.7Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`;
}

function getSavedIds(user) {
  try { return new Set(JSON.parse(localStorage.getItem(savedCardsKey(user)) || "[]")); }
  catch { return new Set(); }
}

function persistSavedIds(user, ids) {
  localStorage.setItem(savedCardsKey(user), JSON.stringify([...ids]));
}

function renderStarterCards(container, cards, allowSave) {
  const savedIds = getSavedIds(currentUser);
  container.innerHTML = "";

  if (!cards.length) {
    container.innerHTML = `<div class="learn-empty-state"><strong>Nenhum exemplo disponível ainda.</strong><span>Os flashcards iniciais aparecerão aqui quando forem adicionados.</span></div>`;
    return;
  }

  cards.forEach((card, index) => {
    const cardId = `${getTargetKey(currentUser)}-${index}-${card.front}`;
    const saved = savedIds.has(cardId);
    const article = document.createElement("article");
    article.className = "starter-card";
    article.innerHTML = `
      <div class="starter-card-language">${languageLabel(getTargetLanguage(currentUser), "inglês")}</div>
      ${allowSave ? `<button type="button" class="starter-save-btn ${saved ? "saved" : ""}" aria-label="${saved ? "Remover dos salvos" : "Salvar flashcard"}" title="${saved ? "Remover dos salvos" : "Salvar"}">${bookmarkIcon(saved)}</button>` : ""}
      <div class="starter-card-front">${escapeHtml(card.front)}</div>
      <div class="starter-card-line"></div>
      <div class="starter-card-back">${escapeHtml(card.back)}</div>
      ${card.description ? `<div class="starter-card-description">${escapeHtml(card.description)}</div>` : ""}
    `;

    if (allowSave) {
      const saveBtn = article.querySelector(".starter-save-btn");
      saveBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        const ids = getSavedIds(currentUser);
        if (ids.has(cardId)) {
          ids.delete(cardId);
          saveBtn.classList.remove("saved");
          saveBtn.setAttribute("aria-label", "Salvar flashcard");
          saveBtn.title = "Salvar";
        } else {
          ids.add(cardId);
          saveBtn.classList.add("saved");
          saveBtn.setAttribute("aria-label", "Remover dos salvos");
          saveBtn.title = "Remover dos salvos";
        }
        saveBtn.innerHTML = bookmarkIcon(ids.has(cardId));
        persistSavedIds(currentUser, ids);
      });
    }
    container.appendChild(article);
  });
}

function showOnly(section) {
  [onboardingEl, previewEl, receivedEl, createViewEl].forEach(el => {
    if (!el) return;
    el.hidden = el !== section;
  });
}

function showChoice() {
  showOnly(onboardingEl);
}

async function showExamplesPreview() {
  try {
    currentStarterCards = await getStarterCards(currentUser);
    renderStarterCards(exampleGridEl, currentStarterCards, false);
    showOnly(previewEl);
  } catch (err) {
    showToast(err.message || "Não foi possível carregar os exemplos.");
  }
}

async function receiveStarterCards() {
  try {
    currentStarterCards = await getStarterCards(currentUser);
  } catch (err) {
    showToast(err.message || "Não foi possível carregar os exemplos.");
    return;
  }

  if (!currentStarterCards.length) {
    markOnboardingDone(currentUser, "create");
    showToast("Ainda não há cards iniciais disponíveis.");
    showOnly(createViewEl);
    frontInput.focus();
    return;
  }

  try {
    const result = await apiFetch("/flashcards/starter/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cards: currentStarterCards }),
    });

    localStorage.setItem(`lit_received_starter_cards_${currentUser.id}`, JSON.stringify(currentStarterCards));
    markOnboardingDone(currentUser, "received");
    renderStarterCards(receivedGridEl, currentStarterCards, true);
    showOnly(receivedEl);
    showToast(`${result?.received ?? currentStarterCards.length} flashcards adicionados!`);
  } catch (err) {
    showToast(err.message || "Não foi possível receber os flashcards.");
  }
}

function showCreateView(options = {}) {
  const { showBack = false } = options;
  markOnboardingDone(currentUser, "create");
  if (createTopbarEl) createTopbarEl.hidden = !showBack;
  const createHeader = createViewEl?.querySelector(".learn-create-header");
  if (createHeader) createHeader.hidden = showBack;
  showOnly(createViewEl);
  setTimeout(() => frontInput.focus(), 0);
}

startExamplesBtn.addEventListener("click", receiveStarterCards);
seeExamplesBtn.addEventListener("click", showExamplesPreview);
previewBackBtn.addEventListener("click", showChoice);
createOwnBtn.addEventListener("click", () => showCreateView({ showBack: true }));
addOwnAfterReceiveBtn.addEventListener("click", () => showCreateView({ showBack: true }));
createBackBtn?.addEventListener("click", () => {
  const mode = getOnboardingMode(currentUser);
  if (mode === "received") {
    renderStarterCards(receivedGridEl, currentStarterCards, true);
    showOnly(receivedEl);
    return;
  }
  showChoice();
});
receiveExamplesBtn?.addEventListener("click", receiveStarterCards);

// ---------------------------------------------------------------------------
// Criação manual — comportamento original preservado
// ---------------------------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;

  const front = frontInput.value.trim();
  const description = descriptionInput.value.trim();

  if (!front) {
    errorBox.textContent = "Digite uma palavra, frase ou expressão na frente do flashcard.";
    errorBox.hidden = false;
    frontInput.focus();
    return;
  }

  createBtn.disabled = true;
  createBtn.querySelector("span:last-child").textContent = "Criando...";

  try {
    await apiFetch("/flashcards/self-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ front, description }),
    });

    form.reset();
    updateCounter(frontInput, frontCounter);
    updateCounter(descriptionInput, descriptionCounter, 300);
    showToast("Flashcard criado!");
    frontInput.focus();
  } catch (err) {
    errorBox.textContent = err.message || "Não foi possível criar o flashcard. Tente novamente.";
    errorBox.hidden = false;
  } finally {
    createBtn.disabled = false;
    createBtn.querySelector("span:last-child").textContent = "Criar Flashcard";
  }
});

async function init() {
  if (!Auth.isLoggedIn()) {
    window.location.href = Auth.loginRedirectUrl();
    return;
  }

  try {
    const user = await fetchCurrentUser();
    currentUser = user;

    studentNameEl.textContent = user.name;
    roleLabelEl.textContent = user.role === "professor" ? "PROFESSOR" : "ALUNO";

    if (user.role !== "aluno") {
      window.location.href = "professor.html";
      return;
    }

    const navExercicios = document.getElementById("nav-exercicios");
    if (navExercicios) {
      navExercicios.style.display = (user.role === "aluno" && user.access_type === "padrao" && user.is_approved === true) ? "" : "none";
    }

    if (!user.is_approved) {
      showOnly(createViewEl);
      frontHintEl.textContent = "Sua conta ainda aguarda aprovação.";
      frontInput.disabled = true;
      descriptionInput.disabled = true;
      createBtn.disabled = true;
      return;
    }

    updateFrontHint(user);

    const mode = getOnboardingMode(user);
    if (!mode) {
      // Sem tela de escolha: aluno cai direto em "criar meus flashcards".
      showCreateView();
      return;
    }

    if (mode === "received") {
      try {
        currentStarterCards = JSON.parse(localStorage.getItem(`lit_received_starter_cards_${user.id}`) || "[]");
      } catch { currentStarterCards = []; }
      if (!currentStarterCards.length) currentStarterCards = await getStarterCards(user);
      else currentStarterCards = personalizeStarterCards(currentStarterCards, user);
      renderStarterCards(receivedGridEl, currentStarterCards, true);
      showOnly(receivedEl);
      return;
    }

    showCreateView();
  } catch (err) {
    const redirectUrl = Auth.loginRedirectUrl();
    Auth.clear();
    window.location.href = redirectUrl;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

init();
