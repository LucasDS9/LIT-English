(function () {
  const form = document.getElementById("name-form");
  const input = document.getElementById("nome");
  const errorEl = document.getElementById("field-error");
  const submitBtn = document.getElementById("submit-btn");

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitBtn.classList.toggle("is-loading", isLoading);
  }

  function showError(message) {
    errorEl.textContent = message;
  }

  input.addEventListener("input", () => showError(""));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const nome = input.value.trim();
    if (!nome) {
      showError("Digite seu nome para continuar.");
      input.focus();
      return;
    }

    showError("");
    setLoading(true);

    try {
      const response = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome }),
      });

      const data = await response.json();

      if (!response.ok) {
        showError(data.error || "Não foi possível continuar. Tente novamente.");
        setLoading(false);
        return;
      }

      // Guarda o nome para a próxima tela usar
      sessionStorage.setItem("lit_english_nome", data.nome || nome);
      window.location.href = "/quiz";
    } catch (err) {
      showError("Erro de conexão com o servidor. Verifique se o backend está rodando.");
      setLoading(false);
    }
  });
})();
