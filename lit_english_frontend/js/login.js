/* ==========================================================================
   LIT English — login.js
   Lógica da tela de login e cadastro de novo aluno.
   ========================================================================== */

(function () {
  // Se já estiver logado e aprovado, pula direto para a tela certa.
  if (Auth.isLoggedIn()) {
    const cachedUser = Auth.getUser();
    if (cachedUser && cachedUser.role === "aluno" && cachedUser.is_approved) {
      window.location.href = "home.html";
      return;
    }
    if (cachedUser && cachedUser.role === "professor") {
      window.location.href = "professor.html";
      return;
    }
  }

  // -------------------------------------------------------------------------
  // Elementos de login
  // -------------------------------------------------------------------------
  const loginCard    = document.getElementById("login-card");
  const loginFooter  = document.getElementById("login-footer");
  const form         = document.getElementById("login-form");
  const emailInput   = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const submitBtn    = document.getElementById("submit-btn");
  const errorBox     = document.getElementById("form-error");
  const infoBox      = document.getElementById("form-info");

  // -------------------------------------------------------------------------
  // Elementos de cadastro
  // -------------------------------------------------------------------------
  const registerCard    = document.getElementById("register-card");
  const registerFooter  = document.getElementById("register-footer");
  const registerForm    = document.getElementById("register-form");
  const regNameInput    = document.getElementById("reg-name");
  const regWhatsInput   = document.getElementById("reg-whatsapp");
  const regEmailUser    = document.getElementById("reg-email-user");
  const regEmailHidden  = document.getElementById("reg-email");
  const regPassInput    = document.getElementById("reg-password");
  const regPassConfirm  = document.getElementById("reg-password-confirm");
  const registerBtn     = document.getElementById("register-btn");
  const regErrorBox     = document.getElementById("reg-form-error");
  const regInfoBox      = document.getElementById("reg-form-info");

  // -------------------------------------------------------------------------
  // Alternar entre login e cadastro
  // -------------------------------------------------------------------------
  document.getElementById("go-register").addEventListener("click", (e) => {
    e.preventDefault();
    loginCard.style.display   = "none";
    loginFooter.style.display = "none";
    registerCard.style.display   = "";
    registerFooter.style.display = "";
  });

  document.getElementById("go-login").addEventListener("click", (e) => {
    e.preventDefault();
    registerCard.style.display   = "none";
    registerFooter.style.display = "none";
    loginCard.style.display   = "";
    loginFooter.style.display = "";
  });

  // -------------------------------------------------------------------------
  // Helpers de mensagem (login)
  // -------------------------------------------------------------------------
  function hideMessages() {
    errorBox.hidden = true;
    infoBox.hidden  = true;
  }

  function showError(message) {
    infoBox.hidden = true;
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function showInfo(message) {
    errorBox.hidden = true;
    infoBox.textContent = message;
    infoBox.hidden = false;
  }

  // -------------------------------------------------------------------------
  // Helpers de mensagem (cadastro)
  // -------------------------------------------------------------------------
  function hideRegMessages() {
    regErrorBox.hidden = true;
    regInfoBox.hidden  = true;
  }

  function showRegError(message) {
    regInfoBox.hidden = true;
    regErrorBox.textContent = message;
    regErrorBox.hidden = false;
  }

  function showRegInfo(message) {
    regErrorBox.hidden = true;
    regInfoBox.textContent = message;
    regInfoBox.hidden = false;
  }

  // -------------------------------------------------------------------------
  // Formatação automática do WhatsApp
  // -------------------------------------------------------------------------
  regWhatsInput.addEventListener("input", function () {
    let v = this.value.replace(/\D/g, "").slice(0, 11);
    if (v.length > 6) {
      v = `(${v.slice(0,2)}) ${v.slice(2,7)}-${v.slice(7)}`;
    } else if (v.length > 2) {
      v = `(${v.slice(0,2)}) ${v.slice(2)}`;
    } else if (v.length > 0) {
      v = `(${v}`;
    }
    this.value = v;
  });

  // -------------------------------------------------------------------------
  // Submit de login
  // -------------------------------------------------------------------------
  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    hideMessages();

    const email    = emailInput.value.trim();
    const password = passwordInput.value;

    submitBtn.disabled   = true;
    submitBtn.textContent = "Entrando...";

    try {
      await login(email, password);
      const user = await fetchCurrentUser();

      if (user.role === "aluno" && !user.is_approved) {
        showInfo(
          "Login realizado! Sua conta ainda está aguardando aprovação do professor. Assim que for aprovada, você poderá revisar seu vocabulário."
        );
        return;
      }

      if (user.role !== "aluno") {
        window.location.href = "professor.html";
        return;
      }

      window.location.href = "home.html";
    } catch (err) {
      if (err.status === 401) {
        showError("E-mail ou senha incorretos.");
      } else {
        showError(err.message || "Não foi possível entrar. Tente novamente.");
      }
    } finally {
      submitBtn.disabled   = false;
      submitBtn.textContent = "Entrar";
    }
  });

  // -------------------------------------------------------------------------
  // Submit de cadastro
  // -------------------------------------------------------------------------
  registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    hideRegMessages();

    const name     = regNameInput.value.trim();
    const whatsapp = regWhatsInput.value.trim();
    const emailUser = regEmailUser.value.trim();
    const password  = regPassInput.value;
    const confirm   = regPassConfirm.value;

    if (!name) { showRegError("Informe seu nome completo."); return; }
    if (!whatsapp) { showRegError("Informe seu número de WhatsApp."); return; }
    if (!emailUser) { showRegError("Informe o nome de usuário do e-mail."); return; }
    if (!password)  { showRegError("Crie uma senha."); return; }
    if (password !== confirm) { showRegError("As senhas não coincidem."); return; }

    const email = `${emailUser}@litstudent.com`;
    regEmailHidden.value = email;

    registerBtn.disabled    = true;
    registerBtn.textContent = "Solicitando...";

    try {
      await apiFetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, whatsapp, email, password, role: "aluno" }),
      });

      showRegInfo(
        "Cadastro solicitado! Assim que o professor aprovar seu acesso, você poderá fazer login."
      );
      registerForm.reset();
    } catch (err) {
      showRegError(err.message || "Não foi possível criar sua conta. Tente novamente.");
    } finally {
      registerBtn.disabled    = false;
      registerBtn.textContent = "Solicitar Cadastro";
    }
  });
})();
