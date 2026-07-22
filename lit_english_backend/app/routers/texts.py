"""
Rotas de Read and Listen:
- Professor: criar, listar, editar e excluir textos (com atribuição por aluno)
- Aluno (aprovado): listar apenas textos atribuídos a ele e ler
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.models import ReadingText, TextAssignment, User, UserRole
from app.schemas import ReadingTextCreate, ReadingTextOut, ReadingTextUpdate

router = APIRouter(prefix="/texts", tags=["Read and Listen"])


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
