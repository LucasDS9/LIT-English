/* ==========================================================================
   LIT English — flashcard-pronounce.js
   Gravação e envio de áudio para pronúncia (Aprender, Revisar, Speak).
   ========================================================================== */

const FlashcardPronounce = (() => {
  const PREFERRED_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  function showFeedback(container, result) {
    if (!container) return;
    container.hidden = false;
    const reasonHtml = result.reason
      ? `<div style="font-weight:400;font-size:0.9em;margin-top:4px;">${result.reason}</div>`
      : "";
    if (result.correct) {
      container.style.background = "#f0faf4";
      container.style.border = "1px solid #b7dfc7";
      const said = result.transcribed_text ? ` Você disse: "${result.transcribed_text}"` : "";
      container.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#155724" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg><span style="color:#155724;font-weight:600;">Pronúncia correta!<span style="font-weight:400;">${said}</span>${reasonHtml}</span>`;
    } else {
      container.style.background = "#fff5f5";
      container.style.border = "1px solid #f5c6cb";
      const said = result.transcribed_text ? ` Você disse: "${result.transcribed_text}".` : "";
      container.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9 9 15M9 9l6 6"/></svg><span style="color:#721c24;font-weight:600;">Pronúncia incorreta.${said} <span style="font-weight:400;">Esperado: <strong>${result.correct_answer}</strong></span>${reasonHtml}</span>`;
    }
  }

  async function submitAudio(recordedBlob, submitUrl) {
    const formData = new FormData();
    const ext = recordedBlob.type.includes("ogg") ? "ogg" : "webm";
    formData.append("audio", recordedBlob, `recording.${ext}`);

    const token = Auth.getToken();
    const response = await fetch(`${API_BASE_URL}${submitUrl}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody.detail || `Erro ${response.status}`);
    }
    return response.json();
  }

  /**
   * Anexa gravação toggle ao botão. onStop recebe o Blob gravado.
   * Retorna função cleanup() para parar stream pendente.
   */
  function attachRecordButton(btn, {
    onStop,
    onError,
    recordingLabel = "Parar gravação",
    idleLabel = "Pronunciar",
    stopLabel = "Analisando...",
    disableOnStop = true,
  }) {
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let stream = null;

    const handler = async () => {
      if (isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        btn.classList.remove("is-recording");
        if (stopLabel) {
          btn.querySelector("span").textContent = stopLabel;
        }
        if (disableOnStop) {
          btn.disabled = true;
        }
        return;
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        onError(new Error("Seu navegador não suporta gravação de áudio."));
        return;
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
        });
        audioChunks = [];
        let mimeType = "";
        for (const mt of PREFERRED_MIME_TYPES) {
          if (MediaRecorder.isTypeSupported(mt)) {
            mimeType = mt;
            break;
          }
        }
        mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };
        mediaRecorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          stream = null;
          const blobType = mimeType || "audio/webm";
          onStop(new Blob(audioChunks, { type: blobType }));
        };
        mediaRecorder.start();
        isRecording = true;
        btn.classList.add("is-recording");
        btn.querySelector("span").textContent = recordingLabel;
      } catch (err) {
        if (stream) {
          stream.getTracks().forEach((t) => t.stop());
          stream = null;
        }
        onError(err);
      }
    };

    btn.addEventListener("click", handler);

    return {
      reset() {
        btn.disabled = false;
        btn.classList.remove("is-recording");
        const span = btn.querySelector("span");
        if (span) span.textContent = idleLabel;
      },
    };
  }

  function buildAudioControlsRow({ listenLabel, onListen, showPronounce, pronounceLabel, onPronounceReady }) {
    const controls = document.createElement("div");
    controls.className = "review-audio-controls";

    const listenBtn = document.createElement("button");
    listenBtn.type = "button";
    listenBtn.className = "btn btn-outline review-audio-btn";
    listenBtn.innerHTML = `${Icons.volume}<span>${listenLabel}</span>`;
    listenBtn.addEventListener("click", onListen);
    controls.appendChild(listenBtn);

    let pronounceBtn = null;
    if (showPronounce) {
      pronounceBtn = document.createElement("button");
      pronounceBtn.type = "button";
      pronounceBtn.className = "btn btn-outline review-audio-btn";
      pronounceBtn.innerHTML = `${Icons.mic}<span>${pronounceLabel || "Pronunciar"}</span>`;
      controls.appendChild(pronounceBtn);
      if (onPronounceReady) onPronounceReady(pronounceBtn);
    }

    return { controls, listenBtn, pronounceBtn };
  }

  return {
    showFeedback,
    submitAudio,
    attachRecordButton,
    buildAudioControlsRow,
  };
})();
