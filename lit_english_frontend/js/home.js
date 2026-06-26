/* ==========================================================================
   LIT English — home.js
   Tela inicial do aluno: saudação simples com o nome do usuário logado.
   ========================================================================== */

const studentNameEl = document.getElementById("student-name");
const roleLabelEl = document.getElementById("role-label");
const welcomeTitleEl = document.getElementById("welcome-title");

document.getElementById("logout-btn").addEventListener("click", () => {
  const ok = window.confirm("Deseja sair da sua conta?");
  if (ok) Auth.logout();
});

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

  if (user.role === "professor") {
    window.location.href = "professor.html";
    return;
  }

  studentNameEl.textContent = user.name;
  roleLabelEl.textContent = "ALUNO";
  welcomeTitleEl.textContent = `Bem-vindo, ${user.name}!`;
}

init();
