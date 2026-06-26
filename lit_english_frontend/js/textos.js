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

  renderReader(text);
}

function renderReader(text) {
  textsArea.innerHTML = "";

  const backLink = document.createElement("button");
  backLink.type = "button";
  backLink.className = "btn btn-outline reader-back";
  backLink.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 6l-6 6 6 6"/></svg><span>Voltar</span>`;
  backLink.addEventListener("click", () => {
    resetPlayer();
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
  body.textContent = text.content;
  card.appendChild(body);

  const toggleWrap = document.createElement("div");
  toggleWrap.className = "reader-translation-toggle";
  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "btn btn-outline btn-sm";
  toggleBtn.textContent = "Ver tradução";
  toggleWrap.appendChild(toggleBtn);
  card.appendChild(toggleWrap);

  const translation = document.createElement("p");
  translation.className = "reader-translation";
  translation.textContent = text.translation;
  translation.hidden = true;
  card.appendChild(translation);

  toggleBtn.addEventListener("click", () => {
    translation.hidden = !translation.hidden;
    toggleBtn.textContent = translation.hidden ? "Ver tradução" : "Ocultar tradução";
  });

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
    status.textContent = `Tocando trecho ${idx + 1} de ${player.chunks.length}`;

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
      status.textContent = "Pausado";
      return;
    }

    // Tocar (ou retomar)
    player.isPlaying = true;
    setPlayIcon();

    if (player.audio && !player.audio.ended && player.audio.currentTime > 0) {
      status.textContent = `Tocando trecho ${player.index + 1} de ${player.chunks.length}`;
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
