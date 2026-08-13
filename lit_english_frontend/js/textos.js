/* ==========================================================================
   LIT English — textos.js
   Tela "Read and Listen" do aluno. Consome:
     GET /texts        (lista)
     GET /texts/{id}   (detalhe)
     GET /tts/speak     (áudio, via proxy do backend)

   O TTS do backend corta o texto em ~200 caracteres por chamada, então
   textos longos são divididos em frases. Antes de iniciar a reprodução,
   TODOS os trechos são buscados e decodificados (Web Audio API) e depois
   concatenados em um único AudioBuffer contínuo — a "faixa" toca de uma vez
   só, sem pausas entre frases. Isso também permite marcar com uma sombra
   vermelha a palavra correspondente ao instante exato da fala (estimando o
   tempo de cada palavra pela duração real de cada trecho, distribuída
   proporcionalmente ao tamanho de cada palavra). Pausar para o áudio de
   verdade (stop do source node) e retomar continua de onde parou.
   ========================================================================== */

const textsArea = document.getElementById("texts-area");
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

function excerptOf(text, maxLen = 130) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= maxLen) return clean;
  return clean.slice(0, maxLen).trimEnd() + "…";
}

// Divide o texto em frases (limite seguro para o TTS, que corta em ~200 chars).
const TTS_CHUNK_MAX = 180;

// Regex de palavra — usada na segmentação, no player e no corpo clicável.
const WORD_ONLY_RE = /[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*/g;

function splitIntoChunks(text) {
  const normalized = (text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return [];

  // Primeiro separa por frases; depois, se uma frase ainda for muito longa,
  // quebra também por vírgulas/espaços para não passar do limite do TTS.
  const sentences = normalized.match(/[^.!?]+[.!?]*\s*/g) || [normalized];

  const chunks = [];
  sentences.forEach((sentence) => {
    const trimmed = sentence.trim();
    if (!trimmed) return;

    if (trimmed.length <= TTS_CHUNK_MAX) {
      chunks.push(trimmed);
      return;
    }

    // Frase longa demais: quebra em pedaços por palavras.
    const words = trimmed.split(" ");
    let current = "";
    words.forEach((word) => {
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length > TTS_CHUNK_MAX && current) {
        chunks.push(current);
        current = word;
      } else {
        current = candidate;
      }
    });
    if (current) chunks.push(current);
  });

  return chunks;
}

// ---------------------------------------------------------------------------
// Segmentação semântica para o Listening Mode (unidades naturais de sentido)
// ---------------------------------------------------------------------------

function countWords(text) {
  return (text.match(WORD_ONLY_RE) || []).length;
}

const LISTENING_CONJ_RE = /\s+(?:and|but|or|nor|yet|so|through|because|although|while|when|if|that|which|who|where|as|before|after|until|since|though|even though|in order to|so that)\s+/i;

function splitAtNaturalBreaks(sentence) {
  const parts = [];
  let remaining = sentence.trim();
  if (!remaining) return parts;

  while (remaining) {
    let bestIdx = -1;

    const commaMatch = remaining.match(/,\s+/);
    if (commaMatch && commaMatch.index > 0) {
      bestIdx = commaMatch.index + commaMatch[0].length;
    }

    const semiMatch = remaining.match(/;\s+/);
    if (semiMatch && semiMatch.index > 0 && (bestIdx < 0 || semiMatch.index < bestIdx)) {
      bestIdx = semiMatch.index + semiMatch[0].length;
    }

    const dashMatch = remaining.match(/\s+[—–]\s+/);
    if (dashMatch && dashMatch.index > 0 && (bestIdx < 0 || dashMatch.index < bestIdx)) {
      bestIdx = dashMatch.index + dashMatch[0].length;
    }

    const conjMatch = remaining.match(LISTENING_CONJ_RE);
    if (conjMatch && conjMatch.index > 0 && (bestIdx < 0 || conjMatch.index < bestIdx)) {
      bestIdx = conjMatch.index + conjMatch[0].length;
    }

    if (bestIdx < 0) {
      parts.push(remaining.trim());
      break;
    }

    parts.push(remaining.slice(0, bestIdx).trim());
    remaining = remaining.slice(bestIdx).trim();
  }

  return parts.filter(Boolean);
}

function splitByWordCount(text, minWords, maxWords) {
  const words = text.match(WORD_ONLY_RE) || [];
  if (words.length <= maxWords) return [text.trim()];

  const result = [];
  let i = 0;
  while (i < words.length) {
    let take = Math.min(maxWords, words.length - i);
    const remaining = words.length - i - take;
    if (remaining > 0 && remaining < minWords) {
      take = words.length - i - minWords;
      if (take < minWords) take = words.length - i;
    }
    result.push(words.slice(i, i + take).join(" "));
    i += take;
  }
  return result;
}

function splitLongSentenceForListening(sentence) {
  const trimmed = sentence.trim();
  const wordCount = countWords(trimmed);
  if (wordCount <= 12) return [trimmed];

  const clauses = splitAtNaturalBreaks(trimmed);
  const merged = [];
  let buffer = "";
  let bufferWords = 0;

  clauses.forEach((clause) => {
    const cw = countWords(clause);
    if (!buffer) {
      buffer = clause;
      bufferWords = cw;
      return;
    }

    if (bufferWords + cw <= 12 && bufferWords < 6) {
      buffer = `${buffer} ${clause}`.replace(/\s+/g, " ").trim();
      bufferWords += cw;
      return;
    }

    if (bufferWords > 12) {
      merged.push(...splitByWordCount(buffer, 6, 12));
    } else {
      merged.push(buffer);
    }
    buffer = clause;
    bufferWords = cw;
  });

  if (buffer) {
    if (bufferWords > 12) {
      merged.push(...splitByWordCount(buffer, 6, 12));
    } else {
      merged.push(buffer);
    }
  }

  return merged.filter(Boolean);
}

function splitIntoListeningSegments(text) {
  const normalized = (text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return [];

  const sentences = normalized.match(/[^.!?]+[.!?]*\s*/g) || [normalized];
  const segments = [];

  sentences.forEach((sentence) => {
    const trimmed = sentence.trim();
    if (!trimmed) return;

    if (countWords(trimmed) <= 12) {
      segments.push(trimmed);
    } else {
      segments.push(...splitLongSentenceForListening(trimmed));
    }
  });

  return segments;
}

function buildSegmentTimings(segments, wordSpans, wordTimings) {
  let spanIdx = 0;
  return segments.map((segmentText) => {
    const segWords = segmentText.match(WORD_ONLY_RE) || [];
    const spans = [];
    segWords.forEach(() => {
      if (spanIdx < wordSpans.length) {
        spans.push(wordSpans[spanIdx]);
        spanIdx += 1;
      }
    });

    const firstTiming = spans.length
      ? wordTimings.find((t) => t.span === spans[0])
      : null;
    const lastTiming = spans.length
      ? wordTimings.find((t) => t.span === spans[spans.length - 1])
      : null;

    return {
      text: segmentText,
      spans,
      start: firstTiming ? firstTiming.start : 0,
      end: lastTiming ? lastTiming.end : 0,
    };
  });
}

function renderStateBox(container, { icon, title, text, actionLabel, onAction }) {
  container.innerHTML = "";
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

  container.appendChild(box);
}

// ---------------------------------------------------------------------------
// Lista de textos
// ---------------------------------------------------------------------------

async function renderTextList() {
  stopReadingHeartbeat();
  closeWordPopup();
  textsArea.innerHTML = '<div class="skeleton">Carregando textos...</div>';

  let texts;
  try {
    texts = await apiFetch("/texts");
  } catch (err) {
    if (err.status === 403) {
      renderStateBox(textsArea, {
        icon: Icons.lock,
        title: "Conta aguardando aprovação",
        text: "Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá acessar os textos.",
      });
    } else {
      renderStateBox(textsArea, {
        icon: Icons.alert,
        title: "Algo deu errado",
        text: err.message || "Não foi possível carregar os textos. Tente novamente.",
        actionLabel: "Tentar novamente",
        onAction: renderTextList,
      });
    }
    return;
  }

  if (texts.length === 0) {
    renderStateBox(textsArea, {
      icon: Icons.bookOpen,
      title: "Nenhum texto disponível ainda",
      text: "Quando seu professor publicar um texto, ele aparece aqui para você ler e ouvir.",
    });
    return;
  }

  textsArea.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "texts-grid";

  texts.forEach((text) => {
    const card = document.createElement("button");
    card.className = "text-card";
    card.type = "button";

    const top = document.createElement("div");
    top.className = "text-card-top";
    const h3 = document.createElement("h3");
    h3.textContent = text.title;
    top.appendChild(h3);
    const levelBadge = document.createElement("span");
    levelBadge.className = "level-badge";
    levelBadge.textContent = text.level;
    top.appendChild(levelBadge);
    card.appendChild(top);

    const excerpt = document.createElement("p");
    excerpt.className = "excerpt";
    excerpt.textContent = excerptOf(text.content);
    card.appendChild(excerpt);

    card.addEventListener("click", () => openText(text.id));
    grid.appendChild(card);
  });

  textsArea.appendChild(grid);
}

// ---------------------------------------------------------------------------
// Popup de vocabulário: clique em palavra do texto -> tradução + frase
// contextualizada (POST /texts/word-lookup), pronúncia da palavra via TTS
// e "Salvar frase nos flashcards" (POST /flashcards/self-add).
// ---------------------------------------------------------------------------

// Cache de áudio da pronúncia de palavras isoladas (independente da faixa
// contínua do player principal).
const wordAudioBlobUrls = new Map();
let activeWordAudioEl = null;

function stopWordAudio() {
  if (activeWordAudioEl) {
    activeWordAudioEl.pause();
    activeWordAudioEl.currentTime = 0;
    activeWordAudioEl = null;
  }
}

async function getWordAudioUrl(word) {
  if (wordAudioBlobUrls.has(word)) return wordAudioBlobUrls.get(word);
  const blob = await apiFetchBlob(ttsUrl(word));
  const url = URL.createObjectURL(blob);
  wordAudioBlobUrls.set(word, url);
  return url;
}

async function playWordAudio(word, playBtn) {
  if (playBtn.disabled) return;
  stopWordAudio();
  playBtn.disabled = true;
  playBtn.classList.add("is-loading");

  try {
    const url = await getWordAudioUrl(word);
    const audio = new Audio(url);
    activeWordAudioEl = audio;
    audio.addEventListener("ended", () => {
      activeWordAudioEl = null;
      playBtn.disabled = false;
      playBtn.classList.remove("is-loading");
    });
    await audio.play();
  } catch (err) {
    activeWordAudioEl = null;
    playBtn.disabled = false;
    playBtn.classList.remove("is-loading");
    showToast(err.message || "Não foi possível tocar o áudio da palavra.");
  }
}

let activeWordPopup = null; // { overlay, popup, wordSpan, escHandler }

function escapeHtml(str) {
  return (str || "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
  ));
}

// Envolve a ocorrência de `term` dentro de `sentence` em <b>, escapando o
// resto do texto (o conteúdo vem da IA, não é HTML confiável).
function highlightTerm(sentence, term) {
  const safeSentence = escapeHtml(sentence);
  const cleanTerm = (term || "").trim();
  if (!cleanTerm) return safeSentence;

  const escapedTerm = cleanTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${escapedTerm})`, "i");
  return re.test(safeSentence) ? safeSentence.replace(re, "<b>$1</b>") : safeSentence;
}

function closeWordPopup() {
  if (!activeWordPopup) return;
  const { overlay, wordSpan, escHandler } = activeWordPopup;
  overlay.remove();
  wordSpan.classList.remove("is-active");
  document.removeEventListener("keydown", escHandler);
  activeWordPopup = null;
}

function positionWordPopup(popup, anchorSpan) {
  const margin = 12;
  const rect = anchorSpan.getBoundingClientRect();
  const popupRect = popup.getBoundingClientRect();
  const width = popupRect.width || 320;
  const height = popupRect.height || 160;

  let left = rect.left;
  left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

  let top = rect.bottom + 8;
  if (top + height > window.innerHeight - margin) {
    top = Math.max(margin, rect.top - height - 8);
  }

  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;
}

function buildWordPopupShell(word) {
  const overlay = document.createElement("div");
  overlay.className = "word-popup-overlay";

  const popup = document.createElement("div");
  popup.className = "word-popup";

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "word-popup-close";
  closeBtn.innerHTML = Icons.x;
  closeBtn.setAttribute("aria-label", "Fechar");
  closeBtn.addEventListener("click", closeWordPopup);
  popup.appendChild(closeBtn);

  const header = document.createElement("div");
  header.className = "word-popup-header";

  const title = document.createElement("h3");
  title.className = "word-popup-title";
  title.textContent = word.toLowerCase();
  header.appendChild(title);

  const playBtn = document.createElement("button");
  playBtn.type = "button";
  playBtn.className = "word-popup-play";
  playBtn.innerHTML = Icons.play;
  playBtn.setAttribute("aria-label", "Ouvir pronúncia da palavra");
  playBtn.addEventListener("click", () => {
    playWordAudio(word, playBtn);
  });
  header.appendChild(playBtn);

  popup.appendChild(header);

  const body = document.createElement("div");
  body.className = "word-popup-body";
  popup.appendChild(body);

  overlay.appendChild(popup);
  return { overlay, popup, body };
}

function renderWordPopupLoading(body) {
  body.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "word-popup-loading";
  wrap.style.marginTop = "16px";
  ["60%", "92%", "78%", "45%"].forEach((w) => {
    const bar = document.createElement("div");
    bar.className = "word-popup-skel";
    bar.style.width = w;
    wrap.appendChild(bar);
  });
  body.appendChild(wrap);
}

function renderWordPopupError(body, message, onRetry) {
  body.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "word-popup-section word-popup-error";

  const p = document.createElement("p");
  p.textContent = message || "Não foi possível consultar esta palavra agora.";
  wrap.appendChild(p);

  const retryBtn = document.createElement("button");
  retryBtn.type = "button";
  retryBtn.className = "btn btn-outline btn-sm";
  retryBtn.innerHTML = `${Icons.refresh}<span>Tentar de novo</span>`;
  retryBtn.addEventListener("click", onRetry);
  wrap.appendChild(retryBtn);

  body.appendChild(wrap);
}

function renderWordPopupContent(body, data) {
  body.innerHTML = "";

  const translationSection = document.createElement("div");
  translationSection.className = "word-popup-section";
  const translationLabel = document.createElement("p");
  translationLabel.className = "word-popup-label";
  translationLabel.innerHTML = `${Icons.translate}<span>Tradução</span>`;
  translationSection.appendChild(translationLabel);
  const translationText = document.createElement("p");
  translationText.className = "word-popup-translation";
  translationText.textContent = data.translation;
  translationSection.appendChild(translationText);
  body.appendChild(translationSection);

  const exampleSection = document.createElement("div");
  exampleSection.className = "word-popup-section";
  const exampleLabel = document.createElement("p");
  exampleLabel.className = "word-popup-label";
  exampleLabel.innerHTML = `${Icons.quote}<span>Frase contextualizada</span>`;
  exampleSection.appendChild(exampleLabel);

  const enP = document.createElement("p");
  enP.className = "word-popup-example";
  enP.innerHTML = highlightTerm(data.example_en, data.word);
  exampleSection.appendChild(enP);

  const ptP = document.createElement("p");
  ptP.className = "word-popup-example";
  ptP.innerHTML = highlightTerm(data.example_pt, data.translation);
  exampleSection.appendChild(ptP);

  body.appendChild(exampleSection);

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "word-popup-save";
  saveBtn.innerHTML = `${Icons.plus}<span>Salvar frase nos flashcards</span>`;
  saveBtn.addEventListener("click", () => {
    saveWordAsFlashcard(saveBtn, data.example_en, data.example_pt);
  });
  body.appendChild(saveBtn);
}

function saveWordAsFlashcard(saveBtn, front, back) {
  if (saveBtn.disabled) return;
  saveBtn.disabled = true;
  saveBtn.innerHTML = `${Icons.refresh}<span>Salvando...</span>`;

  apiFetch("/flashcards/self-add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ front, back }),
  })
    .then(() => {
      saveBtn.innerHTML = `${Icons.checkSmall}<span>Salvo nos flashcards</span>`;
      showToast("Frase salva nos seus flashcards!");
    })
    .catch((err) => {
      saveBtn.disabled = false;
      saveBtn.innerHTML = `${Icons.plus}<span>Salvar frase nos flashcards</span>`;
      showToast(err.message || "Não foi possível salvar a frase agora.");
    });
}

function getWordContext(wordSpan, container) {
  const allWords = Array.from(container.querySelectorAll(".word"));
  const idx = allWords.indexOf(wordSpan);
  const contextBefore = allWords
    .slice(Math.max(0, idx - 3), idx)
    .map((s) => s.textContent)
    .join(" ");
  const contextAfter = allWords
    .slice(idx + 1, idx + 4)
    .map((s) => s.textContent)
    .join(" ");
  return {
    context_before: contextBefore || undefined,
    context_after: contextAfter || undefined,
  };
}

function openWordPopup(wordSpan, word, sentence, textId, contextBefore, contextAfter) {
  closeWordPopup();
  wordSpan.classList.add("is-active");

  const { overlay, popup, body } = buildWordPopupShell(word);
  document.body.appendChild(overlay);

  const escHandler = (e) => {
    if (e.key === "Escape") closeWordPopup();
  };
  document.addEventListener("keydown", escHandler);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeWordPopup();
  });

  activeWordPopup = { overlay, popup, wordSpan, escHandler };

  function fetchAndRender() {
    renderWordPopupLoading(body);
    positionWordPopup(popup, wordSpan);

    apiFetch("/texts/word-lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        word,
        sentence,
        text_id: textId,
        context_before: contextBefore,
        context_after: contextAfter,
      }),
    })
      .then((data) => {
        if (!activeWordPopup || activeWordPopup.wordSpan !== wordSpan) return;
        renderWordPopupContent(body, data);
        positionWordPopup(popup, wordSpan);
      })
      .catch((err) => {
        if (!activeWordPopup || activeWordPopup.wordSpan !== wordSpan) return;
        renderWordPopupError(body, err.message, fetchAndRender);
        positionWordPopup(popup, wordSpan);
      });
  }

  positionWordPopup(popup, wordSpan);
  fetchAndRender();
}

// Divide o conteúdo do texto em tokens de palavra / não-palavra e monta o
// corpo do leitor com cada palavra dentro de um <span class="word">
// clicável, guardando a frase (sentença) de cada uma para servir de
// contexto no popup de vocabulário.
function renderClickableBody(container, rawText, textId) {
  container.innerHTML = "";

  const tokenRe = /[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*|[^A-Za-zÀ-ÖØ-öø-ÿ]+/g;
  const tokens = rawText.match(tokenRe) || [];

  const sentences = [];
  let buffer = "";
  let pendingSpans = [];

  tokens.forEach((token) => {
    const isWord = /[A-Za-zÀ-ÖØ-öø-ÿ]/.test(token[0]);
    buffer += token;

    if (isWord) {
      const span = document.createElement("span");
      span.className = "word";
      span.textContent = token;
      container.appendChild(span);
      pendingSpans.push(span);
      return;
    }

    container.appendChild(document.createTextNode(token));
    if (/[.!?]/.test(token)) {
      const idx = sentences.length;
      sentences.push(buffer.trim());
      pendingSpans.forEach((span) => {
        span.dataset.sentenceIdx = String(idx);
      });
      pendingSpans = [];
      buffer = "";
    }
  });

  if (buffer.trim()) {
    const idx = sentences.length;
    sentences.push(buffer.trim());
    pendingSpans.forEach((span) => {
      span.dataset.sentenceIdx = String(idx);
    });
  }

  container.addEventListener("click", (e) => {
    const span = e.target.closest(".word");
    if (!span || !container.contains(span)) return;
    const word = span.textContent;
    const sentence = sentences[Number(span.dataset.sentenceIdx)] || word;
    const { context_before, context_after } = getWordContext(span, container);
    openWordPopup(span, word, sentence, textId, context_before, context_after);
  });
}

// ---------------------------------------------------------------------------
// Leitura de um texto: conteúdo + player (play/pause)
// ---------------------------------------------------------------------------

let sharedAudioCtx = null;
function getAudioCtx() {
  if (!sharedAudioCtx) {
    sharedAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return sharedAudioCtx;
}

const player = {
  chunks: [],
  isPlaying: false,
  isLoading: false,
  isReady: false, // true depois que a faixa única (concatenada) terminou de carregar
  buffer: null, // AudioBuffer único e contínuo com o texto inteiro
  wordTimings: [], // [{ span, start, end }] em segundos, dentro da faixa única
  sourceNode: null,
  manualStop: false, // diferencia pause() (manual) de fim natural da faixa
  startCtxTime: 0, // audioCtx.currentTime no instante em que a reprodução (re)começou
  startOffset: 0, // posição (s) da faixa no instante em que a reprodução (re)começou
  pausedOffset: 0, // posição (s) guardada ao pausar
  rafId: null,
  activeWordSpan: null,
  isSeeking: false,
};

const listeningMode = {
  active: false,
  segments: [],
  index: 0,
  timers: [],
  sourceNode: null,
  manualStop: false,
  statusEl: null,
  bodyEl: null,
  listeningBtn: null,
};

function clearListeningTimers() {
  listeningMode.timers.forEach(clearTimeout);
  listeningMode.timers = [];
}

function clearListeningHighlight() {
  if (!listeningMode.bodyEl) return;
  listeningMode.bodyEl.querySelectorAll(".word").forEach((el) => {
    el.classList.remove("is-listening-segment", "is-listening-active");
  });
}

function stopListeningSource() {
  if (listeningMode.sourceNode) {
    listeningMode.manualStop = true;
    try {
      listeningMode.sourceNode.stop();
    } catch (err) {
      // já parado
    }
    listeningMode.sourceNode = null;
  }
}

function setListeningStatus(text, isYourTurn) {
  if (!listeningMode.statusEl) return;
  listeningMode.statusEl.textContent = text;
  listeningMode.statusEl.classList.add("is-visible");
  listeningMode.statusEl.classList.toggle("is-your-turn", !!isYourTurn);
}

function highlightListeningSegment(segment, phase) {
  clearListeningHighlight();
  if (!segment || !segment.spans.length) return;
  segment.spans.forEach((span) => {
    span.classList.add("is-listening-segment");
    if (phase === "listening") span.classList.add("is-listening-active");
  });
  segment.spans[0].scrollIntoView({ behavior: "smooth", block: "center" });
}

function stopListeningMode() {
  listeningMode.active = false;
  clearListeningTimers();
  stopListeningSource();
  clearListeningHighlight();
  if (listeningMode.bodyEl) {
    listeningMode.bodyEl.classList.remove("is-listening-mode");
  }
  if (listeningMode.statusEl) {
    listeningMode.statusEl.classList.remove("is-visible", "is-your-turn");
    listeningMode.statusEl.textContent = "";
  }
  if (listeningMode.listeningBtn) {
    listeningMode.listeningBtn.classList.remove("is-active");
    listeningMode.listeningBtn.setAttribute("aria-pressed", "false");
  }
  listeningMode.segments = [];
  listeningMode.index = 0;
}

function onListeningSegmentEnded(segment, audioDuration) {
  if (!listeningMode.active) return;

  const gapTimer = setTimeout(() => {
    if (!listeningMode.active) return;
    highlightListeningSegment(segment, "your-turn");
    setListeningStatus("🎙️ Your turn", true);

    const turnTimer = setTimeout(() => {
      if (!listeningMode.active) return;
      playListeningSegment(listeningMode.index + 1);
    }, audioDuration * 1.5 * 1000);
    listeningMode.timers.push(turnTimer);
  }, 500);
  listeningMode.timers.push(gapTimer);
}

function playListeningSegment(index) {
  if (!listeningMode.active) return;

  if (index >= listeningMode.segments.length) {
    stopListeningMode();
    showToast("Listening mode concluído!");
    return;
  }

  const segment = listeningMode.segments[index];
  listeningMode.index = index;
  highlightListeningSegment(segment, "listening");
  setListeningStatus("🔊 Listening...", false);

  const audioDuration = Math.max(0.1, segment.end - segment.start);
  const ctx = getAudioCtx();
  if (ctx.state === "suspended") ctx.resume();

  stopListeningSource();
  listeningMode.manualStop = false;

  const source = ctx.createBufferSource();
  source.buffer = player.buffer;
  source.connect(ctx.destination);
  source.onended = () => {
    if (listeningMode.manualStop || !listeningMode.active) return;
    onListeningSegmentEnded(segment, audioDuration);
  };
  listeningMode.sourceNode = source;
  source.start(0, segment.start, audioDuration);
}

function startListeningMode(segments) {
  listeningMode.segments = segments;
  listeningMode.index = 0;
  listeningMode.active = true;

  if (listeningMode.bodyEl) {
    listeningMode.bodyEl.classList.add("is-listening-mode");
  }
  if (listeningMode.listeningBtn) {
    listeningMode.listeningBtn.classList.add("is-active");
    listeningMode.listeningBtn.setAttribute("aria-pressed", "true");
  }

  playListeningSegment(0);
}

// Contabiliza tempo ativo de leitura/escuta para a métrica "Tempo de Texto"
// e os LIT Points correspondentes (POST /dashboard/reading-heartbeat a cada
// intervalo, enquanto o aluno está com um texto aberto e a aba visível).
const HEARTBEAT_SECONDS = 20;
const reading = {
  timer: null,
  textId: null,
};

function stopReadingHeartbeat() {
  if (reading.timer) {
    clearInterval(reading.timer);
    reading.timer = null;
  }
  reading.textId = null;
}

function sendReadingHeartbeat() {
  if (document.hidden || !reading.textId) return;
  apiFetch(`/dashboard/reading-heartbeat?text_id=${reading.textId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seconds: HEARTBEAT_SECONDS }),
  }).catch(() => {
    // Falha silenciosa: não interrompe a leitura do aluno por causa da métrica.
  });
}

function startReadingHeartbeat(textId) {
  stopReadingHeartbeat();
  reading.textId = textId;
  reading.timer = setInterval(sendReadingHeartbeat, HEARTBEAT_SECONDS * 1000);
}

function stopWordHighlight() {
  if (player.activeWordSpan) {
    player.activeWordSpan.classList.remove("is-reading");
    player.activeWordSpan = null;
  }
}

function resetPlayer() {
  stopListeningMode();
  stopWordAudio();
  if (player.rafId) {
    cancelAnimationFrame(player.rafId);
    player.rafId = null;
  }
  if (player.sourceNode) {
    player.manualStop = true;
    try {
      player.sourceNode.stop();
    } catch (err) {
      // já parado
    }
    player.sourceNode = null;
  }
  stopWordHighlight();
  player.chunks = [];
  player.isPlaying = false;
  player.isLoading = false;
  player.isReady = false;
  player.buffer = null;
  player.wordTimings = [];
  player.startCtxTime = 0;
  player.startOffset = 0;
  player.pausedOffset = 0;
}

function ttsUrl(text) {
  return `/tts/speak?text=${encodeURIComponent(text)}`;
}

// Concatena vários AudioBuffers (um por trecho do TTS) em um único buffer
// contínuo, para que a reprodução seja uma faixa só, sem cortes entre frases.
function concatAudioBuffers(ctx, buffers) {
  const numberOfChannels = buffers[0].numberOfChannels;
  const sampleRate = buffers[0].sampleRate;
  const totalLength = buffers.reduce((sum, b) => sum + b.length, 0);
  const output = ctx.createBuffer(numberOfChannels, totalLength, sampleRate);

  let offset = 0;
  buffers.forEach((buffer) => {
    for (let ch = 0; ch < numberOfChannels; ch++) {
      const inChannel = Math.min(ch, buffer.numberOfChannels - 1);
      output.getChannelData(ch).set(buffer.getChannelData(inChannel), offset);
    }
    offset += buffer.length;
  });

  return output;
}

// Agrupa as palavras de cada trecho (mesma ordem/tokenização dos <span
// class="word"> já renderizados) para depois distribuir a duração real de
// cada trecho proporcionalmente ao tamanho de cada palavra.
function groupWordsByChunk(chunks, wordSpans) {
  let wordCursor = 0;
  return chunks.map((chunkText) => {
    const words = chunkText.match(WORD_ONLY_RE) || [];
    const group = [];
    words.forEach((w) => {
      const span = wordSpans[wordCursor];
      wordCursor += 1;
      if (span) group.push({ span, weight: w.length + 1 });
    });
    return group;
  });
}

function computeWordTimings(chunkWordGroups, chunkDurations) {
  const timings = [];
  let cursor = 0;
  chunkWordGroups.forEach((group, i) => {
    const duration = chunkDurations[i] || 0;
    const totalWeight = group.reduce((sum, w) => sum + w.weight, 0) || 1;
    let localCursor = 0;
    group.forEach(({ span, weight }) => {
      const wordDuration = (weight / totalWeight) * duration;
      const start = cursor + localCursor;
      const end = start + wordDuration;
      timings.push({ span, start, end });
      localCursor += wordDuration;
    });
    cursor += duration;
  });
  return timings;
}

// Busca e decodifica TODOS os trechos do texto antes de tocar, para formar
// uma faixa de áudio única e contínua (em vez de carregar/tocar trecho a
// trecho). onProgress(loaded, total) permite atualizar o status na tela.
async function loadFullTrack(wordSpans, onProgress) {
  const ctx = getAudioCtx();
  const total = player.chunks.length;
  const buffers = new Array(total);

  let loaded = 0;
  const CONCURRENCY = 3;
  let nextIdx = 0;

  async function worker() {
    while (nextIdx < total) {
      const idx = nextIdx;
      nextIdx += 1;
      const blob = await apiFetchBlob(ttsUrl(player.chunks[idx]));
      const arrayBuffer = await blob.arrayBuffer();
      buffers[idx] = await ctx.decodeAudioData(arrayBuffer);
      loaded += 1;
      if (onProgress) onProgress(loaded, total);
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, total) }, worker);
  await Promise.all(workers);

  const fullBuffer = concatAudioBuffers(ctx, buffers);
  const chunkDurations = buffers.map((b) => b.duration);
  const chunkWordGroups = groupWordsByChunk(player.chunks, wordSpans);
  const wordTimings = computeWordTimings(chunkWordGroups, chunkDurations);

  return { fullBuffer, wordTimings };
}

async function openText(textId) {
  textsArea.innerHTML = '<div class="skeleton">Carregando texto...</div>';

  let text;
  try {
    text = await apiFetch(`/texts/${textId}`);
  } catch (err) {
    showToast(err.message || "Não foi possível abrir este texto.");
    renderTextList();
    return;
  }

  resetPlayer();
  player.chunks = splitIntoChunks(text.content);

  startReadingHeartbeat(text.id);
  renderReader(text);
}

function renderReader(text) {
  textsArea.innerHTML = "";

  const backLink = document.createElement("button");
  backLink.type = "button";
  backLink.className = "btn btn-outline reader-back";
  backLink.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 6l-6 6 6 6"/></svg><span>Voltar</span>`;
  backLink.addEventListener("click", () => {
    document.removeEventListener("fullscreenchange", onFullscreenChange);
    document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
    stopReadingHeartbeat();
    resetPlayer();
    closeWordPopup();
    renderTextList();
  });
  textsArea.appendChild(backLink);

  const card = document.createElement("div");
  card.className = "reader-card";

  const header = document.createElement("div");
  header.className = "reader-card-header";
  const h2 = document.createElement("h2");
  h2.textContent = text.title;
  header.appendChild(h2);
  const levelBadge = document.createElement("span");
  levelBadge.className = "level-badge";
  levelBadge.textContent = text.level;
  header.appendChild(levelBadge);
  card.appendChild(header);

  const viewport = document.createElement("div");
  viewport.className = "reader-viewport";

  const toolbar = document.createElement("div");
  toolbar.className = "reader-toolbar";

  const listeningBtn = document.createElement("button");
  listeningBtn.type = "button";
  listeningBtn.className = "reader-tool-btn listening-mode-btn";
  listeningBtn.innerHTML = `${Icons.headphones}<span>Listening Mode</span>`;
  listeningBtn.setAttribute("aria-pressed", "false");
  listeningBtn.setAttribute("aria-label", "Ativar Listening Mode");
  toolbar.appendChild(listeningBtn);

  const fullscreenBtn = document.createElement("button");
  fullscreenBtn.type = "button";
  fullscreenBtn.className = "reader-tool-btn";
  fullscreenBtn.innerHTML = Icons.fullscreen;
  fullscreenBtn.setAttribute("aria-label", "Tela cheia");
  toolbar.appendChild(fullscreenBtn);

  viewport.appendChild(toolbar);

  const playerBar = document.createElement("div");
  playerBar.className = "player-bar player-bar-top";

  const playBtn = document.createElement("button");
  playBtn.type = "button";
  playBtn.className = "player-play-btn";
  playBtn.innerHTML = Icons.play;
  playerBar.appendChild(playBtn);

  const info = document.createElement("div");
  info.className = "player-info";

  const status = document.createElement("p");
  status.className = "player-status";
  status.textContent = player.chunks.length > 0 ? "Pronto para tocar" : "Áudio não disponível para este texto";
  info.appendChild(status);

  const progress = document.createElement("div");
  progress.className = "player-progress";
  progress.setAttribute("role", "slider");
  progress.setAttribute("aria-label", "Progresso do áudio");
  progress.setAttribute("aria-valuemin", "0");
  progress.setAttribute("aria-valuemax", "100");

  const progressTrack = document.createElement("div");
  progressTrack.className = "player-progress-track";
  const progressFill = document.createElement("div");
  progressFill.className = "player-progress-fill";
  progressTrack.appendChild(progressFill);
  progress.appendChild(progressTrack);

  const progressThumb = document.createElement("div");
  progressThumb.className = "player-progress-thumb";
  progress.appendChild(progressThumb);

  info.appendChild(progress);
  playerBar.appendChild(info);
  viewport.appendChild(playerBar);

  const listeningStatus = document.createElement("div");
  listeningStatus.className = "listening-status";
  listeningStatus.setAttribute("aria-live", "polite");
  viewport.appendChild(listeningStatus);

  const body = document.createElement("p");
  body.className = "reader-body";
  renderClickableBody(body, text.content, text.id);
  viewport.appendChild(body);

  card.appendChild(viewport);
  textsArea.appendChild(card);

  const wordSpans = Array.from(body.querySelectorAll(".word"));

  listeningMode.statusEl = listeningStatus;
  listeningMode.bodyEl = body;
  listeningMode.listeningBtn = listeningBtn;

  function updateProgressUI(elapsed) {
    const duration = (player.buffer && player.buffer.duration) || 1;
    const pct = Math.min(100, Math.max(0, (elapsed / duration) * 100));
    progressFill.style.width = `${pct}%`;
    progressThumb.style.left = `${pct}%`;
    progress.setAttribute("aria-valuenow", String(Math.round(pct)));
  }

  function setPlayIcon() {
    playBtn.classList.remove("is-loading");
    playBtn.innerHTML = player.isPlaying ? Icons.pause : Icons.play;
  }

  function setLoading(on, label) {
    player.isLoading = on;
    playBtn.disabled = on;
    playBtn.classList.toggle("is-loading", on);
    if (on) status.textContent = label || "Carregando áudio...";
  }

  function updateWordHighlight(elapsed) {
    const timings = player.wordTimings;
    if (!timings.length || listeningMode.active) return;

    let current = null;
    for (let i = 0; i < timings.length; i++) {
      if (elapsed >= timings[i].start && elapsed < timings[i].end) {
        current = timings[i];
        break;
      }
    }

    if (current && current.span === player.activeWordSpan) return;

    if (player.activeWordSpan) {
      player.activeWordSpan.classList.remove("is-reading");
    }
    if (current) {
      current.span.classList.add("is-reading");
      player.activeWordSpan = current.span;
    } else {
      player.activeWordSpan = null;
    }
  }

  function finishPlayback() {
    player.isPlaying = false;
    player.startOffset = 0;
    player.pausedOffset = 0;
    setPlayIcon();
    status.textContent = "Pronto para tocar";
    updateProgressUI(0);
    stopWordHighlight();
  }

  function getElapsedTime() {
    if (!player.isPlaying || !player.buffer) return player.pausedOffset || 0;
    const ctx = getAudioCtx();
    return ctx.currentTime - player.startCtxTime + player.startOffset;
  }

  function tick() {
    if (!player.isPlaying) return;
    const elapsed = getElapsedTime();

    if (elapsed >= player.buffer.duration) {
      updateProgressUI(player.buffer.duration);
      return;
    }

    updateProgressUI(elapsed);
    updateWordHighlight(elapsed);
    player.rafId = requestAnimationFrame(tick);
  }

  function startSourceFrom(offsetSeconds) {
    stopWordAudio();
    if (listeningMode.active) stopListeningMode();

    const ctx = getAudioCtx();
    if (ctx.state === "suspended") ctx.resume();

    if (player.sourceNode) {
      player.manualStop = true;
      try {
        player.sourceNode.stop();
      } catch (err) {
        // já parado
      }
      player.sourceNode = null;
    }

    const source = ctx.createBufferSource();
    source.buffer = player.buffer;
    source.connect(ctx.destination);

    source.onended = () => {
      if (player.manualStop) {
        player.manualStop = false;
        return;
      }
      finishPlayback();
    };

    player.sourceNode = source;
    player.startCtxTime = ctx.currentTime;
    player.startOffset = offsetSeconds;
    source.start(0, offsetSeconds);

    player.isPlaying = true;
    setPlayIcon();
    status.textContent = "Tocando áudio...";
    if (player.rafId) cancelAnimationFrame(player.rafId);
    player.rafId = requestAnimationFrame(tick);
  }

  function pausePlayback() {
    const elapsed = getElapsedTime();
    player.pausedOffset = Math.min(elapsed, player.buffer ? player.buffer.duration : elapsed);

    player.isPlaying = false;
    if (player.rafId) {
      cancelAnimationFrame(player.rafId);
      player.rafId = null;
    }
    if (player.sourceNode) {
      player.manualStop = true;
      try {
        player.sourceNode.stop();
      } catch (err) {
        // já parado
      }
      player.sourceNode = null;
    }
    setPlayIcon();
    status.textContent = "Pausado";
    updateProgressUI(player.pausedOffset);
    updateWordHighlight(player.pausedOffset);
  }

  function seekTo(ratio) {
    if (!player.buffer || listeningMode.active) return;
    const target = Math.max(0, Math.min(player.buffer.duration, ratio * player.buffer.duration));

    if (player.isPlaying) {
      startSourceFrom(target);
    } else {
      player.pausedOffset = target;
      updateProgressUI(target);
      updateWordHighlight(target);
    }
  }

  function getProgressRatio(clientX) {
    const rect = progress.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  }

  function onSeekStart(clientX) {
    if (!player.buffer || listeningMode.active) return;
    player.isSeeking = true;
    progress.classList.add("is-seeking");
    seekTo(getProgressRatio(clientX));
  }

  function onSeekMove(clientX) {
    if (!player.isSeeking) return;
    seekTo(getProgressRatio(clientX));
  }

  function onSeekEnd() {
    if (!player.isSeeking) return;
    player.isSeeking = false;
    progress.classList.remove("is-seeking");
    window.removeEventListener("mousemove", onWindowSeekMove);
    window.removeEventListener("mouseup", onWindowSeekEnd);
    window.removeEventListener("touchmove", onWindowSeekTouchMove);
    window.removeEventListener("touchend", onWindowSeekEnd);
  }

  function onWindowSeekMove(e) {
    onSeekMove(e.clientX);
  }

  function onWindowSeekTouchMove(e) {
    if (e.touches[0]) onSeekMove(e.touches[0].clientX);
  }

  function onWindowSeekEnd() {
    onSeekEnd();
  }

  function bindSeekWindowListeners() {
    window.addEventListener("mousemove", onWindowSeekMove);
    window.addEventListener("mouseup", onWindowSeekEnd);
    window.addEventListener("touchmove", onWindowSeekTouchMove, { passive: true });
    window.addEventListener("touchend", onWindowSeekEnd);
  }

  progress.addEventListener("mousedown", (e) => {
    e.preventDefault();
    onSeekStart(e.clientX);
    bindSeekWindowListeners();
  });

  progress.addEventListener("touchstart", (e) => {
    e.preventDefault();
    onSeekStart(e.touches[0].clientX);
    bindSeekWindowListeners();
  }, { passive: false });

  async function ensureAudioLoaded() {
    if (player.isReady && player.buffer) return true;

    setLoading(true, "Carregando áudio...");
    try {
      const { fullBuffer, wordTimings } = await loadFullTrack(wordSpans, (loaded, total) => {
        status.textContent = `Carregando áudio... (${loaded}/${total})`;
      });
      player.buffer = fullBuffer;
      player.wordTimings = wordTimings;
      player.isReady = true;
      setLoading(false);
      return true;
    } catch (err) {
      setLoading(false);
      status.textContent = "Não foi possível tocar o áudio. Tente novamente.";
      showToast(err.message || "Não foi possível carregar o áudio.");
      return false;
    }
  }

  playBtn.addEventListener("click", async () => {
    if (player.chunks.length === 0 || player.isLoading) return;

    if (player.isPlaying) {
      pausePlayback();
      return;
    }

    const ready = await ensureAudioLoaded();
    if (!ready) return;
    startSourceFrom(player.pausedOffset || 0);
  });

  listeningBtn.addEventListener("click", async () => {
    if (player.chunks.length === 0 || player.isLoading) return;

    if (listeningMode.active) {
      stopListeningMode();
      status.textContent = player.isPlaying ? "Tocando áudio..." : "Pronto para tocar";
      return;
    }

    if (player.isPlaying) pausePlayback();

    const ready = await ensureAudioLoaded();
    if (!ready) return;

    const segmentTexts = splitIntoListeningSegments(text.content);
    const segments = buildSegmentTimings(segmentTexts, wordSpans, player.wordTimings);
    if (!segments.length) {
      showToast("Não há trechos disponíveis para o Listening Mode.");
      return;
    }

    startListeningMode(segments);
  });

  function isFullscreenActive() {
    return document.fullscreenElement === viewport
      || document.webkitFullscreenElement === viewport
      || viewport.classList.contains("reader-fullscreen-fallback");
  }

  function syncFullscreenBtn() {
    const active = isFullscreenActive();
    fullscreenBtn.innerHTML = active ? Icons.fullscreenExit : Icons.fullscreen;
    fullscreenBtn.setAttribute("aria-label", active ? "Sair da tela cheia" : "Tela cheia");
    viewport.classList.toggle("is-fullscreen", active);
  }

  fullscreenBtn.addEventListener("click", () => {
    if (isFullscreenActive()) {
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
      }
      viewport.classList.remove("reader-fullscreen-fallback");
      syncFullscreenBtn();
      return;
    }

    const req = viewport.requestFullscreen || viewport.webkitRequestFullscreen;
    if (req) {
      req.call(viewport).catch(() => {
        viewport.classList.add("reader-fullscreen-fallback");
        syncFullscreenBtn();
      });
    } else {
      viewport.classList.add("reader-fullscreen-fallback");
      syncFullscreenBtn();
    }
  });

  function onFullscreenChange() {
    syncFullscreenBtn();
  }

  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("webkitfullscreenchange", onFullscreenChange);

  if (player.chunks.length === 0) {
    playBtn.disabled = true;
    listeningBtn.disabled = true;
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
    renderStateBox(textsArea, {
      icon: Icons.lock,
      title: "Conta aguardando aprovação",
      text: "Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá acessar os textos.",
    });
    return;
  }

  renderTextList();
}

init();
