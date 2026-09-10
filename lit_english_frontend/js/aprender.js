/* LIT English — Aprender */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const toastEl = document.getElementById("toast");
const frontHintEl = document.getElementById("front-hint");
const frontInput = document.getElementById("flashcard-front");
const frontCounter = document.getElementById("front-counter");
const backInput = document.getElementById("flashcard-back");
const backCounter = document.getElementById("back-counter");
const descriptionInput = document.getElementById("flashcard-description");
const descriptionCounter = document.getElementById("description-counter");
const form = document.getElementById("flashcard-form");
const errorBox = document.getElementById("form-error");
const createBtn = document.getElementById("create-flashcard-btn");

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

function getTargetKey(user) {
  const raw = String(getTargetLanguage(user) || "ingles").trim().toLowerCase();
  return raw === "italiano" || raw === "it" ? "italiano"
    : raw === "frances" || raw === "francês" || raw === "fr" ? "frances"
    : raw === "espanhol" || raw === "es" ? "espanhol"
    : raw === "alemão" || raw === "alemao" || raw === "de" ? "alemão"
    : "ingles";
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
backInput.addEventListener("input", () => updateCounter(backInput, backCounter));
descriptionInput.addEventListener("input", () => updateCounter(descriptionInput, descriptionCounter, 300));

document.getElementById("logout-btn").addEventListener("click", () => {
  if (window.confirm("Deseja sair da sua conta?")) Auth.logout();
});

function bookmarkIcon(saved) {
  return saved
    ? `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.2 3.5h11.6c.9 0 1.7.8 1.7 1.7v15.3c0 .5-.6.8-1 .5L12 17.4l-6.5 3.6c-.4.2-1-.1-1-.5V5.2c0-.9.8-1.7 1.7-1.7Z"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.2 3.5h11.6c.9 0 1.7.8 1.7 1.7v15.3c0 .5-.6.8-1 .5L12 17.4l-6.5 3.6c-.4.2-1-.1-1-.5V5.2c0-.9.8-1.7 1.7-1.7Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`;
}

// ---------------------------------------------------------------------------
// Abas "Vocabulário" / "Criar"
// ---------------------------------------------------------------------------
// "Vocabulário" por enquanto é só o template visual (ver aprender.html) --
// ainda não busca flashcards de verdade, só reaproveita o mesmo padrão de
// card já usado em Revisar. "Criar" é o formulário de criação direto (a tela
// de escolha/exemplos da versão anterior foi removida).
const vocabTabBtn = document.getElementById("learn-tab-vocab-btn");
const criarTabBtn = document.getElementById("learn-tab-criar-btn");
const vocabPanel = document.getElementById("learn-tab-vocab");
const criarPanel = document.getElementById("learn-tab-criar");
const vocabFlagEl = document.getElementById("vocab-browse-flag");

const ITALIAN_FLAG_SVG = `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect x="16" width="8" height="16" fill="#CE2B37"/><rect width="8" height="16" fill="#009246"/></svg>`;

function setLearnTab(tab) {
  const isVocab = tab === "vocab";
  vocabTabBtn.classList.toggle("active", isVocab);
  criarTabBtn.classList.toggle("active", !isVocab);
  vocabTabBtn.setAttribute("aria-selected", String(isVocab));
  criarTabBtn.setAttribute("aria-selected", String(!isVocab));
  vocabPanel.hidden = !isVocab;
  criarPanel.hidden = isVocab;
}

vocabTabBtn?.addEventListener("click", () => setLearnTab("vocab"));
criarTabBtn?.addEventListener("click", () => setLearnTab("criar"));

if (vocabTabBtn) vocabTabBtn.querySelector(".learn-tab-icon").innerHTML = Icons.bookOpen;
if (criarTabBtn) criarTabBtn.querySelector(".learn-tab-icon").innerHTML = Icons.edit;
if (vocabFlagEl) vocabFlagEl.innerHTML = ITALIAN_FLAG_SVG;

const vocabListenBtn = document.getElementById("vocab-listen-btn");
const vocabMoreExamplesBtn = document.getElementById("vocab-more-examples-btn");
const vocabMoreExamplesLabel = document.getElementById("vocab-more-examples-label");
const vocabMoreExamplesBox = document.getElementById("vocab-more-examples");
const vocabSaveBtn = document.getElementById("vocab-save-btn");
const vocabSaveLabel = document.getElementById("vocab-save-label");
const vocabWordEl = document.getElementById("vocab-browse-word");
const vocabExampleEl = document.getElementById("vocab-browse-example");
const vocabOptionsEl = document.getElementById("vocab-browse-options");

if (vocabListenBtn) vocabListenBtn.querySelector(".vocab-browse-action-icon").innerHTML = Icons.volume;
if (vocabMoreExamplesBtn) vocabMoreExamplesBtn.querySelector(".vocab-browse-action-icon").innerHTML = Icons.listCheck;
if (vocabSaveBtn) vocabSaveBtn.querySelector(".vocab-browse-action-icon").innerHTML = bookmarkIcon(false);

const vocabMoreExamplesIcon = document.getElementById("vocab-more-examples-icon");
if (vocabMoreExamplesIcon) vocabMoreExamplesIcon.innerHTML = Icons.infoCircle;

// ---- "Ouvir novamente" -- toca a frase de exemplo via TTS (mesmo endpoint
// já usado em Revisar/Textos/Exercícios: GET /tts/speak) ----
let vocabAudioCache = null;
async function playVocabAudio() {
  if (!vocabListenBtn) return;
  const text = vocabExampleEl?.textContent?.trim();
  if (!text) return;
  vocabListenBtn.disabled = true;
  try {
    if (!vocabAudioCache) {
      const blob = await apiFetchBlob(`/tts/speak?text=${encodeURIComponent(text)}`);
      vocabAudioCache = URL.createObjectURL(blob);
    }
    const audio = new Audio(vocabAudioCache);
    audio.addEventListener("ended", () => { vocabListenBtn.disabled = false; });
    audio.addEventListener("error", () => { vocabListenBtn.disabled = false; });
    await audio.play();
  } catch (err) {
    showToast("Não foi possível reproduzir o áudio.");
  } finally {
    vocabListenBtn.disabled = false;
  }
}
vocabListenBtn?.addEventListener("click", playVocabAudio);

// ---- "Ver mais N exemplos" -- mostra/esconde as frases extras ----
vocabMoreExamplesBtn?.addEventListener("click", () => {
  if (!vocabMoreExamplesBox) return;
  const nowHidden = !vocabMoreExamplesBox.hidden;
  vocabMoreExamplesBox.hidden = nowHidden;
  if (vocabMoreExamplesLabel) {
    vocabMoreExamplesLabel.textContent = nowHidden ? "Ver mais 3 exemplos" : "Ocultar exemplos";
  }
});

// ---- "Salvar" -- adiciona a frase de exemplo atual (não só a palavra) como
// flashcard do aluno e leva pra tela de Flashcards (Revisar) ----
vocabSaveBtn?.addEventListener("click", async () => {
  const front = vocabExampleEl?.textContent?.trim();
  if (!front || vocabSaveBtn.disabled) return;

  vocabSaveBtn.disabled = true;
  if (vocabSaveLabel) vocabSaveLabel.textContent = "Salvando...";

  try {
    await apiFetch("/flashcards/self-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ front, back: "", description: vocabWordEl?.textContent?.trim() || "" }),
    });
    window.location.href = "revisar.html";
  } catch (err) {
    showToast(err.message || "Não foi possível salvar o flashcard.");
    vocabSaveBtn.disabled = false;
    if (vocabSaveLabel) vocabSaveLabel.textContent = "Salvar";
  }
});

// ---- Opções de múltipla escolha (2x2), no lugar do antigo "virar card" ----
if (vocabOptionsEl) {
  const options = Array.from(vocabOptionsEl.querySelectorAll(".vocab-browse-option"));
  vocabOptionsEl.addEventListener("click", (event) => {
    const chosen = event.target.closest(".vocab-browse-option");
    if (!chosen || chosen.disabled) return;

    options.forEach(opt => { opt.disabled = true; });

    const isRight = chosen.dataset.correct === "true";
    chosen.classList.add(isRight ? "is-correct" : "is-wrong");
    if (!isRight) {
      const correctOpt = options.find(opt => opt.dataset.correct === "true");
      correctOpt?.classList.add("is-correct");
    }
  });
}

// Aba inicial: "Vocabulário" é a entrada padrão da tela de Aprender.
setLearnTab("vocab");

let currentUser = null;

// ---------------------------------------------------------------------------
// Criação manual — comportamento original preservado
// ---------------------------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;

  const front = frontInput.value.trim();
  const back = backInput.value.trim();
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
      body: JSON.stringify({ front, back, description }),
    });

    form.reset();
    updateCounter(frontInput, frontCounter);
    updateCounter(backInput, backCounter);
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
      frontHintEl.textContent = "Sua conta ainda aguarda aprovação.";
      frontInput.disabled = true;
      backInput.disabled = true;
      descriptionInput.disabled = true;
      createBtn.disabled = true;
      return;
    }

    updateFrontHint(user);
    frontInput.focus();
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
