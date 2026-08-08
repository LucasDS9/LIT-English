// -------------------------------------------------------------------
// Detecta navegador "in-app" (Instagram, Facebook, Messenger, Line).
// Esses navegadores embutidos costumam:
//   - não ter nenhuma voz de TTS carregada (speechSynthesis fica mudo,
//     sem erro nenhum) -> áudio do listening não funciona;
//   - destruir o estado da página quando o usuário navega para o
//     Instagram e volta -> o teste "reseta" sozinho.
// Por isso avisamos o aluno e damos um jeito fácil de abrir no
// navegador padrão do celular (Chrome/Safari), onde tudo funciona.
// -------------------------------------------------------------------
window.LIT_INAPP = (function () {
  const ua = navigator.userAgent || "";
  const isInstagram = /Instagram/i.test(ua);
  const isFacebook = /FBAN|FBAV|FB_IAB|FBIOS/i.test(ua);
  const isLine = /\bLine\//i.test(ua);
  const isInApp = isInstagram || isFacebook || isLine;
  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua);

  function androidIntentUrl() {
    // Reabre a URL atual como um "intent" do Android forçando o Chrome
    // especificamente (package=com.android.chrome) — em aparelhos Xiaomi
    // (MIUI) o intent genérico sem "package" costuma cair no navegador
    // próprio da Xiaomi (Mi Browser) em vez do Chrome, porque a MIUI o
    // define como padrão. S.browser_fallback_url garante que, se o
    // aparelho não tiver Chrome instalado, ele volte pra própria página
    // em vez de não fazer nada.
    const bare = window.location.href.replace(/^https?:\/\//, "");
    const fallback = encodeURIComponent(window.location.href);
    return `intent://${bare}#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${fallback};end`;
  }

  function genericIntentUrl() {
    // Fallback sem forçar um app específico — deixa o Android oferecer
    // o navegador padrão do aparelho (usado se o Chrome não existir).
    const bare = window.location.href.replace(/^https?:\/\//, "");
    return `intent://${bare}#Intent;scheme=https;action=android.intent.action.VIEW;end`;
  }

  function dismiss(banner) {
    banner.classList.add("is-dismissed");
    try {
      sessionStorage.setItem("lit_inapp_banner_dismissed", "1");
    } catch (e) {}
    setTimeout(() => banner.remove(), 250);
  }

  function renderBanner() {
    if (!isInApp) return;
    let dismissed = false;
    try {
      dismissed = sessionStorage.getItem("lit_inapp_banner_dismissed") === "1";
    } catch (e) {}
    if (dismissed) return;

    const banner = document.createElement("div");
    banner.className = "inapp-banner";
    banner.setAttribute("role", "alert");

    const text = isIOS
      ? 'Você está no navegador do Instagram — o áudio pode não funcionar aqui. Toque em <strong>⋮ / •••</strong> no topo da tela e escolha <strong>"Abrir no navegador"</strong> (Safari).'
      : 'Você está no navegador do Instagram — o áudio pode não funcionar aqui. Toque no botão para abrir no seu navegador padrão.';

    banner.innerHTML = `
      <span class="inapp-banner-icon" aria-hidden="true">🔊⚠️</span>
      <span class="inapp-banner-text">${text}</span>
      ${isAndroid ? '<button type="button" class="inapp-banner-btn" id="inapp-open-btn">Abrir no Chrome</button>' : ""}
      <button type="button" class="inapp-banner-close" id="inapp-close-btn" aria-label="Fechar aviso">✕</button>
    `;

    document.body.insertBefore(banner, document.body.firstChild);
    document.body.classList.add("has-inapp-banner");

    const closeBtn = banner.querySelector("#inapp-close-btn");
    closeBtn.addEventListener("click", () => dismiss(banner));

    if (isAndroid) {
      const openBtn = banner.querySelector("#inapp-open-btn");
      openBtn.addEventListener("click", () => {
        window.location.href = androidIntentUrl();
        // Se por algum motivo o Chrome não abrir (ex.: não instalado),
        // tenta de novo sem forçar um app específico logo em seguida.
        setTimeout(() => {
          window.location.href = genericIntentUrl();
        }, 700);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderBanner);
  } else {
    renderBanner();
  }

  return { isInApp, isInstagram, isFacebook, isAndroid, isIOS };
})();
