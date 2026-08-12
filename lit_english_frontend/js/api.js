/* ==========================================================================
   LIT English — api.js
   Comunicação com o backend FastAPI: login, usuário logado e fetch autenticado.
   ========================================================================== */

// Ajuste esta URL para onde o backend estiver rodando.
// Em desenvolvimento local (uvicorn app.main:app --reload) o padrão é:
const API_BASE_URL = "https://litenglish.up.railway.app";

const TOKEN_KEY = "lit_token";
const USER_KEY = "lit_user";

const Auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  },

  getUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },

  setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  /**
   * Descobre para qual tela de login o usuário deve voltar: alunos/professores
   * do cadastro padrão voltam para "login.html", enquanto contas de Acesso
   * Especial (access_type === "especial") voltam para "login.html?acesso=especial".
   * Precisa ser chamado ANTES de Auth.clear(), enquanto os dados do usuário
   * ainda estão salvos localmente.
   */
  loginRedirectUrl() {
    const user = this.getUser();
    return user && user.access_type === "especial"
      ? "login.html?acesso=especial"
      : "login.html";
  },

  logout() {
    const redirectUrl = this.loginRedirectUrl();
    this.clear();
    window.location.href = redirectUrl;
  },
};

/**
 * Faz uma chamada à API. Adiciona automaticamente o header Authorization
 * quando o usuário está logado. Lança um Error com mensagem amigável em caso de falha.
 */
async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  const token = Auth.getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (err) {
    throw new Error(
      "Não foi possível conectar ao servidor. Verifique se o backend está rodando."
    );
  }

  if (response.status === 204) {
    return null;
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      data = null;
    }
  }

  if (!response.ok) {
    const detail =
      (data && (data.detail || data.message)) ||
      `Erro inesperado (${response.status}).`;
    const error = new Error(
      typeof detail === "string" ? detail : "Erro inesperado."
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

/**
 * Faz uma chamada à API esperando uma resposta binária (ex: áudio).
 * Mesma autenticação do apiFetch, mas retorna um Blob em vez de tentar
 * interpretar a resposta como JSON.
 */
async function apiFetchBlob(path) {
  const headers = {};
  const token = Auth.getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(path.startsWith("http") ? path : `${API_BASE_URL}${path}`, { headers });
  } catch (err) {
    throw new Error("Não foi possível conectar ao servidor.");
  }

  if (!response.ok) {
    let detail = `Erro inesperado (${response.status}).`;
    try {
      const data = await response.json();
      detail = (data && (data.detail || data.message)) || detail;
    } catch (err) {
      // resposta não era JSON, mantém a mensagem padrão
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  return response.blob();
}

/**
 * Login no padrão OAuth2 (form-urlencoded) exigido pelo backend.
 */
async function login(email, password, accessType) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  if (accessType) body.set("access_type", accessType);

  const data = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  Auth.setToken(data.access_token);
  return data;
}

async function fetchCurrentUser() {
  const user = await apiFetch("/auth/me");
  Auth.setUser(user);
  applyAccessRestrictions(user);
  return user;
}

/**
 * Redireciona aluno do curso padrão para exercícios prioritários (listas do
 * professor), se houver. Usado na Home e após login.
 */
async function redirectToPriorityActivityIfNeeded(user) {
  if (!user || user.role !== "aluno" || user.access_type === "especial" || !user.is_approved) {
    return false;
  }
  try {
    const next = await apiFetch("/dashboard/next-activity");
    if (next.activity === "exercises" && next.url) {
      window.location.href = next.url;
      return true;
    }
  } catch {
    // Ignora — permanece na página atual.
  }
  return false;
}

/**
 * Destino padrão após login de aluno aprovado (respeita fila global).
 */
async function redirectAfterStudentLogin(user) {
  if (await redirectToPriorityActivityIfNeeded(user)) return;
  window.location.href = "home.html";
}

/**
 * Alunos que se cadastraram pelo "Acesso Especial" (access_type === "especial")
 * ainda não têm conteúdo de exercícios — então o menu "Exercícios" fica
 * escondido, e quem tentar acessar exercicios.html direto pela URL é
 * redirecionado pra home. Não afeta professores nem alunos do cadastro padrão.
 */
function applyAccessRestrictions(user) {
  if (!user || user.access_type !== "especial") return;

  const navExercicios = document.getElementById("nav-exercicios");
  if (navExercicios) navExercicios.style.display = "none";

  const page = window.location.pathname.split("/").pop();
  if (page === "exercicios.html") {
    window.location.href = "home.html";
  }
}
