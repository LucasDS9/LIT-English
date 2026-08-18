/* ==========================================================================
   LIT English — sfx.js
   Efeitos sonoros de feedback (acertar / errar / concluir sessão).
   Usado em: exercicios.js
   (errar + concluir) e revisar.js (concluir).
   ========================================================================== */

const SFX = (() => {
  const SOURCES = {
    correct: "audio/correct.wav",
    wrong: "audio/wrong.wav",
    finish: "audio/finish.wav",
  };

  const cache = {};

  function getAudio(name) {
    if (!cache[name]) {
      cache[name] = new Audio(SOURCES[name]);
    }
    return cache[name];
  }

  function play(name) {
    const audio = getAudio(name);
    if (!audio) return;
    try {
      audio.currentTime = 0;
      // play() pode rejeitar (ex: autoplay bloqueado antes de qualquer
      // interação do usuário) — ignoramos silenciosamente nesse caso.
      audio.play().catch(() => {});
    } catch (err) {
      /* noop */
    }
  }

  return { play };
})();
