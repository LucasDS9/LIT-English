/* ==========================================================================
   LIT English — revisar.js
   Tela de revisão de flashcards (SM-2). Consome:
     GET  /flashcards/review/next
     POST /flashcards/review/{flashcard_id}
   ========================================================================== */

const reviewArea = document.getElementById("review-area");
const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const toastEl = document.getElementById("toast");

let toastTimer = null;
function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.hidden = true;
  }, 2600);
}

document.getElementById("logout-btn").addEventListener("click", () => {
  const ok = window.confirm("Deseja sair da sua conta?");
  if (ok) Auth.logout();
});

// ---------------------------------------------------------------------------
// Sessão de revisão (estado em memória, vive enquanto a página está aberta)
// ---------------------------------------------------------------------------

const session = {
  cards: [],
  index: 0,
  flipped: false,
  remaining: 0,
  limit: 15,
};

// ---------------------------------------------------------------------------
// Áudio (pronúncia em inglês)
// ---------------------------------------------------------------------------
// O áudio é gerado por um serviço de TTS neural (via nosso backend, que
// funciona como proxy — o navegador não consegue chamar o Google Translate
// TTS diretamente por causa de CORS). Caso a requisição falhe (ex: backend
// fora do ar, sem internet), cai de volta para a Web Speech API nativa do
// navegador como reserva.

const audioCache = new Map(); // texto -> URL do blob de áudio já carregado
let currentAudio = null;

function ttsUrl(text) {
  return `/tts/speak?text=${encodeURIComponent(text)}`;
}

async function fetchTtsAudioUrl(text) {
  if (audioCache.has(text)) return audioCache.get(text);

  const blob = await apiFetchBlob(ttsUrl(text));
  const url = URL.createObjectURL(blob);
  audioCache.set(text, url);
  return url;
}

// --- Reserva: Web Speech API nativa do navegador, caso o TTS online falhe ---

let cachedEnglishVoice = null;
let voicesReady = false;

const VOICE_NAME_PRIORITY = [
  "Google US English",
  "Microsoft Aria Online (Natural) - English (United States)",
  "Microsoft Jenny Online (Natural) - English (United States)",
  "Microsoft Guy Online (Natural) - English (United States)",
  "Samantha",
  "Google UK English Female",
  "Google UK English Male",
  "Microsoft Zira",
  "Microsoft David",
];

function pickEnglishVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  for (const name of VOICE_NAME_PRIORITY) {
    const match = voices.find((v) => v.name === name);
    if (match) return match;
  }

  const enUS = voices.find((v) => v.lang === "en-US");
  if (enUS) return enUS;

  const enAny = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("en"));
  if (enAny) return enAny;

  return null;
}

function ensureVoicesLoaded() {
  if (voicesReady || !("speechSynthesis" in window)) return;
  const update = () => {
    cachedEnglishVoice = pickEnglishVoice();
    if (cachedEnglishVoice) voicesReady = true;
  };
  update();
  window.speechSynthesis.onvoiceschanged = update;
}

ensureVoicesLoaded();

function speakWithBrowserFallback(text) {
  if (!("speechSynthesis" in window)) {
    showToast("Não foi possível tocar o áudio.");
    return;
  }

  window.speechSynthesis.cancel();

  if (!cachedEnglishVoice) {
    cachedEnglishVoice = pickEnglishVoice();
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  utterance.pitch = 1;

  if (cachedEnglishVoice) {
    utterance.voice = cachedEnglishVoice;
    utterance.lang = cachedEnglishVoice.lang;
  }

  window.speechSynthesis.speak(utterance);
}

// --- Função principal de áudio, usada pela tela de revisão ---

async function speak(text, btn) {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (btn) btn.disabled = true;

  try {
    const url = await fetchTtsAudioUrl(text);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.addEventListener("ended", () => {
      if (btn) btn.disabled = false;
    });
    audio.addEventListener("error", () => {
      if (btn) btn.disabled = false;
      speakWithBrowserFallback(text);
    });
    await audio.play();
    if (btn) btn.disabled = false;
  } catch (err) {
    if (btn) btn.disabled = false;
    speakWithBrowserFallback(text);
  }
}

function renderStateBox({ icon, title, text, actionLabel, onAction }) {
  reviewArea.innerHTML = "";
  const box = document.createElement("div");
  box.className = "state-box";

  const iconWrap = document.createElement("div");
  iconWrap.className = "state-icon";
  iconWrap.innerHTML = icon;
  box.appendChild(iconWrap);

  const h2 = document.createElement("h2");
  h2.textContent = title;
  box.appendChild(h2);

  const p = document.createElement("p");
  p.textContent = text;
  box.appendChild(p);

  if (actionLabel) {
    const btn = document.createElement("button");
    btn.className = "btn btn-outline";
    btn.style.marginTop = "6px";
    btn.textContent = actionLabel;
    btn.addEventListener("click", onAction);
    box.appendChild(btn);
  }

  reviewArea.appendChild(box);
}

function renderCard() {
  const card = session.cards[session.index];
  reviewArea.innerHTML = "";

  const wrapper = document.createElement("div");

  const cardBox = document.createElement("div");
  cardBox.className = "review-card";

  const counter = document.createElement("div");
  counter.className = "counter";
  counter.textContent = `${session.index + 1} / ${session.cards.length}`;
  cardBox.appendChild(counter);

  const body = document.createElement("div");
  body.className = "card-body";

  const front = document.createElement("p");
  front.className = "front-text";
  front.textContent = card.front;
  body.appendChild(front);

  if (session.flipped) {
    const back = document.createElement("p");
    back.className = "back-text";
    back.textContent = card.back;
    body.appendChild(back);
  }

  const speakBtn = document.createElement("button");
  speakBtn.className = "speak-btn";
  speakBtn.type = "button";
  speakBtn.innerHTML = Icons.volume;
  speakBtn.title = "Ouvir pronúncia";
  speakBtn.addEventListener("click", () => speak(card.front, speakBtn));
  body.appendChild(speakBtn);

  cardBox.appendChild(body);
  wrapper.appendChild(cardBox);

  const actions = document.createElement("div");
  actions.className = "review-actions";

  const flipBtn = document.createElement("button");
  flipBtn.className = "btn btn-outline flip-btn";
  flipBtn.type = "button";
  flipBtn.innerHTML = `${Icons.refresh}<span>${session.flipped ? "Ver frente" : "Virar card"}</span>`;
  flipBtn.addEventListener("click", () => {
    session.flipped = !session.flipped;
    renderCard();
  });
  actions.appendChild(flipBtn);

  if (!session.flipped) {
    const hint = document.createElement("p");
    hint.className = "review-hint";
    hint.innerHTML = `${Icons.info}<span>Tente lembrar a tradução antes de virar</span>`;
    actions.appendChild(hint);
  } else {
    const hint = document.createElement("p");
    hint.className = "review-hint";
    hint.innerHTML = `${Icons.info}<span>Como foi?</span>`;
    actions.appendChild(hint);

    const qualityRow = document.createElement("div");
    qualityRow.className = "quality-row";

    const options = [
      { label: "Esqueci", quality: 0, icon: Icons.frown, solid: true },
      { label: "Difícil", quality: 3, icon: Icons.meh, solid: false },
      { label: "Ok", quality: 4, icon: Icons.smile, solid: false },
      { label: "Fácil", quality: 5, icon: Icons.star, solid: false },
    ];

    options.forEach((opt) => {
      const btn = document.createElement("button");
      btn.className = `quality-btn${opt.solid ? " solid" : ""}`;
      btn.type = "button";
      btn.innerHTML = `${opt.icon}<span>${opt.label}</span>`;
      btn.addEventListener("click", () => submitReview(card.flashcard_id, opt.quality, qualityRow));
      qualityRow.appendChild(btn);
    });

    actions.appendChild(qualityRow);
  }

  wrapper.appendChild(actions);
  reviewArea.appendChild(wrapper);
}

async function submitReview(flashcardId, quality, qualityRow) {
  qualityRow.querySelectorAll("button").forEach((b) => (b.disabled = true));

  try {
    await apiFetch(`/flashcards/review/${flashcardId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quality }),
    });

    session.remaining = Math.max(0, session.remaining - 1);
    session.index += 1;
    session.flipped = false;

    if (session.index >= session.cards.length) {
      renderFinished();
    } else {
      renderCard();
    }
  } catch (err) {
    if (err.status === 429) {
      renderLimitReached();
    } else {
      showToast(err.message || "Não foi possível salvar sua resposta. Tente novamente.");
      qualityRow.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }
  }
}

function renderFinished() {
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Revisão concluída! 🎉",
    text: "Você revisou todos os cards disponíveis por agora. Volte mais tarde para continuar fortalecendo sua memória.",
    actionLabel: "Verificar novamente",
    onAction: loadQueue,
  });
}

function renderEmpty() {
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Você está em dia!",
    text: "Não há nenhum card para revisar agora. Volte mais tarde.",
    actionLabel: "Atualizar",
    onAction: loadQueue,
  });
}

function renderLimitReached() {
  renderStateBox({
    icon: Icons.clock,
    title: "Limite de revisões atingido",
    text: `Você já revisou o máximo de ${session.limit} cards nas últimas 12 horas. Volte mais tarde para continuar.`,
  });
}

function renderPendingApproval() {
  renderStateBox({
    icon: Icons.lock,
    title: "Conta aguardando aprovação",
    text: "Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá começar a revisar seu vocabulário.",
  });
}

function renderNotStudent() {
  renderStateBox({
    icon: Icons.alert,
    title: "Área exclusiva para alunos",
    text: "Esta tela é destinada aos alunos. O painel do professor ainda está em construção.",
  });
}

function renderError(message) {
  renderStateBox({
    icon: Icons.alert,
    title: "Algo deu errado",
    text: message || "Não foi possível carregar sua revisão. Tente novamente.",
    actionLabel: "Tentar novamente",
    onAction: loadQueue,
  });
}

async function loadQueue() {
  reviewArea.innerHTML = '<div class="skeleton">Carregando seus cards...</div>';

  try {
    const data = await apiFetch("/flashcards/review/next");

    session.cards = data.cards;
    session.index = 0;
    session.flipped = false;
    session.remaining = data.remaining_in_window;
    session.limit = data.limit_per_window;

    if (session.remaining <= 0) {
      renderLimitReached();
    } else if (session.cards.length === 0) {
      renderEmpty();
    } else {
      renderCard();
    }
  } catch (err) {
    if (err.status === 403) {
      renderNotStudent();
    } else {
      renderError(err.message);
    }
  }
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------

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

  studentNameEl.textContent = user.name;
  roleLabelEl.textContent = user.role === "professor" ? "PROFESSOR" : "ALUNO";

  if (user.role !== "aluno") {
    window.location.href = "professor.html";
    return;
  }

  if (!user.is_approved) {
    renderPendingApproval();
    return;
  }

  loadQueue();
}

init();
