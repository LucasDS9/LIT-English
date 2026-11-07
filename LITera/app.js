(() => {
  const config = window.LITERA_CONFIG || {};
  const loginScreen = document.getElementById('login-screen');
  const appScreen = document.getElementById('app-screen');
  const loginForm = document.getElementById('login-form');
  const loginError = document.getElementById('login-error');
  const passwordInput = document.getElementById('password');
  const togglePassword = document.getElementById('toggle-password');

  loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const email = document.getElementById('email').value.trim().toLowerCase();
    const password = passwordInput.value;
    const valid = email === String(config.teacherEmail || '').toLowerCase() && password === String(config.teacherPassword || '');
    if (!valid) {
      loginError.hidden = false;
      return;
    }
    loginError.hidden = true;
    document.getElementById('teacher-name').textContent = config.teacherDisplayName || 'Professor';
    loginScreen.hidden = true;
    appScreen.hidden = false;
  });

  togglePassword.addEventListener('click', () => {
    const reveal = passwordInput.type === 'password';
    passwordInput.type = reveal ? 'text' : 'password';
    togglePassword.setAttribute('aria-label', reveal ? 'Ocultar senha' : 'Mostrar senha');
  });

  document.getElementById('logout-button').addEventListener('click', () => {
    appScreen.hidden = true;
    loginScreen.hidden = false;
    loginForm.reset();
    loginError.hidden = true;
  });

  const scrollToForm = () => document.getElementById('add-text-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  document.getElementById('scroll-to-form').addEventListener('click', scrollToForm);
  document.getElementById('empty-add-button').addEventListener('click', scrollToForm);

  const fileInput = document.getElementById('cover-image');
  const fileName = document.getElementById('file-name');
  const previewWrap = document.getElementById('image-preview-wrap');
  const preview = document.getElementById('image-preview');
  let previewUrl = null;

  fileInput.addEventListener('change', () => {
    const file = fileInput.files && fileInput.files[0];
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    if (!file) {
      fileName.textContent = 'Nenhum arquivo selecionado';
      previewWrap.hidden = true;
      return;
    }
    fileName.textContent = file.name;
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    previewWrap.hidden = false;
  });

  document.getElementById('remove-image').addEventListener('click', () => {
    fileInput.value = '';
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.removeAttribute('src');
    previewWrap.hidden = true;
    fileName.textContent = 'Nenhum arquivo selecionado';
  });

  // O formulário é deliberadamente apenas visual nesta etapa; não envia nem salva dados.
  document.getElementById('text-form').addEventListener('submit', event => event.preventDefault());
})();
