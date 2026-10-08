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
const FLAG_SVG = {
  ingles: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect y="0.000" width="24" height="1.231" fill="#B22234"/><rect y="2.462" width="24" height="1.231" fill="#B22234"/><rect y="4.923" width="24" height="1.231" fill="#B22234"/><rect y="7.385" width="24" height="1.231" fill="#B22234"/><rect y="9.846" width="24" height="1.231" fill="#B22234"/><rect y="12.308" width="24" height="1.231" fill="#B22234"/><rect y="14.769" width="24" height="1.231" fill="#B22234"/><rect width="9.6" height="8.615" fill="#3C3B6E"/><circle cx="0.80" cy="0.86" r="0.36" fill="#fff"/><circle cx="2.40" cy="0.86" r="0.36" fill="#fff"/><circle cx="4.00" cy="0.86" r="0.36" fill="#fff"/><circle cx="5.60" cy="0.86" r="0.36" fill="#fff"/><circle cx="7.20" cy="0.86" r="0.36" fill="#fff"/><circle cx="8.80" cy="0.86" r="0.36" fill="#fff"/><circle cx="1.60" cy="1.72" r="0.36" fill="#fff"/><circle cx="3.20" cy="1.72" r="0.36" fill="#fff"/><circle cx="4.80" cy="1.72" r="0.36" fill="#fff"/><circle cx="6.40" cy="1.72" r="0.36" fill="#fff"/><circle cx="8.00" cy="1.72" r="0.36" fill="#fff"/><circle cx="0.80" cy="2.58" r="0.36" fill="#fff"/><circle cx="2.40" cy="2.58" r="0.36" fill="#fff"/><circle cx="4.00" cy="2.58" r="0.36" fill="#fff"/><circle cx="5.60" cy="2.58" r="0.36" fill="#fff"/><circle cx="7.20" cy="2.58" r="0.36" fill="#fff"/><circle cx="8.80" cy="2.58" r="0.36" fill="#fff"/><circle cx="1.60" cy="3.45" r="0.36" fill="#fff"/><circle cx="3.20" cy="3.45" r="0.36" fill="#fff"/><circle cx="4.80" cy="3.45" r="0.36" fill="#fff"/><circle cx="6.40" cy="3.45" r="0.36" fill="#fff"/><circle cx="8.00" cy="3.45" r="0.36" fill="#fff"/><circle cx="0.80" cy="4.31" r="0.36" fill="#fff"/><circle cx="2.40" cy="4.31" r="0.36" fill="#fff"/><circle cx="4.00" cy="4.31" r="0.36" fill="#fff"/><circle cx="5.60" cy="4.31" r="0.36" fill="#fff"/><circle cx="7.20" cy="4.31" r="0.36" fill="#fff"/><circle cx="8.80" cy="4.31" r="0.36" fill="#fff"/><circle cx="1.60" cy="5.17" r="0.36" fill="#fff"/><circle cx="3.20" cy="5.17" r="0.36" fill="#fff"/><circle cx="4.80" cy="5.17" r="0.36" fill="#fff"/><circle cx="6.40" cy="5.17" r="0.36" fill="#fff"/><circle cx="8.00" cy="5.17" r="0.36" fill="#fff"/><circle cx="0.80" cy="6.03" r="0.36" fill="#fff"/><circle cx="2.40" cy="6.03" r="0.36" fill="#fff"/><circle cx="4.00" cy="6.03" r="0.36" fill="#fff"/><circle cx="5.60" cy="6.03" r="0.36" fill="#fff"/><circle cx="7.20" cy="6.03" r="0.36" fill="#fff"/><circle cx="8.80" cy="6.03" r="0.36" fill="#fff"/><circle cx="1.60" cy="6.89" r="0.36" fill="#fff"/><circle cx="3.20" cy="6.89" r="0.36" fill="#fff"/><circle cx="4.80" cy="6.89" r="0.36" fill="#fff"/><circle cx="6.40" cy="6.89" r="0.36" fill="#fff"/><circle cx="8.00" cy="6.89" r="0.36" fill="#fff"/><circle cx="0.80" cy="7.75" r="0.36" fill="#fff"/><circle cx="2.40" cy="7.75" r="0.36" fill="#fff"/><circle cx="4.00" cy="7.75" r="0.36" fill="#fff"/><circle cx="5.60" cy="7.75" r="0.36" fill="#fff"/><circle cx="7.20" cy="7.75" r="0.36" fill="#fff"/><circle cx="8.80" cy="7.75" r="0.36" fill="#fff"/></svg>`,
  italiano: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect x="0" width="8" height="16" fill="#009246"/><rect x="16" width="8" height="16" fill="#CE2B37"/></svg>`,
  frances: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect width="8" height="16" fill="#0055A4"/><rect x="16" width="8" height="16" fill="#EF4135"/></svg>`,
};

const learnCreateArea = document.querySelector(".main-learn-create");

function setLearnTab(tab) {
  const isVocab = tab === "vocab";
  vocabTabBtn.classList.toggle("active", isVocab);
  criarTabBtn.classList.toggle("active", !isVocab);
  vocabTabBtn.setAttribute("aria-selected", String(isVocab));
  criarTabBtn.setAttribute("aria-selected", String(!isVocab));
  vocabPanel.hidden = !isVocab;
  criarPanel.hidden = isVocab;
  learnCreateArea?.classList.toggle("tab-criar-active", !isVocab);
}

vocabTabBtn?.addEventListener("click", () => setLearnTab("vocab"));
criarTabBtn?.addEventListener("click", () => setLearnTab("criar"));

if (vocabTabBtn) vocabTabBtn.querySelector(".learn-tab-icon").innerHTML = Icons.bookOpen;
if (criarTabBtn) criarTabBtn.querySelector(".learn-tab-icon").innerHTML = Icons.edit;

const vocabListenBtn = document.getElementById("vocab-listen-btn");
const vocabMoreExamplesBtn = document.getElementById("vocab-more-examples-btn");
const vocabMoreExamplesLabel = document.getElementById("vocab-more-examples-label");
const vocabMoreExamplesBox = document.getElementById("vocab-more-examples");
const vocabMoreExamplesText = document.getElementById("vocab-more-examples-text");
const vocabSaveBtn = document.getElementById("vocab-save-btn");
const vocabSaveLabel = document.getElementById("vocab-save-label");
const vocabWordEl = document.getElementById("vocab-browse-word");
const vocabPosEl = document.getElementById("vocab-browse-pos");
const vocabExampleEl = document.getElementById("vocab-browse-example");
const vocabOptionsEl = document.getElementById("vocab-browse-options");
const vocabCounterEl = document.getElementById("vocab-browse-counter");
const vocabFlagEl = document.getElementById("vocab-browse-flag");

if (vocabListenBtn) vocabListenBtn.querySelector(".vocab-browse-action-icon").innerHTML = `
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 10v4h4l5 4V6l-5 4H4Z" fill="currentColor" stroke="none"/>
    <path d="M16 9.5a4 4 0 0 1 0 5M18.5 7a7.5 7.5 0 0 1 0 10"/>
  </svg>`;
if (vocabMoreExamplesBtn) vocabMoreExamplesBtn.querySelector(".vocab-browse-action-icon").innerHTML = Icons.listCheck;
if (vocabSaveBtn) vocabSaveBtn.querySelector(".vocab-browse-action-icon").innerHTML = bookmarkIcon(false);

const vocabMoreExamplesIcon = document.getElementById("vocab-more-examples-icon");
if (vocabMoreExamplesIcon) vocabMoreExamplesIcon.innerHTML = Icons.infoCircle;

let vocabCards = [];
let vocabIndex = 0;
let vocabAudioCache = null;
let vocabAnswered = false;
let vocabStorageKey = "lit_vocab_active_card";
let vocabExamples = [];
let vocabSavedExamples = new Set();
let vocabWordAudio = null;
let vocabPendingAutoplay = null;
const vocabWordAudioCache = new Map();

function getDistinctExamples(card) {
  const main = String(card?.example_sentence || "").trim().toLowerCase();
  const list = Array.isArray(card?.example_sentences) ? card.example_sentences : [];
  const seen = new Set();
  return list
    .map(sentence => String(sentence || "").trim())
    .filter(sentence => {
      const key = sentence.toLowerCase();
      if (!sentence || key === main || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 3);
}

async function playVocabWord(word) {
  const text = String(word || "").trim();
  if (!text || vocabPanel?.hidden) return;
  vocabPendingAutoplay = null;
  try {
    if (vocabWordAudio) { vocabWordAudio.pause(); vocabWordAudio = null; }
    let url = vocabWordAudioCache.get(text);
    if (!url) {
      const blob = await apiFetchBlob(`/tts/speak?text=${encodeURIComponent(text)}`);
      url = URL.createObjectURL(blob);
      vocabWordAudioCache.set(text, url);
    }
    if (vocabCards[vocabIndex]?.word !== text) return;
    const audio = new Audio(url);
    vocabWordAudio = audio;
    await audio.play();
  } catch (err) {
    if (err && err.name === "NotAllowedError") vocabPendingAutoplay = text;
  }
}

function flushPendingVocabAutoplay() {
  if (!vocabPendingAutoplay) return;
  const word = vocabPendingAutoplay;
  vocabPendingAutoplay = null;
  playVocabWord(word);
}
document.addEventListener("pointerdown", flushPendingVocabAutoplay);
document.addEventListener("keydown", flushPendingVocabAutoplay);

function setVocabFlag(language) {
  if (vocabFlagEl) vocabFlagEl.innerHTML = FLAG_SVG[getTargetKey({target_language: language})] || FLAG_SVG.ingles;
}

function highlightVocabWord(sentence, word) {
  const text = String(sentence || "");
  const target = String(word || "").trim();
  if (!text || !target) return escapeHtml(text);

  const escapedTarget = target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(${escapedTarget})`, "gi");
  let result = "";
  let lastIndex = 0;

  for (const match of text.matchAll(pattern)) {
    result += escapeHtml(text.slice(lastIndex, match.index));
    result += `<strong>${escapeHtml(match[0])}</strong>`;
    lastIndex = match.index + match[0].length;
  }

  result += escapeHtml(text.slice(lastIndex));
  return result;
}

function saveActiveVocabCard(card) {
  if (!card) return;
  try {
    localStorage.setItem(vocabStorageKey, JSON.stringify({
      word_id: card.word_id,
      card,
    }));
  } catch (_) {}
}

function getActiveVocabCard() {
  try {
    const raw = localStorage.getItem(vocabStorageKey);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    return saved?.card || null;
  } catch (_) {
    return null;
  }
}

function clearActiveVocabCard() {
  try { localStorage.removeItem(vocabStorageKey); } catch (_) {}
}

function renderVocabCard(card) {
  if (!card) {
    // Aprender é uma fila contínua: quando o lote atual acaba, buscamos
    // automaticamente o próximo lote em vez de mostrar uma tela de fim.
    vocabWordEl.textContent = "";
    vocabPosEl.textContent = "";
    vocabExampleEl.textContent = "";
    vocabOptionsEl.innerHTML = "";
    if (vocabCounterEl) vocabCounterEl.textContent = "";
    return;
  }

  vocabAnswered = false;
  vocabAudioCache = null;
  vocabWordEl.textContent = card.word;
  vocabPosEl.textContent = `${card.part_of_speech} · ${card.level}`;
  vocabExampleEl.innerHTML = highlightVocabWord(card.example_sentence || "", card.word);
  // Não há mais limite visual de 10 palavras por sessão.
  if (vocabCounterEl) vocabCounterEl.textContent = "";
  setVocabFlag(card.language);
  saveActiveVocabCard(card);

  vocabMoreExamplesBox.hidden = true;
  vocabMoreExamplesLabel.textContent = "Ver mais 3 exemplos";
  vocabSavedExamples = new Set();
  vocabExamples = getDistinctExamples(card);
  vocabMoreExamplesText.innerHTML = vocabExamples.map((sentence, index) => `
    <div class="vocab-example-row">
      <p>${highlightVocabWord(sentence, card.word)}</p>
      <button type="button" class="vocab-example-save" data-index="${index}" aria-label="Salvar frase nos flashcards" title="Salvar nos flashcards">${bookmarkIcon(false)}</button>
    </div>`).join("");
  playVocabWord(card.word);

  vocabOptionsEl.innerHTML = (card.options || []).map(option =>
    `<button type="button" class="vocab-browse-option" data-answer="${escapeHtml(option)}">${escapeHtml(option)}</button>`
  ).join("");
}

async function advanceVocabCard() {
  vocabIndex += 1;
  if (vocabIndex < vocabCards.length) {
    renderVocabCard(vocabCards[vocabIndex]);
    return;
  }

  // Terminou o lote atual. Busca o próximo automaticamente, sem tela
  // "Você terminou!" e sem limite de 10 palavras.
  clearActiveVocabCard();
  await loadVocabLearn();
}

async function submitVocabAnswer(chosen, button) {
  const card = vocabCards[vocabIndex];
  if (!card || vocabAnswered) return;
  vocabAnswered = true;

  const buttons = Array.from(vocabOptionsEl.querySelectorAll(".vocab-browse-option"));
  buttons.forEach(opt => { opt.disabled = true; });

  try {
    const result = await apiFetch(`/vocab-words/learn/${card.word_id}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({selected_option: chosen}),
    });

    const correct = result.correct;
    SFX.play(correct ? "correct" : "wrong");
    button.classList.add(correct ? "is-correct" : "is-wrong");
    if (!correct) {
      const correctOpt = buttons.find(opt => opt.textContent.trim().toLowerCase() === String(result.correct_answer).trim().toLowerCase());
      correctOpt?.classList.add("is-correct");
    }

    clearActiveVocabCard();
    setTimeout(advanceVocabCard, correct ? 450 : 1100);
  } catch (err) {
    vocabAnswered = false;
    buttons.forEach(opt => { opt.disabled = false; });
    showToast(err.message || "Não foi possível registrar a resposta.");
  }
}

vocabOptionsEl?.addEventListener("click", event => {
  const chosen = event.target.closest(".vocab-browse-option");
  if (!chosen || chosen.disabled) return;
  submitVocabAnswer(chosen.dataset.answer || chosen.textContent.trim(), chosen);
});

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

vocabMoreExamplesBtn?.addEventListener("click", () => {
  if (!vocabMoreExamplesBox) return;
  const hidden = vocabMoreExamplesBox.hidden;
  vocabMoreExamplesBox.hidden = !hidden;
  if (vocabMoreExamplesLabel) vocabMoreExamplesLabel.textContent = hidden ? "Ocultar exemplos" : "Ver mais 3 exemplos";
});

vocabMoreExamplesText?.addEventListener("click", async event => {
  const btn = event.target.closest(".vocab-example-save");
  if (!btn || btn.disabled) return;
  const index = Number(btn.dataset.index);
  const sentence = vocabExamples[index];
  if (!sentence || vocabSavedExamples.has(index)) return;

  btn.disabled = true;
  try {
    await apiFetch("/flashcards/self-add", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        front: sentence,
        back: "",
        description: "",
        source_is_target: true,
      }),
    });
    vocabSavedExamples.add(index);
    btn.innerHTML = bookmarkIcon(true);
    btn.classList.add("is-saved");
    btn.title = "Salvo nos flashcards";
    showToast("Flashcard salvo!");
  } catch (err) {
    btn.disabled = false;
    showToast(err.message || "Não foi possível salvar o flashcard.");
  }
});

vocabSaveBtn?.addEventListener("click", async () => {
  const front = vocabExampleEl?.textContent?.trim();
  if (!front || vocabSaveBtn.disabled) return;

  vocabSaveBtn.disabled = true;
  if (vocabSaveLabel) vocabSaveLabel.textContent = "Salvando...";

  try {
    await apiFetch("/flashcards/self-add", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        front,
        back: "",
        description: "",
        source_is_target: true,
      }),
    });
    showToast("Flashcard salvo!");
  } catch (err) {
    showToast(err.message || "Não foi possível salvar o flashcard.");
  } finally {
    vocabSaveBtn.disabled = false;
    if (vocabSaveLabel) vocabSaveLabel.textContent = "Salvar";
  }
});

async function loadVocabLearn() {
  try {
    const data = await apiFetch("/vocab-words/learn/next?category=palavras_essenciais");
    vocabCards = data.cards || [];

    const activeCard = getActiveVocabCard();
    if (activeCard?.word_id) {
      const serverIndex = vocabCards.findIndex(card => Number(card.word_id) === Number(activeCard.word_id));
      if (serverIndex >= 0) {
        vocabIndex = serverIndex;
        renderVocabCard(vocabCards[vocabIndex]);
        return;
      }

      // Se o backend já retirou a palavra da fila, ainda mantemos a palavra
      // congelada no navegador até que o aluno a responda.
      vocabCards = [activeCard, ...vocabCards.filter(card => Number(card.word_id) !== Number(activeCard.word_id))];
      vocabIndex = 0;
      renderVocabCard(activeCard);
      return;
    }

    vocabIndex = 0;
    if (!vocabCards.length) {
      // A fila é contínua. O backend tenta repor palavras automaticamente;
      // se não houver nenhuma disponível neste instante, tenta novamente
      // depois de um pequeno intervalo em vez de encerrar a atividade.
      if (vocabWordEl) vocabWordEl.textContent = "Carregando novas palavras...";
      if (vocabPosEl) vocabPosEl.textContent = "";
      if (vocabExampleEl) vocabExampleEl.textContent = "";
      if (vocabOptionsEl) vocabOptionsEl.innerHTML = "";
      if (vocabCounterEl) vocabCounterEl.textContent = "";
      setTimeout(() => {
        if (vocabPanel && !vocabPanel.hidden) loadVocabLearn();
      }, 1200);
      return;
    }
    renderVocabCard(vocabCards[0]);
  } catch (err) {
    vocabWordEl.textContent = "Não foi possível carregar";
    vocabExampleEl.textContent = err.message || "Tente novamente.";
    vocabOptionsEl.innerHTML = "";
  }
}

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
    vocabStorageKey = `lit_vocab_active_card_${user.id || "student"}`;

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
    await loadVocabLearn();
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
