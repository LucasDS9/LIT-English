"""
Catálogo automático inicial do Aprender.

A lista é pequena de propósito: serve como núcleo inicial de palavras importantes.
A distribuição por língua é sempre 50% nouns, 30% verbs e 20% expressions.
Novas listas podem substituir este catálogo futuramente sem alterar o mecanismo.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SeedWord:
    word: str
    part_of_speech: str
    translation: str
    example_sentence: str
    distractors: tuple[str, str, str]
    level: str


AUTO_VOCAB = {
    "ingles": [
        SeedWord("money", "noun", "dinheiro", "I need some money.", ("comida", "trabalho", "problema"), "A1"),
        SeedWord("food", "noun", "comida", "The food is good.", ("dinheiro", "amigo", "trabalho"), "A1"),
        SeedWord("friend", "noun", "amigo", "My friend lives here.", ("problema", "comida", "dinheiro"), "A1"),
        SeedWord("work", "noun", "trabalho", "I have a lot of work today.", ("comida", "amigo", "problema"), "A1"),
        SeedWord("problem", "noun", "problema", "We have a small problem.", ("trabalho", "dinheiro", "amigo"), "A2"),
        SeedWord("want", "verb", "querer", "I want some water.", ("precisar", "gostar", "saber"), "A1"),
        SeedWord("need", "verb", "precisar", "I need more time.", ("querer", "gostar", "ter"), "A1"),
        SeedWord("like", "verb", "gostar", "I like this song.", ("querer", "precisar", "saber"), "A1"),
        SeedWord("of course", "expression", "claro", "Of course, I can help you.", ("talvez", "desculpa", "obrigado"), "A1"),
        SeedWord("I don't know", "expression", "eu não sei", "I don't know the answer.", ("eu entendo", "até logo", "com licença"), "A1"),
    ],
    "italiano": [
        SeedWord("soldi", "noun", "dinheiro", "Ho bisogno di soldi.", ("comida", "trabalho", "problema"), "A1"),
        SeedWord("cibo", "noun", "comida", "Il cibo è buono.", ("dinheiro", "amigo", "trabalho"), "A1"),
        SeedWord("amico", "noun", "amigo", "Il mio amico vive qui.", ("problema", "comida", "dinheiro"), "A1"),
        SeedWord("lavoro", "noun", "trabalho", "Ho molto lavoro oggi.", ("comida", "amigo", "problema"), "A1"),
        SeedWord("problema", "noun", "problema", "Abbiamo un piccolo problema.", ("trabalho", "dinheiro", "amigo"), "A2"),
        SeedWord("volere", "verb", "querer", "Voglio un po' d'acqua.", ("precisar", "gostar", "saber"), "A1"),
        SeedWord("avere bisogno", "verb", "precisar", "Ho bisogno di più tempo.", ("querer", "gostar", "ter"), "A1"),
        SeedWord("piacere", "verb", "gostar", "Mi piace questa canzone.", ("querer", "precisar", "saber"), "A1"),
        SeedWord("certo", "expression", "claro", "Certo, posso aiutarti.", ("talvez", "desculpa", "obrigado"), "A1"),
        SeedWord("non lo so", "expression", "eu não sei", "Non lo so.", ("eu entendo", "até logo", "com licença"), "A1"),
    ],
    "frances": [
        SeedWord("argent", "noun", "dinheiro", "J'ai besoin d'argent.", ("comida", "trabalho", "problema"), "A1"),
        SeedWord("nourriture", "noun", "comida", "La nourriture est bonne.", ("dinheiro", "amigo", "trabalho"), "A1"),
        SeedWord("ami", "noun", "amigo", "Mon ami habite ici.", ("problema", "comida", "dinheiro"), "A1"),
        SeedWord("travail", "noun", "trabalho", "J'ai beaucoup de travail aujourd'hui.", ("comida", "amigo", "problema"), "A1"),
        SeedWord("problème", "noun", "problema", "Nous avons un petit problème.", ("trabalho", "dinheiro", "amigo"), "A2"),
        SeedWord("vouloir", "verb", "querer", "Je veux de l'eau.", ("precisar", "gostar", "saber"), "A1"),
        SeedWord("avoir besoin", "verb", "precisar", "J'ai besoin de plus de temps.", ("querer", "gostar", "ter"), "A1"),
        SeedWord("aimer", "verb", "gostar", "J'aime cette chanson.", ("querer", "precisar", "saber"), "A1"),
        SeedWord("bien sûr", "expression", "claro", "Bien sûr, je peux vous aider.", ("talvez", "desculpa", "obrigado"), "A1"),
        SeedWord("je ne sais pas", "expression", "eu não sei", "Je ne sais pas.", ("eu entendo", "até logo", "com licença"), "A1"),
    ],
}
