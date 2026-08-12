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

document.getElementById("add-flashcard-btn").addEventListener("click", openAddFlashcardModal);

// ---------------------------------------------------------------------------
// Sessão de revisão (estado em memória, vive enquanto a página está aberta)
// ---------------------------------------------------------------------------

const session = {
  cards: [],
  index: 0,
  flipped: false,
  remaining: 0,
  limit: 15,
  typingLocked: false,
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

function shouldShowPronounce(card) {
  return isFlipMode(card) && card.status === "concluido";
}

function listenTextForCard(card) {
  return card.front;
}

function buildReviewAudioControls(card, body, { listenLabel = "Ouvir novamente" } = {}) {
  let pronunciationFeedback = null;

  const { controls, listenBtn, pronounceBtn } = FlashcardPronounce.buildAudioControlsRow({
    listenLabel,
    onListen: () => speak(listenTextForCard(card), listenBtn),
    showPronounce: shouldShowPronounce(card),
    pronounceLabel: "Pronunciar",
    onPronounceReady: (btn) => {
      const recorder = FlashcardPronounce.attachRecordButton(btn, {
        onStop: async (blob) => {
          try {
            const result = await FlashcardPronounce.submitAudio(
              blob,
              `/flashcards/review/${card.flashcard_id}/pronounce`
            );
            FlashcardPronounce.showFeedback(pronunciationFeedback, result);
            SFX.play(result.correct ? "correct" : "wrong");
          } catch (err) {
            showToast(err.message || "Não foi possível analisar a pronúncia.");
          } finally {
            recorder.reset();
          }
        },
        onError: (err) => showToast(err.message || "Permissão de microfone negada."),
      });
    },
  });

  body.appendChild(controls);

  if (shouldShowPronounce(card)) {
    pronunciationFeedback = document.createElement("div");
    pronunciationFeedback.className = "review-pronunciation-feedback";
    pronunciationFeedback.hidden = true;
    body.appendChild(pronunciationFeedback);
  }

  return { listenBtn, pronounceBtn, pronunciationFeedback };
}

// ---------------------------------------------------------------------------
// "Adicionar flashcard" — aluno cria o próprio flashcard.
// Verso é opcional: se ficar em branco, o backend gera a tradução
// automaticamente (na língua-alvo certa: inglês no curso normal, ou a
// língua do Acesso Especial, ex.: italiano).
// ---------------------------------------------------------------------------

const FIELD_MAX_LENGTH = 200;

function isReviewSessionActive() {
  return session.cards.length > 0 && session.index < session.cards.length;
}

function buildCounterField({ id, labelText, hintText, placeholder }) {
  const field = document.createElement("div");
  field.className = "field";

  const label = document.createElement("label");
  label.setAttribute("for", id);
  label.textContent = labelText;
  field.appendChild(label);

  const hint = document.createElement("p");
  hint.className = "field-hint";
  hint.textContent = hintText;
  field.appendChild(hint);

  const textarea = document.createElement("textarea");
  textarea.id = id;
  textarea.maxLength = FIELD_MAX_LENGTH;
  textarea.placeholder = placeholder;
  field.appendChild(textarea);

  const counter = document.createElement("span");
  counter.className = "field-char-count";
  counter.textContent = `0/${FIELD_MAX_LENGTH}`;
  field.appendChild(counter);

  textarea.addEventListener("input", () => {
    counter.textContent = `${textarea.value.length}/${FIELD_MAX_LENGTH}`;
  });

  return { field, textarea, counter };
}

function openAddFlashcardModal() {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  const modal = document.createElement("div");
  modal.className = "modal";

  const header = document.createElement("div");
  header.className = "modal-header";
  const h2 = document.createElement("h2");
  h2.textContent = "Adicionar flashcard";
  header.appendChild(h2);
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "icon-btn";
  closeBtn.innerHTML = Icons.x;
  closeBtn.addEventListener("click", () => overlay.remove());
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const form = document.createElement("form");

  const { field: frontField, textarea: frontInput } = buildCounterField({
    id: "flashcard-front",
    labelText: "Frente",
    hintText: "Escreva o termo ou frase na língua alvo.",
    placeholder: "Ex: It's a beautiful day.",
  });
  form.appendChild(frontField);

  const { field: backField, textarea: backInput } = buildCounterField({
    id: "flashcard-back",
    labelText: "Verso",
    hintText: "Escreva a tradução ou o significado.",
    placeholder: "Ex: É um dia lindo.",
  });
  form.appendChild(backField);

  const note = document.createElement("div");
  note.className = "field-note";
  note.innerHTML = `${Icons.alert}<span>Se você não preencher o verso, um flashcard será gerado automaticamente para você.</span>`;
  form.appendChild(note);

  const errorBox = document.createElement("p");
  errorBox.className = "form-error";
  errorBox.hidden = true;
  form.appendChild(errorBox);

  const actions = document.createElement("div");
  actions.className = "modal-actions";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-outline";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", () => overlay.remove());
  actions.appendChild(cancelBtn);

  const addBtn = document.createElement("button");
  addBtn.type = "submit";
  addBtn.className = "btn btn-primary";
  addBtn.textContent = "Adicionar";
  actions.appendChild(addBtn);

  form.appendChild(actions);
  modal.appendChild(form);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  frontInput.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.hidden = true;

    const front = frontInput.value.trim();
    if (!front) {
      errorBox.textContent = "Escreva o termo ou frase na língua-alvo.";
      errorBox.hidden = false;
      return;
    }

    addBtn.disabled = true;
    addBtn.textContent = "Adicionando...";

    try {
      await apiFetch("/flashcards/self-add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ front, back: backInput.value.trim() }),
      });

      overlay.remove();
      showToast("Flashcard adicionado!");

      // Se o aluno não estiver no meio de uma sessão de revisão, atualiza a
      // fila agora pra já mostrar o card novo (ele pode já estar "devido").
      if (!isReviewSessionActive()) {
        loadQueue();
      }
    } catch (err) {
      errorBox.textContent = err.message || "Não foi possível adicionar o flashcard. Tente novamente.";
      errorBox.hidden = false;
      addBtn.disabled = false;
      addBtn.textContent = "Adicionar";
    }
  });
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

const STATUS_CLASS = {
  aprendendo: "is-aprendendo",
  dominando: "is-dominando",
  concluido: "is-concluido",
};

function isFlipMode(card) {
  return !card.mode || card.mode === "flip";
}

function isTypePtMode(card) {
  return card.mode === "type_pt";
}

function isSpeakMode(card) {
  return card.mode === "type_speak" || card.mode === "type_target";
}

function promptText(card) {
  return card.front;
}

function updateStatusLegend(status) {
  document.querySelectorAll(".vocab-status-item").forEach((item) => {
    const dot = item.querySelector(".vocab-status-dot");
    const isCurrent = status && dot.classList.contains(STATUS_CLASS[status]);
    item.classList.toggle("is-current", isCurrent);
  });
}

function statusClassName(card) {
  return card.status ? `status-${card.status}` : "";
}

function advanceToNextCard() {
  session.remaining = Math.max(0, session.remaining - 1);
  session.index += 1;
  session.flipped = false;
  session.typingLocked = false;
  session.speakLocked = false;

  if (session.index >= session.cards.length) {
    renderFinished();
  } else {
    renderCard();
  }
}

function renderCard() {
  const card = session.cards[session.index];
  reviewArea.innerHTML = "";
  updateStatusLegend(card.status);

  if (isTypePtMode(card)) {
    renderTypeCard(card);
  } else if (isSpeakMode(card)) {
    renderSpeakCard(card);
  } else {
    renderFlipCard(card);
  }
}

function renderTypeCard(card) {
  const wrapper = document.createElement("div");

  const cardBox = document.createElement("div");
  cardBox.className = `review-card review-card-status ${statusClassName(card)}`.trim();

  const counter = document.createElement("div");
  counter.className = "counter";
  counter.textContent = `${session.index + 1} / ${session.cards.length}`;
  cardBox.appendChild(counter);

  const body = document.createElement("div");
  body.className = "card-body";

  const prompt = document.createElement("p");
  prompt.className = "front-text";
  prompt.textContent = promptText(card);
  body.appendChild(prompt);

  const hint = document.createElement("p");
  hint.className = "review-hint";
  hint.style.margin = "0";
  hint.textContent = "Digite a tradução em português";
  body.appendChild(hint);

  const input = document.createElement("input");
  input.type = "text";
  input.className = "review-type-input";
  input.autocomplete = "off";
  input.placeholder = "Tradução em português";
  body.appendChild(input);

  const feedback = document.createElement("p");
  feedback.className = "review-type-feedback";
  feedback.hidden = true;
  body.appendChild(feedback);

  const { listenBtn } = buildReviewAudioControls(card, body);

  cardBox.appendChild(body);
  wrapper.appendChild(cardBox);

  const actions = document.createElement("div");
  actions.className = "review-type-actions";

  const submitBtn = document.createElement("button");
  submitBtn.className = "btn btn-primary";
  submitBtn.type = "button";
  submitBtn.textContent = "Verificar";
  submitBtn.addEventListener("click", () =>
    submitTypedAnswer(card, input, feedback, submitBtn)
  );
  actions.appendChild(submitBtn);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !session.typingLocked) {
      submitTypedAnswer(card, input, feedback, submitBtn);
    }
  });

  wrapper.appendChild(actions);
  reviewArea.appendChild(wrapper);

  input.focus();
  speak(listenTextForCard(card), listenBtn);
}

function renderSpeakCard(card) {
  const wrapper = document.createElement("div");

  const cardBox = document.createElement("div");
  cardBox.className = `review-card review-card-status ${statusClassName(card)}`.trim();

  const counter = document.createElement("div");
  counter.className = "counter";
  counter.textContent = `${session.index + 1} / ${session.cards.length}`;
  cardBox.appendChild(counter);

  const body = document.createElement("div");
  body.className = "card-body";

  const prompt = document.createElement("p");
  prompt.className = "front-text";
  prompt.textContent = card.back;
  body.appendChild(prompt);

  const hint = document.createElement("p");
  hint.className = "review-hint";
  hint.style.margin = "0";
  hint.textContent = "Fale a frase na língua-alvo";
  body.appendChild(hint);

  const feedback = document.createElement("div");
  feedback.className = "review-pronunciation-feedback";
  feedback.hidden = true;
  body.appendChild(feedback);

  let recordedBlob = null;
  let speakLocked = false;

  const { controls, listenBtn } = FlashcardPronounce.buildAudioControlsRow({
    listenLabel: "Ouvir novamente",
    onListen: () => speak(listenTextForCard(card), listenBtn),
    showPronounce: true,
    pronounceLabel: "Gravar",
    onPronounceReady: (recordBtn) => {
      FlashcardPronounce.attachRecordButton(recordBtn, {
        recordingLabel: "Parar",
        idleLabel: "Gravar",
        stopLabel: "Gravado — pode refazer",
        disableOnStop: false,
        onStop: (blob) => {
          recordedBlob = blob;
        },
        onError: (err) => showToast(err.message || "Permissão de microfone negada."),
      });
    },
  });
  body.appendChild(controls);

  cardBox.appendChild(body);
  wrapper.appendChild(cardBox);

  const actions = document.createElement("div");
  actions.className = "review-type-actions";

  const submitBtn = document.createElement("button");
  submitBtn.className = "btn btn-primary";
  submitBtn.type = "button";
  submitBtn.textContent = "Verificar";
  submitBtn.addEventListener("click", () =>
    submitSpeakAnswer(card, () => recordedBlob, feedback, submitBtn, () => speakLocked, (v) => { speakLocked = v; })
  );
  actions.appendChild(submitBtn);

  wrapper.appendChild(actions);
  reviewArea.appendChild(wrapper);
}

async function submitSpeakAnswer(card, getBlob, feedback, submitBtn, getLocked, setLocked) {
  if (getLocked()) return;

  const blob = getBlob();
  if (!blob) {
    showToast("Grave sua pronúncia antes de verificar.");
    return;
  }

  setLocked(true);
  submitBtn.disabled = true;

  try {
    const result = await FlashcardPronounce.submitAudio(
      blob,
      `/flashcards/review/${card.flashcard_id}/submit-speak`
    );

    SFX.play(result.correct ? "correct" : "wrong");

    if (result.correct) {
      FlashcardPronounce.showFeedback(feedback, {
        correct: true,
        correct_answer: result.correct_answer,
        transcribed_text: result.transcribed_text,
        reason: result.reason,
      });
      setTimeout(() => advanceToNextCard(), 900);
    } else {
      feedback.hidden = false;
      feedback.className = "review-type-feedback is-wrong";
      feedback.textContent = result.reason
        ? `Resposta correta: ${result.correct_answer}. ${result.reason}`
        : `Resposta correta: ${result.correct_answer}`;
      setLocked(false);
      submitBtn.disabled = false;
    }
  } catch (err) {
    if (err.status === 429) {
      renderLimitReached();
    } else {
      showToast(err.message || "Não foi possível salvar sua resposta. Tente novamente.");
      setLocked(false);
      submitBtn.disabled = false;
    }
  }
}

function renderFlipCard(card) {
  const wrapper = document.createElement("div");

  const cardBox = document.createElement("div");
  cardBox.className = `review-card review-card-status ${statusClassName(card)}`.trim();

  const counter = document.createElement("div");
  counter.className = "counter";
  counter.textContent = `${session.index + 1} / ${session.cards.length}`;
  cardBox.appendChild(counter);

  const body = document.createElement("div");
  body.className = "card-body";

  if (session.flipped) {
    const backWrap = document.createElement("div");
    backWrap.className = "review-card-back card-flip-anim";

    const word = document.createElement("p");
    word.className = `review-back-word ${statusClassName(card)}`.trim();
    word.textContent = card.front;
    backWrap.appendChild(word);

    const answer = document.createElement("p");
    answer.className = "learn-back-answer";
    answer.textContent = card.back;
    backWrap.appendChild(answer);

    if (card.explanation) {
      const dot = document.createElement("span");
      dot.className = "learn-back-dot";
      backWrap.appendChild(dot);

      const explanation = document.createElement("p");
      explanation.className = "learn-back-explanation";
      explanation.textContent = card.explanation;
      backWrap.appendChild(explanation);
    }

    body.appendChild(backWrap);
  } else {
    const front = document.createElement("p");
    front.className = "front-text";
    front.textContent = card.front;
    body.appendChild(front);
  }

  const { listenBtn } = buildReviewAudioControls(card, body);

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
    hint.textContent = "Tente lembrar a tradução antes de virar";
    actions.appendChild(hint);
  } else {
    const hint = document.createElement("p");
    hint.className = "review-hint";
    hint.textContent = "Como foi?";
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

  if (!session.flipped) {
    speak(listenTextForCard(card), listenBtn);
  }
}

async function submitTypedAnswer(card, input, feedback, submitBtn) {
  if (session.typingLocked) return;

  const typed = input.value.trim();
  if (!typed) {
    showToast("Digite sua resposta antes de verificar.");
    return;
  }

  session.typingLocked = true;
  submitBtn.disabled = true;
  input.disabled = true;

  try {
    const result = await apiFetch(`/flashcards/review/${card.flashcard_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ typed_answer: typed }),
    });

    SFX.play(result.correct ? "correct" : "wrong");

    feedback.hidden = false;
    feedback.classList.toggle("is-correct", result.correct);
    feedback.classList.toggle("is-wrong", !result.correct);
    if (result.correct) {
      feedback.textContent = "Correto!";
    } else if (result.reason) {
      feedback.textContent = `Resposta correta: ${result.correct_answer}. ${result.reason}`;
    } else {
      feedback.textContent = `Resposta correta: ${result.correct_answer}`;
    }

    setTimeout(() => advanceToNextCard(), 900);
  } catch (err) {
    if (err.status === 429) {
      renderLimitReached();
    } else {
      showToast(err.message || "Não foi possível salvar sua resposta. Tente novamente.");
      session.typingLocked = false;
      submitBtn.disabled = false;
      input.disabled = false;
    }
  }
}

async function submitReview(flashcardId, quality, qualityRow) {
  qualityRow.querySelectorAll("button").forEach((b) => (b.disabled = true));

  try {
    await apiFetch(`/flashcards/review/${flashcardId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quality }),
    });

    advanceToNextCard();
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
  SFX.play("finish");
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
