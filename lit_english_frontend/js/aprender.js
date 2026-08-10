/* ==========================================================================
   LIT English — aprender.js
   Tela "Aprender": treino de vocabulário por reconhecimento (múltipla
   escolha, sempre 4 opções). Consome:
     GET  /vocab-words/learn/next
     POST /vocab-words/learn/{word_id}

   OBS: o clique nas palavras da frase de exemplo (pra ver o significado,
   igual ao Read and Listen) ainda não está aqui — fica pra depois.
   ========================================================================== */

const learnArea = document.getElementById("learn-area");
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
// Sessão de aprendizado (estado em memória, vive enquanto a página está aberta)
// ---------------------------------------------------------------------------

const session = {
  cards: [],
  index: 0,
  answered: false, // true depois que o aluno escolheu uma opção no card atual
};

// ---------------------------------------------------------------------------
// Áudio (pronúncia da palavra isolada — mesma lógica usada em Revisar)
// ---------------------------------------------------------------------------

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

// Toca a pronúncia de UMA palavra isolada (nunca a frase inteira).
async function speakWord(word, btn) {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (btn) btn.disabled = true;

  try {
    const url = await fetchTtsAudioUrl(word);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.addEventListener("ended", () => {
      if (btn) btn.disabled = false;
    });
    audio.addEventListener("error", () => {
      if (btn) btn.disabled = false;
      speakWithBrowserFallback(word);
    });
    await audio.play();
    if (btn) btn.disabled = false;
  } catch (err) {
    if (btn) btn.disabled = false;
    speakWithBrowserFallback(word);
  }
}

// ---------------------------------------------------------------------------
// Helpers de texto
// ---------------------------------------------------------------------------

function escapeHtml(str) {
  return (str || "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
  ));
}

// Envolve a ocorrência da palavra sendo aprendida dentro da frase de exemplo
// em <b>, escapando o resto do texto.
function highlightWord(sentence, word) {
  const safeSentence = escapeHtml(sentence);
  const cleanWord = (word || "").trim();
  if (!cleanWord) return safeSentence;

  const escapedWord = cleanWord.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${escapedWord})`, "i");
  return re.test(safeSentence) ? safeSentence.replace(re, "<b>$1</b>") : safeSentence;
}

// ---------------------------------------------------------------------------
// Estados vazios / erro (mesmo padrão visual do Revisar)
// ---------------------------------------------------------------------------

function renderStateBox({ icon, title, text, actionLabel, onAction }) {
  learnArea.innerHTML = "";
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

  learnArea.appendChild(box);
}

function renderFinished() {
  SFX.play("finish");
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Sessão concluída! 🎉",
    text: "Você passou por todas as palavras disponíveis por agora. Volte mais tarde para continuar aprendendo.",
    actionLabel: "Verificar novamente",
    onAction: loadQueue,
  });
}

function renderEmpty() {
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Você está em dia!",
    text: "Não há nenhuma palavra nova para aprender agora. Volte mais tarde.",
    actionLabel: "Atualizar",
    onAction: loadQueue,
  });
}

function renderPendingApproval() {
  renderStateBox({
    icon: Icons.lock,
    title: "Conta aguardando aprovação",
    text: "Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá começar a aprender vocabulário.",
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
    text: message || "Não foi possível carregar suas palavras. Tente novamente.",
    actionLabel: "Tentar novamente",
    onAction: loadQueue,
  });
}

// ---------------------------------------------------------------------------
// Card de aprendizado
// ---------------------------------------------------------------------------

const STATUS_CLASS = {
  nova: "is-nova",
  em_revisao: "is-em-revisao",
  aprendida: "is-aprendida",
};

function updateStatusLegend(status) {
  document.querySelectorAll(".vocab-status-item").forEach((item) => {
    const dot = item.querySelector(".vocab-status-dot");
    const isCurrent = dot.classList.contains(STATUS_CLASS[status]);
    item.classList.toggle("is-current", isCurrent);
  });
}

function renderCard() {
  const card = session.cards[session.index];
  session.answered = false;
  learnArea.innerHTML = "";
  updateStatusLegend(card.status);

  const cardBox = document.createElement("div");
  cardBox.className = `review-card learn-card status-${card.status}`;

  const body = document.createElement("div");
  body.className = "card-body";

  const word = document.createElement("p");
  word.className = "front-text";
  word.textContent = card.word;
  body.appendChild(word);

  const pos = document.createElement("p");
  pos.className = "learn-pos";
  pos.textContent = card.part_of_speech;
  body.appendChild(pos);

  // Dica de uso, mostrada logo abaixo da palavra principal (usada
  // principalmente pelas saudações, que não têm frase de exemplo).
  if (card.tip) {
    const tip = document.createElement("p");
    tip.className = "learn-tip";
    tip.textContent = card.tip;
    body.appendChild(tip);
  }

  if (card.example_sentence) {
    const divider = document.createElement("div");
    divider.className = "learn-divider";
    body.appendChild(divider);

    const sentence = document.createElement("p");
    sentence.className = "learn-sentence";
    sentence.innerHTML = highlightWord(card.example_sentence, card.word);
    body.appendChild(sentence);
  }

  const speakBtn = document.createElement("button");
  speakBtn.className = "speak-btn learn-speak-btn";
  speakBtn.type = "button";
  speakBtn.innerHTML = Icons.volume;
  speakBtn.title = "Ouvir pronúncia da palavra";
  speakBtn.addEventListener("click", () => speakWord(card.word, speakBtn));
  body.appendChild(speakBtn);

  cardBox.appendChild(body);

  const optionsGrid = document.createElement("div");
  optionsGrid.className = "learn-options";

  card.options.forEach((option) => {
    const btn = document.createElement("button");
    btn.className = "learn-option-btn";
    btn.type = "button";
    btn.textContent = option;
    btn.addEventListener("click", () => selectOption(card, option, btn, optionsGrid));
    optionsGrid.appendChild(btn);
  });

  cardBox.appendChild(optionsGrid);
  learnArea.appendChild(cardBox);
}

async function selectOption(card, selectedOption, btn, optionsGrid) {
  if (session.answered) return;
  session.answered = true;

  optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => (b.disabled = true));
  btn.classList.add("is-selected");

  try {
    const result = await apiFetch(`/vocab-words/learn/${card.word_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_option: selectedOption }),
    });

    SFX.play(result.correct ? "correct" : "wrong");

    optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => {
      if (b.textContent === result.correct_answer) {
        b.classList.add("is-correct");
      } else if (b === btn && !result.correct) {
        b.classList.add("is-wrong");
      }
    });

    setTimeout(() => {
      session.index += 1;
      if (session.index >= session.cards.length) {
        renderFinished();
      } else {
        renderCard();
      }
    }, 1100);
  } catch (err) {
    showToast(err.message || "Não foi possível salvar sua resposta. Tente novamente.");
    optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => (b.disabled = false));
    btn.classList.remove("is-selected");
    session.answered = false;
  }
}

async function loadQueue() {
  learnArea.innerHTML = '<div class="skeleton">Carregando suas palavras...</div>';

  try {
    const data = await apiFetch("/vocab-words/learn/next");

    session.cards = data.cards;
    session.index = 0;

    if (session.cards.length === 0) {
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
