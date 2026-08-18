/* LIT English — Aprender: criação de flashcards próprios do aluno. */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const toastEl = document.getElementById("toast");
const frontHintEl = document.getElementById("front-hint");
const frontInput = document.getElementById("flashcard-front");
const backInput = document.getElementById("flashcard-back");
const frontCounter = document.getElementById("front-counter");
const backCounter = document.getElementById("back-counter");
const descriptionInput = document.getElementById("flashcard-description");
const descriptionCounter = document.getElementById("description-counter");
const form = document.getElementById("flashcard-form");
const errorBox = document.getElementById("form-error");
const createBtn = document.getElementById("create-flashcard-btn");

const LANGUAGE_NAMES = {
  pt: "português",
  "pt-br": "português",
  portugues: "português",
  português: "português",
  en: "inglês",
  ingles: "inglês",
  inglês: "inglês",
  it: "italiano",
  italiano: "italiano",
  fr: "francês",
  frances: "francês",
  francês: "francês",
  es: "espanhol",
  espanhol: "espanhol",
  de: "alemão",
  alemao: "alemão",
  alemão: "alemão",
};

function languageLabel(value, fallback) {
  const key = String(value || "").trim().toLowerCase();
  return LANGUAGE_NAMES[key] || fallback;
}

function getNativeLanguage(user) {
  return user?.native_language || "pt";
}

function getTargetLanguage(user) {
  if (user?.target_language) return user.target_language;
  return "ingles";
}

function updateFrontHint(user) {
  const nativeLabel = languageLabel(getNativeLanguage(user), "português");
  const targetLabel = languageLabel(getTargetLanguage(user), "inglês");
  frontHintEl.textContent = `Digite a palavra, frase ou expressão em ${nativeLabel} ou ${targetLabel}.`;

  if (targetLabel === "inglês") {
    frontInput.placeholder = "Ex: Livro ou Book";
  } else {
    frontInput.placeholder = `Ex: ${targetLabel} ou ${nativeLabel}`;
  }
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

function updateCounter(input, counter) {
  counter.textContent = `${input.value.length}/200`;
}

frontInput.addEventListener("input", () => updateCounter(frontInput, frontCounter));
backInput.addEventListener("input", () => updateCounter(backInput, backCounter));
descriptionInput.addEventListener("input", () => {
  descriptionCounter.textContent = `${descriptionInput.value.length}/300`;
});

document.getElementById("logout-btn").addEventListener("click", () => {
  const ok = window.confirm("Deseja sair da sua conta?");
  if (ok) Auth.logout();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;

  const front = frontInput.value.trim();
  const back = backInput.value.trim();
  const description = descriptionInput.value.trim();

  if (!front) {
    errorBox.textContent = "Digite uma palavra, frase ou expressão na frente do flashcard.";
    errorBox.hidden = false;
    frontInput.focus();
    return;
  }

  createBtn.disabled = true;
  createBtn.querySelector("span:last-child").textContent = "Criando...";

  try {
    await apiFetch("/flashcards/self-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ front, back, description }),
    });

    form.reset();
    updateCounter(frontInput, frontCounter);
    updateCounter(backInput, backCounter);
    descriptionCounter.textContent = "0/300";
    showToast("Flashcard criado!");
    frontInput.focus();
  } catch (err) {
    errorBox.textContent = err.message || "Não foi possível criar o flashcard. Tente novamente.";
    errorBox.hidden = false;
  } finally {
    createBtn.disabled = false;
    createBtn.querySelector("span:last-child").textContent = "Criar Flashcard";
  }
});

async function init() {
  if (!Auth.isLoggedIn()) {
    window.location.href = Auth.loginRedirectUrl();
    return;
  }

  try {
    const user = await fetchCurrentUser();

    studentNameEl.textContent = user.name;
    roleLabelEl.textContent = user.role === "professor" ? "PROFESSOR" : "ALUNO";

    if (user.role !== "aluno") {
      window.location.href = "professor.html";
      return;
    }

    // Exercícios existem somente para alunos do curso padrão.
    const navExercicios = document.getElementById("nav-exercicios");
    if (navExercicios) navExercicios.style.display = user.access_type === "padrao" ? "" : "none";

    if (!user.is_approved) {
      frontHintEl.textContent = "Sua conta ainda aguarda aprovação.";
      frontInput.disabled = true;
      backInput.disabled = true;
      descriptionInput.disabled = true;
      createBtn.disabled = true;
      return;
    }

    updateFrontHint(user);
    frontInput.focus();
  } catch (err) {
    const redirectUrl = Auth.loginRedirectUrl();
    Auth.clear();
    window.location.href = redirectUrl;
  }
}

init();
