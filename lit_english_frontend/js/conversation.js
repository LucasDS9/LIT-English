/* ==========================================================================
   LIT English — conversation.js
   Tela "Conversa com IA Tutor". Conecta no WebSocket do backend
   (/ws/conversation), captura o microfone em PCM16 16kHz via AudioWorklet,
   manda pro backend, e renderiza as bolhas de chat + o painel
   "Speech Analysis" com o que a IA devolve.

   Usa a autenticação real do app (Auth / apiFetch, de js/api.js): o aluno
   nunca é passado como parâmetro solto — o backend identifica quem está
   falando pelo token JWT.
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
  ws: null,
  audioContext: null,
  workletNode: null,
  micStream: null,
  isRecording: false,
  wantsReconnect: true,

  currentTutorBubbleEl: null, // bolha do tutor sendo montada via delta
  tutorAudioChunks: [], // Int16Array[] acumulados da resposta atual do tutor

  analysisById: new Map(), // id do bloco de análise -> dados, para reabrir no painel
  analysisCounter: 0,
};

// =========================================================================
// WEBSOCKET
// =========================================================================

function wsBaseUrl() {
  return API_BASE_URL.replace(/^http/, "ws");
}

function connectWebSocket() {
  const token = Auth.getToken();
  if (!token) return;

  const params = new URLSearchParams({ token });
  const url = `${wsBaseUrl()}/ws/conversation?${params}`;

  const ws = new WebSocket(url);
  ws.onopen = () => console.log("[conversation] WS conectado");
  ws.onclose = () => {
    console.log("[conversation] WS desconectado");
    setMicEnabled(false);
    if (state.wantsReconnect) {
      setTimeout(connectWebSocket, 3000);
    }
  };
  ws.onerror = (e) => console.error("[conversation] WS erro", e);
  ws.onmessage = (evt) => handleServerMessage(JSON.parse(evt.data));

  state.ws = ws;
}

function sendToServer(payload) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(payload));
  }
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case "session_ready":
      setMicEnabled(true);
      break;

    case "student_transcript":
      // já mostramos a bolha do aluno otimisticamente via speech_analysis;
      // se quiser exibir só quando a transcrição chega, adapte aqui.
      break;

    case "speech_analysis":
      onSpeechAnalysis(msg.analysis);
      break;

    case "tutor_text_delta":
      onTutorTextDelta(msg.delta);
      break;

    case "tutor_text_done":
      onTutorTextDone(msg.text);
      break;

    case "tutor_audio_chunk":
      state.tutorAudioChunks.push(base64ToInt16Array(msg.audio_b64));
      break;

    case "tutor_audio_done":
      playTutorAudio();
      break;

    case "error":
      console.error("[conversation] erro do backend:", msg.message);
      setMicStatus(`Erro: ${msg.message}`);
      break;

    default:
      // ignora eventos não usados pela UI
      break;
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
    playTTS(text, "en-US");
  });

  translateBtn.addEventListener("click", async () => {
    const translationEl = node.querySelector(".bubble-translation");
    const text = node.querySelector(".bubble-text").textContent;

    translateBtn.classList.toggle("active");
    if (translationEl.classList.contains("hidden") && !translationEl.textContent) {
      const { translated } = await translateText(text);
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
// EVENTOS DE CONVERSA
// =========================================================================

function onSpeechAnalysis(analysis) {
  if (analysis.student_transcript) {
    addStudentBubble(analysis.student_transcript);
  }
  addAnalysisSummaryBar(analysis);
  renderAnalysisPanel(analysis); // já abre o painel com a análise mais recente
}

function onTutorTextDelta(delta) {
  if (!state.currentTutorBubbleEl) {
    state.currentTutorBubbleEl = addTutorBubble("");
  }
  const textEl = state.currentTutorBubbleEl.querySelector(".bubble-text");
  textEl.textContent += delta;
  scrollChatToBottom();
}

function onTutorTextDone(fullText) {
  if (state.currentTutorBubbleEl) {
    state.currentTutorBubbleEl.querySelector(".bubble-text").textContent = fullText;
  } else if (fullText) {
    addTutorBubble(fullText);
  }
  state.currentTutorBubbleEl = null;
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
        <span class="feedback-reason">${escapeHtml(err.explanation_pt_br)}</span>
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

    ${analysis.feedback_pt_br ? `<div class="analysis-overall-feedback">${escapeHtml(analysis.feedback_pt_br)}</div>` : ""}
  `;
}

els.analysisCollapseBtn.addEventListener("click", () => {
  els.analysisPanel.classList.add("hidden");
});

// =========================================================================
// MICROFONE (captura PCM16 16kHz via AudioWorklet)
// =========================================================================

function setMicEnabled(enabled) {
  els.micBtn.disabled = !enabled;
  if (enabled) setMicStatus("Toque para falar");
}

function setMicStatus(text) {
  els.micStatus.textContent = text;
}

async function startRecording() {
  try {
    state.micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });

    state.audioContext = new AudioContext();
    await state.audioContext.audioWorklet.addModule("js/pcm-worklet-processor.js");

    const source = state.audioContext.createMediaStreamSource(state.micStream);
    state.workletNode = new AudioWorkletNode(state.audioContext, "pcm-recorder-processor");

    state.workletNode.port.onmessage = (evt) => {
      const int16Buffer = evt.data; // ArrayBuffer
      const audio_b64 = arrayBufferToBase64(int16Buffer);
      sendToServer({ type: "audio_chunk", audio_b64 });
    };

    source.connect(state.workletNode);
    // não conectamos workletNode ao destination -- não queremos ouvir o próprio mic

    state.isRecording = true;
    els.micBtn.classList.add("recording");
    setMicStatus("Ouvindo... toque para parar");
  } catch (err) {
    console.error("Erro ao acessar microfone:", err);
    setMicStatus("Não foi possível acessar o microfone");
  }
}

function stopRecording() {
  state.isRecording = false;
  els.micBtn.classList.remove("recording");
  setMicStatus("Processando...");

  sendToServer({ type: "end_turn" });

  if (state.micStream) {
    state.micStream.getTracks().forEach((t) => t.stop());
    state.micStream = null;
  }
  if (state.workletNode) {
    state.workletNode.disconnect();
    state.workletNode = null;
  }
  if (state.audioContext) {
    state.audioContext.close();
    state.audioContext = null;
  }

  setTimeout(() => setMicStatus("Toque para falar"), 1500);
}

els.micBtn.addEventListener("click", () => {
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// =========================================================================
// REPRODUÇÃO DE ÁUDIO DO TUTOR (PCM16 -> WAV -> <audio>)
// =========================================================================

function playTutorAudio() {
  if (state.tutorAudioChunks.length === 0) return;

  const totalLength = state.tutorAudioChunks.reduce((sum, c) => sum + c.length, 0);
  const merged = new Int16Array(totalLength);
  let offset = 0;
  for (const chunk of state.tutorAudioChunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  state.tutorAudioChunks = [];

  const wavBlob = pcm16ToWavBlob(merged, 24000); // Voice Live costuma devolver áudio a 24kHz
  const url = URL.createObjectURL(wavBlob);
  const audio = new Audio(url);
  audio.play().catch((e) => console.warn("Autoplay bloqueado, aguardando interação:", e));
  audio.addEventListener("ended", () => URL.revokeObjectURL(url));
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

async function translateText(text) {
  try {
    return await apiFetch("/conversation/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch (err) {
    console.error("Erro na tradução:", err);
    return { original: text, translated: "(falha ao traduzir)" };
  }
}

// =========================================================================
// HELPERS
// =========================================================================

function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToInt16Array(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

function pcm16ToWavBlob(int16Array, sampleRate) {
  const numChannels = 1;
  const bytesPerSample = 2;
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = int16Array.length * bytesPerSample;

  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true); // bits per sample
  writeString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < int16Array.length; i++, offset += 2) {
    view.setInt16(offset, int16Array[i], true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

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

// =========================================================================
// INICIALIZAÇÃO
// =========================================================================

function showLocked(message) {
  els.lockedBox.textContent = message;
  els.lockedBox.classList.remove("hidden");
  els.workspace.classList.add("hidden");
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
  addTutorBubble("What did you do last weekend?");
  connectWebSocket();
}

window.addEventListener("beforeunload", () => {
  state.wantsReconnect = false;
});

init();
