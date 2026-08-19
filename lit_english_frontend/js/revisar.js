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

// Escapa texto antes de inseri-lo em HTML.
// revisar.js é carregado como um módulo/script independente e não carrega
// textos.js, onde existia outra versão dessa função.
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

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
  typingLocked: false,
  targetLanguage: "ingles",
  pronunciationResult: null,
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
  // The "Aprendendo" section can contain cards without a persisted
  // status from the backend. In review/flip mode, treat those cards
  // as Aprendendo when they are not already in Dominando.
  if (!isFlipMode(card)) return false;
  const status = String(card?.status || "").toLowerCase();
  return status === "aprendendo" || (!status && card?.mode !== "type_speak");
}

function listenTextForCard(card) {
  // Sem isso, quando o professor usa o formato "Tópico: frase" no front do
  // flashcard, o áudio lia o rótulo em voz alta junto com a frase (ex: "Future,
  // I will go to the store").
  return splitTopicLabel(card.front).text;
}

function buildReviewAudioControls(card, body, { listenLabel = "Ouvir novamente" } = {}) {
  let pronunciationFeedback = null;

  const { controls, listenBtn, pronounceBtn } = FlashcardPronounce.buildAudioControlsRow({
    listenLabel,
    onListen: () => speak(listenTextForCard(card), listenBtn),
    showPronounce: shouldShowPronounce(card),
    pronounceLabel: "Testar pronúncia",
    onPronounceReady: (btn) => {
      const recorder = FlashcardPronounce.attachRecordButton(btn, {
        recordingLabel: "Parar (5s máx)",
        preparingLabel: "Preparando...",
        onStop: async (blob) => {
          try {
            const result = await FlashcardPronounce.submitAudio(
              blob,
              `/flashcards/review/${card.flashcard_id}/pronounce`
            );
            // O resultado da pronúncia vira o verso do card.
            // O card só muda de lado após o aluno iniciar o teste e receber
            // a análise — nunca automaticamente antes de uma ação do aluno.
            session.pronunciationResult = result;
            session.flipped = true;
            renderCard();
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

  return { listenBtn, pronounceBtn, pronunciationFeedback };
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

// ---------------------------------------------------------------------------
// Flashcards do professor às vezes trazem um rótulo de tópico gramatical
// antes da frase, ex: "Future: I will go to the store". Em vez de mostrar
// isso tudo junto como frase, separamos o rótulo (ex: "Future") pra exibir
// pequeno e em preto acima, e deixamos só a frase em si no destaque grande.
// ---------------------------------------------------------------------------

function splitTopicLabel(text) {
  const raw = (text || "").trim();
  const match = /^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{1,29})\s*:\s*(.+)$/s.exec(raw);
  if (!match) return { label: null, text: raw };
  return { label: match[1].trim(), text: match[2].trim() };
}

// Cria (e anexa em `container`) o parágrafo de frase principal, com o
// rótulo de tópico (se houver) num parágrafo pequeno e preto logo acima.
// `className` é a classe do texto principal (ex: "front-text").
function appendPromptText(container, text, className) {
  const { label, text: mainText } = splitTopicLabel(text);
  const holder = document.createElement("div");
  holder.className = "prompt-text-holder";

  if (label) {
    const labelEl = document.createElement("p");
    labelEl.className = "front-topic-label";
    labelEl.textContent = label;
    holder.appendChild(labelEl);
  }

  const mainEl = document.createElement("p");
  mainEl.className = className;
  mainEl.textContent = mainText;
  holder.appendChild(mainEl);

  container.appendChild(holder);
  return mainEl;
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
  session.pronunciationResult = null;

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

  appendPromptText(body, promptText(card), "front-text");

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

  appendPromptText(body, card.back, "front-text");

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
        preparingLabel: "Preparando...",
        stopLabel: "Gravado — pode refazer",
        disableOnStop: false,
        maxDurationMs: 0,
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

    // Quando a Azure Pronunciation Assessment está disponível, mostra o
    // mesmo analisador visual (score + palavra por palavra) usado em
    // Revisar — tanto no acerto quanto no erro, pra o aluno entender ONDE
    // errou antes de tentar de novo.
    if (result.score != null) {
      FlashcardPronounce.renderAnalyzerPanel(feedback, {
        // renderAnalyzerPanel já separa o rótulo de tópico (ex: "Future:")
        // da frase e mostra os dois: rótulo pequeno em preto acima, frase
        // normal embaixo — então passamos o texto completo, sem cortar nada.
        phraseText: card.front,
        translationText: card.back,
        pronunciationResult: result,
        onListen: (btn) => speak(listenTextForCard(card), btn),
      });
    } else if (result.correct) {
      FlashcardPronounce.showFeedback(feedback, {
        correct: true,
        correct_answer: result.correct_answer,
        transcribed_text: result.transcribed_text,
        reason: result.reason,
      });
    } else {
      feedback.hidden = false;
      feedback.className = "review-type-feedback is-wrong";
      feedback.textContent = result.reason
        ? `Resposta correta: ${result.correct_answer}. ${result.reason}`
        : `Resposta correta: ${result.correct_answer}`;
    }

    if (result.correct) {
      setTimeout(() => advanceToNextCard(), result.score != null ? 2200 : 900);
    } else {
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

function normalizeTargetLanguage(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (["it", "italiano"].includes(raw)) return "italiano";
  if (["fr", "frances", "francês", "français"].includes(raw)) return "frances";
  if (["es", "espanhol", "español"].includes(raw)) return "espanhol";
  if (["de", "alemao", "alemão", "deutsch"].includes(raw)) return "alemao";
  if (["pt", "pt-br", "portugues", "português"].includes(raw)) return "portugues";
  return "ingles";
}

function languageMetaForReview(languageCode) {
  const code = normalizeTargetLanguage(languageCode);
  const labels = {
    ingles: "Inglês",
    italiano: "Italiano",
    frances: "Francês",
    espanhol: "Espanhol",
    alemao: "Alemão",
    portugues: "Português",
  };
  const flags = {
    ingles: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#012169"/><path d="M0 0l24 16M24 0L0 16" stroke="#fff" stroke-width="2.4"/><path d="M0 0l24 16M24 0L0 16" stroke="#C8102E" stroke-width="1.2"/><path d="M12 0v16M0 8h24" stroke="#fff" stroke-width="3.2"/><path d="M12 0v16M0 8h24" stroke="#C8102E" stroke-width="1.6"/></svg>`,
    italiano: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect x="16" width="8" height="16" fill="#CE2B37"/><rect width="8" height="16" fill="#009246"/></svg>`,
    frances: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect width="8" height="16" fill="#0055A4"/><rect x="16" width="8" height="16" fill="#EF4135"/></svg>`,
    espanhol: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#AA151B"/><rect y="4" width="24" height="8" fill="#F1BF00"/></svg>`,
    alemao: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" fill="#000"/><rect y="5.33" width="24" height="5.34" fill="#DD0000"/><rect y="10.66" width="24" height="5.34" fill="#FFCE00"/></svg>`,
    portugues: `<span class="review-language-placeholder">PT</span>`,
  };
  return { code, label: labels[code], flag: flags[code] || flags.ingles };
}

function appendReviewCardHeader(cardBox, card) {
  const header = document.createElement("div");
  header.className = "review-card-header";

  const meta = languageMetaForReview(session.targetLanguage);
  const badge = document.createElement("div");
  badge.className = "review-lang-badge";
  badge.innerHTML = `<span class="review-lang-flag">${meta.flag}</span><span>${meta.label}</span>`;
  header.appendChild(badge);

  const counter = document.createElement("span");
  counter.className = "review-card-counter";
  counter.textContent = `${session.index + 1} / ${session.cards.length}`;
  header.appendChild(counter);

  cardBox.appendChild(header);
}

function reviewMeaningQuestion(word) {
  const safeWord = (word || "").trim();
  switch (normalizeTargetLanguage(session.targetLanguage)) {
    case "italiano":
      return `Cosa significa '${safeWord}'?`;
    case "frances":
      return `Que signifie « ${safeWord} » ?`;
    case "espanhol":
      return `¿Qué significa '${safeWord}'?`;
    case "alemao":
      return `Was bedeutet „${safeWord}“?`;
    case "portugues":
      return `O que significa '${safeWord}'?`;
    default:
      return `What does '${safeWord}' mean?`;
  }
}

function buildReviewDescription(description) {
  const text = String(description || "").trim();
  if (!text) return null;

  const box = document.createElement("div");
  box.className = "review-description";
  box.innerHTML = `
    <span class="review-description-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18h6"/>
        <path d="M10 22h4"/>
        <path d="M8.3 14.8C7.2 13.9 6.5 12.6 6.5 11a5.5 5.5 0 0 1 11 0c0 1.6-.7 2.9-1.8 3.8-.8.7-1.2 1.2-1.2 2.2H9.5c0-1-.4-1.5-1.2-2.2Z"/>
      </svg>
    </span>
    <p>${escapeHtml(text)}</p>
  `;
  return box;
}

function renderFlipCard(card) {
  const wrapper = document.createElement("div");

  const cardBox = document.createElement("div");
  cardBox.className = `review-card review-card-status ${statusClassName(card)}`.trim();

  appendReviewCardHeader(cardBox, card);

  const body = document.createElement("div");
  body.className = "card-body review-flip-body";

  if (session.flipped) {
    const backWrap = document.createElement("div");
    backWrap.className = "review-card-back card-flip-anim";

    if (session.pronunciationResult && shouldShowPronounce(card)) {
      FlashcardPronounce.renderAnalyzerPanel(backWrap, {
        phraseText: card.front,
        translationText: card.back,
        pronunciationResult: session.pronunciationResult,
        onListen: (btn) => speak(listenTextForCard(card), btn),
      });
      body.appendChild(backWrap);
    } else {
      const word = document.createElement("p");
    word.className = `review-back-word ${statusClassName(card)}`.trim();
    word.textContent = card.front;
    backWrap.appendChild(word);

    const divider = document.createElement("div");
    divider.className = "review-card-divider";
    backWrap.appendChild(divider);

    const answer = document.createElement("p");
    answer.className = "learn-back-answer";
    answer.textContent = card.back;
    backWrap.appendChild(answer);

      const description = buildReviewDescription(card.description);
      if (description) backWrap.appendChild(description);

      body.appendChild(backWrap);
    }
  } else {
    appendPromptText(body, card.front, "front-text");

    const question = document.createElement("p");
    question.className = "review-meaning-question";
    question.textContent = reviewMeaningQuestion(splitTopicLabel(card.front).text);
    body.appendChild(question);

    const description = buildReviewDescription(card.description);
    if (description) body.appendChild(description);
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
    if (!session.flipped) session.pronunciationResult = null;
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

  // Terminou o lote inteiro que veio do servidor (até `limit` cards, hoje
  // 15) e ainda sobra espaço na janela de revisão: provavelmente há mais
  // cards devidos esperando, então oferece "Continuar" em vez de dar a
  // sessão por encerrada.
  const finishedFullBatch = session.cards.length >= session.limit;
  const canContinue = finishedFullBatch && session.remaining > 0;

  renderStateBox({
    icon: Icons.checkCircle,
    title: canContinue ? `Você revisou ${session.cards.length} flashcards! 🎉` : "Revisão concluída! 🎉",
    text: canContinue
      ? "Mandou bem! Ainda há mais cards esperando por você agora — quer continuar revisando?"
      : "Você revisou todos os cards disponíveis por agora. Volte mais tarde para continuar fortalecendo sua memória.",
    actionLabel: canContinue ? "Continuar" : "Verificar novamente",
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
    actionLabel: "Verificar novamente",
    onAction: loadQueue,
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

    if (data.showcase_started) {
      showToast("Prévia especial: 3 palavras foram direto pro Dominando! 🚀");
    }

    if (data.blocked_by === "exercises") {
      renderStateBox({
        icon: Icons.alert,
        title: "Exercícios prioritários",
        text:
          data.blocked_message ||
          "Complete os exercícios atribuídos pelo professor antes de revisar flashcards.",
        actionLabel: "Ir para exercícios",
        onAction: () => {
          window.location.href = "exercicios.html";
        },
      });
    } else if (session.remaining <= 0 && session.cards.length === 0) {
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
  session.targetLanguage = normalizeTargetLanguage(user.target_language || "ingles");

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