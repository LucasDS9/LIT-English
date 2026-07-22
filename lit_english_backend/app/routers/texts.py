"""
Rotas de Read and Listen:
- Professor: criar, listar, editar e excluir textos (com atribuição por aluno)
- Aluno (aprovado): listar apenas textos atribuídos a ele e ler
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.models import ReadingText, TextAssignment, User, UserRole
from app.schemas import (
    ReadingTextCreate,
    ReadingTextOut,
    ReadingTextUpdate,
    WordLookupOut,
    WordLookupRequest,
)
from app.vocab_lookup import VocabLookupUnavailable, lookup_word

router = APIRouter(prefix="/texts", tags=["Read and Listen"])

logger = logging.getLogger(__name__)


def _sync_assignments(db: Session, text: ReadingText, student_ids: list[int]):
    """Substitui as atribuições de um texto pelos student_ids informados."""
    db.query(TextAssignment).filter(TextAssignment.text_id == text.id).delete()
    for sid in set(student_ids):
        db.add(TextAssignment(text_id=text.id, student_id=sid))


# ============================================================
# PROFESSOR: CRUD de textos
# ============================================================

@router.post("", response_model=ReadingTextOut, status_code=status.HTTP_201_CREATED)
def create_text(
    data: ReadingTextCreate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    text = ReadingText(
        title=data.title,
        level=data.level,
        content=data.content,
        translation=data.translation,
    )
    db.add(text)
    db.commit()
    db.refresh(text)

    if data.student_ids:
        _sync_assignments(db, text, data.student_ids)
        db.commit()
        db.refresh(text)

    return text


@router.put("/{text_id}", response_model=ReadingTextOut)
def update_text(
    text_id: int,
    data: ReadingTextUpdate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    text = db.query(ReadingText).filter(ReadingText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="Texto não encontrado.")

    if data.title is not None:
        text.title = data.title
    if data.level is not None:
        text.level = data.level
    if data.content is not None:
        text.content = data.content
    if data.translation is not None:
        text.translation = data.translation

    if data.student_ids is not None:
        _sync_assignments(db, text, data.student_ids)

    db.commit()
    db.refresh(text)
    return text


@router.delete("/{text_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_text(
    text_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    text = db.query(ReadingText).filter(ReadingText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="Texto não encontrado.")
    db.delete(text)
    db.commit()
    return None


# ============================================================
# PROFESSOR E ALUNO (aprovado): listar e ler textos
# ============================================================

@router.get("", response_model=list[ReadingTextOut])
def list_texts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """
    Professor: vê todos os textos.
    Aluno: vê apenas os textos atribuídos a ele.
    """
    if current_user.role == UserRole.professor:
        return db.query(ReadingText).order_by(ReadingText.created_at.desc()).all()

    assigned_ids = (
        db.query(TextAssignment.text_id)
        .filter(TextAssignment.student_id == current_user.id)
        .subquery()
    )
    return (
        db.query(ReadingText)
        .filter(ReadingText.id.in_(assigned_ids))
        .order_by(ReadingText.created_at.desc())
        .all()
    )


@router.get("/{text_id}", response_model=ReadingTextOut)
def get_text(
    text_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    text = db.query(ReadingText).filter(ReadingText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="Texto não encontrado.")

    # Aluno só pode ler textos atribuídos a ele
    if current_user.role == UserRole.aluno:
        assigned = db.query(TextAssignment).filter(
            TextAssignment.text_id == text_id,
            TextAssignment.student_id == current_user.id,
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="Texto não disponível para você.")

    return text


# ============================================================
# DICIONÁRIO CONTEXTUAL: clique em palavra dentro do texto
# ============================================================

@router.post("/word-lookup", response_model=WordLookupOut)
def word_lookup(
    data: WordLookupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """
    Aluno clicou numa palavra do texto: devolve a tradução contextual da
    palavra, mais uma frase de exemplo em inglês (nova, gerada pela IA) e sua
    tradução. Alimenta o popup de vocabulário e, futuramente, o botão
    "Salvar frase nos flashcards".

    Se `text_id` for informado e quem está chamando for aluno, confere que
    ele tem acesso ao texto (mesma regra de `get_text`), pra não permitir
    usar o endpoint como tradutor genérico sem vínculo com um texto
    atribuído.
    """
    if data.text_id is not None and current_user.role == UserRole.aluno:
        assigned = (
            db.query(TextAssignment)
            .filter(
                TextAssignment.text_id == data.text_id,
                TextAssignment.student_id == current_user.id,
            )
            .first()
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="Texto não disponível para você.")

    word = data.word.strip()
    if not word:
        raise HTTPException(status_code=422, detail="Palavra vazia.")

    try:
        result = lookup_word(word, data.sentence)
    except VocabLookupUnavailable as e:
        logger.warning("Lookup de vocabulário indisponível: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Não foi possível consultar a palavra agora. Tente novamente em alguns segundos.",
        )

    return result
