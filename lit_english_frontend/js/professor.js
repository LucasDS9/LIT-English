/* ==========================================================================
   LIT English — professor.js
   Painel do professor. Por enquanto cobre:
     - Alunos: GET /admin/students, PATCH approve/revoke
     - Flashcards: GET/POST/PUT/DELETE /flashcards
   ========================================================================== */

const contentArea = document.getElementById("content-area");
const professorNameEl = document.getElementById("professor-name");
const toastEl = document.getElementById("toast");

let toastTimer = null;
function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.hidden = true;
  }, 2600);
}

function formatDate(isoString) {
  try {
    return new Date(isoString).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      timeZone: "America/Sao_Paulo",
    });
  } catch (err) {
    return "";
  }
}

function formatDateTime(isoString) {
  try {
    return new Date(isoString).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch (err) {
    return "";
  }
}

function formatBrazilDate(dateKey) {
  try {
    const [y, m, d] = dateKey.split("-").map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
    return dt.toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
      year: "numeric",
      timeZone: "America/Sao_Paulo",
    });
  } catch (err) {
    return dateKey;
  }
}

function formatReviewStatus(item) {
  if (item.is_due || !item.next_review) return "A revisar";
  const next = new Date(item.next_review);
  const days = Math.max(1, Math.ceil((next - new Date()) / (1000 * 60 * 60 * 24)));
  const unit = days === 1 ? "dia" : "dias";
  return `Em ${days} ${unit} · ${formatDateTime(item.next_review)}`;
}

// ---------------------------------------------------------------------------
// Navegação entre seções
// ---------------------------------------------------------------------------

const sectionRenderers = {
  qa: renderQA,
  exercicios: renderExercicios,
  flashcards: renderFlashcards,
  textos: renderTextos,
  configuracoes: renderConfiguracoes,
};

document.querySelectorAll(".nav-item[data-section]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item[data-section]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    contentArea.classList.remove("qa-page");
    sectionRenderers[btn.dataset.section]();
  });
});

document.querySelectorAll(".nav-item[data-feature]").forEach((btn) => {
  btn.addEventListener("click", () => {
    showToast(`"${btn.dataset.feature}" ainda está em construção. Em breve por aqui!`);
  });
});

document.getElementById("logout-btn").addEventListener("click", () => {
  Auth.logout();
});

// ---------------------------------------------------------------------------
// Estados utilitários (loading / vazio / erro)
// ---------------------------------------------------------------------------

function renderLoading() {
  contentArea.innerHTML = '<div class="skeleton">Carregando...</div>';
}

function renderSectionHeader({ title, subtitle, actionLabel, onAction }) {
  const header = document.createElement("header");
  header.className = "section-header";

  const left = document.createElement("div");
  const h1 = document.createElement("h1");
  h1.textContent = title;
  left.appendChild(h1);
  const p = document.createElement("p");
  p.textContent = subtitle;
  left.appendChild(p);
  header.appendChild(left);

  if (actionLabel) {
    const btn = document.createElement("button");
    btn.className = "btn btn-primary btn-sm";
    btn.innerHTML = `${Icons.plus}<span>${actionLabel}</span>`;
    btn.addEventListener("click", onAction);
    header.appendChild(btn);
  }

  return header;
}

function renderStateBox(container, { icon, title, text, actionLabel, onAction }) {
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

  container.appendChild(box);
}


// ---------------------------------------------------------------------------
// Alunos
// ---------------------------------------------------------------------------

async function renderConfiguracoes() {
  let students;
  try {
    students = await apiFetch("/admin/students");
  } catch (err) {
    showToast(err.message || "Não foi possível carregar os alunos.");
    return;
  }

  contentArea.innerHTML = "";
  contentArea.appendChild(
    renderSectionHeader({
      title: "Configurações",
      subtitle: "Gerencie as preferências e o acesso da sua conta.",
    })
  );

  const subsection = document.createElement("div");
  subsection.className = "settings-subsection";

  const subHeader = document.createElement("div");
  subHeader.className = "settings-subheader";
  const subTitle = document.createElement("h2");
  subTitle.textContent = "Alunos";
  subHeader.appendChild(subTitle);
  const subText = document.createElement("p");
  subText.textContent = "Aprove ou bloqueie o acesso dos seus alunos.";
  subHeader.appendChild(subText);
  subsection.appendChild(subHeader);

  if (students.length === 0) {
    renderStateBox(subsection, {
      icon: Icons.users,
      title: "Nenhum aluno cadastrado ainda",
      text: "Quando um aluno se cadastrar, ele aparece aqui para você aprovar o acesso.",
    });
    contentArea.appendChild(subsection);
    return;
  }

  const list = document.createElement("div");
  list.className = "list";

  students.forEach((student) => {
    const row = document.createElement("div");
    row.className = "list-row";

    const info = document.createElement("div");
    info.className = "info";
    const primary = document.createElement("p");
    primary.className = "primary";
    primary.textContent = student.name;
    info.appendChild(primary);
    const secondary = document.createElement("p");
    secondary.className = "secondary";
    secondary.textContent = student.email;
    info.appendChild(secondary);
    if (student.whatsapp) {
      const whatsEl = document.createElement("p");
      whatsEl.className = "secondary";
      whatsEl.style.cssText = "display:flex;align-items:center;gap:4px;margin-top:2px;";
      whatsEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px;flex-shrink:0;"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>${student.whatsapp}`;
      info.appendChild(whatsEl);
    }
    row.appendChild(info);

    const meta = document.createElement("div");
    meta.className = "meta";

    const badge = document.createElement("span");
    if (student.is_approved) {
      badge.className = "badge badge-success";
      badge.innerHTML = `${Icons.checkSmall}<span>Aprovado</span>`;
    } else {
      badge.className = "badge badge-warning";
      badge.innerHTML = `${Icons.clock}<span>Pendente</span>`;
    }
    meta.appendChild(badge);

    const date = document.createElement("span");
    date.className = "date";
    date.textContent = formatDate(student.created_at);
    meta.appendChild(date);

    const actionBtn = document.createElement("button");
    if (student.is_approved) {
      actionBtn.className = "btn btn-outline btn-sm";
      actionBtn.textContent = "Bloquear";
      actionBtn.addEventListener("click", () => setStudentApproval(student.id, false, actionBtn));
    } else {
      actionBtn.className = "btn btn-primary btn-sm";
      actionBtn.textContent = "Aprovar";
      actionBtn.addEventListener("click", () => setStudentApproval(student.id, true, actionBtn));
    }
    meta.appendChild(actionBtn);

    if (student.is_approved) {
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn btn-outline btn-sm";
      deleteBtn.style.cssText = "color:#861E19;border-color:#861E19;";
      deleteBtn.textContent = "Excluir";
      deleteBtn.addEventListener("click", () => deleteStudent(student.id, student.name));
      meta.appendChild(deleteBtn);
    }

    row.appendChild(meta);
    list.appendChild(row);
  });

  subsection.appendChild(list);
  contentArea.appendChild(subsection);
}

async function setStudentApproval(studentId, approve, btn) {
  btn.disabled = true;
  const path = `/admin/students/${studentId}/${approve ? "approve" : "revoke"}`;
  try {
    await apiFetch(path, { method: "PATCH" });
    showToast(approve ? "Aluno aprovado." : "Acesso bloqueado.");
    renderConfiguracoes();
  } catch (err) {
    showToast(err.message || "Não foi possível atualizar o aluno.");
    btn.disabled = false;
  }
}

async function deleteStudent(studentId, studentName) {
  const ok = window.confirm(
    `Excluir permanentemente o aluno "${studentName}"?\n\nTodos os dados dele (exercícios, flashcards, submissões) serão removidos.`
  );
  if (!ok) return;

  try {
    await apiFetch(`/admin/students/${studentId}`, { method: "DELETE" });
    showToast("Aluno excluído.");
    renderConfiguracoes();
  } catch (err) {
    showToast(err.message || "Não foi possível excluir o aluno.");
  }
}

// ---------------------------------------------------------------------------
// Flashcards
// ---------------------------------------------------------------------------

async function renderFlashcards() {
  renderLoading();

  let cards, allStudents;
  try {
    [cards, allStudents] = await Promise.all([
      apiFetch("/flashcards"),
      apiFetch("/admin/students"),
    ]);
  } catch (err) {
    showToast(err.message || "Não foi possível carregar os flashcards.");
    return;
  }
  const approvedStudents = allStudents.filter((s) => s.is_approved);

  contentArea.innerHTML = "";
  contentArea.appendChild(
    renderSectionHeader({
      title: "Flashcards",
      subtitle: "Crie e gerencie o vocabulário disponível para revisão.",
      actionLabel: "Novo Flashcard",
      onAction: () => openFlashcardModal(null, approvedStudents),
    })
  );

  if (cards.length === 0) {
    renderStateBox(contentArea, {
      icon: Icons.library,
      title: "Nenhum flashcard cadastrado ainda",
      text: "Crie o primeiro flashcard para que seus alunos possam começar a revisar.",
      actionLabel: "Novo Flashcard",
      onAction: () => openFlashcardModal(null, approvedStudents),
    });
  } else {
    const list = document.createElement("div");
    list.className = "list";

    cards.forEach((card) => {
      const row = document.createElement("div");
      row.className = "list-row";

      const info = document.createElement("div");
      info.className = "info";
      const primary = document.createElement("p");
      primary.className = "primary";
      primary.textContent = card.front;
      info.appendChild(primary);
      const secondary = document.createElement("p");
      secondary.className = "secondary";
      const names = (card.students || []).map((s) => s.name).join(", ") || "—";
      secondary.textContent = `${card.back} · Para: ${names}`;
      info.appendChild(secondary);
      row.appendChild(info);

      const meta = document.createElement("div");
      meta.className = "meta";

      const date = document.createElement("span");
      date.className = "date";
      date.textContent = formatDate(card.created_at);
      meta.appendChild(date);

      const actions = document.createElement("div");
      actions.className = "row-actions";

      const editBtn = document.createElement("button");
      editBtn.className = "icon-btn";
      editBtn.title = "Editar";
      editBtn.innerHTML = Icons.edit;
      editBtn.addEventListener("click", () => openFlashcardModal(card, approvedStudents));
      actions.appendChild(editBtn);

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "icon-btn danger";
      deleteBtn.title = "Excluir";
      deleteBtn.innerHTML = Icons.trash;
      deleteBtn.addEventListener("click", () => deleteFlashcard(card.id));
      actions.appendChild(deleteBtn);

      meta.appendChild(actions);
      row.appendChild(meta);
      list.appendChild(row);
    });

    contentArea.appendChild(list);
  }

  renderStudentVocabularySection(contentArea, approvedStudents);
}

// ---------------------------------------------------------------------------
// Vocabulário do aluno (status de revisão SM-2)
// ---------------------------------------------------------------------------

function renderStudentVocabularySection(container, approvedStudents) {
  const wrap = document.createElement("div");
  wrap.style.cssText = "margin-top:36px;";

  const title = document.createElement("h3");
  title.textContent = "Vocabulário do aluno";
  title.style.cssText = "font-size:16px;margin-bottom:4px;";
  wrap.appendChild(title);

  const subtitle = document.createElement("p");
  subtitle.style.cssText = "font-size:13px;color:#666;margin-bottom:14px;";
  subtitle.textContent = "Veja as palavras enviadas a um aluno e quando serão revisadas.";
  wrap.appendChild(subtitle);

  const pickerRow = document.createElement("div");
  pickerRow.style.cssText = "display:flex;align-items:center;gap:12px;margin-bottom:16px;";
  const pickerLabel = document.createElement("label");
  pickerLabel.textContent = "Aluno:";
  pickerLabel.style.cssText = "font-weight:600;font-size:14px;";
  const select = document.createElement("select");
  select.style.cssText = "min-width:200px;";

  if (approvedStudents.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "Nenhum aluno aprovado";
    opt.disabled = true;
    select.appendChild(opt);
  } else {
    approvedStudents.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      select.appendChild(opt);
    });
  }
  pickerRow.appendChild(pickerLabel);
  pickerRow.appendChild(select);
  wrap.appendChild(pickerRow);

  const vocabBox = document.createElement("div");
  wrap.appendChild(vocabBox);
  container.appendChild(wrap);

  if (approvedStudents.length === 0) {
    vocabBox.innerHTML = '<p style="color:#666;font-size:14px;">Nenhum aluno aprovado ainda.</p>';
    return;
  }

  select.addEventListener("change", () => loadStudentVocabulary(vocabBox, select.value));
  loadStudentVocabulary(vocabBox, select.value);
}

async function loadStudentVocabulary(container, studentId) {
  container.innerHTML = '<div class="skeleton">Carregando vocabulário...</div>';
  try {
    const items = await apiFetch(`/flashcards/vocabulary/${studentId}`);
    container.innerHTML = "";

    if (!items || items.length === 0) {
      container.innerHTML = '<p style="color:#666;font-size:14px;">Nenhum flashcard enviado para este aluno ainda.</p>';
      return;
    }

    const list = document.createElement("div");
    list.className = "list";

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "list-row";

      const info = document.createElement("div");
      info.className = "info";
      const primary = document.createElement("p");
      primary.className = "primary";
      primary.textContent = item.front;
      info.appendChild(primary);
      const secondary = document.createElement("p");
      secondary.className = "secondary";
      secondary.textContent = item.back;
      info.appendChild(secondary);
      row.appendChild(info);

      const meta = document.createElement("div");
      meta.className = "meta";
      const status = document.createElement("span");
      status.className = `badge ${item.is_due ? "badge-warning" : "badge-success"}`;
      status.textContent = formatReviewStatus(item);
      meta.appendChild(status);
      row.appendChild(meta);

      list.appendChild(row);
    });

    container.appendChild(list);
  } catch (err) {
    container.innerHTML = `<p style="color:#861E19;font-size:14px;">Erro: ${err.message}</p>`;
  }
}

function openFlashcardModal(existingCard, approvedStudents) {
  const isEdit = !!existingCard;

  if (!approvedStudents || approvedStudents.length === 0) {
    showToast("Nenhum aluno aprovado para enviar flashcards.");
    return;
  }

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  const modal = document.createElement("div");
  modal.className = "modal";

  const header = document.createElement("div");
  header.className = "modal-header";
  const h2 = document.createElement("h2");
  h2.textContent = isEdit ? "Editar Flashcard" : "Novo Flashcard";
  header.appendChild(h2);
  const closeBtn = document.createElement("button");
  closeBtn.className = "icon-btn";
  closeBtn.innerHTML = Icons.x;
  closeBtn.addEventListener("click", () => overlay.remove());
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const form = document.createElement("form");

  const existingStudentIds = new Set((existingCard?.students || []).map((s) => s.id));

  const studentsField = document.createElement("div");
  studentsField.className = "field";
  studentsField.innerHTML = '<label>Enviar para</label>';
  const studentsBox = document.createElement("div");
  studentsBox.style.cssText = "display:flex;flex-direction:column;gap:6px;max-height:160px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 12px;margin-top:6px;";
  const studentCheckboxes = [];
  approvedStudents.forEach((s) => {
    const label = document.createElement("label");
    label.style.cssText = "display:flex;align-items:center;gap:8px;font-size:14px;cursor:pointer;";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = s.id;
    checkbox.checked = isEdit ? existingStudentIds.has(s.id) : false;
    label.appendChild(checkbox);
    const span = document.createElement("span");
    span.textContent = s.name;
    label.appendChild(span);
    studentsBox.appendChild(label);
    studentCheckboxes.push(checkbox);
  });
  studentsField.appendChild(studentsBox);
  form.appendChild(studentsField);

  const frontField = document.createElement("div");
  frontField.className = "field";
  frontField.innerHTML = '<label for="card-front">Frase em inglês</label>';
  const frontInput = document.createElement("input");
  frontInput.type = "text";
  frontInput.id = "card-front";
  frontInput.required = true;
  frontInput.placeholder = "Ex: Did they go?";
  frontInput.value = existingCard ? existingCard.front : "";
  frontField.appendChild(frontInput);
  form.appendChild(frontField);

  const backField = document.createElement("div");
  backField.className = "field";
  backField.innerHTML = '<label for="card-back">Tradução em português</label>';
  const backInput = document.createElement("input");
  backInput.type = "text";
  backInput.id = "card-back";
  backInput.required = true;
  backInput.placeholder = "Ex: Eles foram?";
  backInput.value = existingCard ? existingCard.back : "";
  backField.appendChild(backInput);
  form.appendChild(backField);

  const errorBox = document.createElement("p");
  errorBox.className = "form-error";
  errorBox.hidden = true;
  form.appendChild(errorBox);

  const actions = document.createElement("div");
  actions.className = "modal-actions";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-outline";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", () => overlay.remove());
  actions.appendChild(cancelBtn);

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.className = "btn btn-primary";
  saveBtn.textContent = isEdit ? "Salvar" : "Criar";
  actions.appendChild(saveBtn);

  form.appendChild(actions);
  modal.appendChild(form);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  frontInput.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.hidden = true;

    const student_ids = studentCheckboxes
      .filter((c) => c.checked)
      .map((c) => parseInt(c.value));

    if (student_ids.length === 0) {
      errorBox.textContent = "Selecione ao menos um aluno.";
      errorBox.hidden = false;
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = "Salvando...";

    const payload = { front: frontInput.value.trim(), back: backInput.value.trim(), student_ids };

    try {
      if (isEdit) {
        await apiFetch(`/flashcards/${existingCard.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("Flashcard atualizado.");
      } else {
        await apiFetch("/flashcards", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("Flashcard criado.");
      }
      overlay.remove();
      renderFlashcards();
    } catch (err) {
      errorBox.textContent = err.message || "Não foi possível salvar o flashcard.";
      errorBox.hidden = false;
      saveBtn.disabled = false;
      saveBtn.textContent = isEdit ? "Salvar" : "Criar";
    }
  });
}

async function deleteFlashcard(id) {
  const ok = window.confirm("Excluir este flashcard? Essa ação não pode ser desfeita.");
  if (!ok) return;

  try {
    await apiFetch(`/flashcards/${id}`, { method: "DELETE" });
    showToast("Flashcard excluído.");
    renderFlashcards();
  } catch (err) {
    showToast(err.message || "Não foi possível excluir o flashcard.");
  }
}

// ---------------------------------------------------------------------------
// Read and Listen (textos)
// ---------------------------------------------------------------------------

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

function excerptOf(text, maxLen = 110) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= maxLen) return clean;
  return clean.slice(0, maxLen).trimEnd() + "…";
}

async function renderTextos() {
  renderLoading();

  let texts, allStudents;
  try {
    [texts, allStudents] = await Promise.all([
      apiFetch("/texts"),
      apiFetch("/admin/students"),
    ]);
  } catch (err) {
    showToast(err.message || "Não foi possível carregar os textos.");
    return;
  }
  const approvedStudents = allStudents.filter((s) => s.is_approved);

  contentArea.innerHTML = "";
  contentArea.appendChild(
    renderSectionHeader({
      title: "Read and Listen",
      subtitle: "Crie textos em inglês para seus alunos lerem e ouvirem.",
      actionLabel: "Novo Texto",
      onAction: () => openTextoModal(null, approvedStudents),
    })
  );

  if (texts.length === 0) {
    renderStateBox(contentArea, {
      icon: Icons.bookOpen,
      title: "Nenhum texto cadastrado ainda",
      text: "Crie o primeiro texto para que seus alunos possam praticar leitura e escuta.",
      actionLabel: "Novo Texto",
      onAction: () => openTextoModal(null, approvedStudents),
    });
    return;
  }

  const list = document.createElement("div");
  list.className = "list";

  texts.forEach((text) => {
    const row = document.createElement("div");
    row.className = "list-row";

    const info = document.createElement("div");
    info.className = "info";
    const primary = document.createElement("p");
    primary.className = "primary";
    primary.textContent = text.title;
    info.appendChild(primary);
    const secondary = document.createElement("p");
    secondary.className = "secondary";
    secondary.textContent = excerptOf(text.content);
    info.appendChild(secondary);
    row.appendChild(info);

    const meta = document.createElement("div");
    meta.className = "meta";

    const levelBadge = document.createElement("span");
    levelBadge.className = "level-badge";
    levelBadge.textContent = text.level;
    meta.appendChild(levelBadge);

    const date = document.createElement("span");
    date.className = "date";
    date.textContent = formatDate(text.created_at);
    meta.appendChild(date);

    const actions = document.createElement("div");
    actions.className = "row-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "icon-btn";
    editBtn.title = "Editar";
    editBtn.innerHTML = Icons.edit;
    editBtn.addEventListener("click", () => openTextoModal(text, approvedStudents));
    actions.appendChild(editBtn);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "icon-btn danger";
    deleteBtn.title = "Excluir";
    deleteBtn.innerHTML = Icons.trash;
    deleteBtn.addEventListener("click", () => deleteTexto(text.id));
    actions.appendChild(deleteBtn);

    meta.appendChild(actions);
    row.appendChild(meta);
    list.appendChild(row);
  });

  contentArea.appendChild(list);
}

function openTextoModal(existingText, approvedStudents = []) {
  const isEdit = !!existingText;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  const modal = document.createElement("div");
  modal.className = "modal";

  const header = document.createElement("div");
  header.className = "modal-header";
  const h2 = document.createElement("h2");
  h2.textContent = isEdit ? "Editar Texto" : "Novo Texto";
  header.appendChild(h2);
  const closeBtn = document.createElement("button");
  closeBtn.className = "icon-btn";
  closeBtn.innerHTML = Icons.x;
  closeBtn.addEventListener("click", () => overlay.remove());
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const form = document.createElement("form");

  const titleField = document.createElement("div");
  titleField.className = "field";
  titleField.innerHTML = '<label for="text-title">Título</label>';
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.id = "text-title";
  titleInput.required = true;
  titleInput.placeholder = "Ex: A Day at the Park";
  titleInput.value = existingText ? existingText.title : "";
  titleField.appendChild(titleInput);
  form.appendChild(titleField);

  const levelField = document.createElement("div");
  levelField.className = "field";
  levelField.innerHTML = '<label for="text-level">Nível</label>';
  const levelSelect = document.createElement("select");
  levelSelect.id = "text-level";
  levelSelect.required = true;
  CEFR_LEVELS.forEach((lvl) => {
    const opt = document.createElement("option");
    opt.value = lvl;
    opt.textContent = lvl;
    levelSelect.appendChild(opt);
  });
  levelSelect.value = existingText ? existingText.level : "A1";
  levelField.appendChild(levelSelect);
  form.appendChild(levelField);

  const contentField = document.createElement("div");
  contentField.className = "field";
  contentField.innerHTML = '<label for="text-content">Texto em inglês</label>';
  const contentInput = document.createElement("textarea");
  contentInput.id = "text-content";
  contentInput.required = true;
  contentInput.rows = 6;
  contentInput.placeholder = "Cole ou digite o texto em inglês aqui...";
  contentInput.value = existingText ? existingText.content : "";
  contentField.appendChild(contentInput);
  form.appendChild(contentField);


  // ---------- Alunos (multi-select) ----------
  const studentsField = document.createElement("div");
  studentsField.className = "field";
  studentsField.innerHTML = "<label>Enviar para</label>";

  if (approvedStudents.length === 0) {
    const noStudents = document.createElement("p");
    noStudents.style.cssText = "font-size:13px;color:var(--text-secondary);margin-top:4px;";
    noStudents.textContent = "Nenhum aluno aprovado ainda.";
    studentsField.appendChild(noStudents);
  } else {
    const studentsBox = document.createElement("div");
    studentsBox.style.cssText = "display:flex;flex-direction:column;gap:6px;max-height:160px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 12px;margin-top:6px;";

    const existingStudentIds = new Set((existingText?.students || []).map((s) => s.id));

    approvedStudents.forEach((student) => {
      const label = document.createElement("label");
      label.style.cssText = "display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = student.id;
      checkbox.checked = existingStudentIds.has(student.id);
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(student.name));
      studentsBox.appendChild(label);
    });

    studentsField.appendChild(studentsBox);
  }
  form.appendChild(studentsField);

  const errorBox = document.createElement("p");
  errorBox.className = "form-error";
  errorBox.hidden = true;
  form.appendChild(errorBox);

  const actions = document.createElement("div");
  actions.className = "modal-actions";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-outline";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", () => overlay.remove());
  actions.appendChild(cancelBtn);

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.className = "btn btn-primary";
  saveBtn.textContent = isEdit ? "Salvar" : "Criar";
  actions.appendChild(saveBtn);

  form.appendChild(actions);
  modal.appendChild(form);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  titleInput.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.hidden = true;
    saveBtn.disabled = true;
    saveBtn.textContent = "Salvando...";

    const checkedIds = approvedStudents.length > 0
      ? Array.from(studentsField.querySelectorAll("input[type=checkbox]:checked")).map((cb) => Number(cb.value))
      : [];

    const payload = {
      title: titleInput.value.trim(),
      level: levelSelect.value,
      content: contentInput.value.trim(),
      translation: null,
      student_ids: checkedIds,
    };

    try {
      if (isEdit) {
        await apiFetch(`/texts/${existingText.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("Texto atualizado.");
      } else {
        await apiFetch("/texts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("Texto criado.");
      }
      overlay.remove();
      renderTextos();
    } catch (err) {
      errorBox.textContent = err.message || "Não foi possível salvar o texto.";
      errorBox.hidden = false;
      saveBtn.disabled = false;
      saveBtn.textContent = isEdit ? "Salvar" : "Criar";
    }
  });
}

async function deleteTexto(id) {
  const ok = window.confirm("Excluir este texto? Essa ação não pode ser desfeita.");
  if (!ok) return;

  try {
    await apiFetch(`/texts/${id}`, { method: "DELETE" });
    showToast("Texto excluído.");
    renderTextos();
  } catch (err) {
    showToast(err.message || "Não foi possível excluir o texto.");
  }
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------

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

  if (user.role !== "professor") {
    window.location.href = "revisar.html";
    return;
  }

  professorNameEl.textContent = user.name;
  renderFlashcards();
}

init();

// ---------------------------------------------------------------------------
// EXERCÍCIOS
// ---------------------------------------------------------------------------

// Exercícios pendentes criados nesta sessão (aguardando envio ao aluno)
let pendingExercises = [];

async function renderExercicios() {
  contentArea.innerHTML = "";

  // Header with tabs
  const header = renderSectionHeader({
    title: "Exercises",
    subtitle: "Crie exercícios de preencher a lacuna e escolha de palavras.",
  });

  // Tab bar
  const tabBar = document.createElement("div");
  tabBar.className = "tab-bar";
  tabBar.style.cssText = "display:flex;gap:8px;margin-bottom:20px;";
  const tabEx = document.createElement("button");
  tabEx.className = "btn btn-primary btn-sm";
  tabEx.textContent = "Exercícios";
  const tabSub = document.createElement("button");
  tabSub.className = "btn btn-outline btn-sm";
  tabSub.textContent = "Submissões";
  const tabAlunos = document.createElement("button");
  tabAlunos.className = "btn btn-outline btn-sm";
  tabAlunos.textContent = "Exercícios dos Alunos";
  tabBar.appendChild(tabEx);
  tabBar.appendChild(tabSub);
  tabBar.appendChild(tabAlunos);

  const exView = document.createElement("div");
  const subView = document.createElement("div");
  subView.hidden = true;
  const alunosView = document.createElement("div");
  alunosView.hidden = true;

  tabEx.addEventListener("click", () => {
    tabEx.className = "btn btn-primary btn-sm";
    tabSub.className = "btn btn-outline btn-sm";
    tabAlunos.className = "btn btn-outline btn-sm";
    exView.hidden = false;
    subView.hidden = true;
    alunosView.hidden = true;
  });
  tabSub.addEventListener("click", () => {
    tabSub.className = "btn btn-primary btn-sm";
    tabEx.className = "btn btn-outline btn-sm";
    tabAlunos.className = "btn btn-outline btn-sm";
    exView.hidden = true;
    subView.hidden = false;
    alunosView.hidden = true;
    loadSubmissoes(subView);
  });
  tabAlunos.addEventListener("click", () => {
    tabAlunos.className = "btn btn-primary btn-sm";
    tabEx.className = "btn btn-outline btn-sm";
    tabSub.className = "btn btn-outline btn-sm";
    exView.hidden = true;
    subView.hidden = true;
    alunosView.hidden = false;
    loadStudentExerciseProgress(alunosView);
  });

  contentArea.appendChild(header);
  contentArea.appendChild(tabBar);
  contentArea.appendChild(exView);
  contentArea.appendChild(subView);
  contentArea.appendChild(alunosView);

  buildExerciciosView(exView);
}

function buildExerciciosView(container) {
  // ---- Form card ----
  const formCard = document.createElement("div");
  formCard.className = "card";
  formCard.style.cssText = "padding:24px;margin-bottom:20px;";

  const formTitle = document.createElement("h3");
  formTitle.textContent = "Novo exercício";
  formTitle.style.marginBottom = "16px";
  formCard.appendChild(formTitle);

  // Type selector
  const typeRow = document.createElement("div");
  typeRow.style.cssText = "display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;";
  const typeFill = document.createElement("button");
  typeFill.className = "btn btn-primary btn-sm";
  typeFill.textContent = "Preencher lacuna";
  const typeWord = document.createElement("button");
  typeWord.className = "btn btn-outline btn-sm";
  typeWord.textContent = "Listening (TTS)";
  const typeSpeak = document.createElement("button");
  typeSpeak.className = "btn btn-outline btn-sm";
  typeSpeak.textContent = "Falar (Whisper)";
  typeRow.appendChild(typeFill);
  typeRow.appendChild(typeWord);
  typeRow.appendChild(typeSpeak);
  formCard.appendChild(typeRow);

  let currentType = "fill_blank";
  function setActiveTypeButton(btn) {
    [typeFill, typeWord, typeSpeak].forEach((b) => {
      b.className = b === btn ? "btn btn-primary btn-sm" : "btn btn-outline btn-sm";
    });
  }
  typeFill.addEventListener("click", () => {
    currentType = "fill_blank";
    setActiveTypeButton(typeFill);
    fillFields.hidden = false;
    wordFields.hidden = true;
    speakFields.hidden = true;
  });
  typeWord.addEventListener("click", () => {
    currentType = "word_choice";
    setActiveTypeButton(typeWord);
    fillFields.hidden = true;
    wordFields.hidden = false;
    speakFields.hidden = true;
  });
  typeSpeak.addEventListener("click", () => {
    currentType = "speaking";
    setActiveTypeButton(typeSpeak);
    fillFields.hidden = true;
    wordFields.hidden = true;
    speakFields.hidden = false;
  });

  // Title field
  const titleField = document.createElement("div");
  titleField.className = "field";
  titleField.style.marginBottom = "12px";
  titleField.innerHTML = '<label style="font-size:13px;font-weight:600;color:#444;">Título</label>';
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.placeholder = "Ex: Past simple #1";
  titleInput.style.cssText = "width:100%;margin-top:4px;";
  titleField.appendChild(titleInput);
  formCard.appendChild(titleField);

  // ---- Fill blank fields ----
  const fillFields = document.createElement("div");

  const sentenceRow = document.createElement("div");
  sentenceRow.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:6px;";
  const part1Input = document.createElement("input");
  part1Input.type = "text";
  part1Input.placeholder = "Frase (parte 1)";
  part1Input.style.flex = "1";
  const blankInput = document.createElement("input");
  blankInput.type = "text";
  blankInput.placeholder = "resposta";
  blankInput.autocomplete = "off";
  blankInput.title = "Esta é a lacuna: digite aqui a resposta correta.";
  blankInput.style.cssText =
    "width:110px;flex:0 0 110px;text-align:center;border:2px solid #861E19;border-radius:8px;color:#861E19;font-weight:700;background:#fff5f5;";
  const part2Input = document.createElement("input");
  part2Input.type = "text";
  part2Input.placeholder = "Resto da frase";
  part2Input.style.flex = "1";
  sentenceRow.appendChild(part1Input);
  sentenceRow.appendChild(blankInput);
  sentenceRow.appendChild(part2Input);
  fillFields.appendChild(sentenceRow);

  const blankHint = document.createElement("p");
  blankHint.style.cssText = "font-size:12px;color:#888;margin:0 0 12px;";
  blankHint.textContent = "O campo em vermelho é a lacuna: o que você digitar nele é a resposta correta do exercício.";
  fillFields.appendChild(blankHint);

  const fillTrans = document.createElement("div");
  fillTrans.style.marginBottom = "12px";
  fillTrans.innerHTML = '<label style="font-size:13px;font-weight:600;color:#444;">Tradução (dica para o aluno — opcional)</label>';
  const fillTransInput = document.createElement("input");
  fillTransInput.type = "text";
  fillTransInput.placeholder = "Ex: ontem eu ___ na academia";
  fillTransInput.style.cssText = "width:100%;margin-top:4px;";
  fillTrans.appendChild(fillTransInput);
  fillFields.appendChild(fillTrans);

  formCard.appendChild(fillFields);

  // ---- Listening (TTS) fields ----
  const wordFields = document.createElement("div");
  wordFields.hidden = true;

  const wordSentence = document.createElement("div");
  wordSentence.style.marginBottom = "12px";
  wordSentence.innerHTML = '<label style="font-size:13px;font-weight:600;color:#444;">Frase em inglês (o aluno vai escutar)</label>';
  const wordSentenceInput = document.createElement("input");
  wordSentenceInput.type = "text";
  wordSentenceInput.placeholder = "Ex: She goes to work every day.";
  wordSentenceInput.style.cssText = "width:100%;margin-top:4px;";
  wordSentence.appendChild(wordSentenceInput);
  const playTestBtn = document.createElement("button");
  playTestBtn.type = "button";
  playTestBtn.className = "icon-btn";
  playTestBtn.title = "Ouvir";
  playTestBtn.style.cssText = "margin-top:6px;";
  playTestBtn.innerHTML = Icons.volume || "🔊";
  playTestBtn.addEventListener("click", async () => {
    const text = wordSentenceInput.value.trim();
    if (!text) return;
    try {
      const blob = await apiFetchBlob(`/tts/speak?text=${encodeURIComponent(text)}`);
      const url = URL.createObjectURL(blob);
      new Audio(url).play();
    } catch {
      showToast("Erro ao gerar áudio.");
    }
  });
  wordSentence.appendChild(playTestBtn);
  wordFields.appendChild(wordSentence);

  const wordAns = document.createElement("div");
  wordAns.style.marginBottom = "12px";
  

  formCard.appendChild(wordFields);

  // ---- Speaking (Whisper) fields ----
  const speakFields = document.createElement("div");
  speakFields.hidden = true;

  const speakPt = document.createElement("div");
  speakPt.style.marginBottom = "12px";
  speakPt.innerHTML = '<label style="font-size:13px;font-weight:600;color:#444;">Frase em português (o aluno vai ler)</label>';
  const speakPtInput = document.createElement("input");
  speakPtInput.type = "text";
  speakPtInput.placeholder = "Ex: Eu gostaria de viajar para o exterior um dia.";
  speakPtInput.style.cssText = "width:100%;margin-top:4px;";
  speakPt.appendChild(speakPtInput);
  speakFields.appendChild(speakPt);

  const speakEn = document.createElement("div");
  speakEn.style.marginBottom = "12px";
  speakEn.innerHTML = '<label style="font-size:13px;font-weight:600;color:#444;">Tradução em inglês (o aluno vai falar isso)</label>';
  const speakEnInput = document.createElement("input");
  speakEnInput.type = "text";
  speakEnInput.placeholder = "Ex: I would like to travel abroad someday.";
  speakEnInput.style.cssText = "width:100%;margin-top:4px;";
  speakEn.appendChild(speakEnInput);
  speakFields.appendChild(speakEn);

  const speakHint = document.createElement("p");
  speakHint.style.cssText = "font-size:12px;color:#888;margin:0 0 4px;";
  speakHint.textContent = "O aluno vai ler a frase em português e falar a frase em inglês no microfone. O Whisper transcreve a fala e compara com a tradução em inglês.";
  speakFields.appendChild(speakHint);

  formCard.appendChild(speakFields);

  const errorBox = document.createElement("p");
  errorBox.style.cssText = "color:#861E19;font-size:13px;";
  errorBox.hidden = true;
  formCard.appendChild(errorBox);

  const addBtn = document.createElement("button");
  addBtn.className = "btn btn-primary";
  addBtn.innerHTML = `${Icons.plus}<span>Adicionar exercício</span>`;
  addBtn.addEventListener("click", async () => {
    errorBox.hidden = true;
    const title = titleInput.value.trim();
    if (!title) { errorBox.textContent = "Informe o título."; errorBox.hidden = false; return; }

    let payload;
    if (currentType === "fill_blank") {
      const p1 = part1Input.value.trim();
      const p2 = part2Input.value.trim();
      const ans = blankInput.value.trim();
      if (!ans) { errorBox.textContent = "Preencha a lacuna em vermelho com a resposta correta."; errorBox.hidden = false; blankInput.focus(); return; }
      payload = {
        title,
        type: "fill_blank",
        part1: p1,
        part2: p2,
        prompt: `${p1} ___ ${p2}`.trim(),
        correct_answer: ans,
        translation: fillTransInput.value.trim() || null,
        word_choices: null,
      };
    } else if (currentType === "word_choice") {
      const sentence = wordSentenceInput.value.trim();
      if (!sentence) { errorBox.textContent = "Informe a frase em inglês."; errorBox.hidden = false; return; }
      payload = {
        title,
        type: "word_choice",
        part1: null,
        part2: null,
        prompt: sentence,
        correct_answer: sentence,
        translation: null,
        word_choices: null,
      };
    } else {
      const pt = speakPtInput.value.trim();
      const en = speakEnInput.value.trim();
      if (!pt) { errorBox.textContent = "Informe a frase em português."; errorBox.hidden = false; return; }
      if (!en) { errorBox.textContent = "Informe a tradução em inglês."; errorBox.hidden = false; return; }
      payload = {
        title,
        type: "speaking",
        part1: null,
        part2: null,
        prompt: pt,
        correct_answer: en,
        translation: null,
        word_choices: null,
      };
    }

    addBtn.disabled = true;
    addBtn.textContent = "Adicionando...";
    try {
      const ex = await apiFetch("/exercises", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      pendingExercises.push(ex);
      // reset
      titleInput.value = "";
      part1Input.value = ""; part2Input.value = ""; blankInput.value = ""; fillTransInput.value = "";
      wordSentenceInput.value = ""; 
      speakPtInput.value = ""; speakEnInput.value = "";
      showToast("Exercício adicionado à lista.");
      renderPendingList();
    } catch (err) {
      errorBox.textContent = err.message || "Erro ao criar exercício.";
      errorBox.hidden = false;
    } finally {
      addBtn.disabled = false;
      addBtn.innerHTML = `${Icons.plus}<span>Adicionar exercício</span>`;
    }
  });
  formCard.appendChild(addBtn);
  container.appendChild(formCard);

  // ---- Pending list + send ----
  const pendingSection = document.createElement("div");
  container.appendChild(pendingSection);

  function renderPendingList() {
    pendingSection.innerHTML = "";

    if (pendingExercises.length === 0) return;

    const pendingTitle = document.createElement("h3");
    pendingTitle.textContent = `Exercícios para enviar (${pendingExercises.length})`;
    pendingTitle.style.marginBottom = "12px";
    pendingSection.appendChild(pendingTitle);

    const list = document.createElement("div");
    list.style.cssText = "display:flex;flex-direction:column;gap:8px;margin-bottom:16px;";

    pendingExercises.forEach((ex, idx) => {
      const row = document.createElement("div");
      row.className = "card";
      row.style.cssText = "padding:12px 16px;display:flex;justify-content:space-between;align-items:center;";
      const info = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = ex.title;
      const sub = document.createElement("span");
      sub.style.cssText = "font-size:13px;color:#666;margin-left:8px;";
      if (ex.type === "fill_blank") {
        sub.textContent = `${ex.part1 || ""} ___ ${ex.part2 || ""} → ${ex.correct_answer}`;
      } else if (ex.type === "speaking") {
        sub.textContent = `🎤 "${ex.prompt}" → ${ex.correct_answer}`;
      } else {
        sub.textContent = `🔊 "${ex.prompt}" → ${ex.correct_answer}`;
      }
      info.appendChild(label);
      info.appendChild(sub);
      const removeBtn = document.createElement("button");
      removeBtn.className = "icon-btn";
      removeBtn.innerHTML = Icons.trash;
      removeBtn.title = "Remover da lista";
      removeBtn.addEventListener("click", () => {
        pendingExercises.splice(idx, 1);
        renderPendingList();
      });
      row.appendChild(info);
      row.appendChild(removeBtn);
      list.appendChild(row);
    });
    pendingSection.appendChild(list);

    const sendBtn = document.createElement("button");
    sendBtn.className = "btn btn-primary";
    sendBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22 11 13 2 9l20-7z"/></svg><span>Enviar para aluno</span>`;
    sendBtn.style.marginTop = "4px";
    sendBtn.addEventListener("click", () => openSendModal());
    pendingSection.appendChild(sendBtn);
  }

  renderPendingList();

  // ---- Saved exercises list ----
  loadSavedExercises(container);
}

async function loadSavedExercises(container) {
  try {
    const exercises = await apiFetch("/exercises");

    if (!exercises || exercises.length === 0) return;

    const title = document.createElement("h3");
    title.textContent = "Todos os exercícios";
    title.style.cssText = "margin-top:28px;margin-bottom:12px;";
    container.appendChild(title);

    const list = document.createElement("div");
    list.style.cssText = "display:flex;flex-direction:column;gap:8px;";

    exercises.forEach((ex) => {
      const row = document.createElement("div");
      row.className = "card";
      row.style.cssText = "padding:12px 16px;display:flex;justify-content:space-between;align-items:center;";
      const info = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = ex.title;
      const sub = document.createElement("div");
      sub.style.cssText = "font-size:13px;color:#666;margin-top:2px;";
      if (ex.type === "fill_blank") {
        sub.textContent = `${ex.part1 || ""} ___ ${ex.part2 || ""} → ${ex.correct_answer}`;
      } else if (ex.type === "speaking") {
        sub.textContent = `🎤 "${ex.prompt}" → ${ex.correct_answer}`;
      } else {
        sub.textContent = `🔊 "${ex.prompt}" → ${ex.correct_answer}`;
      }
      info.appendChild(label);
      info.appendChild(sub);

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "icon-btn";
      deleteBtn.innerHTML = Icons.trash;
      deleteBtn.title = "Excluir";
      deleteBtn.addEventListener("click", async () => {
        if (!confirm("Excluir este exercício?")) return;
        try {
          await apiFetch(`/exercises/${ex.id}`, { method: "DELETE" });
          showToast("Exercício excluído.");
          renderExercicios();
        } catch (err) {
          showToast(err.message || "Erro ao excluir.");
        }
      });

      row.appendChild(info);
      row.appendChild(deleteBtn);
      list.appendChild(row);
    });
    container.appendChild(list);
  } catch (err) {
    // silently ignore
  }
}

async function openSendModal() {
  let students = [];
  try {
    students = await apiFetch("/admin/students");
    students = students.filter((s) => s.is_approved);
  } catch (err) {
    showToast("Erro ao carregar alunos.");
    return;
  }
  if (students.length === 0) {
    showToast("Nenhum aluno aprovado encontrado.");
    return;
  }

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });

  const modal = document.createElement("div");
  modal.className = "modal";

  const mHeader = document.createElement("div");
  mHeader.className = "modal-header";
  const mTitle = document.createElement("h2");
  mTitle.textContent = "Escolher aluno";
  mHeader.appendChild(mTitle);
  const closeBtn = document.createElement("button");
  closeBtn.className = "icon-btn";
  closeBtn.innerHTML = Icons.x;
  closeBtn.addEventListener("click", () => overlay.remove());
  mHeader.appendChild(closeBtn);
  modal.appendChild(mHeader);

  const p = document.createElement("p");
  p.style.cssText = "margin-bottom:16px;font-size:14px;color:#555;";
  p.textContent = `Enviar ${pendingExercises.length} exercício(s) para:`;
  modal.appendChild(p);

  const select = document.createElement("select");
  select.style.cssText = "width:100%;margin-bottom:16px;";
  students.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    select.appendChild(opt);
  });
  modal.appendChild(select);

  const errBox = document.createElement("p");
  errBox.style.cssText = "color:#861E19;font-size:13px;";
  errBox.hidden = true;
  modal.appendChild(errBox);

  const actions = document.createElement("div");
  actions.className = "modal-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn btn-outline";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", () => overlay.remove());
  const confirmBtn = document.createElement("button");
  confirmBtn.className = "btn btn-primary";
  confirmBtn.textContent = "Enviar";
  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Enviando...";
    try {
      await apiFetch("/exercises/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exercise_ids: pendingExercises.map((e) => e.id),
          student_id: parseInt(select.value),
        }),
      });
      pendingExercises = [];
      overlay.remove();
      showToast("Exercícios enviados!");
      renderExercicios();
    } catch (err) {
      errBox.textContent = err.message || "Erro ao enviar.";
      errBox.hidden = false;
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Enviar";
    }
  });
  actions.appendChild(cancelBtn);
  actions.appendChild(confirmBtn);
  modal.appendChild(actions);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Exercícios dos Alunos — status de revisão espaçada (professor)
// ---------------------------------------------------------------------------

async function loadStudentExerciseProgress(container) {
  container.innerHTML = '<div class="skeleton">Carregando alunos...</div>';

  let students = [];
  try {
    const all = await apiFetch("/admin/students");
    students = all.filter((s) => s.is_approved);
  } catch (err) {
    container.innerHTML = `<p style="color:#861E19;font-size:14px;">Erro ao carregar alunos: ${err.message}</p>`;
    return;
  }

  container.innerHTML = "";

  const wrap = document.createElement("div");

  const subtitle = document.createElement("p");
  subtitle.style.cssText = "font-size:13px;color:#666;margin-bottom:16px;";
  subtitle.textContent = "Veja quando cada exercício voltará a aparecer para o aluno, com base na revisão espaçada.";
  wrap.appendChild(subtitle);

  if (students.length === 0) {
    wrap.innerHTML += '<p style="color:#666;font-size:14px;">Nenhum aluno aprovado ainda.</p>';
    container.appendChild(wrap);
    return;
  }

  // Student picker
  const pickerRow = document.createElement("div");
  pickerRow.style.cssText = "display:flex;align-items:center;gap:12px;margin-bottom:20px;";
  const pickerLabel = document.createElement("label");
  pickerLabel.textContent = "Aluno:";
  pickerLabel.style.cssText = "font-weight:600;font-size:14px;white-space:nowrap;";
  const select = document.createElement("select");
  select.style.cssText = "min-width:200px;";
  students.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    select.appendChild(opt);
  });
  pickerRow.appendChild(pickerLabel);
  pickerRow.appendChild(select);
  wrap.appendChild(pickerRow);

  const progressBox = document.createElement("div");
  wrap.appendChild(progressBox);
  container.appendChild(wrap);

  select.addEventListener("change", () => renderExerciseProgressList(progressBox, select.value));
  renderExerciseProgressList(progressBox, select.value);
}

async function renderExerciseProgressList(container, studentId) {
  container.innerHTML = '<div class="skeleton">Carregando exercícios...</div>';

  let items = [];
  try {
    items = await apiFetch(`/exercises/student-progress/${studentId}`);
  } catch (err) {
    container.innerHTML = `<p style="color:#861E19;font-size:14px;">Erro: ${err.message}</p>`;
    return;
  }

  container.innerHTML = "";

  if (!items || items.length === 0) {
    container.innerHTML = '<p style="color:#666;font-size:14px;">Nenhum exercício atribuído a este aluno ainda.</p>';
    return;
  }

  const typeLabel = (t) => {
    if (t === "fill_blank") return "Fill the Blank";
    if (t === "word_choice") return "Listen & Type";
    if (t === "speaking") return "Speak It";
    return t;
  };

  const statusLabel = (item) => {
    if (!item.last_reviewed) return "Nunca respondido";
    if (item.is_due) return "Disponível agora";
    return `Disponível em ${formatDate(item.next_review)}`;
  };

  const streakLabel = (n) => {
    if (n === 0) return "0 acertos";
    return `${n} acerto${n === 1 ? "" : "s"} consecutivo${n === 1 ? "" : "s"}`;
  };

  const list = document.createElement("div");
  list.style.cssText = "display:flex;flex-direction:column;gap:10px;";

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.cssText = "padding:14px 18px;display:flex;flex-direction:column;gap:6px;";

    // Top row: title + type badge + status badge
    const topRow = document.createElement("div");
    topRow.style.cssText = "display:flex;align-items:center;gap:10px;flex-wrap:wrap;";

    const title = document.createElement("span");
    title.style.cssText = "font-weight:700;font-size:15px;color:#1a1a1a;flex:1;min-width:120px;";
    title.textContent = item.title || "(sem título)";

    const typeBadge = document.createElement("span");
    typeBadge.style.cssText = "font-size:11px;font-weight:600;color:var(--primary);border:1px solid var(--primary);border-radius:20px;padding:2px 10px;white-space:nowrap;";
    typeBadge.textContent = typeLabel(item.exercise_type);

    const statusBadge = document.createElement("span");
    const isDue = item.is_due;
    statusBadge.className = `badge ${isDue ? "badge-warning" : "badge-success"}`;
    statusBadge.textContent = statusLabel(item);

    topRow.appendChild(title);
    topRow.appendChild(typeBadge);
    topRow.appendChild(statusBadge);
    card.appendChild(topRow);

    // Prompt
    const prompt = document.createElement("div");
    prompt.style.cssText = "font-size:13px;color:#444;";
    prompt.textContent = item.prompt;
    card.appendChild(prompt);

    // Meta row
    const metaRow = document.createElement("div");
    metaRow.style.cssText = "display:flex;flex-wrap:wrap;gap:18px;font-size:12px;color:#666;margin-top:2px;";

    const addMeta = (label, value) => {
      const span = document.createElement("span");
      span.innerHTML = `<strong style="color:#444;">${label}:</strong> ${value}`;
      metaRow.appendChild(span);
    };

    addMeta("Acertos consecutivos", streakLabel(item.correct_streak));

    if (item.last_answer !== null && item.last_answer !== undefined) {
      addMeta("Última resposta", `"${item.last_answer}"`);
    } else {
      addMeta("Última resposta", "—");
    }

    if (item.last_reviewed) {
      addMeta("Última revisão", formatDate(item.last_reviewed));
    } else {
      addMeta("Última revisão", "—");
    }

    addMeta("Próxima aparição", item.next_review ? formatDate(item.next_review) : "Imediata");

    card.appendChild(metaRow);
    list.appendChild(card);
  });

  container.appendChild(list);
}

// ---------------------------------------------------------------------------
// Submissões — helpers
// ---------------------------------------------------------------------------

function submissionTypeLabel(type) {
  if (type === "fill_blank")  return "Fill the Blank";
  if (type === "word_choice") return "Listen & Speak";
  if (type === "speaking")    return "Speak It";
  return type;
}

function submissionTypeIcon(type) {
  // All icons rendered in the brand red (#861E19)
  const style = 'width:15px;height:15px;flex-shrink:0;stroke:#861E19;';
  if (type === "word_choice") {
    return Icons.headphones.replace('<svg ', `<svg style="${style}" `);
  }
  if (type === "speaking") {
    return Icons.mic.replace('<svg ', `<svg style="${style}" `);
  }
  // fill_blank (default)
  return Icons.edit.replace('<svg ', `<svg style="${style}" `);
}

function submissionStatusIcon(isCorrect) {
  if (isCorrect) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="#1a7c3e" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;flex-shrink:0;"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>`;
  }
  return `<svg viewBox="0 0 24 24" fill="none" stroke="#c0392b" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;flex-shrink:0;"><path d="M6 6l12 12M18 6 6 18"/></svg>`;
}

// ---------------------------------------------------------------------------
// Submissões — renderização principal
// ---------------------------------------------------------------------------

async function loadSubmissoes(container) {
  container.innerHTML = '<div class="skeleton">Carregando submissões...</div>';
  try {
    const days = await apiFetch("/exercises/submissions");
    container.innerHTML = "";

    if (!days || days.length === 0) {
      container.innerHTML = '<p style="color:#666;padding:20px;">Nenhuma submissão ainda.</p>';
      return;
    }

    const list = document.createElement("div");
    list.style.cssText = "display:flex;flex-direction:column;gap:14px;";

    days.forEach((day) => {
      const card = document.createElement("div");
      card.className = "card";
      card.style.cssText = "padding:18px 20px;";

      // ── Header ──────────────────────────────────────────────────────────
      const header = document.createElement("div");
      header.style.cssText = "display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:14px;";

      const headerLeft = document.createElement("div");
      headerLeft.style.cssText = "display:flex;flex-direction:column;gap:3px;";

      const studentName = document.createElement("span");
      studentName.style.cssText = "font-size:15px;font-weight:700;color:#1a1a1a;";
      studentName.textContent = day.student_name;

      const exerciseCount = document.createElement("span");
      exerciseCount.style.cssText = "font-size:12px;color:#666;";
      const unit = day.total === 1 ? "exercício enviado" : "exercícios enviados";
      exerciseCount.textContent = `${day.total} ${unit}`;

      headerLeft.appendChild(studentName);
      headerLeft.appendChild(exerciseCount);

      const dateLabel = document.createElement("span");
      dateLabel.style.cssText = "font-size:12px;color:#861E19;font-weight:600;white-space:nowrap;margin-top:2px;";
      // Format as dd/mm/yyyy
      const [y, m, d] = day.date.split("-");
      dateLabel.textContent = `${d}/${m}/${y}`;

      header.appendChild(headerLeft);
      header.appendChild(dateLabel);
      card.appendChild(header);

      // ── Divider ──────────────────────────────────────────────────────────
      const divider = document.createElement("div");
      divider.style.cssText = "height:1px;background:#f0f0f0;margin-bottom:12px;";
      card.appendChild(divider);

      // ── Exercise list ─────────────────────────────────────────────────────
      const itemsWrap = document.createElement("div");
      itemsWrap.style.cssText = "display:flex;flex-direction:column;gap:8px;";

      day.submissions.forEach((s) => {
        const item = document.createElement("div");
        item.style.cssText = "display:flex;align-items:center;gap:10px;padding:9px 12px;background:#fafafa;border-radius:8px;border:1px solid #f0f0f0;";

        // Exercise type icon (red)
        const typeIconWrap = document.createElement("span");
        typeIconWrap.style.cssText = "display:flex;align-items:center;flex-shrink:0;";
        typeIconWrap.innerHTML = submissionTypeIcon(s.exercise_type);
        item.appendChild(typeIconWrap);

        // Type label + prompt
        const textWrap = document.createElement("div");
        textWrap.style.cssText = "display:flex;flex-direction:column;gap:1px;flex:1;min-width:0;";

        const typeLabel = document.createElement("span");
        typeLabel.style.cssText = "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#861E19;line-height:1.2;";
        typeLabel.textContent = submissionTypeLabel(s.exercise_type);

        const promptText = document.createElement("span");
        promptText.style.cssText = "font-size:13px;color:#333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
        promptText.textContent = s.exercise_prompt || s.exercise_title;
        promptText.title = s.exercise_prompt || s.exercise_title;

        textWrap.appendChild(typeLabel);
        textWrap.appendChild(promptText);
        item.appendChild(textWrap);

        // Status badge
        const statusWrap = document.createElement("div");
        statusWrap.style.cssText = "display:flex;align-items:center;gap:5px;flex-shrink:0;";

        const statusIcon = document.createElement("span");
        statusIcon.style.cssText = "display:flex;align-items:center;";
        statusIcon.innerHTML = submissionStatusIcon(s.is_correct);

        const statusText = document.createElement("span");
        statusText.style.cssText = `font-size:12px;font-weight:700;${s.is_correct ? "color:#1a7c3e;" : "color:#c0392b;"}`;
        statusText.textContent = s.is_correct ? "Acertou" : "Errou";

        statusWrap.appendChild(statusIcon);
        statusWrap.appendChild(statusText);
        item.appendChild(statusWrap);

        itemsWrap.appendChild(item);
      });

      card.appendChild(itemsWrap);

      // ── OK button ────────────────────────────────────────────────────────
      const okRow = document.createElement("div");
      okRow.style.cssText = "display:flex;justify-content:flex-end;margin-top:14px;";
      const okBtn = document.createElement("button");
      okBtn.className = "btn btn-outline btn-sm";
      okBtn.style.cssText = "font-size:12px;padding:5px 18px;color:#1a7c3e;border-color:#1a7c3e;";
      okBtn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg><span style="margin-left:5px;">OK — Visualizado</span>`;
      okBtn.title = "Marcar como visualizado e remover da lista";
      okBtn.addEventListener("click", () => {
        card.style.transition = "opacity 0.25s";
        card.style.opacity = "0";
        setTimeout(() => card.remove(), 260);
      });
      okRow.appendChild(okBtn);
      card.appendChild(okRow);

      list.appendChild(card);
    });

    container.appendChild(list);
  } catch (err) {
    container.innerHTML = `<p style="color:#861E19;">Erro: ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------------
// QA
// ---------------------------------------------------------------------------

let qaCurrentQuestion = null; // { question_id, question }
let qaStudents = [];

async function renderQA() {
  contentArea.innerHTML = "";
  contentArea.classList.add("qa-page");

  const header = renderSectionHeader({
    title: "QA",
    subtitle: "Gere uma pergunta aleatória, responda em inglês e salve no vocabulário."
  });
  contentArea.appendChild(header);

  // Load approved students
  try {
    const all = await apiFetch("/admin/students");
    qaStudents = all.filter((s) => s.is_approved);
  } catch { qaStudents = []; }

  // ---- Question card ----
  const qCard = document.createElement("div");
  qCard.className = "card qa-card";
  qCard.style.padding = "32px";
  contentArea.appendChild(qCard);

  // ---- "Mostrar banco de perguntas" toggle ----
  const bankToggleWrap = document.createElement("div");
  bankToggleWrap.className = "qa-bank-toggle";
  const bankToggleBtn = document.createElement("button");
  bankToggleBtn.className = "btn btn-primary";
  bankToggleBtn.textContent = "Mostrar banco de perguntas";
  bankToggleWrap.appendChild(bankToggleBtn);
  contentArea.appendChild(bankToggleWrap);

  // ---- Banco de perguntas (escondido até o professor clicar no botão) ----
  const bankSection = document.createElement("div");
  bankSection.className = "qa-bank";
  bankSection.hidden = true;
  contentArea.appendChild(bankSection);

  let bankLoaded = false;
  bankToggleBtn.addEventListener("click", () => {
    bankSection.hidden = !bankSection.hidden;
    bankToggleBtn.textContent = bankSection.hidden
      ? "Mostrar banco de perguntas"
      : "Ocultar banco de perguntas";
    if (!bankSection.hidden && !bankLoaded) {
      bankLoaded = true;
      renderQuestionBank(bankSection);
    }
  });

  // Load first question
  loadNextQuestion(qCard);

  function buildQuestionUI(q) {
    qCard.innerHTML = "";

    const qLabel = document.createElement("div");
    qLabel.className = "qa-label";
    qLabel.textContent = "PERGUNTA";
    qCard.appendChild(qLabel);

    const qText = document.createElement("h2");
    qText.className = "qa-question";
    qText.textContent = q.question;
    qCard.appendChild(qText);

    // Buttons row
    const btnRow = document.createElement("div");
    btnRow.className = "qa-btn-row";

    const newBtn = document.createElement("button");
    newBtn.className = "btn btn-outline btn-sm";
    newBtn.style.cssText = "border-color:#861E19;color:#861E19;";
    newBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10"/><path d="M18 8V2h-6"/></svg><span>Gerar nova</span>`;
    newBtn.addEventListener("click", () => loadRandomQuestion(qCard));

    const swapBtn = document.createElement("button");
    swapBtn.className = "btn btn-outline btn-sm";
    swapBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M21 4v4h-4"/><path d="M3 20v-4h4"/></svg><span>Trocar pergunta</span>`;
    swapBtn.addEventListener("click", () => swapQuestion(qCard, q.question_id));

    btnRow.appendChild(newBtn);
    btnRow.appendChild(swapBtn);
    qCard.appendChild(btnRow);

    // ---- Translation first ----
    const transDiv = document.createElement("div");
    transDiv.className = "qa-field";
    transDiv.innerHTML = '<label>Tradução / contexto (português) — opcional</label>';
    const transInput = document.createElement("input");
    transInput.type = "text";
    transInput.placeholder = "Se vazio, usaremos a pergunta como contexto";
    transDiv.appendChild(transInput);
    qCard.appendChild(transDiv);

    // ---- Answer ----
    const ansDiv = document.createElement("div");
    ansDiv.className = "qa-field";
    ansDiv.innerHTML = '<label>Resposta do aluno (inglês)</label>';
    const ansInput = document.createElement("input");
    ansInput.type = "text";
    ansInput.placeholder = "Digite o que o aluno respondeu";
    ansDiv.appendChild(ansInput);
    qCard.appendChild(ansDiv);

    const saveErr = document.createElement("p");
    saveErr.style.cssText = "color:#861E19;font-size:13px;margin-bottom:8px;";
    saveErr.hidden = true;
    qCard.appendChild(saveErr);

    const saveBtn = document.createElement("button");
    saveBtn.className = "btn btn-primary btn-block";
    saveBtn.style.justifyContent = "center";
    saveBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg><span>Salvar no vocabulário e gerar próxima</span>`;
    saveBtn.addEventListener("click", async () => {
      saveErr.hidden = true;
      const answer = ansInput.value.trim();
      if (!answer) { saveErr.textContent = "Digite a resposta do aluno."; saveErr.hidden = false; return; }

      saveBtn.disabled = true;
      saveBtn.innerHTML = `<span>Salvando...</span>`;

      try {
        await apiFetch("/qa/answers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_id: null,
            question_id: q.question_id,
            question_text: q.question,
            student_answer: answer,
            translation: transInput.value.trim() || null,
          }),
        });
        showToast("Salvo no vocabulário!");
        loadNextQuestion(qCard);
      } catch (err) {
        saveErr.textContent = err.message || "Erro ao salvar.";
        saveErr.hidden = false;
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg><span>Salvar no vocabulário e gerar próxima</span>`;
      }
    });
    qCard.appendChild(saveBtn);
  }

  async function loadRandomQuestion(card) {
    card.innerHTML = '<div class="skeleton">Carregando pergunta...</div>';
    try {
      const q = await apiFetch("/qa/questions/random");
      qaCurrentQuestion = q;
      buildQuestionUI(q);
    } catch (err) {
      card.innerHTML = `<p style="color:#666;font-size:14px;">Nenhuma pergunta cadastrada ainda. Clique em <strong>Mostrar banco de perguntas</strong> para cadastrar.</p>`;
    }
  }

  // Primeira pergunta exibida: a próxima da fila (não totalmente aleatória).
  async function loadNextQuestion(card) {
    return loadRandomQuestion(card);
  }

  // "Trocar pergunta": manda a pergunta atual pro final da fila e mostra a próxima.
  async function swapQuestion(card, currentQuestionId) {
    card.innerHTML = '<div class="skeleton">Carregando pergunta...</div>';
    try {
      const q = await apiFetch(`/qa/questions/${currentQuestionId}/swap`, { method: "POST" });
      qaCurrentQuestion = q;
      buildQuestionUI(q);
    } catch (err) {
      showToast(err.message || "Erro ao trocar a pergunta.");
      buildQuestionUI(qaCurrentQuestion);
    }
  }
}

// ---------------------------------------------------------------------------
// QA — Banco de perguntas (lista + cadastro em lote)
// ---------------------------------------------------------------------------

async function renderQuestionBank(container) {
  container.innerHTML = '<div class="skeleton">Carregando banco de perguntas...</div>';

  const wrap = document.createElement("div");
  wrap.className = "card";
  wrap.style.padding = "24px";

  const title = document.createElement("h3");
  title.textContent = "Banco de perguntas";
  title.style.marginBottom = "4px";
  wrap.appendChild(title);

  const hint = document.createElement("p");
  hint.style.cssText = "font-size:13px;color:#666;margin-bottom:16px;";
  hint.textContent = "Gerencie suas perguntas personalizadas.";
  wrap.appendChild(hint);

  const list = document.createElement("div");
  list.className = "list";
  wrap.appendChild(list);

  async function reload() {
    list.innerHTML = '<div class="skeleton">Carregando...</div>';
    let questions = [];
    try {
      questions = await apiFetch("/qa/questions");
    } catch (err) {
      list.innerHTML = `<p style="color:#666;font-size:14px;">Não foi possível carregar as perguntas.</p>`;
      return;
    }

    if (questions.length === 0) {
      list.innerHTML = `<p style="color:#666;font-size:14px;">Nenhuma pergunta cadastrada ainda.</p>`;
      return;
    }

    list.innerHTML = "";
    questions.forEach((question) => {
      const row = document.createElement("div");
      row.className = "list-row";

      const info = document.createElement("div");
      info.className = "info";
      const primary = document.createElement("p");
      primary.className = "primary";
      primary.textContent = question.question;
      info.appendChild(primary);
      row.appendChild(info);

      const actions = document.createElement("div");
      actions.className = "row-actions";
      const delBtn = document.createElement("button");
      delBtn.className = "icon-btn danger";
      delBtn.innerHTML = Icons.trash;
      delBtn.title = "Excluir pergunta";
      delBtn.addEventListener("click", async () => {
        if (!window.confirm("Excluir esta pergunta do banco?")) return;
        try {
          await apiFetch(`/qa/questions/${question.id}`, { method: "DELETE" });
          showToast("Pergunta excluída.");
          reload();
        } catch (err) {
          showToast(err.message || "Erro ao excluir.");
        }
      });
      actions.appendChild(delBtn);
      row.appendChild(actions);

      list.appendChild(row);
    });
  }

  // ---- Cadastrar novas perguntas ----
  const addTitle = document.createElement("h3");
  addTitle.textContent = "Cadastrar perguntas";
  addTitle.style.cssText = "margin-top:24px;margin-bottom:10px;";
  wrap.appendChild(addTitle);

  const addHint = document.createElement("p");
  addHint.style.cssText = "font-size:13px;color:#666;margin-bottom:10px;";
  addHint.textContent = "Cole abaixo um texto com as perguntas — uma por linha.";
  wrap.appendChild(addHint);

  const importTA = document.createElement("textarea");
  importTA.rows = 5;
  importTA.style.cssText = "width:100%;margin-bottom:10px;";
  importTA.placeholder = "What is your favorite hobby?\nWhat did you do last weekend?\n...";
  wrap.appendChild(importTA);

  const importErr = document.createElement("p");
  importErr.style.cssText = "color:#861E19;font-size:13px;";
  importErr.hidden = true;
  wrap.appendChild(importErr);

  const importBtn = document.createElement("button");
  importBtn.className = "btn btn-outline btn-sm";
  importBtn.textContent = "Cadastrar perguntas";
  importBtn.addEventListener("click", async () => {
    importErr.hidden = true;
    const text = importTA.value.trim();
    if (!text) { importErr.textContent = "Cole as perguntas acima."; importErr.hidden = false; return; }
    importBtn.disabled = true;
    importBtn.textContent = "Cadastrando...";
    try {
      await apiFetch("/qa/questions/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions_text: text }),
      });
      importTA.value = "";
      showToast("Perguntas cadastradas!");
      reload();
    } catch (err) {
      importErr.textContent = err.message || "Erro ao cadastrar.";
      importErr.hidden = false;
    } finally {
      importBtn.disabled = false;
      importBtn.textContent = "Cadastrar perguntas";
    }
  });
  wrap.appendChild(importBtn);

  container.innerHTML = "";
  container.appendChild(wrap);
  reload();
}
