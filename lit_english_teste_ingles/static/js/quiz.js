(function () {
  const shell = document.getElementById("quiz-shell");

  const TYPE_LABELS = {
    fill: "Fill in the blank",
    listening: "Listening",
  };

  function typeLabel(q) {
    if (q.type === "translation") {
      return q.direction === "pt_en" ? "Tradução PT → EN" : "Tradução EN → PT";
    }
    return TYPE_LABELS[q.type] || q.type;
  }

  const state = {
    nome: sessionStorage.getItem("lit_english_nome") || "",
    questions: [],
    index: 0,
    answers: {}, // { [id]: answer }
    selectedKey: null, // opção marcada na questão atual (antes de confirmar)
  };

  // -------------------------------------------------------------------
  // Utils
  // -------------------------------------------------------------------
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function renderShell(html) {
    shell.innerHTML = html;
  }

  // -------------------------------------------------------------------
  // Guarda de entrada: exige nome vindo da tela inicial
  // -------------------------------------------------------------------
  if (!state.nome) {
    window.location.href = "/";
    return;
  }

  // -------------------------------------------------------------------
  // Carrega as questões
  // -------------------------------------------------------------------
  async function loadQuestions() {
    try {
      const res = await fetch("/api/questions");
      const data = await res.json();
      state.questions = data.questions || [];
      if (!state.questions.length) {
        renderShell(`<div class="error-banner">Não foi possível carregar as questões.</div>`);
        return;
      }
      renderQuestion();
    } catch (err) {
      renderShell(`<div class="error-banner">Erro de conexão com o servidor. Verifique se o backend está rodando.</div>`);
    }
  }

  // -------------------------------------------------------------------
  // Tela de questão
  // -------------------------------------------------------------------
  function renderQuestion() {
    const q = state.questions[state.index];
    const total = state.questions.length;
    state.selectedKey = null;

    let body = "";

    if (q.type === "fill") {
      body = `
        <p class="quiz-question">${escapeHtml(q.question_en)}</p>
        ${q.translation_pt ? `
          <p class="quiz-translation-label">Tradução</p>
          <p class="quiz-translation">${escapeHtml(q.translation_pt)}</p>` : ""}
        <div class="quiz-options" id="options">
          ${q.options.map((o) => optionHtml(o)).join("")}
        </div>
      `;
    } else if (q.type === "listening") {
      body = `
        <button type="button" class="audio-btn" id="play-audio">
          <span class="audio-icon">🔊</span> Ouvir a frase
        </button>
        <p class="quiz-audio-hint">Clique quantas vezes precisar antes de responder.</p>
        <div class="quiz-options" id="options">
          ${q.options.map((o) => optionHtml(o)).join("")}
        </div>
      `;
    } else if (q.type === "translation") {
      const isPtToEn = q.direction === "pt_en";
      const sourceSentence = isPtToEn ? q.question_pt : q.question_en;
      body = `
        <p class="quiz-question">${escapeHtml(sourceSentence)}</p>
        <p class="quiz-translation-label">${isPtToEn ? "Traduza para o inglês" : "Traduza para o português"}</p>
        <textarea class="quiz-textarea" id="translation-input" placeholder="${isPtToEn ? "Type your translation..." : "Digite sua tradução..."}"></textarea>
      `;
    }

    renderShell(`
      <div class="quiz-card" id="quiz-card">
        <div class="quiz-topbar">
          <span class="type-badge">${typeLabel(q)}</span>
          <span class="quiz-counter">${q.number} / ${total}</span>
        </div>
        <div class="quiz-progress-track">
          <div class="quiz-progress-fill" style="width:${((q.number - 1) / total) * 100}%"></div>
        </div>
        <p class="quiz-subject-label">Assunto</p>
        <p class="quiz-subject">${escapeHtml(q.subject)}</p>
        ${body}
        <p class="quiz-hint">Revise sua resposta e continue.</p>
        <button class="btn-primary" id="confirm-btn" disabled>
          <span class="btn-label">Confirmar</span>
        </button>
      </div>
    `);

    wireQuestionEvents(q);
  }

  function optionHtml(o) {
    return `
      <label class="option-item" data-key="${o.key}">
        <input type="radio" name="answer" value="${o.key}" />
        <span class="option-radio-dot"></span>
        <span class="option-text">${escapeHtml(o.text)}</span>
      </label>
    `;
  }

  function wireQuestionEvents(q) {
    const confirmBtn = document.getElementById("confirm-btn");

    if (q.type === "listening") {
      const playBtn = document.getElementById("play-audio");
      const speak = () => {
        if (!("speechSynthesis" in window)) return;
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(q.question_en);
        utter.lang = "en-US";
        utter.rate = 0.95;
        window.speechSynthesis.speak(utter);
      };
      playBtn.addEventListener("click", speak);
      // toca automaticamente ao abrir a questão
      setTimeout(speak, 350);
    }

    if (q.type === "fill" || q.type === "listening") {
      const items = document.querySelectorAll(".option-item");
      items.forEach((item) => {
        item.addEventListener("click", () => {
          items.forEach((i) => i.classList.remove("is-selected"));
          item.classList.add("is-selected");
          item.querySelector("input").checked = true;
          state.selectedKey = item.dataset.key;
          confirmBtn.disabled = false;
        });
      });
    }

    if (q.type === "translation") {
      const textarea = document.getElementById("translation-input");
      textarea.addEventListener("input", () => {
        confirmBtn.disabled = textarea.value.trim().length === 0;
      });
    }

    confirmBtn.addEventListener("click", () => submitAnswer(q));
  }

  // -------------------------------------------------------------------
  // Envia a resposta da questão atual para /api/check
  // -------------------------------------------------------------------
  async function submitAnswer(q) {
    let answer;
    if (q.type === "translation") {
      answer = document.getElementById("translation-input").value.trim();
    } else {
      answer = state.selectedKey;
    }

    const confirmBtn = document.getElementById("confirm-btn");
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Corrigindo...";

    try {
      const res = await fetch("/api/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: q.id, answer }),
      });
      const result = await res.json();

      if (!res.ok) {
        renderShell(`<div class="error-banner">${escapeHtml(result.error || "Erro ao corrigir a resposta.")}</div>`);
        return;
      }

      state.answers[q.id] = answer;
      renderFeedback(q, result);
    } catch (err) {
      renderShell(`<div class="error-banner">Erro de conexão com o servidor.</div>`);
    }
  }

  // -------------------------------------------------------------------
  // Tela de feedback
  // -------------------------------------------------------------------
  function boldBlank(questionEn, filledText) {
    // Substitui cada "____" da frase pela palavra correspondente (em negrito),
    // suportando frases com mais de uma lacuna (ex.: "rains, will").
    const words = String(filledText || "").split(",").map((w) => w.trim());
    const segments = questionEn.split("____");
    let html = "";
    segments.forEach((seg, idx) => {
      html += escapeHtml(seg);
      if (idx < segments.length - 1) {
        const word = words[idx] !== undefined ? words[idx] : words[words.length - 1];
        html += `<strong>${escapeHtml(word)}</strong>`;
      }
    });
    return html;
  }

  function exampleLineHtml(isRight, sentenceHtml) {
    return `
      <div class="feedback-example ${isRight ? "is-correct" : "is-wrong"}">
        <span class="feedback-example-icon">${isRight ? "✓" : "✗"}</span>
        <span class="feedback-example-text">${sentenceHtml}</span>
      </div>
    `;
  }

  function whyBlockHtml(reasonText, exampleHtml) {
    return `
      <div class="feedback-why-block">
        <p class="feedback-why-text">${escapeHtml(reasonText || "")}</p>
        ${exampleHtml || ""}
      </div>
    `;
  }

  function renderFeedback(q, result) {
    const isCorrect = result.is_correct;
    const isLast = state.index === state.questions.length - 1;

    // ---- Pills: "Você escolheu" / "A resposta correta é" ----
    let chosenLabel = "Você escolheu:";
    let correctLabel = "A resposta correta é:";
    let chosenText;
    let correctText;

    if (q.type === "translation") {
      chosenLabel = "Sua tradução:";
      correctLabel = "Tradução esperada:";
      chosenText = result.student_answer || "—";
      correctText = result.reference_answer;
    } else {
      chosenText = result.chosen_text || "—";
      correctText = result.correct_text;
    }

    const pillsHtml = `
      <div class="feedback-pills">
        <p class="feedback-pill-label">${chosenLabel}</p>
        <span class="feedback-pill ${isCorrect ? "is-correct" : "is-wrong"}">${escapeHtml(chosenText)}</span>
        ${!isCorrect ? `
          <p class="feedback-pill-label">${correctLabel}</p>
          <span class="feedback-pill is-correct">${escapeHtml(correctText)}</span>
        ` : ""}
      </div>
    `;

    // ---- "Por quê?": nunca mistura "Correto!" com uma resposta errada ----
    // Regra: se acertou, mostramos só "Correto!" + a explicação da opção
    // certa. Se errou, mostramos "O correto seria X. Você escolheu Y." e a
    // explicação de por que a escolha está errada — nunca as duas coisas
    // juntas de forma contraditória.
    let exampleHtml = "";
    if (q.type === "fill") {
      if (isCorrect) {
        exampleHtml = exampleLineHtml(true, boldBlank(q.question_en, result.correct_text));
      } else {
        exampleHtml = `
          ${exampleLineHtml(true, boldBlank(q.question_en, result.correct_text))}
          ${exampleLineHtml(false, boldBlank(q.question_en, result.chosen_text))}
        `;
      }
    }

    const summaryHtml = result.summary
      ? `<p class="feedback-why-summary">${escapeHtml(result.summary)}</p>`
      : "";

    const whyHtml = `
      <div class="feedback-why">
        <p class="feedback-why-title">Por quê?</p>
        ${summaryHtml}
        ${whyBlockHtml(result.explanation, exampleHtml)}
      </div>
    `;

    renderShell(`
      <div class="feedback-panel ${isCorrect ? "is-correct" : "is-wrong"}">
        <div class="feedback-header">
          <span class="feedback-icon-circle">${isCorrect ? "✓" : "✕"}</span>
          <h2 class="feedback-title">${isCorrect ? "Resposta correta!" : "Resposta incorreta"}</h2>
        </div>
        ${pillsHtml}
        <div class="feedback-solid-divider"></div>
        ${whyHtml}
        <button class="btn-primary" id="next-btn">
          <span class="btn-label">${isLast ? "Ver meu resultado" : "Próxima questão →"}</span>
        </button>
      </div>
    `);

    document.getElementById("next-btn").addEventListener("click", () => {
      if (isLast) {
        submitAndShowResult();
      } else {
        state.index += 1;
        renderQuestion();
      }
    });
  }

  // -------------------------------------------------------------------
  // Fim do teste -> envia direto para /api/submit (sem tela intermediária)
  // -------------------------------------------------------------------
  async function submitAndShowResult() {
    renderShell(`
      <div class="quiz-card result-loading">
        <span class="spinner-lg" aria-hidden="true"></span>
        <p>Calculando seu resultado…</p>
      </div>
    `);

    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: state.nome,
          whatsapp: "",
          answers: state.answers,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        renderShell(`<div class="error-banner">${escapeHtml(data.error || "Erro ao enviar o resultado.")}</div>`);
        return;
      }

      renderResult(data.resultado, data.registro_salvo);
    } catch (err) {
      renderShell(`<div class="error-banner">Erro de conexão com o servidor.</div>`);
    }
  }

  // -------------------------------------------------------------------
  // Tela de resultado final
  // -------------------------------------------------------------------
  function renderResult(score, record) {
    const recordId = record && record.id;

    renderShell(`
      <div class="result-card">
        <div class="result-logo">
          <svg class="result-logo-mark" viewBox="0 0 92 68" aria-hidden="true">
            <rect class="cc-stroke" x="4" y="4" width="84" height="52" rx="14" />
            <text class="cc-letters" x="46" y="42" font-size="26" text-anchor="middle">CC</text>
            <line class="cc-slash" x1="10" y1="62" x2="82" y2="6" />
          </svg>
          <p class="result-wordmark">LIT ENGLISH</p>
          <p class="result-tagline">· Don't Get Lost In Translation ·</p>
        </div>

        <h2 class="result-heading">Teste finalizado!</h2>
        <p class="result-subheading">Parabéns! Você concluiu seu teste de nível.</p>

        <div class="result-grid">
          <div class="result-box">
            <p class="result-box-label">Seu nível estimado</p>
            <p class="result-level-code">${escapeHtml(score.nivel_codigo)}</p>
            <p class="result-level-label">${escapeHtml(score.nivel_estimado)}</p>
            <p class="result-box-desc">${escapeHtml(score.nivel_descricao)}</p>
          </div>

          <div class="result-box">
            <p class="result-box-label">Seu desempenho</p>
            <div class="result-circle" style="--pct:${score.percent_geral}">
              <div class="result-circle-inner">
                <span class="result-circle-pct">${score.percent_geral}%</span>
                <span class="result-circle-sub">de acertos</span>
              </div>
            </div>
            <p class="result-box-desc">${score.correct_count} de ${score.total_questions} questões corretas</p>
          </div>
        </div>

        <div class="result-whatsapp-row">
          <p class="result-cta-heading">Descubra como chegar ao próximo nível em poucos meses.</p>
          <p class="result-cta-sublabel">Receba gratuitamente:</p>
          <ul class="result-checklist">
            <li><span class="checklist-mark">✓</span> uma análise personalizada</li>
            <li><span class="checklist-mark">✓</span> um plano de estudos</li>
            <li><span class="checklist-mark">✓</span> uma aula experimental</li>
          </ul>

          <p class="result-whatsapp-label result-whatsapp-label-lg">Digite seu WhatsApp abaixo.</p>
          <div class="result-whatsapp-field">
            <input type="text" id="result-whatsapp" placeholder="(11) 99999-9999" />
            <button class="btn-send-sm" id="send-whatsapp-btn">Enviar</button>
          </div>

          <div class="result-checkbox-list">
            <label class="result-checkbox-row">
              <input type="checkbox" id="interesse-aula" />
              <span>Quero uma aula experimental</span>
            </label>
            <label class="result-checkbox-row">
              <input type="checkbox" id="interesse-analise" />
              <span>Quero receber minha análise e plano de estudos</span>
            </label>
          </div>

          <p class="result-whatsapp-status" id="whatsapp-status" aria-live="polite"></p>
        </div>

        <button class="btn-finish-link" id="finish-btn">Finalizar</button>
      </div>
    `);

    const sendBtn = document.getElementById("send-whatsapp-btn");
    sendBtn.addEventListener("click", async () => {
      const input = document.getElementById("result-whatsapp");
      const status = document.getElementById("whatsapp-status");
      const whatsapp = input.value.trim();
      const aulaExperimental = document.getElementById("interesse-aula").checked;
      const analisePlano = document.getElementById("interesse-analise").checked;

      if (!whatsapp) {
        status.textContent = "Digite um número antes de enviar.";
        return;
      }
      if (!recordId) {
        status.textContent = "Não foi possível salvar agora, tente novamente.";
        return;
      }

      sendBtn.disabled = true;
      status.textContent = "";

      try {
        const res = await fetch("/api/whatsapp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: recordId,
            whatsapp,
            aula_experimental: aulaExperimental,
            analise_plano: analisePlano,
          }),
        });
        const data = await res.json();

        if (!res.ok) {
          status.textContent = data.error || "Não foi possível enviar.";
          sendBtn.disabled = false;
          return;
        }

        status.textContent = "Recebido! Vamos entrar em contato. 🎉";
        input.disabled = true;
        document.getElementById("interesse-aula").disabled = true;
        document.getElementById("interesse-analise").disabled = true;
      } catch (err) {
        status.textContent = "Erro de conexão. Tente novamente.";
        sendBtn.disabled = false;
      }
    });

    document.getElementById("finish-btn").addEventListener("click", () => {
      sessionStorage.removeItem("lit_english_nome");
      window.location.href = window.SITE_PRINCIPAL_URL || "/";
    });
  }

  loadQuestions();
})();
