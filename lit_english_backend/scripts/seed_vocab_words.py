"""
Script de seed: cria OU ATUALIZA as palavras da tela "Aprender" via API
(upsert). Como o campo `student_ids` é OPCIONAL (ver
VocabWordCreate/create_vocab_word), não enviamos ele aqui de propósito — a
API atribui a palavra automaticamente a TODOS os alunos aprovados no
momento **que tenham a mesma língua-alvo** (campo `language`, abaixo —
'ingles' aqui), e o backend garante que qualquer aluno aprovado
depois (em admin.approve_student) dessa mesma língua também receba as
mesmas palavras. Ou seja: rodar este script envia o lote inteiro pra TODOS
os alunos do curso normal de inglês agora, de uma vez, sem precisar selecionar aluno
por aluno.

COMPORTAMENTO DE UPSERT (criar, atualizar ou deixar como está):
Antes de enviar cada item de WORDS, o script busca em GET /vocab-words se
já existe uma palavra com o mesmo texto (`word`, sem diferenciar
maiúscula/minúscula), a mesma LANGUAGE e a mesma `translation` (algumas
palavras se repetem com sentidos diferentes — ex.: "Ciao" em italiano
significa tanto "Oi" quanto "Tchau" — por isso a tradução também entra na
chave, senão uma sobrescreveria a outra). A partir daí:
- Não existe ainda            -> cria via POST /vocab-words ("Criado").
- Existe e está diferente     -> atualiza via PUT /vocab-words/{id}
                                  ("Atualizado").
- Existe e já está idêntica   -> não faz nenhuma chamada de escrita
                                  ("Inalterado").
Ou seja: o fluxo do dia a dia é editar a lista WORDS abaixo (mudar uma
tradução, corrigir uma explicação, adicionar uma palavra nova no final) e
rodar o script de novo — nunca duplica nada, e só grava no banco o que de
fato mudou. No final, o script imprime um resumo com a contagem de cada
caso.

Cada item tem:
- word/translation/distractors: a palavra ou expressão (Parte 1, nível A1),
  a tradução certa e as 3 opções erradas — sempre 4 alternativas na tela.
- tip: a pergunta/contexto mostrado ANTES de responder (não entrega a
  resposta).
- explanation: mostrada no VERSO do card, junto com a resposta certa, só
  DEPOIS que o aluno responde (nunca antes) — é o "vira o flashcard".

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_vocab_words.py

Este arquivo contém as palavras/expressões da Parte 1 (Saudações e
sobrevivência linguística) e da Parte 2 (Chunks e verbos essenciais),
nível A1, em INGLÊS.

A Parte 2 segue a regra central da parte: os verbos não são ensinados
isoladamente (verbo = tradução). A progressão é chunk -> chunk + palavra
conhecida -> chunk + noun novo -> mini-frase -> variação, com chunks como
I need..., I want..., I'd like..., I have..., We have..., I like...,
I don't like..., I need to..., I want to..., I have to...,
I'm looking for... e I'm going to..., cada um reaproveitado com nouns
diferentes.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Língua-alvo deste lote de palavras. Alunos do curso normal são sempre
# "ingles"; alunos de Acesso Especial usam o target_language do cadastro
# (ex.: "italiano").
LANGUAGE = 'ingles'

# ---------------------------------------------------------------------------
# Parte 1 (A1) — 200 palavras/expressões, extraídas do baralho de
# flashcards em INGLÊS. `tip` é a pergunta/contexto mostrado
# ANTES de responder; `explanation` só aparece DEPOIS, no verso do card,
# junto com a resposta certa.
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": 'Hello',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Hello'?",
        "translation": 'Olá',
        "distractors": ['Por favor', 'Tchau', 'Obrigado'],
        "explanation": "'Hello' é a saudação mais comum em inglês.",
    },
    {
        "word": 'Hi',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Hi'?",
        "translation": 'Oi',
        "distractors": ['Sim', 'Não', 'Adeus'],
        "explanation": "'Hi' é uma forma informal e comum de cumprimentar.",
    },
    {
        "word": 'Good morning',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Good morning'?",
        "translation": 'Bom dia',
        "distractors": ['Boa noite', 'Boa tarde', 'Até logo'],
        "explanation": 'Usado para cumprimentar até por volta do meio-dia.',
    },
    {
        "word": 'Good afternoon',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Good afternoon'?",
        "translation": 'Boa tarde',
        "distractors": ['Bom dia', 'Boa sorte', 'Boa noite'],
        "explanation": 'Usado à tarde, após o meio-dia.',
    },
    {
        "word": 'Good evening',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Good evening'?",
        "translation": 'Boa noite (ao chegar)',
        "distractors": ['Bom dia', 'Boa noite (ao dormir)', 'Boa tarde'],
        "explanation": 'Usado ao encontrar alguém à noite, não ao se despedir.',
    },
    {
        "word": 'Good night',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Good night'?",
        "translation": 'Boa noite (ao dormir)',
        "distractors": ['Boa tarde', 'Boa noite (ao chegar)', 'Bom dia'],
        "explanation": 'Usado ao se despedir à noite, geralmente antes de dormir.',
    },
    {
        "word": 'Hey',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'Hey'?",
        "translation": 'Ei',
        "distractors": ['Tchau', 'Sim', 'Desculpa'],
        "explanation": 'Cumprimento bem informal, comum entre amigos.',
    },
    {
        "word": 'How are you?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'How are you?'",
        "translation": 'Como você está?',
        "distractors": ['O que você quer?', 'Onde você está?', 'Quem é você?'],
        "explanation": 'Pergunta comum logo após cumprimentar alguém.',
    },
    {
        "word": "I'm fine, thanks",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm fine, thanks'?",
        "translation": 'Estou bem, obrigado(a)',
        "distractors": ['Eu não sei', 'Estou cansado', 'Não estou bem'],
        "explanation": "Resposta comum e educada para 'How are you?'.",
    },
    {
        "word": 'Nice to meet you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Nice to meet you'?",
        "translation": 'Prazer em te conhecer',
        "distractors": ['Com licença', 'Até mais', 'Muito obrigado'],
        "explanation": 'Usado ao conhecer alguém pela primeira vez.',
    },
    {
        "word": 'Welcome',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Welcome'?",
        "translation": 'Bem-vindo(a)',
        "distractors": ['Cuidado', 'Adeus', 'Desculpe'],
        "explanation": 'Usado para receber alguém em um lugar.',
    },
    {
        "word": 'Hello, how are you?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se cumprimenta alguém e pergunta como ele está?',
        "translation": 'Olá, como você está?',
        "distractors": ['Desculpe, estou atrasado(a)', 'Muito obrigado(a)', 'Ei'],
        "explanation": "Combina a saudação 'Hello' com a pergunta 'How are you?'.",
    },
    {
        "word": "What's up?",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What's up?'",
        "translation": 'E aí?',
        "distractors": ['Muito obrigado', 'Com certeza', 'Boa noite'],
        "explanation": 'Cumprimento informal muito comum entre jovens.',
    },
    {
        "word": 'Long time no see',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Long time no see'?",
        "translation": 'Quanto tempo!',
        "distractors": ['Nunca te vi', 'Vejo você amanhã', 'Eu não te conheço'],
        "explanation": 'Usado ao reencontrar alguém depois de muito tempo.',
    },
    {
        "word": 'Good morning, everyone',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Bom dia a todos' em inglês?",
        "translation": 'Bom dia a todos',
        "distractors": ['Desculpe, eu não concordo com isso', 'Isso é muito gentil da sua parte', 'Por favor'],
        "explanation": 'Saudação usada para um grupo de pessoas pela manhã.',
    },
    {
        "word": 'Goodbye',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Goodbye'?",
        "translation": 'Adeus',
        "distractors": ['Obrigado', 'Desculpa', 'Olá'],
        "explanation": 'Forma padrão de se despedir em inglês.',
    },
    {
        "word": 'Bye',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'Bye'?",
        "translation": 'Tchau',
        "distractors": ['Sim', 'Por favor', 'Oi'],
        "explanation": "Forma curta e informal de 'Goodbye'.",
    },
    {
        "word": 'See you later',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'See you later'?",
        "translation": 'Até mais tarde',
        "distractors": ['Bom dia', 'Nunca mais te vejo', 'Muito prazer'],
        "explanation": 'Usado ao se despedir esperando ver a pessoa novamente em breve.',
    },
    {
        "word": 'See you soon',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'See you soon'?",
        "translation": 'Até logo',
        "distractors": ['Com licença', 'Até nunca', 'Boa sorte'],
        "explanation": 'Despedida indicando que o reencontro será em breve.',
    },
    {
        "word": 'See you tomorrow',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'See you tomorrow'?",
        "translation": 'Até amanhã',
        "distractors": ['Bom dia', 'Boa noite', 'Até a próxima semana'],
        "explanation": 'Despedida usada quando o reencontro será no dia seguinte.',
    },
    {
        "word": 'Take care',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Take care'?",
        "translation": 'Se cuida',
        "distractors": ['Vem cá', 'Espera aí', 'Fica tranquilo'],
        "explanation": 'Despedida amigável, desejando bem-estar à pessoa.',
    },
    {
        "word": 'Have a good day',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Have a good day'?",
        "translation": 'Tenha um bom dia',
        "distractors": ['Boa sorte', 'Tenha uma boa noite', 'Bom apetite'],
        "explanation": 'Despedida educada usada durante o dia.',
    },
    {
        "word": 'Have a good night',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Have a good night'?",
        "translation": 'Tenha uma boa noite',
        "distractors": ['Até logo', 'Muito prazer', 'Tenha um bom dia'],
        "explanation": 'Despedida usada à noite, geralmente antes de dormir.',
    },
    {
        "word": 'Farewell',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Farewell'?",
        "translation": 'Adeus (formal)',
        "distractors": ['Obrigado', 'Com licença', 'Oi (informal)'],
        "explanation": 'Forma mais formal e literária de dizer adeus.',
    },
    {
        "word": 'Catch you later',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Catch you later'?",
        "translation": 'Te pego depois',
        "distractors": ['Bom dia para você', 'Nunca te vi antes', 'Com muito prazer'],
        "explanation": 'Despedida bem informal, comum entre amigos.',
    },
    {
        "word": 'See you later, bye!',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se despede informalmente dizendo que verá a pessoa depois?',
        "translation": 'Até mais tarde, tchau!',
        "distractors": ['Não se preocupe com isso', 'Muito obrigado, eu agradeço', 'Eu concordo com você, isso é verdade'],
        "explanation": 'Combina duas despedidas comuns em sequência.',
    },
    {
        "word": 'Take care, see you soon',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se despede desejando bem-estar e um reencontro próximo?',
        "translation": 'Se cuida, até logo',
        "distractors": ['Obrigado(a)', 'Foi bom falar com você', 'Desculpe, eu não concordo com isso'],
        "explanation": 'Une duas expressões de despedida amigáveis.',
    },
    {
        "word": 'Thank you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thank you'?",
        "translation": 'Obrigado(a)',
        "distractors": ['Desculpa', 'Por favor', 'De nada'],
        "explanation": 'Forma padrão de agradecer em inglês.',
    },
    {
        "word": 'Thanks',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'Thanks'?",
        "translation": 'Obrigado(a) (informal)',
        "distractors": ['Por favor', 'Com licença', 'Adeus'],
        "explanation": "Versão curta e informal de 'Thank you'.",
    },
    {
        "word": 'Thank you very much',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thank you very much'?",
        "translation": 'Muito obrigado(a)',
        "distractors": ['Por favor, não', 'Com certeza', 'Sinto muito'],
        "explanation": 'Forma mais enfática de agradecer.',
    },
    {
        "word": 'Thanks a lot',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thanks a lot'?",
        "translation": 'Muito obrigado(a) (informal)',
        "distractors": ['Boa sorte', 'Desculpe muito', 'Sem problema'],
        "explanation": 'Forma informal e enfática de agradecer.',
    },
    {
        "word": 'Thank you so much',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thank you so much'?",
        "translation": 'Muitíssimo obrigado(a)',
        "distractors": ['Com licença', 'De jeito nenhum', 'Não se preocupe'],
        "explanation": 'Agradecimento bastante caloroso e enfático.',
    },
    {
        "word": 'I appreciate it',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I appreciate it'?",
        "translation": 'Eu agradeço',
        "distractors": ['Eu sinto muito', 'Eu não sei', 'Eu não quero'],
        "explanation": 'Forma um pouco mais formal de expressar gratidão.',
    },
    {
        "word": 'Thanks for your help',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thanks for your help'?",
        "translation": 'Obrigado pela sua ajuda',
        "distractors": ['Obrigado pela comida', 'Desculpe pelo problema', 'Por favor, me ajude'],
        "explanation": 'Agradecimento específico por uma ajuda recebida.',
    },
    {
        "word": 'Thank you for coming',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Thank you for coming'?",
        "translation": 'Obrigado por vir',
        "distractors": ['Obrigado por esperar', 'Desculpe por chegar tarde', 'Por favor, entre'],
        "explanation": 'Agradecimento por alguém ter comparecido.',
    },
    {
        "word": 'Thank you so much for everything',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se agradece por tudo de forma calorosa?',
        "translation": 'Muito obrigado por tudo',
        "distractors": ['Mandou bem!', 'Tenha uma boa noite', 'Que horas são?'],
        "explanation": "Combina 'thank you so much' com 'for everything'.",
    },
    {
        "word": 'Thanks a lot, I appreciate it',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se agradece de forma informal e enfática ao mesmo tempo?',
        "translation": 'Muito obrigado, eu agradeço',
        "distractors": ['Eu discordo', 'Estou bem, obrigado(a)', 'Como você está?'],
        "explanation": 'Une duas expressões de agradecimento diferentes.',
    },
    {
        "word": "You're welcome",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'You're welcome'?",
        "translation": 'De nada',
        "distractors": ['Com licença', 'Muito obrigado', 'Sinto muito'],
        "explanation": 'Resposta padrão a um agradecimento.',
    },
    {
        "word": 'No problem',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'No problem'?",
        "translation": 'Sem problema',
        "distractors": ['De jeito nenhum', 'Há um problema', 'Não entendi'],
        "explanation": 'Resposta informal a um agradecimento.',
    },
    {
        "word": 'No worries',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'No worries'?",
        "translation": 'Não se preocupe',
        "distractors": ['Muito obrigado', 'Estou preocupado', 'Com certeza'],
        "explanation": 'Resposta informal e tranquila a um agradecimento.',
    },
    {
        "word": "Don't mention it",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Don't mention it'?",
        "translation": 'Não há de quê',
        "distractors": ['Fale mais alto', 'Não fale comigo', 'Diga de novo'],
        "explanation": 'Resposta educada indicando que não é necessário agradecer.',
    },
    {
        "word": "It's my pleasure",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's my pleasure'?",
        "translation": 'É um prazer (para mim)',
        "distractors": ['Sinto muito por isso', 'É um problema meu', 'Não é da minha conta'],
        "explanation": 'Resposta educada e calorosa a um agradecimento.',
    },
    {
        "word": 'Anytime',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Anytime'?",
        "translation": 'Quando quiser',
        "distractors": ['Nunca mais', 'Talvez', 'Às vezes'],
        "explanation": 'Resposta informal indicando disponibilidade futura.',
    },
    {
        "word": 'Sure, no problem',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sure, no problem'?",
        "translation": 'Claro, sem problema',
        "distractors": ['Talvez amanhã', 'Desculpe, não posso', 'Não, obrigado'],
        "explanation": 'Resposta afirmativa e tranquila a um pedido ou agradecimento.',
    },
    {
        "word": "You're welcome, no problem",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se responde a um agradecimento de forma dupla e informal?',
        "translation": 'De nada, sem problema',
        "distractors": ['Adeus (formal)', 'Está tudo bem', 'Nenhum mal foi feito'],
        "explanation": 'Combina duas respostas comuns a agradecimentos.',
    },
    {
        "word": 'Sorry',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sorry'?",
        "translation": 'Desculpa',
        "distractors": ['De nada', 'Obrigado', 'Por favor'],
        "explanation": 'Forma curta e comum de pedir desculpas.',
    },
    {
        "word": "I'm sorry",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm sorry'?",
        "translation": 'Eu sinto muito',
        "distractors": ['Eu não sei', 'Eu concordo', 'Eu estou feliz'],
        "explanation": 'Forma completa de pedir desculpas.',
    },
    {
        "word": 'Excuse me',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Excuse me'?",
        "translation": 'Com licença',
        "distractors": ['Vá embora', 'Muito obrigado', 'Boa sorte'],
        "explanation": 'Usado para pedir licença ou chamar atenção educadamente.',
    },
    {
        "word": 'I apologize',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I apologize'?",
        "translation": 'Eu peço desculpas (formal)',
        "distractors": ['Eu agradeço muito', 'Eu concordo totalmente', 'Eu não entendo nada'],
        "explanation": 'Forma mais formal de pedir desculpas.',
    },
    {
        "word": 'My mistake',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'My mistake'?",
        "translation": 'Foi meu erro',
        "distractors": ['Meu prazer', 'Boa ideia', 'Sua vez'],
        "explanation": 'Usado para admitir um erro cometido.',
    },
    {
        "word": "I'm so sorry",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm so sorry'?",
        "translation": 'Sinto muitíssimo',
        "distractors": ['Estou de acordo', 'Estou com pressa', 'Estou muito feliz'],
        "explanation": 'Forma enfática de pedir desculpas.',
    },
    {
        "word": 'Sorry to bother you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sorry to bother you'?",
        "translation": 'Desculpe incomodar',
        "distractors": ['Vamos comemorar', 'Obrigado por ajudar', 'Prazer em conhecer'],
        "explanation": 'Usado antes de interromper ou pedir algo a alguém.',
    },
    {
        "word": "I didn't mean it",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I didn't mean it'?",
        "translation": 'Eu não quis dizer isso',
        "distractors": ['Eu concordo com você', 'Eu não te conheço', 'Eu quis dizer isso mesmo'],
        "explanation": 'Usado para explicar que algo não foi proposital.',
    },
    {
        "word": "I'm sorry, excuse me",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede desculpa e licença ao mesmo tempo?',
        "translation": 'Desculpe, com licença',
        "distractors": ['Melhoras', 'Onde fica o banheiro?', 'Ei'],
        "explanation": 'Combina duas expressões usadas para pedir desculpas educadamente.',
    },
    {
        "word": 'Sorry, it was my mistake',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se admite um erro pedindo desculpas?',
        "translation": 'Desculpe, foi meu erro',
        "distractors": ['Meu nome é...', 'Sinto muitíssimo', 'Bom dia, como você está hoje?'],
        "explanation": "Combina 'sorry' com a admissão de erro 'my mistake'.",
    },
    {
        "word": "It's okay",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's okay'?",
        "translation": 'Está tudo bem',
        "distractors": ['Não está bem', 'Está errado', 'É impossível'],
        "explanation": 'Resposta comum aceitando um pedido de desculpas.',
    },
    {
        "word": "It's fine",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's fine'?",
        "translation": 'Está tudo bem',
        "distractors": ['Não é possível', 'Está péssimo', 'Está caro'],
        "explanation": 'Resposta tranquila a um pedido de desculpas.',
    },
    {
        "word": 'No worries at all',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'No worries at all'?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Há um grande problema', 'Não aceito desculpas', 'Estou muito bravo'],
        "explanation": 'Resposta tranquilizadora e enfática.',
    },
    {
        "word": "Don't worry about it",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Don't worry about it'?",
        "translation": 'Não se preocupe com isso',
        "distractors": ['Pense bastante nisso', 'Fale sobre isso agora', 'Preocupe-se muito com isso'],
        "explanation": 'Resposta usada para tranquilizar alguém após um erro.',
    },
    {
        "word": "That's alright",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's alright'?",
        "translation": 'Tudo bem',
        "distractors": ['Isso é impossível', 'Isso é caro', 'Isso está errado'],
        "explanation": 'Resposta aceitando desculpas de forma tranquila.',
    },
    {
        "word": 'No harm done',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'No harm done'?",
        "translation": 'Nenhum mal foi feito',
        "distractors": ['Foi um grande problema', 'Isso doeu muito', 'Muito mal foi feito'],
        "explanation": 'Resposta indicando que não houve consequência negativa.',
    },
    {
        "word": 'It happens',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It happens'?",
        "translation": 'Acontece',
        "distractors": ['É impossível', 'Nunca acontece', 'É sua culpa'],
        "explanation": 'Resposta tranquilizadora, indicando que erros são normais.',
    },
    {
        "word": "It's okay, don't worry",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se tranquiliza alguém que pediu desculpas?',
        "translation": 'Está tudo bem, não se preocupe',
        "distractors": ['Por favor, espere um momento', 'Agora mesmo', 'Mandou bem!'],
        "explanation": 'Combina duas expressões que aceitam desculpas e tranquilizam.',
    },
    {
        "word": 'Please',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'Please'?",
        "translation": 'Por favor',
        "distractors": ['Obrigado', 'De nada', 'Desculpa'],
        "explanation": 'Usado para fazer pedidos de forma educada.',
    },
    {
        "word": 'Could you, please?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Could you, please?'",
        "translation": 'Você poderia, por favor?',
        "distractors": ['Você sabe disso?', 'Você já fez isso?', 'Você gosta disso?'],
        "explanation": 'Forma educada de fazer um pedido.',
    },
    {
        "word": 'Would you like...?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Would you like...?'",
        "translation": 'Você gostaria de...?',
        "distractors": ['Você fez...?', 'Você sabe...?', 'Você já tem...?'],
        "explanation": 'Usado para oferecer algo educadamente.',
    },
    {
        "word": 'After you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'After you'?",
        "translation": 'Depois de você',
        "distractors": ['Junto comigo', 'Antes de mim', 'Longe de mim'],
        "explanation": 'Expressão educada usada para ceder a vez a alguém.',
    },
    {
        "word": 'May I?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'May I?'",
        "translation": 'Posso?',
        "distractors": ['Eu sei?', 'Eu devo?', 'Eu quero?'],
        "explanation": 'Usado para pedir permissão educadamente.',
    },
    {
        "word": 'Excuse me, please',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Excuse me, please'?",
        "translation": 'Com licença, por favor',
        "distractors": ['Prazer em conhecer', 'De nada, tranquilo', 'Muito obrigado mesmo'],
        "explanation": 'Combinação educada para pedir licença.',
    },
    {
        "word": "If you don't mind",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'If you don't mind'?",
        "translation": 'Se você não se importar',
        "distractors": ['Se você estiver ocupado', 'Se você quiser brigar', 'Se você não gostar'],
        "explanation": 'Usado para suavizar um pedido educadamente.',
    },
    {
        "word": 'Would you mind...?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Would you mind...?'",
        "translation": 'Você se importaria de...?',
        "distractors": ['Você já foi lá?', 'Você tem certeza?', 'Você gostaria de comer?'],
        "explanation": 'Forma educada de pedir algo a alguém.',
    },
    {
        "word": "That's very kind of you",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's very kind of you'?",
        "translation": 'Isso é muito gentil da sua parte',
        "distractors": ['Isso é muito estranho', 'Isso é muito difícil', 'Isso é muito caro'],
        "explanation": 'Elogio educado usado para agradecer um gesto gentil.',
    },
    {
        "word": 'With pleasure',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'With pleasure'?",
        "translation": 'Com prazer',
        "distractors": ['Com pressa', 'Com raiva', 'Com medo'],
        "explanation": 'Resposta educada indicando disposição em ajudar.',
    },
    {
        "word": 'Pardon me',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Pardon me'?",
        "translation": 'Perdão',
        "distractors": ['Fale mais baixo', 'Espere um pouco', 'Vá embora agora'],
        "explanation": 'Forma educada de pedir desculpas ou chamar atenção.',
    },
    {
        "word": 'Sorry to interrupt',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sorry to interrupt'?",
        "translation": 'Desculpe interromper',
        "distractors": ['Vamos continuar', 'Prazer em conhecer', 'Obrigado por esperar'],
        "explanation": 'Usado antes de interromper alguém educadamente.',
    },
    {
        "word": 'Could you help me, please?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede ajuda de forma educada?',
        "translation": 'Você poderia me ajudar, por favor?',
        "distractors": ['Eu concordo', 'Está tudo bem', 'Eu acho que não'],
        "explanation": "Combina 'could you' com 'please' para um pedido educado.",
    },
    {
        "word": 'Excuse me, may I ask something?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede licença para fazer uma pergunta?',
        "translation": 'Com licença, posso perguntar algo?',
        "distractors": ['O que você faz? (profissão)', 'Isso é muito gentil da sua parte', 'Oi'],
        "explanation": "Combina 'excuse me' com 'may I' para pedir permissão.",
    },
    {
        "word": 'Would you like some help?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se oferece ajuda educadamente?',
        "translation": 'Você gostaria de ajuda?',
        "distractors": ['Sim, por favor, muito obrigado', 'Não há de quê', 'Pode deixar'],
        "explanation": "Usa 'would you like' para oferecer algo de forma educada.",
    },
    {
        "word": 'Yes',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'Yes'?",
        "translation": 'Sim',
        "distractors": ['Nunca', 'Não', 'Talvez'],
        "explanation": 'Resposta afirmativa básica.',
    },
    {
        "word": 'No',
        "part_of_speech": 'palavra',
        "tip": "O que significa 'No'?",
        "translation": 'Não',
        "distractors": ['Sim', 'Sempre', 'Claro'],
        "explanation": 'Resposta negativa básica.',
    },
    {
        "word": 'Yes, please',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Yes, please'?",
        "translation": 'Sim, por favor',
        "distractors": ['Não, obrigado', 'Nunca mais', 'Talvez depois'],
        "explanation": 'Resposta afirmativa educada, comum ao aceitar algo.',
    },
    {
        "word": 'No, thanks',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'No, thanks'?",
        "translation": 'Não, obrigado',
        "distractors": ['Com certeza', 'Sim, por favor', 'Claro que sim'],
        "explanation": 'Resposta negativa educada, comum ao recusar algo.',
    },
    {
        "word": 'Sure',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sure'?",
        "translation": 'Claro',
        "distractors": ['De jeito nenhum', 'Nunca', 'Talvez não'],
        "explanation": 'Resposta afirmativa informal e comum.',
    },
    {
        "word": 'Of course',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Of course'?",
        "translation": 'Claro',
        "distractors": ['Talvez amanhã', 'Eu não sei', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa enfática.',
    },
    {
        "word": 'Not really',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Not really'?",
        "translation": 'Não muito',
        "distractors": ['Muito obrigado', 'Sempre é assim', 'Com certeza sim'],
        "explanation": 'Resposta que suaviza uma negação.',
    },
    {
        "word": 'I think so',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I think so'?",
        "translation": 'Eu acho que sim',
        "distractors": ['Eu não me importo', 'Eu nunca soube disso', 'Eu tenho certeza que não'],
        "explanation": 'Resposta afirmativa com certo grau de incerteza.',
    },
    {
        "word": "I don't think so",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I don't think so'?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu adoro isso', 'Com certeza absoluta', 'Eu tenho certeza que sim'],
        "explanation": 'Resposta negativa com certo grau de incerteza.',
    },
    {
        "word": 'Maybe',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Maybe'?",
        "translation": 'Talvez',
        "distractors": ['Com certeza', 'Sempre', 'Nunca'],
        "explanation": 'Resposta indicando incerteza.',
    },
    {
        "word": 'Definitely',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Definitely'?",
        "translation": 'Com certeza',
        "distractors": ['Eu não sei', 'De jeito nenhum', 'Talvez não'],
        "explanation": 'Resposta afirmativa muito enfática.',
    },
    {
        "word": 'Absolutely not',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Absolutely not'?",
        "translation": 'De jeito nenhum',
        "distractors": ['Eu acho que sim', 'Talvez sim', 'Com certeza sim'],
        "explanation": 'Resposta negativa muito enfática.',
    },
    {
        "word": 'I guess so',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I guess so'?",
        "translation": 'Eu acho que sim (meio incerto)',
        "distractors": ['Eu tenho certeza absoluta', 'Eu nunca faria isso', 'Isso é impossível'],
        "explanation": 'Resposta afirmativa hesitante, informal.',
    },
    {
        "word": 'Yes, of course I can',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se afirma algo com certeza e disposição?',
        "translation": 'Sim, claro que posso',
        "distractors": ['Eu discordo', 'Talvez', 'Isso é muito gentil da sua parte'],
        "explanation": "Combina 'yes' com 'of course' para uma resposta afirmativa forte.",
    },
    {
        "word": "No, I don't think so",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se nega algo de forma suave e educada?',
        "translation": 'Não, eu acho que não',
        "distractors": ['Não se preocupe', 'Está tudo bem', 'Desculpe, foi meu erro, com licença'],
        "explanation": "Combina 'no' com 'I don't think so' para suavizar a negação.",
    },
    {
        "word": 'I understand',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I understand'?",
        "translation": 'Eu entendo',
        "distractors": ['Eu não entendo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para indicar que algo foi compreendido.',
    },
    {
        "word": "I don't understand",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I don't understand'?",
        "translation": 'Eu não entendo',
        "distractors": ['Eu concordo', 'Eu sei disso', 'Eu entendo tudo'],
        "explanation": 'Usado para indicar que algo não foi compreendido.',
    },
    {
        "word": 'I see',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I see'?",
        "translation": 'Entendi',
        "distractors": ['Eu discordo', 'Eu esqueci tudo', 'Eu não vejo nada'],
        "explanation": 'Expressão informal para indicar compreensão.',
    },
    {
        "word": 'Can you repeat that?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Can you repeat that?'",
        "translation": 'Você pode repetir isso?',
        "distractors": ['Você pode parar agora?', 'Você pode ir embora?', 'Você pode me ajudar?'],
        "explanation": 'Usado para pedir que algo seja dito novamente.',
    },
    {
        "word": 'Can you speak slowly?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Can you speak slowly?'",
        "translation": 'Você pode falar devagar?',
        "distractors": ['Você pode falar rápido?', 'Você pode parar de falar?', 'Você pode falar baixo?'],
        "explanation": 'Pedido comum para facilitar a compreensão.',
    },
    {
        "word": 'What does it mean?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What does it mean?'",
        "translation": 'O que isso significa?',
        "distractors": ['Onde isso está?', 'Quem fez isso?', 'Quando isso ocorre?'],
        "explanation": 'Pergunta usada para pedir o significado de algo.',
    },
    {
        "word": 'I have no idea',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I have no idea'?",
        "translation": 'Não faço ideia',
        "distractors": ['Eu sei exatamente', 'Eu concordo totalmente', 'Eu tenho certeza'],
        "explanation": 'Expressão usada quando não se sabe algo.',
    },
    {
        "word": "Sorry, I didn't get that",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Sorry, I didn't get that'?",
        "translation": 'Desculpe, não entendi isso',
        "distractors": ['Desculpe, eu entendi tudo', 'Obrigado, ficou claro', 'Com certeza eu sei'],
        "explanation": 'Usado educadamente quando algo não foi compreendido.',
    },
    {
        "word": 'Could you explain that?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Could you explain that?'",
        "translation": 'Você poderia explicar isso?',
        "distractors": ['Você poderia parar isso?', 'Você poderia comprar isso?', 'Você poderia esquecer isso?'],
        "explanation": 'Pedido educado de explicação.',
    },
    {
        "word": "It's clear now",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's clear now'?",
        "translation": 'Agora está claro',
        "distractors": ['Isso é impossível', 'Isso está errado', 'Ainda não está claro'],
        "explanation": 'Usado após entender algo que antes era confuso.',
    },
    {
        "word": "I'm confused",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm confused'?",
        "translation": 'Estou confuso(a)',
        "distractors": ['Estou com pressa', 'Estou tranquilo', 'Estou feliz'],
        "explanation": 'Usado para expressar confusão ou falta de clareza.',
    },
    {
        "word": 'What did you say?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What did you say?'",
        "translation": 'O que você disse?',
        "distractors": ['Quando você vem?', 'Onde você está?', 'Quem disse isso?'],
        "explanation": 'Pergunta usada quando não se ouviu ou entendeu algo.',
    },
    {
        "word": 'Sorry, can you repeat that, please?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede educadamente para repetir algo?',
        "translation": 'Desculpe, você pode repetir isso, por favor?',
        "distractors": ['Eu acho que não', 'Se cuida, até logo', 'Adeus (formal)'],
        "explanation": "Combina 'sorry' com o pedido 'can you repeat that'.",
    },
    {
        "word": "I don't understand, can you help?",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede ajuda por não ter entendido algo?',
        "translation": 'Eu não entendo, você pode ajudar?',
        "distractors": ['Você pode falar devagar?', 'Te pego depois', 'Sim, claro que posso'],
        "explanation": 'Une a falta de compreensão a um pedido de ajuda.',
    },
    {
        "word": 'Could you speak slowly, please?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede educadamente que alguém fale devagar?',
        "translation": 'Você poderia falar devagar, por favor?',
        "distractors": ['Com certeza', 'Onde fica o banheiro?', 'Posso?'],
        "explanation": "Combina 'could you' com 'speak slowly' e 'please'.",
    },
    {
        "word": 'I agree',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I agree'?",
        "translation": 'Eu concordo',
        "distractors": ['Eu discordo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para expressar concordância.',
    },
    {
        "word": 'I disagree',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I disagree'?",
        "translation": 'Eu discordo',
        "distractors": ['Eu concordo', 'Eu entendo', 'Eu gosto'],
        "explanation": 'Usado para expressar discordância.',
    },
    {
        "word": "That's true",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's true'?",
        "translation": 'Isso é verdade',
        "distractors": ['Isso é estranho', 'Isso é caro', 'Isso é falso'],
        "explanation": 'Usado para confirmar que algo é verdadeiro.',
    },
    {
        "word": "That's not true",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's not true'?",
        "translation": 'Isso não é verdade',
        "distractors": ['Isso é fácil', 'Isso é verdade', 'Isso é interessante'],
        "explanation": 'Usado para negar que algo é verdadeiro.',
    },
    {
        "word": "You're right",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'You're right'?",
        "translation": 'Você está certo(a)',
        "distractors": ['Você está errado', 'Você está cansado', 'Você está atrasado'],
        "explanation": 'Usado para concordar com o que alguém disse.',
    },
    {
        "word": "You're wrong",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'You're wrong'?",
        "translation": 'Você está errado(a)',
        "distractors": ['Você está certo', 'Você está bem', 'Você está pronto'],
        "explanation": 'Usado para discordar do que alguém disse.',
    },
    {
        "word": 'Exactly',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Exactly'?",
        "translation": 'Exatamente',
        "distractors": ['Talvez', 'De jeito nenhum', 'Eu não sei'],
        "explanation": 'Usado para concordar fortemente com algo.',
    },
    {
        "word": "I don't think so",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I don't think so'?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu tenho certeza que sim', 'Com certeza absoluta', 'Eu concordo plenamente'],
        "explanation": 'Usado para discordar de forma suave.',
    },
    {
        "word": 'Me too',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Me too'?",
        "translation": 'Eu também',
        "distractors": ['Eu não', 'Nunca', 'Nem eu'],
        "explanation": 'Usado para concordar dizendo que a mesma coisa se aplica a você.',
    },
    {
        "word": 'Me neither',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Me neither'?",
        "translation": 'Nem eu',
        "distractors": ['Eu também', 'Sempre eu', 'Eu sim'],
        "explanation": 'Usado para concordar com uma afirmação negativa.',
    },
    {
        "word": "I'm not sure",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm not sure'?",
        "translation": 'Eu não tenho certeza',
        "distractors": ['Eu concordo totalmente', 'Eu discordo totalmente', 'Eu tenho certeza absoluta'],
        "explanation": 'Usado para expressar incerteza diante de uma opinião.',
    },
    {
        "word": 'Fair enough',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Fair enough'?",
        "translation": 'Faz sentido',
        "distractors": ['Isso é impossível', 'Isso é injusto', 'Isso é errado'],
        "explanation": 'Usado para aceitar um argumento de forma parcial ou informal.',
    },
    {
        "word": 'I agree with you',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se expressa concordância com a opinião de alguém?',
        "translation": 'Eu concordo com você',
        "distractors": ['Olá, como você está?', 'Muito obrigado, você é muito gentil', 'Nem eu'],
        "explanation": "Combina 'I agree' com 'with you'.",
    },
    {
        "word": 'I disagree, sorry',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se discorda educadamente de alguém?',
        "translation": 'Eu discordo, desculpe',
        "distractors": ['Vai com calma', 'Muitíssimo obrigado(a)', 'Você pode repetir isso?'],
        "explanation": "Une 'I disagree' com um pedido de desculpas educado.",
    },
    {
        "word": "You're right, I agree",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se confirma que a outra pessoa está certa?',
        "translation": 'Você está certo, eu concordo',
        "distractors": ['Se cuida', 'Boa sorte, se cuida!', 'Você poderia me ajudar, por favor?'],
        "explanation": "Combina 'you're right' com 'I agree' para reforçar a concordância.",
    },
    {
        "word": 'Congratulations',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Congratulations'?",
        "translation": 'Parabéns',
        "distractors": ['Boa sorte', 'De nada', 'Sinto muito'],
        "explanation": 'Usado para parabenizar alguém.',
    },
    {
        "word": 'Good luck',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Good luck'?",
        "translation": 'Boa sorte',
        "distractors": ['Bem-vindo', 'Parabéns', 'Desculpa'],
        "explanation": 'Usado para desejar sorte a alguém.',
    },
    {
        "word": 'Happy birthday',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Happy birthday'?",
        "translation": 'Feliz aniversário',
        "distractors": ['Parabéns pelo trabalho', 'Bem-vindo', 'Boa sorte'],
        "explanation": 'Expressão usada para celebrar o aniversário de alguém.',
    },
    {
        "word": 'Bless you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Bless you'?",
        "translation": 'Saúde (após espirro)',
        "distractors": ['Bom apetite', 'Parabéns', 'Boa sorte'],
        "explanation": 'Dito educadamente quando alguém espirra.',
    },
    {
        "word": 'Cheers',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Cheers'?",
        "translation": 'Saúde (brinde)',
        "distractors": ['Adeus para sempre', 'Com licença', 'Sinto muito'],
        "explanation": 'Usado em brindes ou como agradecimento informal (britânico).',
    },
    {
        "word": 'Enjoy your meal',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Enjoy your meal'?",
        "translation": 'Bom apetite',
        "distractors": ['Boa viagem', 'Bom trabalho', 'Boa sorte'],
        "explanation": 'Dito antes de alguém começar a comer.',
    },
    {
        "word": 'Have a safe trip',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Have a safe trip'?",
        "translation": 'Tenha uma boa viagem',
        "distractors": ['Feliz aniversário', 'Boa sorte no trabalho', 'Bom apetite'],
        "explanation": 'Dito antes de alguém viajar.',
    },
    {
        "word": 'Get well soon',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Get well soon'?",
        "translation": 'Melhoras',
        "distractors": ['Parabéns', 'Boa sorte', 'Bom apetite'],
        "explanation": 'Desejo de melhora para alguém doente.',
    },
    {
        "word": 'Welcome back',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Welcome back'?",
        "translation": 'Bem-vindo de volta',
        "distractors": ['Sinto muito', 'Boa viagem', 'Até logo'],
        "explanation": 'Usado ao receber alguém que retornou.',
    },
    {
        "word": 'Make yourself at home',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Make yourself at home'?",
        "translation": 'Fique à vontade',
        "distractors": ['Espere lá fora', 'Fique de pé', 'Vá embora agora'],
        "explanation": 'Usado para deixar um convidado confortável.',
    },
    {
        "word": "It's nice here",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's nice here'?",
        "translation": 'Aqui é legal',
        "distractors": ['Aqui é longe', 'Aqui é caro', 'Aqui é ruim'],
        "explanation": 'Comentário positivo simples sobre um lugar.',
    },
    {
        "word": "That's great!",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's great!'",
        "translation": 'Isso é ótimo!',
        "distractors": ['Isso é estranho!', 'Isso é difícil!', 'Isso é péssimo!'],
        "explanation": 'Expressão de entusiasmo positivo.',
    },
    {
        "word": "That's too bad",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'That's too bad'?",
        "translation": 'Que pena',
        "distractors": ['Que ótimo', 'Que engraçado', 'Que legal'],
        "explanation": 'Expressão de pesar ou decepção.',
    },
    {
        "word": 'What a pity',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What a pity'?",
        "translation": 'Que pena',
        "distractors": ['Que sorte', 'Que orgulho', 'Que alegria'],
        "explanation": 'Expressão usada para lamentar algo.',
    },
    {
        "word": 'Have fun',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Have fun'?",
        "translation": 'Divirta-se',
        "distractors": ['Tenha paciência', 'Tenha cuidado', 'Tenha sorte'],
        "explanation": 'Dito antes de alguém sair para se divertir.',
    },
    {
        "word": 'Take it easy',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Take it easy'?",
        "translation": 'Vai com calma',
        "distractors": ['Corre rápido', 'Trabalhe mais', 'Fique bravo'],
        "explanation": 'Usado para pedir que alguém fique tranquilo.',
    },
    {
        "word": 'Same to you',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Same to you'?",
        "translation": 'Igualmente',
        "distractors": ['De jeito nenhum', 'Nunca mais', 'Ao contrário'],
        "explanation": 'Usado para devolver um desejo bom a alguém.',
    },
    {
        "word": 'Nice one',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Nice one'?",
        "translation": 'Mandou bem!',
        "distractors": ['Que pena!', 'Cuidado!', 'Sinto muito!'],
        "explanation": 'Expressão informal para elogiar algo bem feito.',
    },
    {
        "word": 'Happy birthday, have fun!',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se deseja um feliz aniversário e diversão ao mesmo tempo?',
        "translation": 'Feliz aniversário, divirta-se!',
        "distractors": ['Qual é o seu nome? Meu nome é Ana', 'Por quê?', 'Não, eu acho que não'],
        "explanation": "Combina 'happy birthday' com 'have fun'.",
    },
    {
        "word": 'Good luck, take care!',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se deseja boa sorte e bem-estar juntos?',
        "translation": 'Boa sorte, se cuida!',
        "distractors": ['Eu sou do Brasil', 'Foi meu erro', 'Só por precaução'],
        "explanation": "Combina 'good luck' com 'take care'.",
    },
    {
        "word": "What's your name?",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What's your name?'",
        "translation": 'Qual é o seu nome?',
        "distractors": ['Quantos anos você tem?', 'Onde você mora?', 'De onde você é?'],
        "explanation": 'Pergunta básica para saber o nome de alguém.',
    },
    {
        "word": 'My name is...',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'My name is...'?",
        "translation": 'Meu nome é...',
        "distractors": ['Eu sou de...', 'Eu tenho... anos', 'Eu moro em...'],
        "explanation": 'Resposta usada para dizer o próprio nome.',
    },
    {
        "word": 'How old are you?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'How old are you?'",
        "translation": 'Quantos anos você tem?',
        "distractors": ['Onde você mora?', 'Qual é o seu nome?', 'O que você faz?'],
        "explanation": 'Pergunta básica sobre idade.',
    },
    {
        "word": "I'm ... years old",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm ... years old'?",
        "translation": 'Eu tenho ... anos',
        "distractors": ['Eu me chamo ...', 'Eu moro em ...', 'Eu sou de ...'],
        "explanation": 'Resposta usada para dizer a idade.',
    },
    {
        "word": 'Where are you from?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Where are you from?'",
        "translation": 'De onde você é?',
        "distractors": ['O que você quer?', 'Quando você chega?', 'Como você está?'],
        "explanation": 'Pergunta sobre origem/nacionalidade.',
    },
    {
        "word": "I'm from Brazil",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I'm from Brazil'?",
        "translation": 'Eu sou do Brasil',
        "distractors": ['Eu moro perto', 'Eu gosto do Brasil', 'Eu vou ao Brasil'],
        "explanation": 'Resposta comum indicando o país de origem.',
    },
    {
        "word": 'Where do you live?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Where do you live?'",
        "translation": 'Onde você mora?',
        "distractors": ['Como você vive?', 'Quando você chega?', 'Por que você mora aqui?'],
        "explanation": 'Pergunta básica sobre local de moradia.',
    },
    {
        "word": 'I live in...',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'I live in...'?",
        "translation": 'Eu moro em...',
        "distractors": ['Eu vou a...', 'Eu gosto de...', 'Eu nasci em...'],
        "explanation": 'Resposta usada para dizer o local de moradia.',
    },
    {
        "word": 'What do you do?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What do you do?'",
        "translation": 'O que você faz? (profissão)',
        "distractors": ['O que você quer?', 'Quando você trabalha?', 'Onde você está?'],
        "explanation": 'Pergunta comum sobre a profissão de alguém.',
    },
    {
        "word": 'What time is it?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What time is it?'",
        "translation": 'Que horas são?',
        "distractors": ['Onde você está?', 'Que dia é hoje?', 'Quem é você?'],
        "explanation": 'Pergunta básica sobre o horário.',
    },
    {
        "word": "It's two o'clock",
        "part_of_speech": 'expressão',
        "tip": "O que significa 'It's two o'clock'?",
        "translation": 'São duas horas',
        "distractors": ['É a sala dois', 'São duas pessoas', 'É o dia dois'],
        "explanation": 'Resposta comum indicando horário.',
    },
    {
        "word": 'How much is it?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'How much is it?'",
        "translation": 'Quanto custa?',
        "distractors": ['Onde fica?', 'Quantos são?', 'Quando é?'],
        "explanation": 'Pergunta comum sobre preço.',
    },
    {
        "word": 'Where is the bathroom?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Where is the bathroom?'",
        "translation": 'Onde fica o banheiro?',
        "distractors": ['Onde fica a escola?', 'Onde fica o hotel?', 'Onde fica a saída?'],
        "explanation": 'Pergunta prática muito comum ao viajar.',
    },
    {
        "word": 'Can you help me?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Can you help me?'",
        "translation": 'Você pode me ajudar?',
        "distractors": ['Você pode me ver?', 'Você pode me ouvir?', 'Você pode me pagar?'],
        "explanation": 'Pedido básico de ajuda.',
    },
    {
        "word": 'What is this?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'What is this?'",
        "translation": 'O que é isso?',
        "distractors": ['Quando é isso?', 'Quem é este?', 'Onde está isso?'],
        "explanation": 'Pergunta básica sobre um objeto.',
    },
    {
        "word": 'Who is that?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Who is that?'",
        "translation": 'Quem é aquele(a)?',
        "distractors": ['O que é aquilo?', 'Como está aquilo?', 'Onde está aquilo?'],
        "explanation": 'Pergunta básica sobre uma pessoa.',
    },
    {
        "word": 'Why?',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Why?'",
        "translation": 'Por quê?',
        "distractors": ['Onde?', 'Quem?', 'Quando?'],
        "explanation": 'Pergunta básica pedindo uma razão.',
    },
    {
        "word": 'Because',
        "part_of_speech": 'expressão',
        "tip": "O que significa 'Because'?",
        "translation": 'Porque',
        "distractors": ['Quando', 'Onde', 'Quem'],
        "explanation": 'Usado para dar uma razão ou explicação.',
    },
    {
        "word": "What's your name? My name is Ana",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pergunta e responde o nome de alguém?',
        "translation": 'Qual é o seu nome? Meu nome é Ana',
        "distractors": ['Até mais tarde', 'Olá, como você está?', 'Desculpe, com licença'],
        "explanation": 'Combina a pergunta e a resposta básica sobre nome.',
    },
    {
        "word": "Where are you from? I'm from Brazil",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pergunta e responde sobre origem?',
        "translation": 'De onde você é? Eu sou do Brasil',
        "distractors": ['Não se preocupe com isso', 'Obrigado, e de nada também', 'Desculpe interromper'],
        "explanation": 'Combina pergunta e resposta sobre origem/nacionalidade.',
    },
    {
        "word": 'Thank you very much indeed',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Thank you very much indeed'?",
        "translation": 'Muito obrigado mesmo',
        "distractors": ['Com certeza não', 'Sinto muito mesmo', 'De jeito nenhum mesmo'],
        "explanation": 'Combinação enfática de agradecimento.',
    },
    {
        "word": "I'm sorry, I'm late",
        "part_of_speech": 'chunk',
        "tip": "O que significa 'I'm sorry, I'm late'?",
        "translation": 'Desculpe, estou atrasado(a)',
        "distractors": ['Obrigado, estou pronto', 'Com licença, estou aqui', 'Desculpe, estou cedo'],
        "explanation": 'Combinação comum ao chegar atrasado.',
    },
    {
        "word": 'Please, come in',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Please, come in'?",
        "translation": 'Por favor, entre',
        "distractors": ['Por favor, saia', 'Por favor, sente', 'Por favor, espere'],
        "explanation": 'Combinação usada para convidar alguém a entrar.',
    },
    {
        "word": 'Please, sit down',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Please, sit down'?",
        "translation": 'Por favor, sente-se',
        "distractors": ['Por favor, levante-se', 'Por favor, saia', 'Por favor, corra'],
        "explanation": 'Combinação usada para convidar alguém a se sentar.',
    },
    {
        "word": 'Please, wait a moment',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Please, wait a moment'?",
        "translation": 'Por favor, espere um momento',
        "distractors": ['Por favor, fique calado', 'Por favor, corra rápido', 'Por favor, vá agora'],
        "explanation": 'Combinação usada para pedir paciência.',
    },
    {
        "word": 'Yes, of course',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Yes, of course'?",
        "translation": 'Sim, claro',
        "distractors": ['Nunca, impossível', 'Não, de jeito nenhum', 'Talvez, não sei'],
        "explanation": 'Combinação afirmativa muito comum.',
    },
    {
        "word": 'No, thank you',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'No, thank you'?",
        "translation": 'Não, obrigado',
        "distractors": ['Claro que sim', 'Com certeza', 'Sim, por favor'],
        "explanation": 'Combinação usada para recusar educadamente.',
    },
    {
        "word": 'Sorry, excuse me',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Sorry, excuse me'?",
        "translation": 'Desculpe, com licença',
        "distractors": ['Prazer, igualmente', 'Tchau, até logo', 'Obrigado, de nada'],
        "explanation": 'Combinação comum ao pedir passagem educadamente.',
    },
    {
        "word": 'Hello again',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Hello again'?",
        "translation": 'Olá de novo',
        "distractors": ['Com licença agora', 'Tchau para sempre', 'Muito obrigado'],
        "explanation": 'Combinação usada ao reencontrar alguém no mesmo dia.',
    },
    {
        "word": 'See you around',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'See you around'?",
        "translation": 'Nos vemos por aí',
        "distractors": ['Nunca mais te vejo', 'Muito prazer nisso', 'Bom dia para você'],
        "explanation": 'Despedida informal e casual.',
    },
    {
        "word": 'Good to see you',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Good to see you'?",
        "translation": 'Bom te ver',
        "distractors": ['Difícil te ver', 'Ruim te ver', 'Estranho te ver'],
        "explanation": 'Combinação amigável usada ao encontrar alguém.',
    },
    {
        "word": 'Nice talking to you',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Nice talking to you'?",
        "translation": 'Foi bom falar com você',
        "distractors": ['Foi ruim falar com você', 'Não gostei de falar', 'Não quero falar mais'],
        "explanation": 'Combinação usada ao encerrar uma conversa agradável.',
    },
    {
        "word": 'Just a moment, please',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Just a moment, please'?",
        "translation": 'Só um momento, por favor',
        "distractors": ['Nunca mais espere', 'Corra rapidamente', 'Vá agora mesmo'],
        "explanation": 'Combinação usada para pedir uma pequena espera.',
    },
    {
        "word": 'Not a problem',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Not a problem'?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Impossível de resolver', 'Muito complicado', 'Um grande problema'],
        "explanation": 'Combinação informal usada como resposta tranquilizadora.',
    },
    {
        "word": 'All right then',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'All right then'?",
        "translation": 'Tudo bem então',
        "distractors": ['Tudo errado então', 'Impossível assim', 'Nada bem assim'],
        "explanation": 'Combinação usada para concordar ou aceitar algo.',
    },
    {
        "word": 'Okay, sounds good',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Okay, sounds good'?",
        "translation": 'Ok, parece bom',
        "distractors": ['Não, parece ruim', 'Talvez, parece estranho', 'Nunca, parece caro'],
        "explanation": 'Combinação informal de concordância positiva.',
    },
    {
        "word": 'Sure thing',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Sure thing'?",
        "translation": 'Pode deixar',
        "distractors": ['Nunca mais', 'Talvez amanhã', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa informal e descontraída.',
    },
    {
        "word": 'Right away',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Right away'?",
        "translation": 'Agora mesmo',
        "distractors": ['Nunca', 'Talvez amanhã', 'Mais tarde'],
        "explanation": 'Combinação que indica ação imediata.',
    },
    {
        "word": 'Just in case',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'Just in case'?",
        "translation": 'Só por precaução',
        "distractors": ['Sem motivo nenhum', 'Nunca mais', 'De qualquer jeito ruim'],
        "explanation": 'Combinação usada para indicar precaução.',
    },
    {
        "word": 'By the way',
        "part_of_speech": 'chunk',
        "tip": "O que significa 'By the way'?",
        "translation": 'A propósito',
        "distractors": ['No final das contas', 'De jeito nenhum', 'Ao contrário disso'],
        "explanation": 'Combinação usada para introduzir um novo assunto.',
    },
    {
        "word": 'Hi, my name is Ana, nice to meet you',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se apresenta com nome e cortesia?',
        "translation": 'Oi, meu nome é Ana, prazer em te conhecer',
        "distractors": ['Se cuida', 'Tudo bem', 'Até mais tarde, tchau!'],
        "explanation": 'Combina saudação, apresentação de nome e cortesia.',
    },
    {
        "word": 'Good morning, how are you today?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se cumprimenta pela manhã e pergunta como a pessoa está?',
        "translation": 'Bom dia, como você está hoje?',
        "distractors": ['Você pode falar devagar?', 'Isso é muito gentil da sua parte', 'Eu também'],
        "explanation": 'Une a saudação matinal com a pergunta sobre o estado da pessoa.',
    },
    {
        "word": "I'm sorry, I don't understand",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede desculpa por não ter entendido algo?',
        "translation": 'Desculpe, eu não entendo',
        "distractors": ['De onde você é? Eu sou do Brasil', 'Eu entendo', 'É um prazer (para mim)'],
        "explanation": 'Combina o pedido de desculpas com a falta de compreensão.',
    },
    {
        "word": 'Excuse me, can you help me, please?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede ajuda de forma bem educada?',
        "translation": 'Com licença, você pode me ajudar, por favor?',
        "distractors": ['Eu não entendo', 'Eu acho que sim (meio incerto)', 'Desculpe, com licença'],
        "explanation": "Combina 'excuse me' com o pedido de ajuda educado.",
    },
    {
        "word": "Thank you so much, you're very kind",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se agradece elogiando a gentileza de alguém?',
        "translation": 'Muito obrigado, você é muito gentil',
        "distractors": ['Olá de novo', 'Com licença, por favor', 'Pode deixar'],
        "explanation": 'Combina agradecimento enfático com um elogio de cortesia.',
    },
    {
        "word": "Nice to meet you, what's your name?",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se cumprimenta alguém novo perguntando o nome?',
        "translation": 'Prazer em te conhecer, qual é o seu nome?',
        "distractors": ['Foi bom falar com você', 'Por favor, entre', 'Até logo'],
        "explanation": 'Combina a apresentação com a pergunta pelo nome.',
    },
    {
        "word": "I agree with you, that's true",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se concorda com alguém confirmando que é verdade?',
        "translation": 'Eu concordo com você, isso é verdade',
        "distractors": ['Onde fica o banheiro?', 'De onde você é? Eu sou do Brasil', 'Claro, sem problema'],
        "explanation": 'Une concordância com confirmação de veracidade.',
    },
    {
        "word": "Sorry, I don't agree with that",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se discorda educadamente pedindo desculpa antes?',
        "translation": 'Desculpe, eu não concordo com isso',
        "distractors": ['Que pena', 'Com licença, você pode me ajudar, por favor?', 'Está tudo bem, não se preocupe'],
        "explanation": 'Combina desculpa com discordância educada.',
    },
    {
        "word": 'Excuse me, where is the bathroom?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pergunta educadamente sobre a localização do banheiro?',
        "translation": 'Com licença, onde fica o banheiro?',
        "distractors": ['É um prazer (para mim)', 'Eu não tenho certeza', 'Você pode falar devagar?'],
        "explanation": "Combina 'excuse me' com a pergunta prática de localização.",
    },
    {
        "word": "Can you repeat that, please? I don't understand",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se pede repetição explicando a falta de entendimento?',
        "translation": 'Você pode repetir isso, por favor? Eu não entendo',
        "distractors": ['Se você não se importar', 'Muito obrigado mesmo', 'Sem problema nenhum'],
        "explanation": 'Une o pedido de repetição com a explicação da dúvida.',
    },
    {
        "word": "It's okay, don't worry, no problem",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se tranquiliza alguém repetindo a ideia de forma reforçada?',
        "translation": 'Está tudo bem, não se preocupe, sem problema',
        "distractors": ['Boa sorte, se cuida!', 'Está tudo bem', 'Só um momento, por favor'],
        "explanation": 'Reforça a tranquilização combinando três expressões parecidas.',
    },
    {
        "word": 'Good luck today, take care, see you soon',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se despede desejando sorte e bem-estar juntos?',
        "translation": 'Boa sorte hoje, se cuida, até logo',
        "distractors": ['Claro', 'Olá, bom dia, como você está?', 'Prazer em te conhecer, até logo, tchau'],
        "explanation": 'Combina três expressões sociais de despedida positiva.',
    },
    {
        "word": 'Yes, please, thank you very much',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se aceita uma oferta educadamente e agradece?',
        "translation": 'Sim, por favor, muito obrigado',
        "distractors": ['Bom dia a todos', 'Não se preocupe com isso', 'Estou bem, obrigado(a)'],
        "explanation": 'Combina aceitação educada com agradecimento enfático.',
    },
    {
        "word": "I'm sorry, that was my mistake, excuse me",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se assume um erro pedindo desculpas de forma completa?',
        "translation": 'Desculpe, foi meu erro, com licença',
        "distractors": ['Sim, por favor', 'Agora está claro', 'Com licença, por favor'],
        "explanation": 'Combina desculpa, admissão de erro e pedido de licença.',
    },
    {
        "word": 'Hello, good morning, how are you?',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se cumprimenta combinando duas saudações e uma pergunta?',
        "translation": 'Olá, bom dia, como você está?',
        "distractors": ['Tchau', 'Desculpe, foi meu erro', 'Quantos anos você tem?'],
        "explanation": 'Une duas saudações com a pergunta padrão sobre o estado da pessoa.',
    },
    {
        "word": "Thank you, and you're welcome too",
        "part_of_speech": 'mini-frase',
        "tip": 'Como se agradece e devolve a cortesia ao mesmo tempo?',
        "translation": 'Obrigado, e de nada também',
        "distractors": ['Oi, meu nome é Ana, prazer em te conhecer', 'Sim, por favor', 'Desculpe, foi meu erro'],
        "explanation": "Combina agradecimento com a devolução de 'you're welcome'.",
    },
    {
        "word": 'Nice to meet you, see you soon, bye',
        "part_of_speech": 'mini-frase',
        "tip": 'Como se apresenta e já se despede de forma educada?',
        "translation": 'Prazer em te conhecer, até logo, tchau',
        "distractors": ['Por favor, espere um momento', 'Saúde (brinde)', 'Você poderia explicar isso?'],
        "explanation": 'Une apresentação e despedida em uma sequência natural.',
    },

    # =========================================================================
    # PARTE 2 (A1) — CHUNKS E VERBOS ESSENCIAIS, em INGLÊS.
    # Progressão: chunk -> chunk + palavra conhecida -> chunk + noun novo ->
    # mini-frase -> variação. Distratores reaproveitam o mesmo noun trocando
    # o chunk, nunca sinônimos perfeitos.
    # =========================================================================

    # --- I need... -----------------------------------------------------
    {
        "word": 'I need...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I need...'?",
        "translation": 'Eu preciso de...',
        "distractors": ['Eu quero...', 'Eu tenho...', 'Eu gosto de...'],
        "explanation": "'I need' expressa uma necessidade. É seguido de um complemento, como 'I need water.'",
    },
    {
        "word": 'I need water.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de água' em inglês?",
        "translation": 'Eu preciso de água.',
        "distractors": ['Eu quero água.', 'Eu tenho água.', 'Eu gosto de água.'],
        "explanation": "'Water' (água) é o complemento novo do chunk 'I need'.",
    },
    {
        "word": 'I need coffee.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de café' em inglês?",
        "translation": 'Eu preciso de café.',
        "distractors": ['Eu quero café.', 'Eu tenho café.', 'Eu gosto de café.'],
        "explanation": "Mesmo chunk 'I need', agora com o noun 'coffee'.",
    },
    {
        "word": 'I need a ticket.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de uma passagem' em inglês?",
        "translation": 'Eu preciso de uma passagem.',
        "distractors": ['Eu quero uma passagem.', 'Eu tenho uma passagem.', 'Eu gosto de uma passagem.'],
        "explanation": "'A ticket' (uma passagem) é um noun novo, usado com o chunk 'I need'.",
    },
    {
        "word": 'I need help.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de ajuda' em inglês?",
        "translation": 'Eu preciso de ajuda.',
        "distractors": ['Eu quero ajuda.', 'Eu tenho ajuda.', 'Eu gosto de ajuda.'],
        "explanation": "'Help' (ajuda) é um dos complementos mais usados com 'I need'.",
    },
    {
        "word": 'I need money.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de dinheiro' em inglês?",
        "translation": 'Eu preciso de dinheiro.',
        "distractors": ['Eu quero dinheiro.', 'Eu tenho dinheiro.', 'Eu gosto de dinheiro.'],
        "explanation": "'Money' (dinheiro) combina naturalmente com 'I need'.",
    },
    {
        "word": 'I need a taxi.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de um táxi' em inglês?",
        "translation": 'Eu preciso de um táxi.',
        "distractors": ['Eu quero um táxi.', 'Eu tenho um táxi.', 'Eu gosto de um táxi.'],
        "explanation": "'A taxi' (um táxi) é um noun novo, muito útil em situações do dia a dia.",
    },
    {
        "word": 'I need more time.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de mais tempo' em inglês?",
        "translation": 'Eu preciso de mais tempo.',
        "distractors": ['Eu quero mais tempo.', 'Eu tenho mais tempo.', 'Eu gosto de mais tempo.'],
        "explanation": "'More time' (mais tempo) é uma combinação comum com 'I need'.",
    },
    {
        "word": 'I need a napkin.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de um guardanapo' em inglês?",
        "translation": 'Eu preciso de um guardanapo.',
        "distractors": ['Eu quero um guardanapo.', 'Eu tenho um guardanapo.', 'Eu gosto de um guardanapo.'],
        "explanation": "'A napkin' (um guardanapo) é comum em contextos de restaurante.",
    },
    {
        "word": 'I need a fork.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de um garfo' em inglês?",
        "translation": 'Eu preciso de um garfo.',
        "distractors": ['Eu quero um garfo.', 'Eu tenho um garfo.', 'Eu gosto de um garfo.'],
        "explanation": "'A fork' (um garfo) é outro noun útil de restaurante.",
    },
    {
        "word": 'I need an umbrella.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de um guarda-chuva' em inglês?",
        "translation": 'Eu preciso de um guarda-chuva.',
        "distractors": ['Eu quero um guarda-chuva.', 'Eu tenho um guarda-chuva.', 'Eu gosto de um guarda-chuva.'],
        "explanation": "'An umbrella' (um guarda-chuva) usa 'an' porque começa com som de vogal.",
    },
    {
        "word": 'I need sugar.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso de açúcar' em inglês?",
        "translation": 'Eu preciso de açúcar.',
        "distractors": ['Eu quero açúcar.', 'Eu tenho açúcar.', 'Eu gosto de açúcar.'],
        "explanation": "'Sugar' (açúcar) é um noun não contável, sem artigo antes.",
    },
    {
        "word": 'I really need this.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu realmente preciso disso' em inglês?",
        "translation": 'Eu realmente preciso disso.',
        "distractors": ['Eu realmente quero isso.', 'Eu realmente tenho isso.', 'Eu realmente gosto disso.'],
        "explanation": "'Really' reforça o chunk 'I need', deixando a necessidade mais forte.",
    },
    {
        "word": 'Do you need help?',
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você precisa de ajuda?' em inglês?",
        "translation": 'Você precisa de ajuda?',
        "distractors": ['Você quer ajuda?', 'Você tem ajuda?', 'Você gosta de ajuda?'],
        "explanation": "Pergunta com 'Do you' + o chunk 'need', reutilizando o noun 'help'.",
    },

    # --- We need... ------------------------------------------------------
    {
        "word": 'We need...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'We need...'?",
        "translation": 'Nós precisamos de...',
        "distractors": ['Nós queremos...', 'Nós temos...', 'Nós gostamos de...'],
        "explanation": "Mesmo chunk de 'I need', agora na forma 'we' (nós).",
    },
    {
        "word": 'We need a table.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de uma mesa' em inglês?",
        "translation": 'Nós precisamos de uma mesa.',
        "distractors": ['Nós queremos uma mesa.', 'Nós temos uma mesa.', 'Nós gostamos de uma mesa.'],
        "explanation": "'A table' (uma mesa) é um noun novo usado com 'we need'.",
    },
    {
        "word": 'We need a plan.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um plano' em inglês?",
        "translation": 'Nós precisamos de um plano.',
        "distractors": ['Nós queremos um plano.', 'Nós temos um plano.', 'Nós gostamos de um plano.'],
        "explanation": "'A plan' (um plano) combina naturalmente com 'need'.",
    },
    {
        "word": 'We need a break.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de uma pausa' em inglês?",
        "translation": 'Nós precisamos de uma pausa.',
        "distractors": ['Nós queremos uma pausa.', 'Nós temos uma pausa.', 'Nós gostamos de uma pausa.'],
        "explanation": "'A break' (uma pausa) é um noun muito usado no dia a dia.",
    },
    {
        "word": 'We need some help.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de ajuda' em inglês?",
        "translation": 'Nós precisamos de ajuda.',
        "distractors": ['Nós queremos ajuda.', 'Nós temos ajuda.', 'Nós gostamos de ajuda.'],
        "explanation": "'Some help' reforça que é 'um pouco de ajuda', sem quantidade exata.",
    },
    {
        "word": 'We need a fork.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um garfo' em inglês?",
        "translation": 'Nós precisamos de um garfo.',
        "distractors": ['Nós queremos um garfo.', 'Nós temos um garfo.', 'Nós gostamos de um garfo.'],
        "explanation": "Reaproveita o noun 'fork', já visto com o chunk 'I need'.",
    },
    {
        "word": 'We need an appointment.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de uma consulta/horário marcado' em inglês?",
        "translation": 'Nós precisamos de uma consulta.',
        "distractors": ['Nós queremos uma consulta.', 'Nós temos uma consulta.', 'Nós gostamos de uma consulta.'],
        "explanation": "'An appointment' (uma consulta/hora marcada) é um noun novo e frequente.",
    },
    {
        "word": 'We need a menu.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um cardápio' em inglês?",
        "translation": 'Nós precisamos de um cardápio.',
        "distractors": ['Nós queremos um cardápio.', 'Nós temos um cardápio.', 'Nós gostamos de um cardápio.'],
        "explanation": "'A menu' (um cardápio) é essencial em restaurantes.",
    },
    {
        "word": 'We need an umbrella.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um guarda-chuva' em inglês?",
        "translation": 'Nós precisamos de um guarda-chuva.',
        "distractors": ['Nós queremos um guarda-chuva.', 'Nós temos um guarda-chuva.', 'Nós gostamos de um guarda-chuva.'],
        "explanation": "Reaproveita 'umbrella', agora com o chunk 'we need'.",
    },
    {
        "word": 'We need a map.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um mapa' em inglês?",
        "translation": 'Nós precisamos de um mapa.',
        "distractors": ['Nós queremos um mapa.', 'Nós temos um mapa.', 'Nós gostamos de um mapa.'],
        "explanation": "'A map' (um mapa) é um noun novo, útil em viagens.",
    },

    {
        "word": 'We need a receipt.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós precisamos de um recibo' em inglês?",
        "translation": 'Nós precisamos de um recibo.',
        "distractors": ['Nós queremos um recibo.', 'Nós temos um recibo.', 'Nós gostamos de um recibo.'],
        "explanation": "Reaproveita 'receipt', já visto com 'I'd like'.",
    },

    # --- I want... ---------------------------------------------------------
    {
        "word": 'I want...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I want...'?",
        "translation": 'Eu quero...',
        "distractors": ['Eu preciso de...', 'Eu tenho...', 'Eu gosto de...'],
        "explanation": "'I want' expressa um desejo, algo que a pessoa gostaria de ter ou fazer.",
    },
    {
        "word": 'I want coffee.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero café' em inglês?",
        "translation": 'Eu quero café.',
        "distractors": ['Eu preciso de café.', 'Eu tenho café.', 'Eu gosto de café.'],
        "explanation": "Mesmo noun 'coffee', agora com o chunk 'I want'.",
    },
    {
        "word": 'I want a table.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero uma mesa' em inglês?",
        "translation": 'Eu quero uma mesa.',
        "distractors": ['Eu preciso de uma mesa.', 'Eu tenho uma mesa.', 'Eu gosto de uma mesa.'],
        "explanation": "Reaproveita o noun 'table' com o chunk 'I want'.",
    },
    {
        "word": 'I want the bill.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero a conta' em inglês?",
        "translation": 'Eu quero a conta.',
        "distractors": ['Eu preciso da conta.', 'Eu tenho a conta.', 'Eu gosto da conta.'],
        "explanation": "'The bill' (a conta) é essencial em restaurantes e lojas.",
    },
    {
        "word": 'I want a new car.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero um carro novo' em inglês?",
        "translation": 'Eu quero um carro novo.',
        "distractors": ['Eu preciso de um carro novo.', 'Eu tenho um carro novo.', 'Eu gosto de um carro novo.'],
        "explanation": "'A new car' (um carro novo) é o chunk 'I want' com noun + adjetivo.",
    },
    {
        "word": 'I want a napkin.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero um guardanapo' em inglês?",
        "translation": 'Eu quero um guardanapo.',
        "distractors": ['Eu preciso de um guardanapo.', 'Eu tenho um guardanapo.', 'Eu gosto de um guardanapo.'],
        "explanation": "Reaproveita 'napkin', já visto com 'I need'.",
    },
    {
        "word": 'I want a favor.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero pedir um favor' em inglês?",
        "translation": 'Eu quero um favor.',
        "distractors": ['Eu preciso de um favor.', 'Eu tenho um favor.', 'Eu gosto de um favor.'],
        "explanation": "'A favor' (um favor) é um noun novo, comum em pedidos educados.",
    },
    {
        "word": 'I really want this.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu realmente quero isso' em inglês?",
        "translation": 'Eu realmente quero isso.',
        "distractors": ['Eu realmente preciso disso.', 'Eu realmente tenho isso.', 'Eu realmente gosto disso.'],
        "explanation": "'Really' reforça a intensidade do desejo em 'I want'.",
    },
    {
        "word": 'Do you want some coffee?',
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você quer um pouco de café?' em inglês?",
        "translation": 'Você quer um pouco de café?',
        "distractors": ['Você precisa de um pouco de café?', 'Você tem um pouco de café?', 'Você gosta de um pouco de café?'],
        "explanation": "Pergunta comum ao oferecer algo, com 'Do you want'.",
    },

    {
        "word": 'I want some milk.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero um pouco de leite' em inglês?",
        "translation": 'Eu quero um pouco de leite.',
        "distractors": ['Eu preciso de um pouco de leite.', 'Eu tenho um pouco de leite.', 'Eu gosto de um pouco de leite.'],
        "explanation": "Reaproveita 'milk', já visto com 'I'd like'.",
    },

    # --- I'd like... ---------------------------------------------------
    {
        "word": "I'd like...",
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I'd like...'?",
        "translation": 'Eu gostaria de...',
        "distractors": ['Eu quero...', 'Eu preciso de...', 'Eu tenho...'],
        "explanation": "'I'd like' é a forma mais educada de 'I want', muito usada em pedidos.",
    },
    {
        "word": "I'd like some water.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um pouco de água' em inglês?",
        "translation": 'Eu gostaria de um pouco de água.',
        "distractors": ['Eu quero um pouco de água.', 'Eu preciso de um pouco de água.', 'Eu tenho um pouco de água.'],
        "explanation": "Forma educada de pedir algo, reutilizando o noun 'water'.",
    },
    {
        "word": "I'd like a coffee.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um café' em inglês?",
        "translation": 'Eu gostaria de um café.',
        "distractors": ['Eu quero um café.', 'Eu preciso de um café.', 'Eu tenho um café.'],
        "explanation": "Pedido educado, comum em cafeterias.",
    },
    {
        "word": "I'd like a table for two.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de uma mesa para dois' em inglês?",
        "translation": 'Eu gostaria de uma mesa para dois.',
        "distractors": ['Eu quero uma mesa para dois.', 'Eu preciso de uma mesa para dois.', 'Eu tenho uma mesa para dois.'],
        "explanation": "Frase clássica ao entrar em um restaurante.",
    },
    {
        "word": "I'd like the menu, please.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria do cardápio, por favor' em inglês?",
        "translation": 'Eu gostaria do cardápio, por favor.',
        "distractors": ['Eu quero o cardápio, por favor.', 'Eu preciso do cardápio, por favor.', 'Eu tenho o cardápio, por favor.'],
        "explanation": "Combina o chunk 'I'd like' com o noun 'menu' e a educação de 'please'.",
    },
    {
        "word": "I'd like a receipt.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um recibo' em inglês?",
        "translation": 'Eu gostaria de um recibo.',
        "distractors": ['Eu quero um recibo.', 'Eu preciso de um recibo.', 'Eu tenho um recibo.'],
        "explanation": "'A receipt' (um recibo) é um noun útil em compras.",
    },
    {
        "word": "I'd like a napkin.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um guardanapo' em inglês?",
        "translation": 'Eu gostaria de um guardanapo.',
        "distractors": ['Eu quero um guardanapo.', 'Eu preciso de um guardanapo.', 'Eu tenho um guardanapo.'],
        "explanation": "Reaproveita 'napkin' na forma mais educada 'I'd like'.",
    },
    {
        "word": "I'd like some sugar.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um pouco de açúcar' em inglês?",
        "translation": 'Eu gostaria de um pouco de açúcar.',
        "distractors": ['Eu quero um pouco de açúcar.', 'Eu preciso de um pouco de açúcar.', 'Eu tenho um pouco de açúcar.'],
        "explanation": "'Some sugar' reaproveita 'sugar' com o chunk educado.",
    },
    {
        "word": "I'd like some milk.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um pouco de leite' em inglês?",
        "translation": 'Eu gostaria de um pouco de leite.',
        "distractors": ['Eu quero um pouco de leite.', 'Eu preciso de um pouco de leite.', 'Eu tenho um pouco de leite.'],
        "explanation": "'Milk' (leite) é um noun novo, muito comum no café da manhã.",
    },
    {
        "word": "I'd like a blanket.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gostaria de um cobertor' em inglês?",
        "translation": 'Eu gostaria de um cobertor.',
        "distractors": ['Eu quero um cobertor.', 'Eu preciso de um cobertor.', 'Eu tenho um cobertor.'],
        "explanation": "'A blanket' (um cobertor) é comum em pedidos em voos e hotéis.",
    },
    # --- I have... -------------------------------------------------------
    {
        "word": 'I have...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I have...'?",
        "translation": 'Eu tenho...',
        "distractors": ['Eu quero...', 'Eu preciso de...', 'Eu gosto de...'],
        "explanation": "'I have' indica posse ou existência de algo.",
    },
    {
        "word": 'I have a car.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um carro' em inglês?",
        "translation": 'Eu tenho um carro.',
        "distractors": ['Eu quero um carro.', 'Eu preciso de um carro.', 'Eu gosto de um carro.'],
        "explanation": "Mesmo noun 'car', agora com o chunk 'I have'.",
    },
    {
        "word": 'I have a question.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho uma pergunta' em inglês?",
        "translation": 'Eu tenho uma pergunta.',
        "distractors": ['Eu quero uma pergunta.', 'Eu preciso de uma pergunta.', 'Eu gosto de uma pergunta.'],
        "explanation": "'A question' (uma pergunta) é um noun novo, muito usado com 'I have'.",
    },
    {
        "word": 'I have an idea.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho uma ideia' em inglês?",
        "translation": 'Eu tenho uma ideia.',
        "distractors": ['Eu quero uma ideia.', 'Eu preciso de uma ideia.', 'Eu gosto de uma ideia.'],
        "explanation": "'An idea' (uma ideia) usa 'an' pelo som de vogal inicial.",
    },
    {
        "word": 'I have a problem.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um problema' em inglês?",
        "translation": 'Eu tenho um problema.',
        "distractors": ['Eu quero um problema.', 'Eu preciso de um problema.', 'Eu gosto de um problema.'],
        "explanation": "'A problem' (um problema) é um noun de alta frequência.",
    },
    {
        "word": 'I have some time.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um pouco de tempo' em inglês?",
        "translation": 'Eu tenho um pouco de tempo.',
        "distractors": ['Eu quero um pouco de tempo.', 'Eu preciso de um pouco de tempo.', 'Eu gosto de um pouco de tempo.'],
        "explanation": "Reaproveita 'time', agora indicando posse com 'I have'.",
    },
    {
        "word": 'I have a hobby.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um hobby' em inglês?",
        "translation": 'Eu tenho um hobby.',
        "distractors": ['Eu quero um hobby.', 'Eu preciso de um hobby.', 'Eu gosto de um hobby.'],
        "explanation": "'A hobby' (um hobby) é um noun novo, comum ao falar de si mesmo.",
    },
    {
        "word": 'I have a book.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um livro' em inglês?",
        "translation": 'Eu tenho um livro.',
        "distractors": ['Eu quero um livro.', 'Eu preciso de um livro.', 'Eu gosto de um livro.'],
        "explanation": "'A book' (um livro) é um noun básico e reutilizável.",
    },
    {
        "word": 'I have an appointment.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho uma consulta' em inglês?",
        "translation": 'Eu tenho uma consulta.',
        "distractors": ['Eu quero uma consulta.', 'Eu preciso de uma consulta.', 'Eu gosto de uma consulta.'],
        "explanation": "Reaproveita 'appointment', agora indicando posse.",
    },
    {
        "word": 'Do you have a plan?',
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você tem um plano?' em inglês?",
        "translation": 'Você tem um plano?',
        "distractors": ['Você quer um plano?', 'Você precisa de um plano?', 'Você gosta de um plano?'],
        "explanation": "Pergunta com 'Do you have', reutilizando o noun 'plan'.",
    },

    {
        "word": 'I have a friend.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho um amigo' em inglês?",
        "translation": 'Eu tenho um amigo.',
        "distractors": ['Eu quero um amigo.', 'Eu preciso de um amigo.', 'Eu gosto de um amigo.'],
        "explanation": "'A friend' (um amigo) é um noun novo, muito frequente.",
    },

    # --- We have... ------------------------------------------------------
    {
        "word": 'We have...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'We have...'?",
        "translation": 'Nós temos...',
        "distractors": ['Nós queremos...', 'Nós precisamos de...', 'Nós gostamos de...'],
        "explanation": "Mesmo chunk de 'I have', agora na forma 'we' (nós).",
    },
    {
        "word": 'We have a reservation.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos uma reserva' em inglês?",
        "translation": 'Nós temos uma reserva.',
        "distractors": ['Nós queremos uma reserva.', 'Nós precisamos de uma reserva.', 'Nós gostamos de uma reserva.'],
        "explanation": "'A reservation' (uma reserva) é essencial em hotéis e restaurantes.",
    },
    {
        "word": 'We have a plan.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos um plano' em inglês?",
        "translation": 'Nós temos um plano.',
        "distractors": ['Nós queremos um plano.', 'Nós precisamos de um plano.', 'Nós gostamos de um plano.'],
        "explanation": "Reaproveita 'plan', agora indicando posse com 'we have'.",
    },
    {
        "word": 'We have some questions.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos algumas perguntas' em inglês?",
        "translation": 'Nós temos algumas perguntas.',
        "distractors": ['Nós queremos algumas perguntas.', 'Nós precisamos de algumas perguntas.', 'Nós gostamos de algumas perguntas.'],
        "explanation": "'Some questions' usa o plural de 'question' com o chunk 'we have'.",
    },
    {
        "word": 'We have some sugar.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos um pouco de açúcar' em inglês?",
        "translation": 'Nós temos um pouco de açúcar.',
        "distractors": ['Nós queremos um pouco de açúcar.', 'Nós precisamos de um pouco de açúcar.', 'Nós gostamos de um pouco de açúcar.'],
        "explanation": "Reaproveita 'sugar', agora indicando posse.",
    },
    {
        "word": 'We have a blanket.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos um cobertor' em inglês?",
        "translation": 'Nós temos um cobertor.',
        "distractors": ['Nós queremos um cobertor.', 'Nós precisamos de um cobertor.', 'Nós gostamos de um cobertor.'],
        "explanation": "Reaproveita 'blanket', já visto com 'I'd like'.",
    },

    {
        "word": 'We have a napkin.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Nós temos um guardanapo' em inglês?",
        "translation": 'Nós temos um guardanapo.',
        "distractors": ['Nós queremos um guardanapo.', 'Nós precisamos de um guardanapo.', 'Nós gostamos de um guardanapo.'],
        "explanation": "Reaproveita 'napkin', já visto em vários chunks anteriores.",
    },

    # --- I like... -------------------------------------------------------
    {
        "word": 'I like...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I like...'?",
        "translation": 'Eu gosto de...',
        "distractors": ['Eu quero...', 'Eu tenho...', 'Eu preciso de...'],
        "explanation": "'I like' expressa uma preferência, algo que a pessoa aprecia.",
    },
    {
        "word": 'I like coffee.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gosto de café' em inglês?",
        "translation": 'Eu gosto de café.',
        "distractors": ['Eu quero café.', 'Eu tenho café.', 'Eu preciso de café.'],
        "explanation": "Mesmo noun 'coffee', agora com o chunk 'I like'.",
    },
    {
        "word": 'I like this place.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gosto deste lugar' em inglês?",
        "translation": 'Eu gosto deste lugar.',
        "distractors": ['Eu quero este lugar.', 'Eu tenho este lugar.', 'Eu preciso deste lugar.'],
        "explanation": "'This place' (este lugar) é um noun frequente ao falar de preferências.",
    },
    {
        "word": 'I like music.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gosto de música' em inglês?",
        "translation": 'Eu gosto de música.',
        "distractors": ['Eu quero música.', 'Eu tenho música.', 'Eu preciso de música.'],
        "explanation": "'Music' (música) é um noun não contável, sem artigo antes.",
    },
    {
        "word": 'I like this book.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gosto deste livro' em inglês?",
        "translation": 'Eu gosto deste livro.',
        "distractors": ['Eu quero este livro.', 'Eu tenho este livro.', 'Eu preciso deste livro.'],
        "explanation": "Reaproveita 'book', já visto com 'I have'.",
    },
    {
        "word": 'I like this hobby.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu gosto deste hobby' em inglês?",
        "translation": 'Eu gosto deste hobby.',
        "distractors": ['Eu quero este hobby.', 'Eu tenho este hobby.', 'Eu preciso deste hobby.'],
        "explanation": "Reaproveita 'hobby', já visto com 'I have'.",
    },
    {
        "word": 'I really like this.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu realmente gosto disso' em inglês?",
        "translation": 'Eu realmente gosto disso.',
        "distractors": ['Eu realmente quero isso.', 'Eu realmente tenho isso.', 'Eu realmente preciso disso.'],
        "explanation": "'Really' reforça a intensidade do gosto em 'I like'.",
    },
    {
        "word": 'Do you like coffee?',
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você gosta de café?' em inglês?",
        "translation": 'Você gosta de café?',
        "distractors": ['Você quer café?', 'Você tem café?', 'Você precisa de café?'],
        "explanation": "Pergunta comum ao conversar sobre preferências, com 'Do you like'.",
    },

    # --- I don't like... ---------------------------------------------------
    {
        "word": "I don't like...",
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I don't like...'?",
        "translation": 'Eu não gosto de...',
        "distractors": ['Eu não quero...', 'Eu não tenho...', 'Eu não preciso de...'],
        "explanation": "'I don't like' é a forma negativa de 'I like', para expressar que algo não agrada.",
    },
    {
        "word": "I don't like coffee.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto de café' em inglês?",
        "translation": 'Eu não gosto de café.',
        "distractors": ['Eu não quero café.', 'Eu não tenho café.', 'Eu não preciso de café.'],
        "explanation": "Reaproveita 'coffee', agora na forma negativa.",
    },
    {
        "word": "I don't like waiting.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto de esperar' em inglês?",
        "translation": 'Eu não gosto de esperar.',
        "distractors": ['Eu não quero esperar.', 'Eu não tenho tempo de esperar.', 'Eu não preciso esperar.'],
        "explanation": "'Waiting' (esperar) aparece depois de 'like' na forma -ing.",
    },
    {
        "word": "I don't like this place.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto deste lugar' em inglês?",
        "translation": 'Eu não gosto deste lugar.',
        "distractors": ['Eu não quero este lugar.', 'Eu não tenho este lugar.', 'Eu não preciso deste lugar.'],
        "explanation": "Reaproveita 'this place', agora na forma negativa.",
    },
    {
        "word": "I don't like the taste.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto do sabor' em inglês?",
        "translation": 'Eu não gosto do sabor.',
        "distractors": ['Eu não quero o sabor.', 'Eu não tenho o sabor.', 'Eu não preciso do sabor.'],
        "explanation": "'The taste' (o sabor) é um noun novo, comum ao falar de comida.",
    },
    {
        "word": "I don't like sugar.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto de açúcar' em inglês?",
        "translation": 'Eu não gosto de açúcar.',
        "distractors": ['Eu não quero açúcar.', 'Eu não tenho açúcar.', 'Eu não preciso de açúcar.'],
        "explanation": "Reaproveita 'sugar', agora na forma negativa.",
    },
    {
        "word": "I don't like the smell.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto do cheiro' em inglês?",
        "translation": 'Eu não gosto do cheiro.',
        "distractors": ['Eu não quero o cheiro.', 'Eu não tenho o cheiro.', 'Eu não preciso do cheiro.'],
        "explanation": "'The smell' (o cheiro) é um noun novo, no mesmo campo de 'taste'.",
    },

    {
        "word": "I don't like this hobby.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu não gosto deste hobby' em inglês?",
        "translation": 'Eu não gosto deste hobby.',
        "distractors": ['Eu não quero este hobby.', 'Eu não tenho este hobby.', 'Eu não preciso deste hobby.'],
        "explanation": "Reaproveita 'this hobby', agora na forma negativa.",
    },

    # --- I need to... --------------------------------------------------
    {
        "word": 'I need to...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I need to...'?",
        "translation": 'Eu preciso...',
        "distractors": ['Eu quero...', 'Eu tenho que...', 'Eu vou...'],
        "explanation": "'I need to' é seguido de um verbo, indicando uma ação necessária.",
    },
    {
        "word": 'I need to go.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso ir' em inglês?",
        "translation": 'Eu preciso ir.',
        "distractors": ['Eu quero ir.', 'Eu tenho que ir.', 'Eu vou ir.'],
        "explanation": "'Go' (ir) é o verbo mais simples usado com 'I need to'.",
    },
    {
        "word": 'I need to call someone.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso ligar para alguém' em inglês?",
        "translation": 'Eu preciso ligar para alguém.',
        "distractors": ['Eu quero ligar para alguém.', 'Eu tenho que ligar para alguém.', 'Eu vou ligar para alguém.'],
        "explanation": "'Call someone' (ligar para alguém) é um chunk comum com verbos de necessidade.",
    },
    {
        "word": 'I need to check something.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso verificar uma coisa' em inglês?",
        "translation": 'Eu preciso verificar uma coisa.',
        "distractors": ['Eu quero verificar uma coisa.', 'Eu tenho que verificar uma coisa.', 'Eu vou verificar uma coisa.'],
        "explanation": "'Check something' (verificar uma coisa) é um verbo útil no cotidiano.",
    },
    {
        "word": 'I need to leave now.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso ir agora' em inglês?",
        "translation": 'Eu preciso ir agora.',
        "distractors": ['Eu quero ir agora.', 'Eu tenho que ir agora.', 'Eu vou agora.'],
        "explanation": "'Leave now' (ir/sair agora) reforça urgência com o chunk 'I need to'.",
    },
    {
        "word": 'I need to think about it.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso pensar sobre isso' em inglês?",
        "translation": 'Eu preciso pensar sobre isso.',
        "distractors": ['Eu quero pensar sobre isso.', 'Eu tenho que pensar sobre isso.', 'Eu vou pensar sobre isso.'],
        "explanation": "'Think about it' (pensar sobre isso) é uma resposta comum antes de decidir.",
    },
    {
        "word": 'I need to take a shower.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso tomar um banho' em inglês?",
        "translation": 'Eu preciso tomar um banho.',
        "distractors": ['Eu quero tomar um banho.', 'Eu tenho que tomar um banho.', 'Eu vou tomar um banho.'],
        "explanation": "'Take a shower' (tomar um banho) é um chunk fixo em inglês.",
    },
    {
        "word": 'I need to take a nap.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu preciso tirar uma soneca' em inglês?",
        "translation": 'Eu preciso tirar uma soneca.',
        "distractors": ['Eu quero tirar uma soneca.', 'Eu tenho que tirar uma soneca.', 'Eu vou tirar uma soneca.'],
        "explanation": "'Take a nap' (tirar uma soneca) é outro chunk fixo com 'take'.",
    },
    {
        "word": 'Do you need to go now?',
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você precisa ir agora?' em inglês?",
        "translation": 'Você precisa ir agora?',
        "distractors": ['Você quer ir agora?', 'Você tem que ir agora?', 'Você vai agora?'],
        "explanation": "Pergunta com 'Do you need to', reutilizando 'go now'.",
    },

    # --- I want to... ----------------------------------------------------
    {
        "word": 'I want to...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I want to...'?",
        "translation": 'Eu quero...',
        "distractors": ['Eu preciso...', 'Eu tenho que...', 'Eu vou...'],
        "explanation": "'I want to' é seguido de um verbo, indicando um desejo de fazer algo.",
    },
    {
        "word": 'I want to go home.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero ir para casa' em inglês?",
        "translation": 'Eu quero ir para casa.',
        "distractors": ['Eu preciso ir para casa.', 'Eu tenho que ir para casa.', 'Eu vou para casa.'],
        "explanation": "'Go home' (ir para casa) é um chunk muito comum.",
    },
    {
        "word": 'I want to try this.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero experimentar isso' em inglês?",
        "translation": 'Eu quero experimentar isso.',
        "distractors": ['Eu preciso experimentar isso.', 'Eu tenho que experimentar isso.', 'Eu vou experimentar isso.'],
        "explanation": "'Try this' (experimentar isso) é usado ao provar algo novo.",
    },
    {
        "word": 'I want to help you.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero te ajudar' em inglês?",
        "translation": 'Eu quero te ajudar.',
        "distractors": ['Eu preciso te ajudar.', 'Eu tenho que te ajudar.', 'Eu vou te ajudar.'],
        "explanation": "'Help you' (te ajudar) reutiliza o verbo 'help', já visto como noun em 'I need help'.",
    },
    {
        "word": 'I want to see it.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero ver isso' em inglês?",
        "translation": 'Eu quero ver isso.',
        "distractors": ['Eu preciso ver isso.', 'Eu tenho que ver isso.', 'Eu vou ver isso.'],
        "explanation": "'See it' (ver isso) é um chunk curto e muito usado.",
    },
    {
        "word": 'I want to read this book.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero ler este livro' em inglês?",
        "translation": 'Eu quero ler este livro.',
        "distractors": ['Eu preciso ler este livro.', 'Eu tenho que ler este livro.', 'Eu vou ler este livro.'],
        "explanation": "Reaproveita 'this book', já visto com 'I like'.",
    },
    {
        "word": 'I want to ask a favor.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu quero pedir um favor' em inglês?",
        "translation": 'Eu quero pedir um favor.',
        "distractors": ['Eu preciso pedir um favor.', 'Eu tenho que pedir um favor.', 'Eu vou pedir um favor.'],
        "explanation": "'Ask a favor' (pedir um favor) reaproveita 'a favor', já visto com 'I want'.",
    },

    # --- I have to... ----------------------------------------------------
    {
        "word": 'I have to...',
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I have to...'?",
        "translation": 'Eu tenho que...',
        "distractors": ['Eu quero...', 'Eu preciso...', 'Eu vou...'],
        "explanation": "'I have to' indica uma obrigação, algo que precisa ser feito.",
    },
    {
        "word": 'I have to go now.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que ir agora' em inglês?",
        "translation": 'Eu tenho que ir agora.',
        "distractors": ['Eu quero ir agora.', 'Eu preciso ir agora.', 'Eu vou agora.'],
        "explanation": "Reaproveita 'go now', já visto com 'I need to'.",
    },
    {
        "word": 'I have to work.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que trabalhar' em inglês?",
        "translation": 'Eu tenho que trabalhar.',
        "distractors": ['Eu quero trabalhar.', 'Eu preciso trabalhar.', 'Eu vou trabalhar.'],
        "explanation": "'Work' (trabalhar) é um verbo de alta frequência com 'have to'.",
    },
    {
        "word": 'I have to check my phone.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que checar meu celular' em inglês?",
        "translation": 'Eu tenho que checar meu celular.',
        "distractors": ['Eu quero checar meu celular.', 'Eu preciso checar meu celular.', 'Eu vou checar meu celular.'],
        "explanation": "'My phone' (meu celular) é um noun novo, usado com 'check'.",
    },
    {
        "word": 'I have to leave early.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que sair mais cedo' em inglês?",
        "translation": 'Eu tenho que sair mais cedo.',
        "distractors": ['Eu quero sair mais cedo.', 'Eu preciso sair mais cedo.', 'Eu vou sair mais cedo.'],
        "explanation": "'Leave early' (sair mais cedo) é um chunk comum sobre horários.",
    },
    {
        "word": 'I have to ask a favor.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que pedir um favor' em inglês?",
        "translation": 'Eu tenho que pedir um favor.',
        "distractors": ['Eu quero pedir um favor.', 'Eu preciso pedir um favor.', 'Eu vou pedir um favor.'],
        "explanation": "Reaproveita 'ask a favor', já visto com 'I want to'.",
    },
    {
        "word": 'I have to read this book.',
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu tenho que ler este livro' em inglês?",
        "translation": 'Eu tenho que ler este livro.',
        "distractors": ['Eu quero ler este livro.', 'Eu preciso ler este livro.', 'Eu vou ler este livro.'],
        "explanation": "Reaproveita 'read this book', já visto com 'I want to'.",
    },

    # --- I'm looking for... ----------------------------------------------
    {
        "word": "I'm looking for...",
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I'm looking for...'?",
        "translation": 'Eu estou procurando...',
        "distractors": ['Eu estou precisando de...', 'Eu estou querendo...', 'Eu estou indo para...'],
        "explanation": "'I'm looking for' é usado quando você está à procura de algo ou alguém.",
    },
    {
        "word": "I'm looking for a hotel.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando um hotel' em inglês?",
        "translation": 'Eu estou procurando um hotel.',
        "distractors": ['Eu estou precisando de um hotel.', 'Eu estou querendo um hotel.', 'Eu estou indo para um hotel.'],
        "explanation": "'A hotel' (um hotel) é um noun essencial em viagens.",
    },
    {
        "word": "I'm looking for my keys.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando minhas chaves' em inglês?",
        "translation": 'Eu estou procurando minhas chaves.',
        "distractors": ['Eu estou precisando de minhas chaves.', 'Eu estou querendo minhas chaves.', 'Eu estou indo para minhas chaves.'],
        "explanation": "'My keys' (minhas chaves) é um noun no plural, muito usado no dia a dia.",
    },
    {
        "word": "I'm looking for a job.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando um emprego' em inglês?",
        "translation": 'Eu estou procurando um emprego.',
        "distractors": ['Eu estou precisando de um emprego.', 'Eu estou querendo um emprego.', 'Eu estou indo para um emprego.'],
        "explanation": "'A job' (um emprego) é um noun de alta utilidade.",
    },
    {
        "word": "I'm looking for the bathroom.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando o banheiro' em inglês?",
        "translation": 'Eu estou procurando o banheiro.',
        "distractors": ['Eu estou precisando do banheiro.', 'Eu estou querendo o banheiro.', 'Eu estou indo para o banheiro.'],
        "explanation": "'The bathroom' (o banheiro) é essencial em qualquer lugar novo.",
    },
    {
        "word": "I'm looking for a charger.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando um carregador' em inglês?",
        "translation": 'Eu estou procurando um carregador.',
        "distractors": ['Eu estou precisando de um carregador.', 'Eu estou querendo um carregador.', 'Eu estou indo para um carregador.'],
        "explanation": "'A charger' (um carregador) é um noun muito atual e útil.",
    },
    {
        "word": "I'm looking for the wifi password.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando a senha do wifi' em inglês?",
        "translation": 'Eu estou procurando a senha do wifi.',
        "distractors": ['Eu estou precisando da senha do wifi.', 'Eu estou querendo a senha do wifi.', 'Eu estou indo para a senha do wifi.'],
        "explanation": "'The wifi password' (a senha do wifi) é um chunk moderno e prático.",
    },
    {
        "word": "I'm looking for a blanket.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando um cobertor' em inglês?",
        "translation": 'Eu estou procurando um cobertor.',
        "distractors": ['Eu estou precisando de um cobertor.', 'Eu estou querendo um cobertor.', 'Eu estou indo para um cobertor.'],
        "explanation": "Reaproveita 'blanket', já visto com 'I'd like' e 'we have'.",
    },
    {
        "word": "I'm looking for sugar.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu estou procurando açúcar' em inglês?",
        "translation": 'Eu estou procurando açúcar.',
        "distractors": ['Eu estou precisando de açúcar.', 'Eu estou querendo açúcar.', 'Eu estou indo para açúcar.'],
        "explanation": "Reaproveita 'sugar', já visto em vários chunks anteriores.",
    },

    # --- I'm going to... ---------------------------------------------------
    {
        "word": "I'm going to...",
        "part_of_speech": 'chunk',
        "tip": "O que significa o chunk 'I'm going to...'?",
        "translation": 'Eu vou...',
        "distractors": ['Eu estou procurando...', 'Eu tenho que...', 'Eu quero...'],
        "explanation": "'I'm going to' indica um plano ou intenção futura próxima.",
    },
    {
        "word": "I'm going to the airport.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou para o aeroporto' em inglês?",
        "translation": 'Eu vou para o aeroporto.',
        "distractors": ['Eu estou procurando o aeroporto.', 'Eu tenho que ir ao aeroporto.', 'Eu quero ir ao aeroporto.'],
        "explanation": "'The airport' (o aeroporto) é um noun essencial em viagens.",
    },
    {
        "word": "I'm going to call you.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou te ligar' em inglês?",
        "translation": 'Eu vou te ligar.',
        "distractors": ['Eu estou procurando te ligar.', 'Eu tenho que te ligar.', 'Eu quero te ligar.'],
        "explanation": "Reaproveita 'call someone', já visto com 'I need to'.",
    },
    {
        "word": "I'm going to try.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou tentar' em inglês?",
        "translation": 'Eu vou tentar.',
        "distractors": ['Eu estou procurando tentar.', 'Eu tenho que tentar.', 'Eu quero tentar.'],
        "explanation": "'Try' (tentar) é um verbo curto e muito reutilizável.",
    },
    {
        "word": "I'm going to be late.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou me atrasar' em inglês?",
        "translation": 'Eu vou me atrasar.',
        "distractors": ['Eu estou procurando me atrasar.', 'Eu tenho que me atrasar.', 'Eu quero me atrasar.'],
        "explanation": "'Be late' (se atrasar) é um chunk muito usado ao avisar alguém.",
    },
    {
        "word": "I'm going to take a nap.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou tirar uma soneca' em inglês?",
        "translation": 'Eu vou tirar uma soneca.',
        "distractors": ['Eu estou procurando tirar uma soneca.', 'Eu tenho que tirar uma soneca.', 'Eu quero tirar uma soneca.'],
        "explanation": "Reaproveita 'take a nap', já visto com 'I need to'.",
    },
    {
        "word": "I'm going to read this book.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou ler este livro' em inglês?",
        "translation": 'Eu vou ler este livro.',
        "distractors": ['Eu estou procurando ler este livro.', 'Eu tenho que ler este livro.', 'Eu quero ler este livro.'],
        "explanation": "Reaproveita 'read this book', já visto com 'I want to' e 'I have to'.",
    },
    {
        "word": "I'm going to check my phone.",
        "part_of_speech": 'mini-frase',
        "tip": "Como se diz 'Eu vou checar meu celular' em inglês?",
        "translation": 'Eu vou checar meu celular.',
        "distractors": ['Eu estou procurando checar meu celular.', 'Eu tenho que checar meu celular.', 'Eu quero checar meu celular.'],
        "explanation": "Reaproveita 'check my phone', já visto com 'I have to'.",
    },
    {
        "word": "Are you going to call me?",
        "part_of_speech": 'mini-frase',
        "tip": "Como se pergunta 'Você vai me ligar?' em inglês?",
        "translation": 'Você vai me ligar?',
        "distractors": ['Você quer me ligar?', 'Você tem que me ligar?', 'Você está procurando me ligar?'],
        "explanation": "Pergunta com 'Are you going to', reutilizando 'call me'.",
    },
]

# ---------------------------------------------------------------------------
# Categoria de cada item, pra tela "Aprender" (frontend) conseguir separar
# a fila por categoria: os primeiros 200 itens são a Parte 1 (Saudações e
# frases essenciais / sobrevivência linguística, A1); o restante é a Parte 2
# (Chunks e verbos essenciais). O índice 200 é o começo comprovado da Parte 2
# — primeiro item é o chunk "I need...".
# ---------------------------------------------------------------------------
PART_1_SIZE = 200
assert WORDS[PART_1_SIZE]["word"] == "I need...", (
    "A lista WORDS mudou — o corte da Parte 1 (índice 200) não bate mais "
    "com o começo da Parte 2 ('I need...'). Ajuste PART_1_SIZE."
)
for _i, _item in enumerate(WORDS):
    _item["category"] = "saudacoes" if _i < PART_1_SIZE else "verbos"


def _fetch_existing_words(api_base_url: str, headers: dict) -> dict:
    """
    Busca todas as palavras já cadastradas (GET /vocab-words, visão do
    professor) e devolve um dicionário {(word_lower, language, translation_lower): word_dict},
    pra decidir rapidamente se cada item de WORDS já existe ou não.
    """
    resp = requests.get(f"{api_base_url}/vocab-words", headers=headers)
    resp.raise_for_status()
    existing = {}
    for w in resp.json():
        key = (w["word"].strip().lower(), w["language"].strip().lower(), w["translation"].strip().lower())
        existing[key] = w
    return existing


def _norm(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _needs_update(existing: dict, item: dict, language: str) -> bool:
    """
    Compara o que já está cadastrado com o que o item de WORDS quer enviar.
    Só chamamos o PUT se algo realmente for diferente — assim uma palavra
    que já está em dia não sofre uma escrita desnecessária no banco.
    """
    if existing["word"].strip() != item["word"].strip():
        return True
    if existing["part_of_speech"].strip() != item["part_of_speech"].strip():
        return True
    if existing["translation"].strip() != item["translation"].strip():
        return True
    if _norm(existing.get("example_sentence")) != _norm(item.get("example_sentence")):
        return True
    if _norm(existing.get("tip")) != _norm(item.get("tip")):
        return True
    if _norm(existing.get("explanation")) != _norm(item.get("explanation")):
        return True
    existing_distractors = sorted(d.strip().lower() for d in existing["distractors"])
    item_distractors = sorted(d.strip().lower() for d in item["distractors"])
    if existing_distractors != item_distractors:
        return True
    if existing["language"].strip().lower() != language.strip().lower():
        return True
    if existing.get("category", "saudacoes").strip().lower() != item.get("category", "saudacoes").strip().lower():
        return True
    return False


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        print("Defina PROFESSOR_EMAIL e PROFESSOR_PASSWORD nas variáveis de ambiente.")
        sys.exit(1)

    print(f"Fazendo login em {API_BASE_URL}...")
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        data={"username": PROFESSOR_EMAIL, "password": PROFESSOR_PASSWORD},
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("Verificando palavras já cadastradas...")
    existing_words = _fetch_existing_words(API_BASE_URL, headers)

    summary = {"Criado": 0, "Atualizado": 0, "Inalterado": 0}

    for item in WORDS:
        key = (item["word"].strip().lower(), LANGUAGE.strip().lower(), item["translation"].strip().lower())
        existing = existing_words.get(key)

        # Sem `student_ids`: na CRIAÇÃO, a API atribui automaticamente a
        # TODOS os alunos aprovados agora (e aos aprovados depois) que
        # tenham a mesma língua-alvo (LANGUAGE, acima) — é assim que o
        # lote inteiro é "enviado" pra todos os alunos de uma vez. Na
        # ATUALIZAÇÃO, não reenviamos student_ids de propósito, pra não
        # alterar quem já está atribuído à palavra.
        payload = {**item, "language": LANGUAGE}

        if existing and not _needs_update(existing, item, LANGUAGE):
            # Já está tudo igual: não chama a API, só reporta.
            n_students = len(existing.get("students", []))
            print(f"Inalterado: '{existing['word']}' (id={existing['id']}) -> {existing['translation']} "
                  f"[{n_students} aluno(s) atribuído(s)]")
            summary["Inalterado"] += 1
            continue

        if existing:
            word_id = existing["id"]
            resp = requests.put(f"{API_BASE_URL}/vocab-words/{word_id}", json=payload, headers=headers)
            action = "Atualizado"
        else:
            resp = requests.post(f"{API_BASE_URL}/vocab-words", json=payload, headers=headers)
            action = "Criado"

        if resp.status_code >= 400:
            verbo = "atualizar" if existing else "criar"
            print(f"Falha ao {verbo} '{item['word']}': {resp.status_code} {resp.text}")
            continue

        result = resp.json()
        n_students = len(result.get("students", []))
        print(f"{action}: '{result['word']}' (id={result['id']}) -> {result['translation']} "
              f"[{n_students} aluno(s) atribuído(s)]")
        summary[action] += 1

    print(
        f"Concluído. Criado: {summary['Criado']} | "
        f"Atualizado: {summary['Atualizado']} | "
        f"Inalterado: {summary['Inalterado']}"
    )


if __name__ == "__main__":
    main()