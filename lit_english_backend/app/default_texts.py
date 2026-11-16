"""
Textos padrão do Read and Listen (nível A2), um por língua-alvo.

Aparecem automaticamente para TODAS as contas de alunos (inclusive as criadas
depois), sem precisar de atribuição do professor: o aluno vê o texto da sua
própria língua-alvo. São criados no startup (ensure_default_texts) apenas se
ainda não existirem — editar o texto pelo painel do professor é preservado.

A tradução é sempre em português (língua nativa dos alunos).
"""
import logging

from sqlalchemy.orm import Session

from app.models import ReadingLevel, ReadingText

logger = logging.getLogger(__name__)

_PT_EN = """Na LIT English, aprender vai além da gramática. Nossas aulas foram criadas para ajudar você a se comunicar naturalmente por meio da fala, da escuta, da escrita e da prática na vida real.

Com exercícios interativos, aulas personalizadas e uma plataforma de aprendizado exclusiva, você pode evoluir no seu ritmo enquanto ganha confiança a cada aula.

Se você aprende inglês para o trabalho, para viajar, para a escola ou para o crescimento pessoal, a LIT English oferece as ferramentas e o apoio para você alcançar seus objetivos.

Pratique todos os dias. Melhore a cada aula. Fale com confiança."""

_PT_OTHER = """Na LIT, aprender vai além da gramática. Nossas aulas foram criadas para ajudar você a se comunicar naturalmente por meio da fala, da escuta, da escrita e da prática na vida real.

Com exercícios interativos, aulas personalizadas e uma plataforma de aprendizado exclusiva, você pode evoluir no seu ritmo enquanto ganha confiança a cada aula.

Se você aprende {lang} para o trabalho, para viajar, para a escola ou para o crescimento pessoal, a LIT oferece as ferramentas e o apoio para você alcançar seus objetivos.

Pratique todos os dias. Melhore a cada aula. Fale com confiança."""

DEFAULT_TEXTS = {
    "ingles": {
        "title": "Learn English with Confidence",
        "content": """At LIT English, learning goes beyond grammar. Our lessons are designed to help you communicate naturally through speaking, listening, writing, and real-life practice.

With interactive exercises, personalized classes, and an exclusive learning platform, you can improve at your own pace while building confidence in every lesson.

Whether you are learning English for work, travel, school, or personal growth, LIT English gives you the tools and support to reach your goals.

Practice every day. Improve every lesson. Speak with confidence.""",
        "translation": _PT_EN,
    },
    "italiano": {
        "title": "Impara l'italiano con sicurezza",
        "content": """Da LIT, imparare va oltre la grammatica. Le nostre lezioni sono pensate per aiutarti a comunicare in modo naturale attraverso il parlato, l'ascolto, la scrittura e la pratica nella vita reale.

Con esercizi interattivi, lezioni personalizzate e una piattaforma esclusiva, puoi migliorare al tuo ritmo e costruire sicurezza in ogni lezione.

Che tu studi l'italiano per lavoro, per viaggiare, per la scuola o per crescita personale, LIT ti offre gli strumenti e il supporto per raggiungere i tuoi obiettivi.

Pratica ogni giorno. Migliora a ogni lezione. Parla con sicurezza.""",
        "translation": _PT_OTHER.format(lang="italiano"),
    },
    "frances": {
        "title": "Apprenez le français avec confiance",
        "content": """Chez LIT, apprendre va au-delà de la grammaire. Nos cours sont conçus pour vous aider à communiquer naturellement grâce à la parole, à l'écoute, à l'écriture et à la pratique de la vie réelle.

Avec des exercices interactifs, des cours personnalisés et une plateforme exclusive, vous pouvez progresser à votre rythme tout en prenant confiance à chaque leçon.

Que vous appreniez le français pour le travail, les voyages, les études ou votre développement personnel, LIT vous donne les outils et le soutien pour atteindre vos objectifs.

Pratiquez chaque jour. Progressez à chaque leçon. Parlez avec confiance.""",
        "translation": _PT_OTHER.format(lang="francês"),
    },
    "mandarim": {
        "title": "自信地学习中文",
        "content": """在 LIT，学习不只是语法。我们的课程帮助你通过说、听、写和真实生活中的练习，自然地交流。

通过互动练习、个性化课程和专属学习平台，你可以按照自己的节奏进步，并在每节课中建立自信。

无论你学习中文是为了工作、旅行、学习还是个人成长，LIT 都为你提供工具和支持，帮助你实现目标。

每天练习，每节课都进步，自信地开口说。""",
        "translation": _PT_OTHER.format(lang="chinês"),
    },
}


def ensure_default_texts(db: Session) -> None:
    """Cria os textos padrão que ainda não existem (idempotente)."""
    existing = {
        lang
        for (lang,) in db.query(ReadingText.language).filter(ReadingText.is_default.is_(True)).all()
    }
    created = 0
    for language, data in DEFAULT_TEXTS.items():
        if language in existing:
            continue
        db.add(
            ReadingText(
                title=data["title"],
                level=ReadingLevel.A2,
                content=data["content"],
                translation=data["translation"],
                language=language,
                is_default=True,
            )
        )
        created += 1
    if created:
        db.commit()
        logger.info("Textos padrão criados: %d", created)
