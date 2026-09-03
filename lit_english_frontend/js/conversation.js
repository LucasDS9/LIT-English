/* ==========================================================================
   LIT English — conversation.js
   Tela "Conversa com IA Tutor".

   Fluxo (requisição única, sem streaming ao vivo):
     1. Aluno segura/toca o botão do microfone e grava a fala inteira
        (MediaRecorder -- mesmo mecanismo já usado no "Speak it!" dos
        exercícios, comprovadamente confiável).
     2. Ao parar a gravação, o áudio completo é enviado de uma vez pro
        backend (POST /conversation/turn, multipart/form-data).
     3. O backend transcreve, manda pra IA analisar a gramática E gerar a
        resposta do tutor, e devolve tudo (texto + análise + áudio da
        resposta) numa única resposta JSON.
     4. Essa tela só precisa desenhar o que voltou -- sem WebSocket, sem
        AudioWorklet, sem lidar com deltas chegando aos poucos.

   Usa a autenticação real do app (Auth / apiFetch, de js/api.js).
   ========================================================================== */

// -----------------------------------------------------------------------
// ELEMENTOS
// -----------------------------------------------------------------------
const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");

const els = {
  lockedBox: document.getElementById("conv-locked"),
  workspace: document.getElementById("conv-workspace"),
  chatScroll: document.getElementById("chat-scroll"),
  micBtn: document.getElementById("mic-btn"),
  micStatus: document.getElementById("mic-status"),
  analysisPanel: document.getElementById("analysis-panel"),
  analysisBody: document.getElementById("analysis-body"),
  analysisCollapseBtn: document.getElementById("analysis-collapse-btn"),
};

document.getElementById("logout-btn").addEventListener("click", () => {
  const ok = window.confirm("Deseja sair da sua conta?");
  if (ok) Auth.logout();
});

// -----------------------------------------------------------------------
// ESTADO
// -----------------------------------------------------------------------
const state = {
  mediaRecorder: null,
  micStream: null,
  audioChunks: [],
  recordedMimeType: "audio/webm",
  isRecording: false,
  isSending: false,
  targetLanguage: "ingles",
  nativeLanguage: "pt",

  currentTutorBubbleEl: null,

  analysisById: new Map(), // id do bloco de análise -> dados, para reabrir no painel
  analysisCounter: 0,
};

// =========================================================================
// ENVIO DE UM TURNO (áudio -> transcrição + análise + resposta do tutor)
// =========================================================================

async function sendTurnToServer(audioBlob) {
  const formData = new FormData();
  const ext = state.recordedMimeType.includes("ogg") ? "ogg" : "webm";
  formData.append("audio", audioBlob, `fala.${ext}`);
  formData.append("target_language", state.targetLanguage);
  formData.append("native_language", state.nativeLanguage);

  const token = Auth.getToken();
  const response = await fetch(`${API_BASE_URL}/conversation/turn`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) {
    let detail = `Erro inesperado (${response.status}).`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = body.detail;
    } catch (e) {
      /* resposta sem corpo JSON, mantém mensagem genérica */
    }
    throw new Error(detail);
  }

  return response.json();
}

function handleTurnResult(result) {
  if (result.student_transcript) {
    addStudentBubble(result.student_transcript);
  }
  if (result.analysis) {
    addAnalysisSummaryBar(result.analysis);
    renderAnalysisPanel(result.analysis);
  }
  if (result.tutor_reply) {
    addTutorBubble(result.tutor_reply);
  }
  if (result.tutor_audio_b64) {
    playTutorAudioFromBase64Mp3(result.tutor_audio_b64);
  }
}

// =========================================================================
// CHAT -- renderização das bolhas
// =========================================================================

function scrollChatToBottom() {
  els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
}

function addTutorBubble(initialText = "") {
  const tpl = document.getElementById("tpl-tutor-bubble");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".bubble-text").textContent = initialText;

  const listenBtn = node.querySelector(".listen-btn");
  const translateBtn = node.querySelector(".translate-btn");

  listenBtn.addEventListener("click", () => {
    const text = node.querySelector(".bubble-text").textContent;
    playTTS(text, targetLocale(state.targetLanguage));
  });

  translateBtn.addEventListener("click", async () => {
    const translationEl = node.querySelector(".bubble-translation");
    const text = node.querySelector(".bubble-text").textContent;

    translateBtn.classList.toggle("active");
    if (translationEl.classList.contains("hidden") && !translationEl.textContent) {
      const { translated } = await translateText(text, state.nativeLanguage);
      translationEl.innerHTML = `
        <svg viewBox="0 0 24 24"><path d="M3 5h9M7 3v2m0 0c0 4-2 7-5 8m5-8c1 2 2.5 3.4 4 4.3M14 21l4-9 4 9M15.6 18h4.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span>${escapeHtml(translated)}</span>`;
    }
    translationEl.classList.toggle("hidden");
  });

  els.chatScroll.appendChild(node);
  scrollChatToBottom();
  return node;
}

function addStudentBubble(text) {
  const tpl = document.getElementById("tpl-student-bubble");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".bubble-text").textContent = text;
  els.chatScroll.appendChild(node);
  scrollChatToBottom();
  return node;
}

function addAnalysisSummaryBar(analysis) {
  const tpl = document.getElementById("tpl-analysis-summary");
  const node = tpl.content.firstElementChild.cloneNode(true);

  const id = ++state.analysisCounter;
  state.analysisById.set(id, analysis);

  const titleEl = node.querySelector(".analysis-summary-title");
  const chevEl = titleEl.querySelector(".chev");
  titleEl.addEventListener("click", () => {
    node.classList.toggle("collapsed-summary");
    chevEl.textContent = chevEl.textContent === "⌃" ? "⌄" : "⌃";
  });

  node.querySelector(".ver-analise-btn").addEventListener("click", () => {
    renderAnalysisPanel(analysis);
  });

  els.chatScroll.appendChild(node);
  scrollChatToBottom();
  return node;
}

// =========================================================================
// PAINEL "SPEECH ANALYSIS"
// =========================================================================

function renderAnalysisPanel(analysis) {
  els.analysisPanel.classList.remove("hidden");

  const sentence = analysis.student_transcript || "";
  const errors = analysis.errors || [];

  let highlightedSentence = escapeHtml(sentence);
  errors.forEach((err) => {
    if (!err.wrong_fragment) return;
    const safe = escapeHtml(err.wrong_fragment);
    const re = new RegExp(escapeRegExp(safe), "i");
    highlightedSentence = highlightedSentence.replace(re, `<span class="wrong">${safe}</span>`);
  });

  const feedbackItems = errors.map((err, idx) => `
    <li>
      <span class="feedback-index">${idx + 1}.</span>
      <div>
        <span class="feedback-diff">
          <span class="wrong">${escapeHtml(err.wrong_fragment)}</span>
          <span class="arrow">→</span>
          <span class="right">${escapeHtml(err.correct_fragment)}</span>
        </span>
        <span class="feedback-reason">${escapeHtml(err.explanation_native || err.explanation_pt_br || "")}</span>
      </div>
    </li>
  `).join("");

  els.analysisBody.innerHTML = `
    <div class="analysis-sentence">${highlightedSentence || "-"}</div>

    <div class="analysis-correction">
      <div class="analysis-section-title">Correção</div>
      ${escapeHtml(analysis.corrected_sentence || "-")}
    </div>

    <div>
      <div class="analysis-section-title">Feedback</div>
      <ul class="analysis-feedback-list">
        ${feedbackItems || "<li>Nenhum erro encontrado. 🎉</li>"}
      </ul>
    </div>

    ${(analysis.feedback_native || analysis.feedback_pt_br) ? `<div class="analysis-overall-feedback">${escapeHtml(analysis.feedback_native || analysis.feedback_pt_br)}</div>` : ""}
  `;
}

els.analysisCollapseBtn.addEventListener("click", () => {
  els.analysisPanel.classList.add("hidden");
});

// =========================================================================
// MICROFONE (grava a fala inteira com MediaRecorder, manda de uma vez)
// =========================================================================

function setMicEnabled(enabled) {
  els.micBtn.disabled = !enabled;
  if (enabled) setMicStatus("Toque para falar");
}

function setMicStatus(text) {
  els.micStatus.textContent = text;
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setMicStatus("Seu navegador não suporta gravação de áudio.");
    return;
  }

  try {
    state.micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });

    const preferredMimeTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ];
    let mimeType = "";
    for (const mt of preferredMimeTypes) {
      if (MediaRecorder.isTypeSupported(mt)) {
        mimeType = mt;
        break;
      }
    }
    state.recordedMimeType = mimeType || "audio/webm";

    state.audioChunks = [];
    state.mediaRecorder = new MediaRecorder(
      state.micStream,
      mimeType ? { mimeType } : undefined
    );

    state.mediaRecorder.ondataavailable = (evt) => {
      if (evt.data && evt.data.size > 0) state.audioChunks.push(evt.data);
    };

    state.mediaRecorder.onstop = onRecordingStopped;

    state.mediaRecorder.start();
    state.isRecording = true;
    els.micBtn.classList.add("recording");
    setMicStatus("Ouvindo... toque para parar");
  } catch (err) {
    console.error("Erro ao acessar microfone:", err);
    setMicStatus("Não foi possível acessar o microfone");
  }
}

function stopRecording() {
  if (!state.mediaRecorder || !state.isRecording) return;
  state.isRecording = false;
  els.micBtn.classList.remove("recording");
  state.mediaRecorder.stop(); // dispara onRecordingStopped quando o blob estiver pronto
}

async function onRecordingStopped() {
  if (state.micStream) {
    state.micStream.getTracks().forEach((t) => t.stop());
    state.micStream = null;
  }

  const blob = new Blob(state.audioChunks, { type: state.recordedMimeType });
  state.audioChunks = [];

  if (blob.size < 300) {
    setMicStatus("Fala muito curta, segure o botão e fale um pouco mais");
    setTimeout(() => setMicStatus("Toque para falar"), 1800);
    return;
  }

  state.isSending = true;
  els.micBtn.disabled = true;
  setMicStatus("Processando sua fala...");

  try {
    const result = await sendTurnToServer(blob);
    handleTurnResult(result);
    setMicStatus("Toque para falar");
  } catch (err) {
    console.error("Erro no turno de conversa:", err);
    setMicStatus(err.message || "Erro ao processar áudio. Tente de novo.");
    setTimeout(() => setMicStatus("Toque para falar"), 3000);
  } finally {
    state.isSending = false;
    els.micBtn.disabled = false;
  }
}

els.micBtn.addEventListener("click", () => {
  if (state.isSending) return;
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// =========================================================================
// REPRODUÇÃO DE ÁUDIO DO TUTOR (mp3 em base64, vindo pronto do backend)
// =========================================================================

function playTutorAudioFromBase64Mp3(base64Mp3) {
  try {
    const url = `data:audio/mpeg;base64,${base64Mp3}`;
    const audio = new Audio(url);
    audio.play().catch((e) => console.warn("Autoplay bloqueado, aguardando interação:", e));
  } catch (err) {
    console.warn("Falha ao reproduzir áudio do tutor:", err);
  }
}

/**
 * POST autenticado que espera de volta áudio binário (Blob), reaproveitando
 * o mesmo token de sessão usado em apiFetch (js/api.js).
 */
async function apiPostForBlob(path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = Auth.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Erro inesperado (${response.status}).`);
  }
  return response.blob();
}

async function playTTS(text, lang) {
  try {
    const blob = await apiPostForBlob("/conversation/tts", { text, lang });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
    audio.addEventListener("ended", () => URL.revokeObjectURL(url));
  } catch (err) {
    console.error("Erro no TTS:", err);
  }
}

async function translateText(text, nativeLanguage = "pt") {
  try {
    return await apiFetch("/conversation/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, native_language: nativeLanguage }),
    });
  } catch (err) {
    console.error("Erro na tradução:", err);
    return { original: text, translated: "(falha ao traduzir)" };
  }
}

// =========================================================================
// HELPERS
// =========================================================================

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeLanguage(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (["it", "italiano"].includes(raw)) return "italiano";
  if (["fr", "frances", "francês", "français"].includes(raw)) return "frances";
  if (["es", "espanhol", "español"].includes(raw)) return "espanhol";
  if (["de", "alemao", "alemão", "deutsch"].includes(raw)) return "alemao";
  if (["pt", "pt-br", "portugues", "português"].includes(raw)) return "portugues";
  return "ingles";
}

function targetLocale(language) {
  return { ingles: "en-US", italiano: "it-IT", frances: "fr-FR", espanhol: "es-ES", alemao: "de-DE", portugues: "pt-BR" }[normalizeLanguage(language)] || "en-US";
}

// =========================================================================
// INICIALIZAÇÃO
// =========================================================================

function showLocked(message) {
  els.lockedBox.textContent = message;
  els.lockedBox.classList.remove("hidden");
  els.workspace.classList.add("hidden");
}

async function tryResumeHistory() {
  try {
    const data = await apiFetch("/conversation/history");
    if (data && data.active && Array.isArray(data.history) && data.history.length > 0) {
      for (const turn of data.history) {
        if (turn.role === "student") {
          addStudentBubble(turn.text);
          if (turn.analysis) {
            addAnalysisSummaryBar(turn.analysis);
          }
        } else if (turn.role === "tutor") {
          addTutorBubble(turn.text);
        }
      }
      return true;
    }
  } catch (err) {
    console.warn("Não foi possível retomar o histórico da conversa:", err);
  }
  return false;
}

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
  state.targetLanguage = normalizeLanguage(user.target_language || "ingles");
  state.nativeLanguage = normalizeLanguage(user.native_language || "pt");
  roleLabelEl.textContent = user.role === "professor" ? "PROFESSOR" : "ALUNO";

  if (user.role !== "aluno") {
    window.location.href = "professor.html";
    return;
  }

  if (!user.is_approved) {
    showLocked("Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá conversar com o IA Tutor.");
    return;
  }

  els.workspace.classList.remove("hidden");

  const resumed = await tryResumeHistory();
  // A nova conversa começa vazia: o aluno escolhe e inicia o assunto.
  // Nenhuma mensagem automática é inserida aqui.


  setMicEnabled(true);
}

init();
