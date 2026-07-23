/* ==========================================================================
   LIT English — textos.js
   Tela "Read and Listen" do aluno. Consome:
     GET /texts        (lista)
     GET /texts/{id}   (detalhe)
     GET /tts/speak     (áudio, via proxy do backend)

   O TTS do backend corta o texto em ~200 caracteres por chamada, então
   textos longos são divididos em frases e tocados em sequência, um áudio
   após o outro, dando a sensação de um único player contínuo.
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

// Cache de áudio da pronúncia de palavras isoladas (separado do cache de
// trechos do player principal, em player.blobUrls).
const wordAudioBlobUrls = new Map();

async function getWordAudioUrl(word) {
  if (wordAudioBlobUrls.has(word)) return wordAudioBlobUrls.get(word);
  const blob = await apiFetchBlob(ttsUrl(word));
  const url = URL.createObjectURL(blob);
  wordAudioBlobUrls.set(word, url);
  return url;
}

async function playWordAudio(word, speakerBtn) {
  if (speakerBtn.disabled) return;
  speakerBtn.disabled = true;
  speakerBtn.classList.add("is-loading");

  try {
    const url = await getWordAudioUrl(word);
    const audio = new Audio(url);
    await audio.play();
    audio.addEventListener("ended", () => {
      speakerBtn.disabled = false;
      speakerBtn.classList.remove("is-loading");
    });
  } catch (err) {
    speakerBtn.disabled = false;
    speakerBtn.classList.remove("is-loading");
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

  const speakerBtn = document.createElement("button");
  speakerBtn.type = "button";
  speakerBtn.className = "word-popup-speaker";
  speakerBtn.innerHTML = Icons.volume;
  speakerBtn.setAttribute("aria-label", "Ouvir pronúncia");
  speakerBtn.addEventListener("click", () => {
    playWordAudio(word, speakerBtn);
  });
  header.appendChild(speakerBtn);

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

function openWordPopup(wordSpan, word, sentence, textId) {
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
      body: JSON.stringify({ word, sentence, text_id: textId }),
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
    openWordPopup(span, word, sentence, textId);
  });
}

// ---------------------------------------------------------------------------
// Leitura de um texto: conteúdo + player (play/pause)
// ---------------------------------------------------------------------------

const player = {
  chunks: [],
  index: 0,
  isPlaying: false,
  isLoading: false,
  audio: null,
  blobUrls: new Map(), // chunk -> object URL já buscado
};

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

function resetPlayer() {
  if (player.audio) {
    player.audio.pause();
    player.audio.src = "";
  }
  player.chunks = [];
  player.index = 0;
  player.isPlaying = false;
  player.isLoading = false;
  player.audio = null;
}

function ttsUrl(text) {
  return `/tts/speak?text=${encodeURIComponent(text)}`;
}

async function getChunkAudioUrl(text) {
  if (player.blobUrls.has(text)) return player.blobUrls.get(text);
  const blob = await apiFetchBlob(ttsUrl(text));
  const url = URL.createObjectURL(blob);
  player.blobUrls.set(text, url);
  return url;
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

  // ---------- Player (play / pause) — fica acima do texto ----------

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
  const progressFill = document.createElement("div");
  progressFill.className = "player-progress-fill";
  progress.appendChild(progressFill);
  info.appendChild(progress);

  playerBar.appendChild(info);
  card.appendChild(playerBar);

  // ---------- Texto ----------

  const body = document.createElement("p");
  body.className = "reader-body";
  renderClickableBody(body, text.content, text.id);
  card.appendChild(body);

  textsArea.appendChild(card);

  function updateProgress() {
    const total = player.chunks.length || 1;
    const pct = Math.min(100, (player.index / total) * 100);
    progressFill.style.width = `${pct}%`;
  }

  function setPlayIcon() {
    playBtn.classList.remove("is-loading");
    playBtn.innerHTML = player.isPlaying ? Icons.pause : Icons.play;
  }

  function setLoading(on) {
    player.isLoading = on;
    playBtn.disabled = on;
    playBtn.classList.toggle("is-loading", on);
    if (on) status.textContent = "Carregando áudio...";
  }

  async function playFromIndex(idx) {
    if (idx >= player.chunks.length) {
      // Fim do texto
      player.isPlaying = false;
      player.index = 0;
      setPlayIcon();
      status.textContent = "Pronto para tocar";
      progressFill.style.width = "0%";
      return;
    }

    player.index = idx;
    updateProgress();

    setLoading(true);
    let url;
    try {
      url = await getChunkAudioUrl(player.chunks[idx]);
    } catch (err) {
      setLoading(false);
      player.isPlaying = false;
      setPlayIcon();
      status.textContent = "Não foi possível tocar o áudio. Tente novamente.";
      showToast(err.message || "Não foi possível tocar o áudio.");
      return;
    }
    setLoading(false);

    if (!player.isPlaying) return; // usuário pausou enquanto carregava

    const audio = new Audio(url);
    player.audio = audio;
    status.textContent = "Tocando áudio...";

    audio.addEventListener("ended", () => {
      if (!player.isPlaying) return; // foi pausado
      playFromIndex(idx + 1);
    });
    audio.addEventListener("error", () => {
      player.isPlaying = false;
      setPlayIcon();
      status.textContent = "Não foi possível tocar o áudio. Tente novamente.";
    });

    try {
      await audio.play();
    } catch (err) {
      player.isPlaying = false;
      setPlayIcon();
      status.textContent = "Não foi possível tocar o áudio.";
    }
  }

  playBtn.addEventListener("click", () => {
    if (player.chunks.length === 0) return;

    if (player.isPlaying) {
      // Pausar
      player.isPlaying = false;
      if (player.audio) player.audio.pause();
      setPlayIcon();
      return;
    }

    // Tocar (ou retomar)
    player.isPlaying = true;
    setPlayIcon();

    if (player.audio && !player.audio.ended && player.audio.currentTime > 0) {
      status.textContent = "Tocando áudio...";
      player.audio.play().catch(() => {
        player.isPlaying = false;
        setPlayIcon();
      });
    } else {
      playFromIndex(player.index);
    }
  });

  if (player.chunks.length === 0) {
    playBtn.disabled = true;
  }
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------

async function init() {
  if (!Auth.isLoggedIn()) {
    window.location.href = "login.html";
    return;
  }

  let user;
  try {
    user = await fetchCurrentUser();
  } catch (err) {
    Auth.clear();
    window.location.href = "login.html";
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
