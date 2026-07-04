/* ==========================================================================
   LIT English — exercicios.js  v6
   Tela de exercícios no mesmo formato visual do "Revisar": um único
   flashcard centralizado por vez, do mais antigo para o mais novo.
   Fluxo de cada card: Confirmar (trava a resposta/áudio) → Enviar
   (corrige com o professor e mostra o resultado) → avança automaticamente
   para o próximo (sem voltar).
   ========================================================================== */

const area = document.getElementById("exercises-area");
const toastEl = document.getElementById("toast");
let toastTimer = null;

function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2600);
}

// ---------------------------------------------------------------------------
// Sessão do carrossel (estado em memória, vive enquanto a página está aberta)
// ---------------------------------------------------------------------------
const session = {
  exercises: [],
  index: 0,
};

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "America/Sao_Paulo",
  });
}

function renderStateBox({ icon, title, text }) {
  area.innerHTML = "";
  const box = document.createElement("div");
  box.className = "state-box";

  if (icon) {
    const iconWrap = document.createElement("div");
    iconWrap.className = "state-icon";
    iconWrap.innerHTML = icon;
    box.appendChild(iconWrap);
  }

  const h2 = document.createElement("h2");
  h2.textContent = title;
  box.appendChild(h2);

  const p = document.createElement("p");
  p.textContent = text;
  box.appendChild(p);

  area.appendChild(box);
}

async function init() {
  if (!Auth.isLoggedIn()) { window.location.href = "index.html"; return; }

  let user;
  try { user = await fetchCurrentUser(); } catch { Auth.clear(); window.location.href = "index.html"; return; }

  if (user.role === "professor") { window.location.href = "professor.html"; return; }

  document.getElementById("student-name").textContent = user.name;
  document.getElementById("logout-btn").addEventListener("click", () => Auth.logout());

  await loadExercises();
}

async function loadExercises() {
  area.innerHTML = '<div class="skeleton">Carregando...</div>';

  let exercises = [];
  try {
    exercises = await apiFetch("/exercises/my-assignments");
  } catch (err) {
    renderStateBox({
      icon: Icons.alert,
      title: "Algo deu errado",
      text: err.message || "Erro ao carregar exercícios.",
    });
    return;
  }

  if (!exercises || exercises.length === 0) {
    renderStateBox({
      icon: Icons.checkCircle,
      title: "Nenhum exercício para revisar agora",
      text: "Você não possui exercícios para revisar agora. Volte mais tarde!",
    });
    return;
  }

  // Do mais antigo para o mais novo
  exercises.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  session.exercises = exercises;
  session.index = 0;
  renderCurrent();
}

function renderFinished() {
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Sessão concluída! 🎉",
    text: "Você não possui exercícios para revisar agora. Os próximos aparecerão conforme o cronograma de revisão.",
  });
}

function renderCurrent() {
  if (session.index >= session.exercises.length) {
    renderFinished();
    return;
  }

  const ex = session.exercises[session.index];
  area.innerHTML = "";

  let cardBox;
  if (ex.type === "fill_blank") {
    cardBox = buildFillBlankCard(ex);
  } else if (ex.type === "word_choice") {
    cardBox = buildListenTypeCard(ex);
  } else if (ex.type === "speaking") {
    cardBox = buildSpeakingCard(ex);
  } else {
    // Tipo desconhecido — avança automaticamente para não travar o carrossel
    session.index += 1;
    renderCurrent();
    return;
  }

  area.appendChild(cardBox);
}

function goToNext() {
  session.index += 1;
  renderCurrent();
}

// ---------------------------------------------------------------------------
// Estrutura comum do card, no mesmo formato visual do "Revisar"
// (.review-card → .counter + .card-body), com badge do tipo de exercício
// ---------------------------------------------------------------------------

function buildCardBox(ex, badgeLabel) {
  const cardBox = document.createElement("div");
  cardBox.className = "review-card";
  cardBox.dataset.exId = ex.id;

  const topRow = document.createElement("div");
  topRow.style.cssText = "display:flex;justify-content:space-between;align-items:center;";

  const badge = document.createElement("span");
  badge.style.cssText = "font-size:12px;font-weight:600;color:var(--primary);border:1px solid var(--primary);border-radius:20px;padding:3px 12px;";
  badge.textContent = badgeLabel;
  topRow.appendChild(badge);

  const counter = document.createElement("span");
  counter.className = "counter";
  counter.style.alignSelf = "auto";
  counter.textContent = `${session.index + 1} / ${session.exercises.length}`;
  topRow.appendChild(counter);

  cardBox.appendChild(topRow);

  if (ex.created_at) {
    const dateEl = document.createElement("div");
    dateEl.style.cssText = "text-align:right;font-size:11px;color:var(--text-muted);margin-top:2px;";
    dateEl.textContent = `Adicionado em ${formatDate(ex.created_at)}`;
    cardBox.appendChild(dateEl);
  }

  const body = document.createElement("div");
  body.className = "card-body";
  cardBox.appendChild(body);

  if (ex.title) {
    const subjectLabel = document.createElement("div");
    subjectLabel.innerHTML = `<span style="font-size:13px;font-weight:700;color:var(--primary);letter-spacing:1px;text-transform:uppercase;border-bottom:2px solid var(--primary);padding-bottom:2px;">Assunto</span>`;
    body.appendChild(subjectLabel);

    const subjectTitle = document.createElement("p");
    subjectTitle.className = "front-text";
    subjectTitle.style.cssText = "font-size:26px;text-transform:none;";
    subjectTitle.textContent = ex.title;
    body.appendChild(subjectTitle);
  }

  return { cardBox, body };
}

function buildResultArea() {
  const resultArea = document.createElement("div");
  resultArea.style.cssText = "width:100%;max-width:100%;box-sizing:border-box;border-radius:10px;padding:14px 16px;display:flex;align-items:center;gap:10px;text-align:left;overflow-wrap:break-word;word-break:break-word;";
  resultArea.hidden = true;
  return resultArea;
}

function showResult(resultArea, result) {
  resultArea.hidden = false;
  const reasonHtml = result.reason
    ? `<div style="font-weight:400;font-size:0.9em;margin-top:4px;">${result.reason}</div>`
    : "";
  if (result.correct) {
    resultArea.style.background = "#f0faf4";
    resultArea.style.border = "1px solid #b7dfc7";
    const said = result.transcribed_text ? ` Você disse: "${result.transcribed_text}"` : "";
    resultArea.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#155724" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg><span style="color:#155724;font-weight:600;">Correto!<span style="font-weight:400;">${said}</span>${reasonHtml}</span>`;
  } else {
    resultArea.style.background = "#fff5f5";
    resultArea.style.border = "1px solid #f5c6cb";
    const said = result.transcribed_text ? ` Você disse: "${result.transcribed_text}".` : "";
    resultArea.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9 9 15M9 9l6 6"/></svg><span style="color:#721c24;font-weight:600;">Errado!${said} <span style="font-weight:400;">A resposta correta era: <strong>${result.correct_answer}</strong></span>${reasonHtml}</span>`;
  }
}

/** Monta a área de ações (review-actions) com hint + botão único, trocável. */
function buildActions() {
  const actions = document.createElement("div");
  actions.className = "review-actions";

  const hint = document.createElement("p");
  hint.className = "review-hint";
  actions.appendChild(hint);

  const btnRow = document.createElement("div");
  btnRow.style.cssText = "width:100%;max-width:340px;";
  actions.appendChild(btnRow);

  return { actions, hint, btnRow };
}

function makeButton(label, variant) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `btn ${variant === "primary" ? "btn-primary" : "btn-outline"} btn-block`;
  btn.textContent = label;
  return btn;
}

// ---------------------------------------------------------------------------
// Fill in the blank
// ---------------------------------------------------------------------------

function buildFillBlankCard(ex) {
  const { cardBox, body } = buildCardBox(ex, "Fill in the blank");

  const sentenceRow = document.createElement("div");
  sentenceRow.style.cssText = "display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;font-size:18px;font-weight:500;color:var(--text);width:100%;max-width:100%;box-sizing:border-box;overflow-wrap:break-word;word-break:break-word;";

  if (ex.part1) {
    const p1 = document.createElement("span");
    p1.textContent = ex.part1;
    sentenceRow.appendChild(p1);
  }

  const input = document.createElement("input");
  input.type = "text";
  input.style.cssText = "width:160px;text-align:center;border:2px solid var(--primary);border-radius:8px;padding:10px 12px;font-size:17px;font-weight:700;color:var(--primary);outline:none;background:var(--bg);";
  input.placeholder = "...";
  sentenceRow.appendChild(input);

  if (ex.part2) {
    const p2 = document.createElement("span");
    p2.textContent = ex.part2;
    sentenceRow.appendChild(p2);
  }

  body.appendChild(sentenceRow);

  if (ex.translation) {
    const transWrap = document.createElement("div");
    transWrap.style.cssText = "text-align:center;margin-top:4px;";
    transWrap.innerHTML = `<div style="font-size:12px;font-weight:700;color:var(--primary);letter-spacing:1px;margin-bottom:4px;">TRADUÇÃO</div><div style="font-size:14px;color:var(--text-secondary);">${ex.translation}</div>`;
    body.appendChild(transWrap);
  }

  const resultArea = buildResultArea();
  body.appendChild(resultArea);

  const { actions, hint, btnRow } = buildActions();
  cardBox.appendChild(actions);

  let confirmed = false;
  let confirmedValue = "";

  const confirmBtn = makeButton("Confirmar", "outline");
  btnRow.appendChild(confirmBtn);
  hint.textContent = "Digite sua resposta e confirme.";

  const doConfirm = () => {
    const val = input.value.trim();
    if (!val) { showToast("Digite uma resposta antes de confirmar."); return; }
    confirmed = true;
    confirmedValue = val;
    input.disabled = true;

    const sendBtn = makeButton("Enviar", "primary");
    btnRow.innerHTML = "";
    btnRow.appendChild(sendBtn);
    hint.textContent = "Resposta confirmada. Envie para o professor.";
    sendBtn.addEventListener("click", doSubmit);
  };

  const doSubmit = async () => {
    const sendBtn = btnRow.querySelector("button");
    sendBtn.disabled = true;
    sendBtn.textContent = "Enviando...";

    try {
      const result = await apiFetch(`/exercises/${ex.id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: confirmedValue }),
      });
      showResult(resultArea, result);
      hint.textContent = "";
      const nextBtn = makeButton("Próximo", "primary");
      btnRow.innerHTML = "";
      btnRow.appendChild(nextBtn);
      nextBtn.addEventListener("click", goToNext);
    } catch (err) {
      showToast(err.message || "Erro ao enviar resposta.");
      sendBtn.disabled = false;
      sendBtn.textContent = "Enviar";
    }
  };

  confirmBtn.addEventListener("click", doConfirm);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); if (!confirmed) doConfirm(); }
  });

  return cardBox;
}

// ---------------------------------------------------------------------------
// Listen and type — resposta sempre em inglês
// ---------------------------------------------------------------------------

const ttsAudioCache = new Map(); // texto -> URL do blob de áudio já carregado

async function fetchTtsAudioUrl(text) {
  if (ttsAudioCache.has(text)) return ttsAudioCache.get(text);
  const blob = await apiFetchBlob(`/tts/speak?text=${encodeURIComponent(text)}`);
  const url = URL.createObjectURL(blob);
  ttsAudioCache.set(text, url);
  return url;
}

function buildListenTypeCard(ex) {
  const { cardBox, body } = buildCardBox(ex, "Listen and type");

  const playBtn = document.createElement("button");
  playBtn.type = "button";
  playBtn.className = "speak-btn";
  playBtn.style.cssText = "width:56px;height:56px;";
  playBtn.innerHTML = Icons.play;
  body.appendChild(playBtn);

  // Mantém a instância de áudio para permitir pausar/retomar sem recarregar o TTS.
  let currentAudio = null;

  playBtn.addEventListener("click", async () => {
    // Já existe áudio carregado: apenas alterna entre pausar e retomar.
    if (currentAudio) {
      if (currentAudio.paused) {
        currentAudio.play().catch(() => showToast("Erro ao tocar o áudio."));
      } else {
        currentAudio.pause();
      }
      return;
    }

    playBtn.disabled = true;
    try {
      const url = await fetchTtsAudioUrl(ex.prompt);
      const audio = new Audio(url);
      currentAudio = audio;

      audio.addEventListener("play", () => { playBtn.innerHTML = Icons.pause; });
      audio.addEventListener("pause", () => { playBtn.innerHTML = Icons.play; });
      audio.addEventListener("ended", () => { playBtn.innerHTML = Icons.play; });
      audio.addEventListener("error", () => {
        showToast("Erro ao tocar o áudio.");
        currentAudio = null;
        playBtn.innerHTML = Icons.play;
        playBtn.disabled = false;
      });

      playBtn.disabled = false;
      await audio.play();
    } catch {
      showToast("Erro ao tocar o áudio.");
      playBtn.disabled = false;
    }
  });

  const inputLabel = document.createElement("div");
  inputLabel.style.cssText = "font-size:14px;color:var(--text-secondary);";
  inputLabel.textContent = "Digite em inglês o que você ouviu:";
  body.appendChild(inputLabel);

  const input = document.createElement("input");
  input.type = "text";
  input.lang = "en";
  input.autocomplete = "off";
  input.autocapitalize = "off";
  input.spellcheck = true;
  input.style.cssText = "width:100%;max-width:380px;text-align:center;border:2px solid var(--primary);border-radius:8px;padding:12px 16px;font-size:17px;font-weight:700;color:var(--primary);outline:none;background:var(--bg);";
  input.placeholder = "Type in English...";
  body.appendChild(input);

  const resultArea = buildResultArea();
  body.appendChild(resultArea);

  const { actions, hint, btnRow } = buildActions();
  cardBox.appendChild(actions);

  let confirmed = false;
  let confirmedValue = "";

  const confirmBtn = makeButton("Confirmar", "outline");
  btnRow.appendChild(confirmBtn);
  hint.textContent = "Digite a resposta em inglês e confirme.";

  const doConfirm = () => {
    const val = input.value.trim();
    if (!val) { showToast("Digite uma resposta antes de confirmar."); return; }
    confirmed = true;
    confirmedValue = val;
    input.disabled = true;

    const sendBtn = makeButton("Enviar", "primary");
    btnRow.innerHTML = "";
    btnRow.appendChild(sendBtn);
    hint.textContent = "Resposta confirmada. Envie para o professor.";
    sendBtn.addEventListener("click", doSubmit);
  };

  const doSubmit = async () => {
    const sendBtn = btnRow.querySelector("button");
    sendBtn.disabled = true;
    sendBtn.textContent = "Enviando...";

    try {
      const result = await apiFetch(`/exercises/${ex.id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: confirmedValue }),
      });
      showResult(resultArea, result);
      hint.textContent = "";
      const nextBtn = makeButton("Próximo", "primary");
      btnRow.innerHTML = "";
      btnRow.appendChild(nextBtn);
      nextBtn.addEventListener("click", goToNext);
    } catch (err) {
      showToast(err.message || "Erro ao enviar resposta.");
      sendBtn.disabled = false;
      sendBtn.textContent = "Enviar";
    }
  };

  confirmBtn.addEventListener("click", doConfirm);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); if (!confirmed) doConfirm(); }
  });

  return cardBox;
}

// ---------------------------------------------------------------------------
// Speak it! — só conta como certo se TODAS as palavras baterem (ver backend)
// ---------------------------------------------------------------------------

function buildSpeakingCard(ex) {
  const { cardBox, body } = buildCardBox(ex, "Speak it!");

  const ptLabel = document.createElement("div");
  ptLabel.style.cssText = "font-size:13px;font-weight:700;color:var(--primary);letter-spacing:1px;";
  ptLabel.textContent = "Leia e fale em inglês:";
  body.appendChild(ptLabel);

  const ptText = document.createElement("p");
  ptText.className = "front-text";
  ptText.style.cssText = "font-size:24px;text-transform:none;";
  ptText.textContent = ex.prompt;
  body.appendChild(ptText);

  const recordBtn = document.createElement("button");
  recordBtn.type = "button";
  recordBtn.className = "speak-btn";
  recordBtn.style.cssText = "width:56px;height:56px;";
  recordBtn.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/><path d="M9 22h6"/></svg>`;
  body.appendChild(recordBtn);

  const statusText = document.createElement("div");
  statusText.style.cssText = "font-size:13px;color:var(--text-muted);max-width:380px;";
  statusText.textContent = "Toque no microfone e fale a frase em inglês. Para acertar, todas as palavras precisam estar certas.";
  body.appendChild(statusText);

  const resultArea = buildResultArea();
  body.appendChild(resultArea);

  const { actions, hint, btnRow } = buildActions();
  cardBox.appendChild(actions);

  const confirmBtn = makeButton("Confirmar", "outline");
  confirmBtn.disabled = true;
  btnRow.appendChild(confirmBtn);
  hint.textContent = "Grave seu áudio e confirme.";

  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let recordedBlob = null;
  let confirmed = false;

  recordBtn.addEventListener("click", async () => {
    if (confirmed) return;
    if (!isRecording) {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast("Seu navegador não suporta gravação de áudio.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
        });
        audioChunks = [];
        const preferredMimeTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
        let mimeType = "";
        for (const mt of preferredMimeTypes) {
          if (MediaRecorder.isTypeSupported(mt)) { mimeType = mt; break; }
        }
        mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
        mediaRecorder.onstop = () => {
          const blobType = mimeType || "audio/webm";
          recordedBlob = new Blob(audioChunks, { type: blobType });
          statusText.textContent = "Áudio gravado. Pode gravar de novo se quiser refazer.";
          confirmBtn.disabled = false;
          stream.getTracks().forEach((t) => t.stop());
        };
        mediaRecorder.start();
        isRecording = true;
        recordBtn.style.background = "var(--primary)";
        recordBtn.style.color = "#fff";
        statusText.textContent = "🔴 Gravando... toque novamente para parar.";
      } catch (err) {
        showToast("Permissão de microfone negada.");
      }
    } else {
      mediaRecorder.stop();
      isRecording = false;
      recordBtn.style.background = "var(--bg)";
      recordBtn.style.color = "var(--primary)";
    }
  });

  const doConfirm = () => {
    if (!recordedBlob) { showToast("Grave seu áudio antes de confirmar."); return; }
    confirmed = true;
    recordBtn.disabled = true;

    const sendBtn = makeButton("Enviar", "primary");
    btnRow.innerHTML = "";
    btnRow.appendChild(sendBtn);
    hint.textContent = "Áudio confirmado. Envie para o professor.";
    sendBtn.addEventListener("click", doSubmit);
  };

  const doSubmit = async () => {
    const sendBtn = btnRow.querySelector("button");
    sendBtn.disabled = true;
    sendBtn.textContent = "Enviando...";

    try {
      const formData = new FormData();
      const ext = recordedBlob.type.includes("ogg") ? "ogg" : "webm";
      formData.append("audio", recordedBlob, `recording.${ext}`);

      const token = Auth.getToken();
      const response = await fetch(`${API_BASE_URL}/exercises/${ex.id}/submit-audio`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.detail || `Erro ${response.status}`);
      }
      const result = await response.json();

      showResult(resultArea, result);
      hint.textContent = "";
      const nextBtn = makeButton("Próximo", "primary");
      btnRow.innerHTML = "";
      btnRow.appendChild(nextBtn);
      nextBtn.addEventListener("click", goToNext);
    } catch (err) {
      showToast(err.message || "Erro ao enviar áudio.");
      sendBtn.disabled = false;
      sendBtn.textContent = "Enviar";
    }
  };

  confirmBtn.addEventListener("click", doConfirm);

  return cardBox;
}

init();
