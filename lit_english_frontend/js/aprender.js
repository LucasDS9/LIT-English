/* ==========================================================================
   LIT English — aprender.js
   Tela "Aprender": treino de vocabulário por reconhecimento (múltipla
   escolha, sempre 4 opções). Consome:
     GET  /vocab-words/learn/next
     POST /vocab-words/learn/{word_id}

   OBS: o clique nas palavras da frase de exemplo (pra ver o significado,
   igual ao Read and Listen) ainda não está aqui — fica pra depois.
   ========================================================================== */

const learnArea = document.getElementById("learn-area");
const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const toastEl = document.getElementById("toast");
const pageSubtitleEl = document.getElementById("page-subtitle");

const SUBTITLE_CATEGORIES = "Escolha uma categoria para começar a estudar.";
const SUBTITLE_LEARNING = "Aprenda palavras novas e expanda seu vocabulário.";

function setSubtitle(text) {
  if (pageSubtitleEl) pageSubtitleEl.textContent = text;
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
// Sessão de aprendizado (estado em memória, vive enquanto a página está aberta)
// ---------------------------------------------------------------------------

const session = {
  category: "saudacoes",
  cards: [],
  index: 0,
  answered: false,
  newWordsCount: 0, // quantas palavras novas vieram no início da sessão
  pronunciationByWordId: {}, // word_id -> resultado da última gravação neste card
};

let currentUser = null;

function studentLanguage(user) {
  if (user?.access_type === "especial" && user?.target_language) {
    return user.target_language.trim().toLowerCase();
  }
  return "ingles";
}

// ---------------------------------------------------------------------------
// Áudio (pronúncia da palavra isolada — mesma lógica usada em Revisar)
// ---------------------------------------------------------------------------

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

// Toca a pronúncia de UMA palavra isolada (nunca a frase inteira).
async function speakWord(word, btn) {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (btn) btn.disabled = true;

  try {
    const url = await fetchTtsAudioUrl(word);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.addEventListener("ended", () => {
      if (btn) btn.disabled = false;
    });
    audio.addEventListener("error", () => {
      if (btn) btn.disabled = false;
      speakWithBrowserFallback(word);
    });
    await audio.play();
    if (btn) btn.disabled = false;
  } catch (err) {
    if (btn) btn.disabled = false;
    speakWithBrowserFallback(word);
  }
}

// ---------------------------------------------------------------------------
// Helpers de texto
// ---------------------------------------------------------------------------

function escapeHtml(str) {
  return (str || "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
  ));
}

// Envolve a ocorrência da palavra sendo aprendida dentro da frase de exemplo
// em <b>, escapando o resto do texto.
function highlightWord(sentence, word) {
  const safeSentence = escapeHtml(sentence);
  const cleanWord = (word || "").trim();
  if (!cleanWord) return safeSentence;

  const escapedWord = cleanWord.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${escapedWord})`, "i");
  return re.test(safeSentence) ? safeSentence.replace(re, "<b>$1</b>") : safeSentence;
}

// ---------------------------------------------------------------------------
// Estados vazios / erro (mesmo padrão visual do Revisar)
// ---------------------------------------------------------------------------

function renderStateBox({ icon, title, text, actionLabel, onAction }) {
  learnArea.innerHTML = "";
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

  learnArea.appendChild(box);
}

function renderFinished() {
  SFX.play("finish");
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Sessão concluída! 🎉",
    text: "Você passou pelas palavras novas e pelas que tinha errado. Quer continuar aprendendo?",
    actionLabel: "Continuar aprendendo",
    onAction: loadQueue,
  });
}

function renderEmpty() {
  renderStateBox({
    icon: Icons.checkCircle,
    title: "Você está em dia!",
    text: "Não há nenhuma palavra nova para aprender agora. Volte mais tarde.",
    actionLabel: "Atualizar",
    onAction: loadQueue,
  });
}

function renderPendingApproval() {
  setSubtitle("");
  renderStateBox({
    icon: Icons.lock,
    title: "Conta aguardando aprovação",
    text: "Sua conta ainda não foi aprovada pelo professor. Assim que for aprovada, você poderá começar a aprender vocabulário.",
  });
}

function renderNotStudent() {
  setSubtitle("");
  renderStateBox({
    icon: Icons.alert,
    title: "Área exclusiva para alunos",
    text: "Esta tela é destinada aos alunos. O painel do professor ainda está em construção.",
  });
}

function renderError(message, retryFn) {
  renderStateBox({
    icon: Icons.alert,
    title: "Algo deu errado",
    text: message || "Não foi possível carregar suas palavras. Tente novamente.",
    actionLabel: "Tentar novamente",
    onAction: retryFn || loadQueue,
  });
}

// ---------------------------------------------------------------------------
// Tela de categorias ("Aprender")
// ---------------------------------------------------------------------------

const CATEGORY_META = {
  saudacoes: {
    title: "Saudações e frases essenciais",
    desc: "Frases básicas para cumprimentar, se apresentar e se comunicar no dia a dia.",
    image: "img/category-saudacoes-v3.png",
    alt: "Duas pessoas se cumprimentando em inglês",
  },
  verbos_essenciais_pt1: {
    title: "Verbos essenciais — Parte 1",
    desc: "Os verbos mais importantes para começar a formar frases em inglês.",
    image: "img/category-verbos-pt1.png",
    alt: "Pessoa aprendendo verbos essenciais em inglês",
  },
  verbos_essenciais_pt2: {
    title: "Verbos essenciais — Parte 2",
    desc: "Continue aprendendo verbos e chunks essenciais para se comunicar.",
    image: "img/category-verbos-pt2.png",
    alt: "Pessoa estudando verbos essenciais em inglês",
  },
  pronomes: {
    title: "Pronomes essenciais",
    desc: "Pronomes que você precisa dominar para montar frases naturalmente.",
    image: "img/category-pronomes.png",
    alt: "Pessoa estudando inglês",
  },
};

function categoryMeta(category) {
  return CATEGORY_META[category] || {
    title: category.replaceAll("_", " "),
    desc: "Vocabulário para ampliar seu inglês.",
    image: null,
    alt: "",
  };
}

function buildCategoryIllustration(category) {
  const meta = categoryMeta(category);
  const illustration = document.createElement("div");
  illustration.className = "category-illustration";

  if (meta.image) {
    illustration.innerHTML = `<img src="${meta.image}" width="500" height="500" alt="${meta.alt}" class="category-illustration-img" />`;
  } else {
    illustration.innerHTML = `<div class="category-illustration-icon">${Icons.bookOpen}</div>`;
  }
  return illustration;
}

function buildCategoryCard(item) {
  const category = item.category;
  const meta = categoryMeta(category);
  const totalAssigned = item.total_assigned || 0;
  const totalLearned = Math.min(item.total_learned || 0, totalAssigned);
  const percent = totalAssigned > 0 ? Math.round((totalLearned / totalAssigned) * 100) : 0;

  const card = document.createElement("button");
  card.type = "button";
  card.className = "category-card";

  card.appendChild(buildCategoryIllustration(category));

  const title = document.createElement("h3");
  title.className = "category-title";
  title.textContent = meta.title;
  card.appendChild(title);

  const desc = document.createElement("p");
  desc.className = "category-desc";
  desc.textContent = meta.desc;
  card.appendChild(desc);

  const progressTrack = document.createElement("div");
  progressTrack.className = "category-progress-track";
  const progressFill = document.createElement("div");
  progressFill.className = "category-progress-fill";
  progressFill.style.width = `${percent}%`;
  progressTrack.appendChild(progressFill);
  card.appendChild(progressTrack);

  const statsRow = document.createElement("div");
  statsRow.className = "category-stats-row";
  statsRow.innerHTML = `
    <span class="category-stats-icon">${Icons.cards}</span>
    <span class="category-stats-text">
      <span class="category-stats-label">Cartões estudados</span>
      <span class="category-stats-value">${totalLearned} / ${totalAssigned}</span>
    </span>
    <span class="category-stats-percent">${percent}%</span>
  `;
  card.appendChild(statsRow);

  card.addEventListener("click", () => {
    session.category = category;
    setSubtitle(SUBTITLE_LEARNING);
    learnArea.classList.remove("categories-area");
    loadQueue(category);
  });

  return card;
}

function renderCategories(data) {
  setSubtitle(SUBTITLE_CATEGORIES);
  learnArea.innerHTML = "";
  learnArea.classList.add("categories-area");

  const grid = document.createElement("div");
  grid.className = "categories-grid";

  // Mantém a ordem visual fixa da tela: Saudações → Verbos PT1 → Verbos PT2 → Pronomes.
  // O backend pode devolver as categorias em outra ordem dependendo do banco.
  const order = [
    "saudacoes",
    "verbos_essenciais_pt1",
    "verbos_essenciais_pt2",
    "pronomes",
  ];
  const byCategory = new Map(data.map((item) => [item.category, item]));

  order.forEach((category) => {
    const item = byCategory.get(category);
    if (item) grid.appendChild(buildCategoryCard(item));
  });

  // Mantém categorias futuras sem quebrar a tela, depois das quatro principais.
  data.forEach((item) => {
    if (!order.includes(item.category)) {
      grid.appendChild(buildCategoryCard(item));
    }
  });

  learnArea.appendChild(grid);
}

async function loadCategoriesScreen() {
  learnArea.classList.add("categories-area");
  learnArea.innerHTML = '<div class="skeleton">Carregando suas categorias...</div>';

  try {
    const data = await apiFetch("/vocab-words/learn/categories");
    renderCategories(data);
  } catch (err) {
    learnArea.classList.remove("categories-area");
    if (err.status === 403) {
      renderNotStudent();
    } else {
      renderError(err.message, loadCategoriesScreen);
    }
  }
}

// ---------------------------------------------------------------------------
// Card de aprendizado
// ---------------------------------------------------------------------------

// Header do card (badge de idioma + contador).
function buildLearnHeader(counterText) {
  const header = document.createElement("div");
  header.className = "learn-card-header";

  header.appendChild(FlashcardPronounce.buildLangBadge(studentLanguage(currentUser)));

  const counter = document.createElement("span");
  counter.className = "learn-card-counter";
  counter.textContent = counterText;
  header.appendChild(counter);

  return header;
}

// Botão "Voltar", fora do card, pra sair da sessão de flashcards e
// retornar à tela de categorias.
function buildBackToCategoriesBtn() {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "learn-back-outside-btn";
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12H4.5"/><path d="M10.5 5.5 4 12l6.5 6.5"/></svg><span>Voltar</span>';
  btn.addEventListener("click", () => loadCategoriesScreen());
  return btn;
}

function renderCard() {
  const card = session.cards[session.index];
  session.answered = false;
  learnArea.innerHTML = "";

  learnArea.appendChild(buildBackToCategoriesBtn());

  const cardBox = document.createElement("div");
  cardBox.className = "review-card learn-card";

  cardBox.appendChild(buildLearnHeader(`${session.index + 1} / ${session.cards.length}`));

  const body = document.createElement("div");
  body.className = "card-body";

  const word = document.createElement("p");
  word.className = "front-text";
  word.textContent = card.word;
  body.appendChild(word);

  const pos = document.createElement("p");
  pos.className = "learn-pos";
  pos.textContent = card.part_of_speech;
  body.appendChild(pos);

  // Dica de uso, mostrada logo abaixo da palavra principal (usada
  // principalmente pelas saudações, que não têm frase de exemplo).
  if (card.tip) {
    const tip = document.createElement("p");
    tip.className = "learn-tip";
    tip.textContent = card.tip;
    body.appendChild(tip);
  }

  if (card.example_sentence) {
    const divider = document.createElement("div");
    divider.className = "learn-divider";
    body.appendChild(divider);

    const sentence = document.createElement("p");
    sentence.className = "learn-sentence";
    sentence.innerHTML = highlightWord(card.example_sentence, card.word);
    body.appendChild(sentence);
  }

  const { controls, listenBtn } = FlashcardPronounce.buildAudioControlsRow({
    listenLabel: "Ouvir pronúncia",
    onListen: () => speakWord(card.word, listenBtn),
    showPronounce: true,
    pronounceLabel: "Pronunciar",
    onPronounceReady: (btn) => {
      const recorder = FlashcardPronounce.attachRecordButton(btn, {
        recordingLabel: "Parar (5s máx)",
        preparingLabel: "Preparando...",
        onStop: async (blob) => {
          try {
    const result = await FlashcardPronounce.submitAudio(
              blob,
              `/vocab-words/learn/${card.word_id}/pronounce`
            );
            session.pronunciationByWordId[card.word_id] = result;
            showToast(result.score != null
              ? "Pronúncia avaliada — veja o feedback ao virar o card."
              : "Pronúncia registrada — veja o feedback ao virar o card.");
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

  cardBox.appendChild(body);

  const optionsGrid = document.createElement("div");
  optionsGrid.className = "learn-options";

  card.options.forEach((option) => {
    const btn = document.createElement("button");
    btn.className = "learn-option-btn";
    btn.type = "button";
    btn.textContent = option;
    btn.addEventListener("click", () => selectOption(card, option, btn, optionsGrid));
    optionsGrid.appendChild(btn);
  });

  cardBox.appendChild(optionsGrid);
  learnArea.appendChild(cardBox);

  // Toca a pronúncia automaticamente assim que o card aparece — sem
  // precisar clicar no botão de áudio. Falha silenciosamente se o
  // navegador bloquear o autoplay (ex: antes de qualquer interação).
  speakWord(card.word, listenBtn);
}

function appendContinueFab(cardBox, card, result) {
  const isLastCard = session.index + 1 >= session.cards.length;
  const continueBtn = document.createElement("button");
  continueBtn.className = "learn-continue-fab";
  continueBtn.type = "button";
  continueBtn.title = isLastCard ? "Concluir" : "Continuar";
  continueBtn.setAttribute("aria-label", isLastCard ? "Concluir" : "Continuar");
  continueBtn.innerHTML = isLastCard ? Icons.checkSmall : Icons.arrowRight;
  continueBtn.addEventListener("click", () => {
    delete session.pronunciationByWordId[card.word_id];

    if (!result.correct && !result.graduated_to_review) {
      const alreadyQueued = session.cards
        .slice(session.index + 1)
        .some((c) => c.word_id === card.word_id);
      if (!alreadyQueued) {
        session.cards.push({
          word_id: card.word_id,
          word: card.word,
          part_of_speech: card.part_of_speech,
          example_sentence: card.example_sentence,
          tip: card.tip,
          options: card.options,
        });
      }
    }

    session.index += 1;
    if (session.index >= session.cards.length) {
      renderFinished();
    } else {
      renderCard();
    }
  });
  cardBox.appendChild(continueBtn);
}

// Depois que o aluno responde, o card "vira": o corpo (palavra + opções)
// dá lugar ao verso. Se o aluno usou pronúncia, mostra o painel visual;
// caso contrário, mantém o verso simples de antes.
function renderCardBack(cardBox, card, result) {
  const pronunciationResult = session.pronunciationByWordId[card.word_id];

  if (pronunciationResult) {
    learnArea.innerHTML = "";
    learnArea.appendChild(buildBackToCategoriesBtn());

    const view = document.createElement("div");
    view.className = "learn-pronunciation-view";

    view.appendChild(FlashcardPronounce.buildLegend());

    const cardBoxNew = document.createElement("div");
    cardBoxNew.className = "review-card learn-card learn-card--pronunciation-back";

    const back = FlashcardPronounce.buildPronunciationBack({
      card,
      learnResult: result,
      pronunciationResult,
      languageCode: studentLanguage(currentUser),
      cardIndex: session.index,
      totalCards: session.cards.length,
      onListen: (btn) => speakWord(card.word, btn),
    });
    cardBoxNew.appendChild(back);
    appendContinueFab(cardBoxNew, card, result);

    view.appendChild(cardBoxNew);
    learnArea.appendChild(view);
    return;
  }

  cardBox.innerHTML = "";

  const back = document.createElement("div");
  back.className = "learn-card-back";

  back.appendChild(buildLearnHeader(`${session.index + 1} / ${session.cards.length}`));

  // Conteúdo centralizado do verso, separado do header: assim a
  // bandeirinha do idioma fica fixa no topo do card, e só este bloco
  // (palavra + resposta + explicação) é centralizado verticalmente no
  // espaço restante.
  const content = document.createElement("div");
  content.className = "learn-card-back-content";

  const phrase = document.createElement("p");
  phrase.className = "front-text";
  phrase.textContent = card.word;
  content.appendChild(phrase);

  const answer = document.createElement("p");
  answer.className = "learn-back-answer";
  answer.textContent = result.correct_answer;
  content.appendChild(answer);

  if (result.explanation) {
    const dot = document.createElement("span");
    dot.className = "learn-back-dot";
    content.appendChild(dot);

    const explanation = document.createElement("p");
    explanation.className = "learn-back-explanation";
    explanation.textContent = result.explanation;
    content.appendChild(explanation);
  }

  back.appendChild(content);

  cardBox.appendChild(back);
  appendContinueFab(cardBox, card, result);
}

async function selectOption(card, selectedOption, btn, optionsGrid) {
  if (session.answered) return;
  session.answered = true;

  optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => (b.disabled = true));
  btn.classList.add("is-selected");

  try {
    const result = await apiFetch(`/vocab-words/learn/${card.word_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_option: selectedOption }),
    });

    SFX.play(result.correct ? "correct" : "wrong");

    optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => {
      if (b.textContent === result.correct_answer) {
        b.classList.add("is-correct");
      } else if (b === btn && !result.correct) {
        b.classList.add("is-wrong");
      }
    });

    // Breve pausa pra o aluno ver qual opção marcou antes de virar o card
    // e revelar a resposta certa + explicação no verso.
    const cardBox = optionsGrid.closest(".learn-card");
    setTimeout(() => {
      if (cardBox) renderCardBack(cardBox, card, result);
    }, 900);
  } catch (err) {
    showToast(err.message || "Não foi possível salvar sua resposta. Tente novamente.");
    optionsGrid.querySelectorAll(".learn-option-btn").forEach((b) => (b.disabled = false));
    btn.classList.remove("is-selected");
    session.answered = false;
  }
}

async function loadQueue(category = session.category) {
  session.category = category || "saudacoes";
  learnArea.innerHTML = '<div class="skeleton">Carregando suas palavras...</div>';

  try {
    const data = await apiFetch(`/vocab-words/learn/next?category=${encodeURIComponent(session.category)}`);

    session.cards = data.cards;
    session.index = 0;
    session.newWordsCount = data.new_words_count ?? session.cards.length;
    session.pronunciationByWordId = {};

    if (session.cards.length === 0) {
      renderEmpty();
    } else {
      renderCard();
    }
  } catch (err) {
    if (err.status === 403) {
      renderNotStudent();
    } else {
      renderError(err.message, () => loadQueue(session.category));
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

  currentUser = user;
  studentNameEl.textContent = user.name;
  roleLabelEl.textContent = user.role === "professor" ? "PROFESSOR" : "ALUNO";

  if (user.role !== "aluno") {
    window.location.href = "professor.html";
    return;
  }

  if (!user.is_approved) {
    renderPendingApproval();
    return;
  }

  loadCategoriesScreen();
}

init();