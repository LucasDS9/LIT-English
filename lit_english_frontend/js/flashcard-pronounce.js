/* ==========================================================================
   LIT English — flashcard-pronounce.js
   Gravação, envio e UI de feedback de pronúncia (Aprender, Revisar, Speak).
   ========================================================================== */

const FlashcardPronounce = (() => {
  const PREFERRED_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  /** Limite alinhado ao backend (Azure free tier). */
  const PRONUNCIATION_MAX_DURATION_MS = 5000;

  const SCORE_TIERS = [
    { min: 80, id: "good", legend: "Boa pronúncia (80-100)", color: "#861E19", className: "tier-good" },
    { min: 60, id: "medium", legend: "Pode melhorar (60-79)", color: "#D18C8C", className: "tier-medium" },
    { min: 0, id: "bad", legend: "Pronúncia incorreta (0-59)", color: "#F2C4C4", className: "tier-bad" },
  ];

  const LANGUAGE_META = {
    ingles: {
      label: "Inglês",
      flag: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#012169"/><path d="M0 0l24 16M24 0L0 16" stroke="#fff" stroke-width="2.4"/><path d="M0 0l24 16M24 0L0 16" stroke="#C8102E" stroke-width="1.2"/><path d="M12 0v16M0 8h24" stroke="#fff" stroke-width="3.2"/><path d="M12 0v16M0 8h24" stroke="#C8102E" stroke-width="1.6"/></svg>`,
    },
    italiano: {
      label: "Italiano",
      flag: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect x="8" width="8" height="16" fill="#CE2B37"/><rect width="8" height="16" fill="#009246"/></svg>`,
    },
    frances: {
      label: "Francês",
      flag: `<svg viewBox="0 0 24 16" aria-hidden="true"><rect width="24" height="16" rx="2" fill="#fff"/><rect width="8" height="16" fill="#0055A4"/><rect x="16" width="8" height="16" fill="#EF4135"/></svg>`,
    },
  };

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"]/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
    ));
  }

  function getScoreTier(score) {
    const value = Number(score) || 0;
    for (const tier of SCORE_TIERS) {
      if (value >= tier.min) return tier;
    }
    return SCORE_TIERS[SCORE_TIERS.length - 1];
  }

  function getLanguageMeta(languageCode) {
    const code = (languageCode || "ingles").trim().toLowerCase();
    return LANGUAGE_META[code] || LANGUAGE_META.ingles;
  }

  function buildWordScoresFromReference(referenceText, wordScores) {
    const refWords = (referenceText || "").trim().split(/\s+/).filter(Boolean);
    if (refWords.length === 0) return wordScores || [];

    if (!wordScores || wordScores.length === 0) {
      return refWords.map((word) => ({ word, score: 0 }));
    }

    return refWords.map((word, index) => {
      const direct = wordScores[index];
      if (direct) {
        return {
          word,
          score: Math.max(0, Math.min(100, Number(direct.score))),
        };
      }
      const match = wordScores.find(
        (entry) => entry.word.toLowerCase() === word.toLowerCase()
      );
      if (match) {
        return {
          word,
          score: Math.max(0, Math.min(100, Number(match.score))),
        };
      }
      return { word, score: 0 };
    });
  }

  /** Usa apenas score e word_scores reais da Azure — sem estimativas. */
  function normalizePronunciationResult(result) {
    const score = result.score != null
      ? Math.max(0, Math.min(100, Number(result.score)))
      : null;

    const rawWordScores = Array.isArray(result.word_scores)
      ? result.word_scores.map((item) => ({
        word: item.word,
        score: Math.max(0, Math.min(100, Number(item.score))),
      }))
      : [];

    const wordScores = buildWordScoresFromReference(result.correct_answer, rawWordScores);
    const effectiveScore = score != null ? score : 0;

    return {
      score,
      wordScores,
      feedbackTitle: result.feedback_title || "",
      reason: result.reason || "",
      transcribedText: result.transcribed_text || "",
      tier: getScoreTier(effectiveScore),
      hasAssessment: score != null,
    };
  }

  function colorizePhrase(text, wordScores) {
    const refWords = (text || "").trim().split(/\s+/).filter(Boolean);
    if (refWords.length === 0) {
      return escapeHtml(text);
    }

    const aligned = buildWordScoresFromReference(text, wordScores);
    return aligned.map((entry) => {
      const tier = getScoreTier(entry.score);
      return `<span class="pronunciation-word ${tier.className}">${escapeHtml(entry.word)}</span>`;
    }).join(" ");
  }

  function buildLangBadge(languageCode) {
    const meta = getLanguageMeta(languageCode);
    const badge = document.createElement("div");
    badge.className = "learn-lang-badge";
    badge.innerHTML = `<span class="learn-lang-flag">${meta.flag}</span><span>${meta.label}</span>`;
    return badge;
  }

  function buildLegend() {
    const legend = document.createElement("div");
    legend.className = "pronunciation-legend";
    legend.innerHTML = `
      <p class="pronunciation-legend-title">Indicador de pronúncia da frase</p>
      <div class="pronunciation-legend-items">
        ${SCORE_TIERS.map((tier) => `
          <span class="pronunciation-legend-item">
            <span class="pronunciation-legend-dot ${tier.className}"></span>
            ${tier.legend}
          </span>
        `).join("")}
      </div>
    `;
    return legend;
  }

  function buildScoreRing(score, tier) {
    const radius = 52;
    const circumference = 2 * Math.PI * radius;
    const progress = Math.max(0, Math.min(100, score)) / 100;
    const dashOffset = circumference * (1 - progress);

    const wrap = document.createElement("div");
    wrap.className = "pronunciation-score-ring-wrap";
    wrap.innerHTML = `
      <svg class="pronunciation-score-ring" viewBox="0 0 120 120" aria-hidden="true">
        <circle class="ring-bg" cx="60" cy="60" r="${radius}" />
        <circle
          class="ring-fill ${tier.className}"
          cx="60"
          cy="60"
          r="${radius}"
          stroke="${tier.color}"
          stroke-dasharray="${circumference.toFixed(2)}"
          stroke-dashoffset="${dashOffset.toFixed(2)}"
        />
      </svg>
      <div class="pronunciation-score-value ${tier.className}">
        <span class="score-num">${score}</span>
        <span class="score-denom">/ 100</span>
      </div>
    `;
    return wrap;
  }

  function feedbackHeadline(tier) {
    if (tier.id === "good") return "Ótima pronúncia!";
    if (tier.id === "medium") return "Boa pronúncia!";
    return "Tente novamente!";
  }

  function feedbackIcon(tier) {
    if (tier.id === "good") {
      return `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>`;
    }
    return `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9 9 15M9 9l6 6"/></svg>`;
  }

  function defaultFeedbackDetail(tier, wordScores) {
    if (tier.id === "good") {
      return "Continue praticando para manter essa fluência.";
    }
    if (tier.id === "medium") {
      return "Sua pronúncia está no caminho certo — refine o ritmo e os sons finais.";
    }
    const weak = [...wordScores].sort((a, b) => a.score - b.score)[0];
    if (weak) {
      return `Preste atenção ao som de "${weak.word}" e ao ritmo da frase.`;
    }
    return "Preste atenção ao ritmo da frase e aos sons de cada palavra.";
  }

  /**
   * Verso do card Aprender com feedback visual de pronúncia (após virar).
   */
  function buildPronunciationBack({
    card,
    learnResult,
    pronunciationResult,
    languageCode,
    cardIndex,
    totalCards,
    onListen,
  }) {
    const normalized = normalizePronunciationResult(pronunciationResult);
    const usageText = learnResult.explanation || card.tip || "";
    const displayScore = normalized.score != null ? normalized.score : 0;

    const back = document.createElement("div");
    back.className = "learn-card-back-pronunciation";

    const header = document.createElement("div");
    header.className = "learn-card-header";
    header.appendChild(buildLangBadge(languageCode));
    const counter = document.createElement("span");
    counter.className = "learn-card-counter";
    counter.textContent = `${cardIndex + 1} / ${totalCards}`;
    header.appendChild(counter);
    back.appendChild(header);

    const phrase = document.createElement("p");
    phrase.className = "pronunciation-phrase";
    phrase.innerHTML = colorizePhrase(card.word, normalized.wordScores);
    back.appendChild(phrase);

    const divider = document.createElement("div");
    divider.className = "pronunciation-phrase-divider";
    back.appendChild(divider);

    const translation = document.createElement("p");
    translation.className = "pronunciation-translation";
    translation.textContent = learnResult.correct_answer;
    back.appendChild(translation);

    if (usageText) {
      const usage = document.createElement("div");
      usage.className = "pronunciation-usage";
      usage.innerHTML = `
        <span class="pronunciation-usage-label">Usado para</span>
        <p class="pronunciation-usage-text">${escapeHtml(usageText)}</p>
      `;
      back.appendChild(usage);
    }

    const scoreSection = document.createElement("div");
    scoreSection.className = "pronunciation-score-section";
    scoreSection.innerHTML = `<p class="pronunciation-score-label">Sua pronúncia</p>`;
    scoreSection.appendChild(buildScoreRing(displayScore, normalized.tier));

    const feedback = document.createElement("div");
    feedback.className = `pronunciation-ai-feedback ${normalized.tier.className}`;
    const headline = normalized.feedbackTitle || feedbackHeadline(normalized.tier);
    const detail = normalized.reason || defaultFeedbackDetail(normalized.tier, normalized.wordScores);
    feedback.innerHTML = `
      <span class="pronunciation-ai-icon">${feedbackIcon(normalized.tier)}</span>
      <div class="pronunciation-ai-text">
        <strong>${escapeHtml(headline)}</strong>
        <p>${escapeHtml(detail)}</p>
      </div>
    `;
    scoreSection.appendChild(feedback);
    back.appendChild(scoreSection);

    const listenBtn = document.createElement("button");
    listenBtn.type = "button";
    listenBtn.className = "btn btn-outline pronunciation-listen-btn";
    listenBtn.innerHTML = `${Icons.volume}<span>Ouvir pronúncia correta</span>`;
    listenBtn.addEventListener("click", () => onListen(listenBtn));
    back.appendChild(listenBtn);

    return back;
  }

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

  function attachRecordButton(btn, {
    onStop,
    onError,
    recordingLabel = "Parar gravação",
    idleLabel = "Pronunciar",
    preparingLabel = "Preparando...",
    stopLabel = "Analisando...",
    disableOnStop = true,
    maxDurationMs = PRONUNCIATION_MAX_DURATION_MS,
  }) {
    let mediaRecorder = null;
    let audioChunks = [];
    let stream = null;
    let maxDurationTimer = null;
    let state = "idle"; // idle | preparing | recording | analyzing

    function getLabelSpan() {
      return btn.querySelector(".record-label") || btn.querySelector("span:last-child");
    }

    function setLabel(text) {
      const span = getLabelSpan();
      if (span) span.textContent = text;
    }

    function clearMaxDurationTimer() {
      if (maxDurationTimer) {
        clearTimeout(maxDurationTimer);
        maxDurationTimer = null;
      }
    }

    function cleanupStream() {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        stream = null;
      }
    }

    function resetToIdle() {
      clearMaxDurationTimer();
      cleanupStream();
      mediaRecorder = null;
      audioChunks = [];
      state = "idle";
      btn.disabled = false;
      btn.classList.remove("is-preparing", "is-recording", "is-analyzing");
      setLabel(idleLabel);
    }

    function finishRecording() {
      if (state !== "recording" || !mediaRecorder) return;

      clearMaxDurationTimer();
      state = "analyzing";
      btn.disabled = disableOnStop;
      btn.classList.remove("is-recording");
      btn.classList.add("is-analyzing");
      setLabel(stopLabel || "Analisando...");
      mediaRecorder.stop();
    }

    const handler = async () => {
      if (state === "preparing" || state === "analyzing") return;

      if (state === "recording") {
        finishRecording();
        return;
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        onError(new Error("Seu navegador não suporta gravação de áudio."));
        return;
      }

      state = "preparing";
      btn.disabled = true;
      btn.classList.add("is-preparing");
      setLabel(preparingLabel);

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
        });

        if (state !== "preparing") {
          cleanupStream();
          return;
        }

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
          cleanupStream();
          const blobType = mimeType || "audio/webm";
          const blob = new Blob(audioChunks, { type: blobType });
          mediaRecorder = null;
          audioChunks = [];
          onStop(blob);
          if (!disableOnStop) {
            state = "idle";
            btn.disabled = false;
            btn.classList.remove("is-recording", "is-analyzing");
            setLabel(stopLabel || idleLabel);
          }
        };

        mediaRecorder.start(200);
        state = "recording";
        btn.disabled = false;
        btn.classList.remove("is-preparing");
        btn.classList.add("is-recording");
        setLabel(recordingLabel);

        if (maxDurationMs > 0) {
          maxDurationTimer = setTimeout(() => {
            if (state === "recording") finishRecording();
          }, maxDurationMs);
        }
      } catch (err) {
        resetToIdle();
        onError(err);
      }
    };

    btn.addEventListener("click", handler);

    return {
      reset: resetToIdle,
      cancel() {
        if (state === "recording" && mediaRecorder) {
          try {
            mediaRecorder.stop();
          } catch (_) {
            /* ignore */
          }
        }
        resetToIdle();
      },
    };
  }

  function buildMicButtonContent(label) {
    return `<span class="mic-icon-wrap" aria-hidden="true">${Icons.mic}</span><span class="record-label">${label}</span>`;
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
      pronounceBtn.className = "btn btn-outline review-audio-btn review-audio-btn--mic";
      pronounceBtn.innerHTML = buildMicButtonContent(pronounceLabel || "Pronunciar");
      controls.appendChild(pronounceBtn);
      if (onPronounceReady) onPronounceReady(pronounceBtn);
    }

    return { controls, listenBtn, pronounceBtn };
  }

  return {
    buildLangBadge,
    buildLegend,
    buildPronunciationBack,
    getLanguageMeta,
    getScoreTier,
    normalizePronunciationResult,
    showFeedback,
    submitAudio,
    attachRecordButton,
    buildAudioControlsRow,
    PRONUNCIATION_MAX_DURATION_MS,
  };
})();
