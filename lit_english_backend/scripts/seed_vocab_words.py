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
sobrevivência linguística), nível A1, em INGLÊS.
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
]

# ---------------------------------------------------------------------------
# Categoria de cada item, pra tela "Aprender" (frontend) conseguir separar
# a fila por categoria. Por enquanto só existe a Parte 1 (Saudações e
# frases essenciais / sobrevivência linguística, A1) neste arquivo.
# ---------------------------------------------------------------------------
for _item in WORDS:
    _item["category"] = "saudacoes"


def _fetch_existing_words(api_base_url: str, headers: dict) -> dict:
    """
    Busca todas as palavras já cadastradas (GET /vocab-words, visão do
    professor) e devolve um dicionário {(word_lower, language): [word_dict, ...]},
    agrupando por palavra+língua (SEM a tradução na chave).

    Por quê: se a tradução entrar na chave de busca, editar a tradução de
    uma palavra que já existe (ex.: melhorar "Boa noite" -> "Boa noite (ao
    chegar)") faz o script deixar de "achar" o registro antigo e CRIAR um
    novo — a palavra antiga fica órfã no banco pra sempre, ainda atribuída
    aos alunos, inflando a contagem e nunca mais sendo atualizada. Foi
    isso que aconteceu com boa parte da Parte 1 no passado.

    Agrupar só por (word, language) resolve o caso comum (uma palavra, uma
    tradução, que evolui com o tempo) sem perder o caso raro de verdade
    (uma mesma palavra com DOIS sentidos diferentes, tipo "Ciao" em
    italiano = Oi/Tchau) — esse caso é resolvido em _match_existing, que
    usa a tradução só como desempate quando há mais de um candidato.
    """
    resp = requests.get(f"{api_base_url}/vocab-words", headers=headers)
    resp.raise_for_status()
    existing_by_word: dict[tuple[str, str], list[dict]] = {}
    for w in resp.json():
        key = (w["word"].strip().lower(), w["language"].strip().lower())
        existing_by_word.setdefault(key, []).append(w)
    return existing_by_word


def _match_existing(existing_by_word: dict, item: dict, language: str) -> dict | None:
    """
    Acha o registro existente (se houver) que corresponde a este item de
    WORDS, pra decidir CRIAR vs ATUALIZAR.

    - 0 candidatos com essa palavra+língua        -> None (cria).
    - 1 candidato                                  -> é ele, mesmo que a
      tradução tenha mudado (é uma atualização de tradução, não uma
      palavra nova).
    - 2+ candidatos (mesma palavra, sentidos
      diferentes, ex. "Ciao")                      -> tenta achar o que
      já tem a MESMA tradução (pra não misturar sentidos); se nenhum
      bater, trata como palavra nova de fato (cria mais um sentido).
    """
    key = (item["word"].strip().lower(), language.strip().lower())
    candidates = existing_by_word.get(key, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    target_translation = item["translation"].strip().lower()
    for c in candidates:
        if c["translation"].strip().lower() == target_translation:
            return c
    return None


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
        existing = _match_existing(existing_words, item, LANGUAGE)

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