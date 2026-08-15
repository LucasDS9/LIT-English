"""
Script de seed: cria OU ATUALIZA as palavras da tela "Aprender" via API
(upsert). Como o campo `student_ids` é OPCIONAL (ver
VocabWordCreate/create_vocab_word), não enviamos ele aqui de propósito — a
API atribui a palavra automaticamente a TODOS os alunos aprovados no
momento **que tenham a mesma língua-alvo** (campo `language`, abaixo —
'italiano' aqui), e o backend garante que qualquer aluno aprovado
depois (em admin.approve_student) dessa mesma língua também receba as
mesmas palavras. Ou seja: rodar este script envia o lote inteiro pra TODOS
os alunos de Acesso Especial com língua-alvo italiano agora, de uma vez, sem precisar selecionar aluno
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
    python scripts/seed_vocab_words_italiano.py

Este arquivo contém as 200 palavras/expressões da Parte 1 (nível A1)
em ITALIANO, extraídas do baralho de flashcards fornecido
pelo professor.
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
LANGUAGE = 'italiano'

# ---------------------------------------------------------------------------
# Parte 1 (A1) — 200 palavras/expressões, extraídas do baralho de
# flashcards em ITALIANO. `tip` é a pergunta/contexto mostrado
# ANTES de responder; `explanation` só aparece DEPOIS, no verso do card,
# junto com a resposta certa.
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": 'Salve',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Salve'?",
        "translation": 'Olá',
        "distractors": ['Por favor', 'Tchau', 'Obrigado'],
        "explanation": "'Salve' é uma saudação comum e neutra em italiano.",
    },
    {
        "word": 'Ciao',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ciao' (ao cumprimentar alguém)?",
        "translation": 'Oi',
        "distractors": ['Sim', 'Não', 'Adeus'],
        "explanation": "'Ciao' é a forma mais informal e comum de cumprimentar em italiano.",
    },
    {
        "word": 'Buongiorno',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buongiorno'?",
        "translation": 'Bom dia',
        "distractors": ['Boa noite', 'Boa tarde', 'Até logo'],
        "explanation": 'Usado para cumprimentar até por volta do meio-dia.',
    },
    {
        "word": 'Buon pomeriggio',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buon pomeriggio'?",
        "translation": 'Boa tarde',
        "distractors": ['Bom dia', 'Boa sorte', 'Boa noite'],
        "explanation": 'Usado à tarde, após o meio-dia.',
    },
    {
        "word": 'Buonasera',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buonasera'?",
        "translation": 'Boa noite (ao chegar)',
        "distractors": ['Bom dia', 'Boa noite (ao dormir)', 'Boa tarde'],
        "explanation": 'Usado ao encontrar alguém à noite, não ao se despedir.',
    },
    {
        "word": 'Buonanotte',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buonanotte'?",
        "translation": 'Boa noite (ao dormir)',
        "distractors": ['Boa tarde', 'Boa noite (ao chegar)', 'Bom dia'],
        "explanation": 'Usado ao se despedir à noite, geralmente antes de dormir.',
    },
    {
        "word": 'Ehi',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'Ehi'?",
        "translation": 'Ei',
        "distractors": ['Tchau', 'Sim', 'Desculpa'],
        "explanation": 'Cumprimento bem informal, comum entre amigos.',
    },
    {
        "word": 'Come stai?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Come stai?'?",
        "translation": 'Como você está?',
        "distractors": ['O que você quer?', 'Onde você está?', 'Quem é você?'],
        "explanation": 'Pergunta comum logo após cumprimentar alguém.',
    },
    {
        "word": 'Sto bene, grazie',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sto bene, grazie'?",
        "translation": 'Estou bem, obrigado(a)',
        "distractors": ['Eu não sei', 'Estou cansado', 'Não estou bem'],
        "explanation": "Resposta comum e educada para 'Come stai?'.",
    },
    {
        "word": 'Piacere di conoscerti',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Piacere di conoscerti'?",
        "translation": 'Prazer em te conhecer',
        "distractors": ['Com licença', 'Até mais', 'Muito obrigado'],
        "explanation": 'Usado ao conhecer alguém pela primeira vez.',
    },
    {
        "word": 'Benvenuto/a',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Benvenuto/a'?",
        "translation": 'Bem-vindo(a)',
        "distractors": ['Cuidado', 'Adeus', 'Desculpe'],
        "explanation": 'Usado para receber alguém em um lugar.',
    },
    {
        "word": 'Ciao, come stai?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Ciao, come stai?'?",
        "translation": 'Olá, como você está?',
        "distractors": ['Por favor, entre', 'Eu não tenho certeza', 'De nada'],
        "explanation": "Combina a saudação 'Ciao' com a pergunta 'Come stai?'.",
    },
    {
        "word": 'Come va?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Come va?'?",
        "translation": 'E aí?',
        "distractors": ['Muito obrigado', 'Com certeza', 'Boa noite'],
        "explanation": 'Cumprimento informal muito comum entre jovens.',
    },
    {
        "word": 'Quanto tempo!',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Quanto tempo!'?",
        "translation": 'Quanto tempo!',
        "distractors": ['Nunca te vi', 'Vejo você amanhã', 'Eu não te conheço'],
        "explanation": 'Usado ao reencontrar alguém depois de muito tempo.',
    },
    {
        "word": 'Buongiorno a tutti',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Buongiorno a tutti'?",
        "translation": 'Bom dia a todos',
        "distractors": ['Com licença, por favor', 'Muito obrigado, eu agradeço', 'Você poderia, por favor?'],
        "explanation": 'Saudação usada para um grupo de pessoas pela manhã.',
    },
    {
        "word": 'Arrivederci',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Arrivederci'?",
        "translation": 'Adeus',
        "distractors": ['Obrigado', 'Desculpa', 'Olá'],
        "explanation": 'Forma padrão de se despedir em italiano.',
    },
    {
        "word": 'Ciao',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'Ciao' (ao se despedir)?",
        "translation": 'Tchau',
        "distractors": ['Sim', 'Por favor', 'Oi'],
        "explanation": "Em italiano, 'ciao' também é usado para se despedir, não só para cumprimentar.",
    },
    {
        "word": 'A più tardi',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'A più tardi'?",
        "translation": 'Até mais tarde',
        "distractors": ['Bom dia', 'Nunca mais te vejo', 'Muito prazer'],
        "explanation": 'Usado ao se despedir esperando ver a pessoa novamente em breve.',
    },
    {
        "word": 'A presto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'A presto'?",
        "translation": 'Até logo',
        "distractors": ['Com licença', 'Até nunca', 'Boa sorte'],
        "explanation": 'Despedida indicando que o reencontro será em breve.',
    },
    {
        "word": 'A domani',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'A domani'?",
        "translation": 'Até amanhã',
        "distractors": ['Bom dia', 'Boa noite', 'Até a próxima semana'],
        "explanation": 'Despedida usada quando o reencontro será no dia seguinte.',
    },
    {
        "word": 'Abbi cura di te',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Abbi cura di te'?",
        "translation": 'Se cuida',
        "distractors": ['Vem cá', 'Espera aí', 'Fica tranquilo'],
        "explanation": 'Despedida amigável, desejando bem-estar à pessoa.',
    },
    {
        "word": 'Buona giornata',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buona giornata'?",
        "translation": 'Tenha um bom dia',
        "distractors": ['Boa sorte', 'Tenha uma boa noite', 'Bom apetite'],
        "explanation": 'Despedida educada usada durante o dia.',
    },
    {
        "word": 'Buonanotte',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buonanotte'?",
        "translation": 'Tenha uma boa noite',
        "distractors": ['Até logo', 'Muito prazer', 'Tenha um bom dia'],
        "explanation": 'Despedida usada à noite, geralmente antes de dormir.',
    },
    {
        "word": 'Addio',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Addio'?",
        "translation": 'Adeus (formal)',
        "distractors": ['Obrigado', 'Com licença', 'Oi (informal)'],
        "explanation": 'Forma mais formal e literária de dizer adeus.',
    },
    {
        "word": 'Ci vediamo dopo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ci vediamo dopo'?",
        "translation": 'Te pego depois',
        "distractors": ['Bom dia para você', 'Nunca te vi antes', 'Com muito prazer'],
        "explanation": 'Despedida bem informal, comum entre amigos.',
    },
    {
        "word": 'A più tardi, ciao!',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'A più tardi, ciao!'?",
        "translation": 'Até mais tarde, tchau!',
        "distractors": ['Com licença, onde fica o banheiro?', 'Meu nome é...', 'Vai com calma'],
        "explanation": 'Combina duas despedidas comuns em sequência.',
    },
    {
        "word": 'Abbi cura di te, a presto',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Abbi cura di te, a presto'?",
        "translation": 'Se cuida, até logo',
        "distractors": ['Com licença, por favor', 'Você pode repetir isso, por favor? Eu não entendo', 'Eu moro em...'],
        "explanation": 'Une duas expressões de despedida amigáveis.',
    },
    {
        "word": 'Grazie',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Grazie'?",
        "translation": 'Obrigado(a)',
        "distractors": ['Desculpa', 'Por favor', 'De nada'],
        "explanation": 'Forma padrão de agradecer em italiano.',
    },
    {
        "word": 'Grazie',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'Grazie'?",
        "translation": 'Obrigado(a) (informal)',
        "distractors": ['Por favor', 'Com licença', 'Adeus'],
        "explanation": 'Mesma palavra usada em contextos formais e informais em italiano.',
    },
    {
        "word": 'Grazie mille',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Grazie mille'?",
        "translation": 'Muito obrigado(a)',
        "distractors": ['Por favor, não', 'Com certeza', 'Sinto muito'],
        "explanation": 'Forma mais enfática de agradecer.',
    },
    {
        "word": 'Molte grazie',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Molte grazie'?",
        "translation": 'Muito obrigado(a) (informal)',
        "distractors": ['Boa sorte', 'Desculpe muito', 'Sem problema'],
        "explanation": 'Forma informal e enfática de agradecer.',
    },
    {
        "word": 'Grazie infinite',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Grazie infinite'?",
        "translation": 'Muitíssimo obrigado(a)',
        "distractors": ['Com licença', 'De jeito nenhum', 'Não se preocupe'],
        "explanation": 'Agradecimento bastante caloroso e enfático.',
    },
    {
        "word": 'Lo apprezzo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Lo apprezzo'?",
        "translation": 'Eu agradeço',
        "distractors": ['Eu sinto muito', 'Eu não sei', 'Eu não quero'],
        "explanation": 'Forma um pouco mais formal de expressar gratidão.',
    },
    {
        "word": 'Grazie per il tuo aiuto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Grazie per il tuo aiuto'?",
        "translation": 'Obrigado pela sua ajuda',
        "distractors": ['Obrigado pela comida', 'Desculpe pelo problema', 'Por favor, me ajude'],
        "explanation": 'Agradecimento específico por uma ajuda recebida.',
    },
    {
        "word": 'Grazie per essere venuto/a',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Grazie per essere venuto/a'?",
        "translation": 'Obrigado por vir',
        "distractors": ['Obrigado por esperar', 'Desculpe por chegar tarde', 'Por favor, entre'],
        "explanation": 'Agradecimento por alguém ter comparecido.',
    },
    {
        "word": 'Grazie infinite per tutto',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Grazie infinite per tutto'?",
        "translation": 'Muito obrigado por tudo',
        "distractors": ['Isso é verdade', 'Eu moro em...', 'Estou confuso(a)'],
        "explanation": "Combina 'grazie infinite' com 'per tutto'.",
    },
    {
        "word": 'Grazie mille, lo apprezzo',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Grazie mille, lo apprezzo'?",
        "translation": 'Muito obrigado, eu agradeço',
        "distractors": ['Eu entendo', 'Sem problema nenhum', 'Muito obrigado por tudo'],
        "explanation": 'Une duas expressões de agradecimento diferentes.',
    },
    {
        "word": 'Prego',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Prego'?",
        "translation": 'De nada',
        "distractors": ['Com licença', 'Muito obrigado', 'Sinto muito'],
        "explanation": 'Resposta padrão a um agradecimento.',
    },
    {
        "word": 'Nessun problema',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Nessun problema'?",
        "translation": 'Sem problema',
        "distractors": ['De jeito nenhum', 'Há um problema', 'Não entendi'],
        "explanation": 'Resposta informal a um agradecimento.',
    },
    {
        "word": 'Non ti preoccupare',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non ti preoccupare'?",
        "translation": 'Não se preocupe',
        "distractors": ['Muito obrigado', 'Estou preocupado', 'Com certeza'],
        "explanation": 'Forma direta de pedir que alguém não se preocupe.',
    },
    {
        "word": 'Tranquillo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Tranquillo'?",
        "translation": 'Tranquilo',
        "distractors": ['Com pressa', 'De jeito nenhum', 'Estou nervoso'],
        "explanation": 'Usado sozinho para tranquilizar alguém, de forma informal.',
    },
    {
        "word": "Non c'è di che",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non c'è di che'?",
        "translation": 'Não há de quê',
        "distractors": ['Fale mais alto', 'Não fale comigo', 'Diga de novo'],
        "explanation": 'Resposta educada indicando que não é necessário agradecer.',
    },
    {
        "word": 'È un piacere (per me)',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'È un piacere (per me)'?",
        "translation": 'É um prazer (para mim)',
        "distractors": ['Sinto muito por isso', 'É um problema meu', 'Não é da minha conta'],
        "explanation": 'Resposta educada e calorosa a um agradecimento.',
    },
    {
        "word": 'Quando vuoi',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Quando vuoi'?",
        "translation": 'Quando quiser',
        "distractors": ['Nunca mais', 'Talvez', 'Às vezes'],
        "explanation": 'Resposta informal indicando disponibilidade futura.',
    },
    {
        "word": 'Certo, nessun problema',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Certo, nessun problema'?",
        "translation": 'Claro, sem problema',
        "distractors": ['Talvez amanhã', 'Desculpe, não posso', 'Não, obrigado'],
        "explanation": 'Resposta afirmativa e tranquila a um pedido ou agradecimento.',
    },
    {
        "word": 'Prego, nessun problema',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Prego, nessun problema'?",
        "translation": 'De nada, sem problema',
        "distractors": ['Bem-vindo de volta', 'Saúde (brinde)', 'Adeus (formal)'],
        "explanation": 'Combina duas respostas comuns a agradecimentos.',
    },
    {
        "word": 'Scusa',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusa'?",
        "translation": 'Desculpa',
        "distractors": ['De nada', 'Obrigado', 'Por favor'],
        "explanation": 'Forma curta e comum de pedir desculpas.',
    },
    {
        "word": 'Mi dispiace',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Mi dispiace'?",
        "translation": 'Eu sinto muito',
        "distractors": ['Eu não sei', 'Eu concordo', 'Eu estou feliz'],
        "explanation": 'Forma completa de pedir desculpas.',
    },
    {
        "word": 'Scusami',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusami'?",
        "translation": 'Desculpa',
        "distractors": ['Vá embora', 'Muito obrigado', 'Boa sorte'],
        "explanation": 'Forma informal de pedir desculpas ou chamar atenção.',
    },
    {
        "word": 'Mi scusi',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Mi scusi'?",
        "translation": 'Com licença',
        "distractors": ['Vá embora', 'Muito obrigado', 'Boa sorte'],
        "explanation": 'Forma formal e educada de pedir licença ou chamar atenção.',
    },
    {
        "word": 'Mi scuso (formale)',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Mi scuso (formale)'?",
        "translation": 'Eu peço desculpas (formal)',
        "distractors": ['Eu agradeço muito', 'Eu concordo totalmente', 'Eu não entendo nada'],
        "explanation": 'Forma mais formal de pedir desculpas.',
    },
    {
        "word": 'Colpa mia',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Colpa mia'?",
        "translation": 'Foi meu erro',
        "distractors": ['Meu prazer', 'Boa ideia', 'Sua vez'],
        "explanation": 'Usado para admitir um erro cometido.',
    },
    {
        "word": 'Mi dispiace tantissimo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Mi dispiace tantissimo'?",
        "translation": 'Sinto muitíssimo',
        "distractors": ['Estou de acordo', 'Estou com pressa', 'Estou muito feliz'],
        "explanation": 'Forma enfática de pedir desculpas.',
    },
    {
        "word": 'Scusa il disturbo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusa il disturbo'?",
        "translation": 'Desculpe incomodar',
        "distractors": ['Vamos comemorar', 'Obrigado por ajudar', 'Prazer em conhecer'],
        "explanation": 'Usado antes de interromper ou pedir algo a alguém.',
    },
    {
        "word": 'Non volevo dire questo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non volevo dire questo'?",
        "translation": 'Eu não quis dizer isso',
        "distractors": ['Eu concordo com você', 'Eu não te conheço', 'Eu quis dizer isso mesmo'],
        "explanation": 'Usado para corrigir algo que soou mal.',
    },
    {
        "word": 'Non era intenzionale',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non era intenzionale'?",
        "translation": 'Não foi intencional',
        "distractors": ['Eu concordo com você', 'Eu fiz de propósito', 'Eu não te conheço'],
        "explanation": 'Usado para explicar que algo não foi proposital.',
    },
    {
        "word": 'Mi dispiace, scusami',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Mi dispiace, scusami'?",
        "translation": 'Desculpe, com licença',
        "distractors": ['Sim, por favor, muito obrigado', 'E aí?', 'Obrigado(a) (informal)'],
        "explanation": 'Combina duas expressões usadas para pedir desculpas educadamente.',
    },
    {
        "word": 'Scusa, è stata colpa mia',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, è stata colpa mia'?",
        "translation": 'Desculpe, foi meu erro',
        "distractors": ['Não se preocupe', 'Qual é o seu nome? Meu nome é Ana', 'Não há de quê'],
        "explanation": "Combina 'scusa' com a admissão de erro 'è stata colpa mia'.",
    },
    {
        "word": 'Va bene',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Va bene'?",
        "translation": 'Está tudo bem',
        "distractors": ['Não está bem', 'Está errado', 'É impossível'],
        "explanation": 'Resposta comum aceitando um pedido de desculpas.',
    },
    {
        "word": 'Va tutto bene',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Va tutto bene'?",
        "translation": 'Está tudo bem',
        "distractors": ['Não é possível', 'Está péssimo', 'Está caro'],
        "explanation": 'Resposta tranquila a um pedido de desculpas.',
    },
    {
        "word": 'Nessun problema per niente',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Nessun problema per niente'?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Há um grande problema', 'Não aceito desculpas', 'Estou muito bravo'],
        "explanation": 'Resposta tranquilizadora e enfática.',
    },
    {
        "word": 'Non ti preoccupare per questo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non ti preoccupare per questo'?",
        "translation": 'Não se preocupe com isso',
        "distractors": ['Pense bastante nisso', 'Fale sobre isso agora', 'Preocupe-se muito com isso'],
        "explanation": 'Resposta usada para tranquilizar alguém após um erro.',
    },
    {
        "word": 'Va bene così',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Va bene così'?",
        "translation": 'Está bem assim',
        "distractors": ['Isso é impossível', 'Isso é caro', 'Isso está errado'],
        "explanation": 'Resposta aceitando algo do jeito que está.',
    },
    {
        "word": 'È giusto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'È giusto'?",
        "translation": 'É justo',
        "distractors": ['Isso é impossível', 'Isso é caro', 'Isso está errado'],
        "explanation": 'Usado para concordar que algo é correto ou adequado.',
    },
    {
        "word": 'Nessun danno fatto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Nessun danno fatto'?",
        "translation": 'Nenhum mal foi feito',
        "distractors": ['Foi um grande problema', 'Isso doeu muito', 'Muito mal foi feito'],
        "explanation": 'Resposta indicando que não houve consequência negativa.',
    },
    {
        "word": 'Succede',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Succede'?",
        "translation": 'Acontece',
        "distractors": ['É impossível', 'Nunca acontece', 'É sua culpa'],
        "explanation": 'Resposta tranquilizadora, indicando que erros são normais.',
    },
    {
        "word": 'Va bene, non ti preoccupare',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Va bene, non ti preoccupare'?",
        "translation": 'Está tudo bem, não se preocupe',
        "distractors": ['Só um momento, por favor', 'Eu discordo', 'São duas horas'],
        "explanation": 'Combina duas expressões que aceitam desculpas e tranquilizam.',
    },
    {
        "word": 'Per favore',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'Per favore'?",
        "translation": 'Por favor',
        "distractors": ['Obrigado', 'De nada', 'Desculpa'],
        "explanation": 'Usado para fazer pedidos de forma educada.',
    },
    {
        "word": 'Potresti, per favore?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Potresti, per favore?'?",
        "translation": 'Você poderia, por favor?',
        "distractors": ['Você sabe disso?', 'Você já fez isso?', 'Você gosta disso?'],
        "explanation": 'Forma educada de fazer um pedido.',
    },
    {
        "word": 'Ti piacerebbe...?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ti piacerebbe...?'?",
        "translation": 'Você gostaria de...?',
        "distractors": ['Você fez...?', 'Você sabe...?', 'Você já tem...?'],
        "explanation": 'Usado para oferecer algo educadamente.',
    },
    {
        "word": 'Dopo di te',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Dopo di te'?",
        "translation": 'Depois de você',
        "distractors": ['Junto comigo', 'Antes de mim', 'Longe de mim'],
        "explanation": 'Expressão educada usada para ceder a vez a alguém.',
    },
    {
        "word": 'Prima tu',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Prima tu'?",
        "translation": 'Primeiro você',
        "distractors": ['Junto comigo', 'Depois de mim', 'Longe de mim'],
        "explanation": 'Usado para convidar alguém a ir primeiro.',
    },
    {
        "word": 'Posso?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Posso?'?",
        "translation": 'Posso?',
        "distractors": ['Eu sei?', 'Eu devo?', 'Eu quero?'],
        "explanation": 'Usado para pedir permissão educadamente.',
    },
    {
        "word": 'Scusami, per favore',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusami, per favore'?",
        "translation": 'Com licença, por favor',
        "distractors": ['Prazer em conhecer', 'De nada, tranquilo', 'Muito obrigado mesmo'],
        "explanation": 'Combinação educada para pedir licença.',
    },
    {
        "word": 'Se non ti dispiace',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Se non ti dispiace'?",
        "translation": 'Se você não se importar',
        "distractors": ['Se você estiver ocupado', 'Se você quiser brigar', 'Se você não gostar'],
        "explanation": 'Usado para suavizar um pedido educadamente.',
    },
    {
        "word": 'Ti dispiacerebbe...?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ti dispiacerebbe...?'?",
        "translation": 'Você se importaria de...?',
        "distractors": ['Você já foi lá?', 'Você tem certeza?', 'Você gostaria de comer?'],
        "explanation": 'Forma educada de pedir algo a alguém.',
    },
    {
        "word": 'È molto gentile da parte tua',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'È molto gentile da parte tua'?",
        "translation": 'Isso é muito gentil da sua parte',
        "distractors": ['Isso é muito estranho', 'Isso é muito difícil', 'Isso é muito caro'],
        "explanation": 'Elogio educado usado para agradecer um gesto gentil.',
    },
    {
        "word": 'Con piacere',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Con piacere'?",
        "translation": 'Com prazer',
        "distractors": ['Com pressa', 'Com raiva', 'Com medo'],
        "explanation": 'Resposta educada indicando disposição em ajudar.',
    },
    {
        "word": 'Chiedo scusa',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Chiedo scusa'?",
        "translation": 'Peço desculpas',
        "distractors": ['Fale mais baixo', 'Espere um pouco', 'Vá embora agora'],
        "explanation": 'Forma educada de pedir desculpas formalmente.',
    },
    {
        "word": 'Scusa se interrompo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusa se interrompo'?",
        "translation": 'Desculpe interromper',
        "distractors": ['Vamos continuar', 'Prazer em conhecer', 'Obrigado por esperar'],
        "explanation": 'Usado antes de interromper alguém educadamente.',
    },
    {
        "word": 'Potresti aiutarmi, per favore?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Potresti aiutarmi, per favore?'?",
        "translation": 'Você poderia me ajudar, por favor?',
        "distractors": ['Tchau', 'Não faço ideia', 'O que isso significa?'],
        "explanation": "Combina 'potresti' com 'per favore' para um pedido educado.",
    },
    {
        "word": 'Scusa, posso chiedere una cosa?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, posso chiedere una cosa?'?",
        "translation": 'Com licença, posso perguntar algo?',
        "distractors": ['São duas horas', 'Eu concordo com você', 'Que pena'],
        "explanation": "Combina 'scusa' com 'posso' para pedir permissão.",
    },
    {
        "word": 'Ti piacerebbe un aiuto?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Ti piacerebbe un aiuto?'?",
        "translation": 'Você gostaria de ajuda?',
        "distractors": ['Você poderia, por favor?', 'Boa sorte, se cuida!', 'Bom dia'],
        "explanation": "Usa 'ti piacerebbe' para oferecer algo de forma educada.",
    },
    {
        "word": 'Sì',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'Sì'?",
        "translation": 'Sim',
        "distractors": ['Nunca', 'Não', 'Talvez'],
        "explanation": 'Resposta afirmativa básica.',
    },
    {
        "word": 'No',
        "part_of_speech": 'palavra',
        "tip": "Cosa significa 'No'?",
        "translation": 'Não',
        "distractors": ['Sim', 'Sempre', 'Claro'],
        "explanation": 'Resposta negativa básica.',
    },
    {
        "word": 'Sì, per favore',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sì, per favore'?",
        "translation": 'Sim, por favor',
        "distractors": ['Não, obrigado', 'Nunca mais', 'Talvez depois'],
        "explanation": 'Resposta afirmativa educada, comum ao aceitar algo.',
    },
    {
        "word": 'No, grazie',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'No, grazie'?",
        "translation": 'Não, obrigado',
        "distractors": ['Com certeza', 'Sim, por favor', 'Claro que sim'],
        "explanation": 'Resposta negativa educada, comum ao recusar algo.',
    },
    {
        "word": 'Certo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Certo'?",
        "translation": 'Claro',
        "distractors": ['De jeito nenhum', 'Nunca', 'Talvez não'],
        "explanation": 'Resposta afirmativa informal e comum.',
    },
    {
        "word": 'Certamente',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Certamente'?",
        "translation": 'Certamente',
        "distractors": ['Talvez amanhã', 'Eu não sei', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa formal e enfática.',
    },
    {
        "word": 'Ovvio',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ovvio'?",
        "translation": 'Óbvio',
        "distractors": ['Talvez amanhã', 'Eu não sei', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa informal, usada quando algo é evidente.',
    },
    {
        "word": 'Non proprio',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non proprio'?",
        "translation": 'Não exatamente',
        "distractors": ['Muito obrigado', 'Sempre é assim', 'Com certeza sim'],
        "explanation": 'Resposta que corrige suavemente uma afirmação.',
    },
    {
        "word": 'Non tanto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non tanto'?",
        "translation": 'Não muito',
        "distractors": ['Muito obrigado', 'Sempre é assim', 'Com certeza sim'],
        "explanation": 'Resposta que suaviza uma negação.',
    },
    {
        "word": 'Penso di sì',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Penso di sì'?",
        "translation": 'Eu acho que sim',
        "distractors": ['Eu não me importo', 'Eu nunca soube disso', 'Eu tenho certeza que não'],
        "explanation": 'Resposta afirmativa com certo grau de incerteza.',
    },
    {
        "word": 'Penso di no',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Penso di no'?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu adoro isso', 'Com certeza absoluta', 'Eu tenho certeza que sim'],
        "explanation": 'Resposta negativa com certo grau de incerteza.',
    },
    {
        "word": 'Forse',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Forse'?",
        "translation": 'Talvez',
        "distractors": ['Com certeza', 'Sempre', 'Nunca'],
        "explanation": 'Resposta indicando incerteza.',
    },
    {
        "word": 'Sicuramente',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sicuramente'?",
        "translation": 'Certamente',
        "distractors": ['Eu não sei', 'De jeito nenhum', 'Talvez não'],
        "explanation": 'Resposta afirmativa enfática, usada para confirmar algo.',
    },
    {
        "word": 'Decisamente',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Decisamente'?",
        "translation": 'Definitivamente',
        "distractors": ['Eu não sei', 'De jeito nenhum', 'Talvez não'],
        "explanation": 'Resposta afirmativa muito enfática.',
    },
    {
        "word": 'Assolutamente no',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Assolutamente no'?",
        "translation": 'De jeito nenhum',
        "distractors": ['Eu acho que sim', 'Talvez sim', 'Com certeza sim'],
        "explanation": 'Resposta negativa muito enfática.',
    },
    {
        "word": "Immagino di sì (un po' incerto)",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Immagino di sì (un po' incerto)'?",
        "translation": 'Eu acho que sim (meio incerto)',
        "distractors": ['Eu tenho certeza absoluta', 'Eu nunca faria isso', 'Isso é impossível'],
        "explanation": 'Resposta afirmativa hesitante, informal.',
    },
    {
        "word": 'Sì, certo che posso',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Sì, certo che posso'?",
        "translation": 'Sim, claro que posso',
        "distractors": ['Só um momento, por favor', 'Desculpe, eu não entendo', 'Muito obrigado(a)'],
        "explanation": "Combina 'sì' com 'certo' para uma resposta afirmativa forte.",
    },
    {
        "word": 'No, penso di no',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'No, penso di no'?",
        "translation": 'Não, eu acho que não',
        "distractors": ['Só um momento, por favor', 'Vai com calma', 'Está tudo bem, não se preocupe, sem problema'],
        "explanation": "Combina 'no' com 'penso di no' para suavizar a negação.",
    },
    {
        "word": 'Capisco',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Capisco'?",
        "translation": 'Eu entendo',
        "distractors": ['Eu não entendo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para indicar que algo foi compreendido.',
    },
    {
        "word": 'Non capisco',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non capisco'?",
        "translation": 'Eu não entendo',
        "distractors": ['Eu concordo', 'Eu sei disso', 'Eu entendo tudo'],
        "explanation": 'Usado para indicar que algo não foi compreendido.',
    },
    {
        "word": 'Ho capito',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ho capito'?",
        "translation": 'Entendi',
        "distractors": ['Eu discordo', 'Eu esqueci tudo', 'Eu não vejo nada'],
        "explanation": 'Expressão comum para indicar compreensão.',
    },
    {
        "word": 'Vedo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Vedo'?",
        "translation": 'Vejo',
        "distractors": ['Eu discordo', 'Eu esqueci tudo', 'Eu não vejo nada'],
        "explanation": "Usado sozinho, de forma informal, pra indicar compreensão (como 'ah, entendi').",
    },
    {
        "word": 'Puoi ripeterlo?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Puoi ripeterlo?'?",
        "translation": 'Você pode repetir isso?',
        "distractors": ['Você pode parar agora?', 'Você pode ir embora?', 'Você pode me ajudar?'],
        "explanation": 'Usado para pedir que algo seja dito novamente.',
    },
    {
        "word": 'Puoi parlare lentamente?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Puoi parlare lentamente?'?",
        "translation": 'Você pode falar devagar?',
        "distractors": ['Você pode falar rápido?', 'Você pode parar de falar?', 'Você pode falar baixo?'],
        "explanation": 'Pedido comum para facilitar a compreensão.',
    },
    {
        "word": 'Cosa significa?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Cosa significa?'?",
        "translation": 'O que isso significa?',
        "distractors": ['Onde isso está?', 'Quem fez isso?', 'Quando isso ocorre?'],
        "explanation": 'Pergunta usada para pedir o significado de algo.',
    },
    {
        "word": 'Non ne ho idea',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non ne ho idea'?",
        "translation": 'Não faço ideia',
        "distractors": ['Eu sei exatamente', 'Eu concordo totalmente', 'Eu tenho certeza'],
        "explanation": 'Expressão usada quando não se sabe algo.',
    },
    {
        "word": 'Scusa, non ho capito',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Scusa, non ho capito'?",
        "translation": 'Desculpe, não entendi isso',
        "distractors": ['Desculpe, eu entendi tudo', 'Obrigado, ficou claro', 'Com certeza eu sei'],
        "explanation": 'Usado educadamente quando algo não foi compreendido.',
    },
    {
        "word": 'Potresti spiegarlo?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Potresti spiegarlo?'?",
        "translation": 'Você poderia explicar isso?',
        "distractors": ['Você poderia parar isso?', 'Você poderia comprar isso?', 'Você poderia esquecer isso?'],
        "explanation": 'Pedido educado de explicação.',
    },
    {
        "word": 'Ora è chiaro',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ora è chiaro'?",
        "translation": 'Agora está claro',
        "distractors": ['Isso é impossível', 'Isso está errado', 'Ainda não está claro'],
        "explanation": 'Usado após entender algo que antes era confuso.',
    },
    {
        "word": 'Sono confuso/a',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sono confuso/a'?",
        "translation": 'Estou confuso(a)',
        "distractors": ['Estou com pressa', 'Estou tranquilo', 'Estou feliz'],
        "explanation": 'Usado para expressar confusão ou falta de clareza.',
    },
    {
        "word": 'Cosa hai detto?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Cosa hai detto?'?",
        "translation": 'O que você disse?',
        "distractors": ['Quando você vem?', 'Onde você está?', 'Quem disse isso?'],
        "explanation": 'Pergunta usada quando não se ouviu ou entendeu algo.',
    },
    {
        "word": 'Scusa, puoi ripeterlo, per favore?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, puoi ripeterlo, per favore?'?",
        "translation": 'Desculpe, você pode repetir isso, por favor?',
        "distractors": ['Com licença, por favor', 'Olá, bom dia, como você está?', 'Por favor, entre'],
        "explanation": "Combina 'scusa' com o pedido 'puoi ripeterlo'.",
    },
    {
        "word": 'Non capisco, puoi aiutarmi?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Non capisco, puoi aiutarmi?'?",
        "translation": 'Eu não entendo, você pode ajudar?',
        "distractors": ['Talvez', 'Obrigado(a) (informal)', 'Você poderia me ajudar, por favor?'],
        "explanation": 'Une a falta de compreensão a um pedido de ajuda.',
    },
    {
        "word": 'Potresti parlare lentamente, per favore?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Potresti parlare lentamente, per favore?'?",
        "translation": 'Você poderia falar devagar, por favor?',
        "distractors": ['Você está certo(a)', 'Não há de quê', 'Nem eu'],
        "explanation": "Combina 'potresti' com 'parlare lentamente' e 'per favore'.",
    },
    {
        "word": "Sono d'accordo",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sono d'accordo'?",
        "translation": 'Eu concordo',
        "distractors": ['Eu discordo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para expressar concordância.',
    },
    {
        "word": "Non sono d'accordo",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non sono d'accordo'?",
        "translation": 'Eu discordo',
        "distractors": ['Eu concordo', 'Eu entendo', 'Eu gosto'],
        "explanation": 'Usado para expressar discordância.',
    },
    {
        "word": 'È vero',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'È vero'?",
        "translation": 'Isso é verdade',
        "distractors": ['Isso é estranho', 'Isso é caro', 'Isso é falso'],
        "explanation": 'Usado para confirmar que algo é verdadeiro.',
    },
    {
        "word": 'Non è vero',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non è vero'?",
        "translation": 'Isso não é verdade',
        "distractors": ['Isso é fácil', 'Isso é verdade', 'Isso é interessante'],
        "explanation": 'Usado para negar que algo é verdadeiro.',
    },
    {
        "word": 'Hai ragione',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Hai ragione'?",
        "translation": 'Você está certo(a)',
        "distractors": ['Você está errado', 'Você está cansado', 'Você está atrasado'],
        "explanation": 'Usado para concordar com o que alguém disse.',
    },
    {
        "word": 'Hai torto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Hai torto'?",
        "translation": 'Você está errado(a)',
        "distractors": ['Você está certo', 'Você está bem', 'Você está pronto'],
        "explanation": 'Usado para discordar do que alguém disse.',
    },
    {
        "word": 'Esattamente',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Esattamente'?",
        "translation": 'Exatamente',
        "distractors": ['Talvez', 'De jeito nenhum', 'Eu não sei'],
        "explanation": 'Usado para concordar fortemente com algo.',
    },
    {
        "word": 'Non credo',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non credo'?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu tenho certeza que sim', 'Com certeza absoluta', 'Eu concordo plenamente'],
        "explanation": 'Usado para discordar de forma suave.',
    },
    {
        "word": "Anch'io",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Anch'io'?",
        "translation": 'Eu também',
        "distractors": ['Eu não', 'Nunca', 'Nem eu'],
        "explanation": 'Usado para concordar dizendo que a mesma coisa se aplica a você.',
    },
    {
        "word": 'Nemmeno io',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Nemmeno io'?",
        "translation": 'Nem eu',
        "distractors": ['Eu também', 'Sempre eu', 'Eu sim'],
        "explanation": 'Usado para concordar com uma afirmação negativa.',
    },
    {
        "word": 'Non sono sicuro/a',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Non sono sicuro/a'?",
        "translation": 'Eu não tenho certeza',
        "distractors": ['Eu concordo totalmente', 'Eu discordo totalmente', 'Eu tenho certeza absoluta'],
        "explanation": 'Usado para expressar incerteza diante de uma opinião.',
    },
    {
        "word": 'Ha senso',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ha senso'?",
        "translation": 'Faz sentido',
        "distractors": ['Isso é impossível', 'Isso é injusto', 'Isso é errado'],
        "explanation": 'Usado para aceitar um argumento ou explicação.',
    },
    {
        "word": "Sono d'accordo con te",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Sono d'accordo con te'?",
        "translation": 'Eu concordo com você',
        "distractors": ['Olá', 'Desculpe, eu não entendo', 'Posso?'],
        "explanation": "Combina 'sono d'accordo' com 'con te'.",
    },
    {
        "word": "Non sono d'accordo, scusa",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Non sono d'accordo, scusa'?",
        "translation": 'Eu discordo, desculpe',
        "distractors": ['Tenha uma boa viagem', 'Desculpe, foi meu erro, com licença', 'Desculpa'],
        "explanation": "Une 'non sono d'accordo' com um pedido de desculpas educado.",
    },
    {
        "word": "Hai ragione, sono d'accordo",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Hai ragione, sono d'accordo'?",
        "translation": 'Você está certo, eu concordo',
        "distractors": ['Melhoras', 'Obrigado(a)', 'Qual é o seu nome? Meu nome é Ana'],
        "explanation": "Combina 'hai ragione' com 'sono d'accordo' para reforçar a concordância.",
    },
    {
        "word": 'Congratulazioni',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Congratulazioni'?",
        "translation": 'Parabéns',
        "distractors": ['Boa sorte', 'De nada', 'Sinto muito'],
        "explanation": 'Usado para parabenizar alguém.',
    },
    {
        "word": 'Buona fortuna',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buona fortuna'?",
        "translation": 'Boa sorte',
        "distractors": ['Bem-vindo', 'Parabéns', 'Desculpa'],
        "explanation": 'Usado para desejar sorte a alguém.',
    },
    {
        "word": 'Buon compleanno',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buon compleanno'?",
        "translation": 'Feliz aniversário',
        "distractors": ['Parabéns pelo trabalho', 'Bem-vindo', 'Boa sorte'],
        "explanation": 'Expressão usada para celebrar o aniversário de alguém.',
    },
    {
        "word": 'Salute (dopo lo starnuto)',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Salute (dopo lo starnuto)'?",
        "translation": 'Saúde (após espirro)',
        "distractors": ['Bom apetite', 'Parabéns', 'Boa sorte'],
        "explanation": 'Dito educadamente quando alguém espirra.',
    },
    {
        "word": 'Salute',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Salute'?",
        "translation": 'Saúde',
        "distractors": ['Adeus para sempre', 'Com licença', 'Sinto muito'],
        "explanation": 'Usado como brinde, ao levantar o copo.',
    },
    {
        "word": 'Cin cin',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Cin cin'?",
        "translation": 'Tim-tim',
        "distractors": ['Adeus para sempre', 'Com licença', 'Sinto muito'],
        "explanation": 'Expressão informal e sonora usada ao brindar, tocando os copos.',
    },
    {
        "word": 'Buon appetito',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buon appetito'?",
        "translation": 'Bom apetite',
        "distractors": ['Boa viagem', 'Bom trabalho', 'Boa sorte'],
        "explanation": 'Dito antes de alguém começar a comer.',
    },
    {
        "word": 'Buon viaggio',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Buon viaggio'?",
        "translation": 'Tenha uma boa viagem',
        "distractors": ['Feliz aniversário', 'Boa sorte no trabalho', 'Bom apetite'],
        "explanation": 'Dito antes de alguém viajar.',
    },
    {
        "word": 'Guarisci presto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Guarisci presto'?",
        "translation": 'Melhoras',
        "distractors": ['Parabéns', 'Boa sorte', 'Bom apetite'],
        "explanation": 'Desejo de melhora para alguém doente.',
    },
    {
        "word": 'Bentornato/a',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Bentornato/a'?",
        "translation": 'Bem-vindo de volta',
        "distractors": ['Sinto muito', 'Boa viagem', 'Até logo'],
        "explanation": 'Usado ao receber alguém que retornou.',
    },
    {
        "word": 'Fai come se fossi a casa tua',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Fai come se fossi a casa tua'?",
        "translation": 'Fique à vontade',
        "distractors": ['Espere lá fora', 'Fique de pé', 'Vá embora agora'],
        "explanation": 'Usado para deixar um convidado confortável.',
    },
    {
        "word": 'Qui è bello',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Qui è bello'?",
        "translation": 'Aqui é bonito',
        "distractors": ['Aqui é longe', 'Aqui é caro', 'Aqui é ruim'],
        "explanation": 'Comentário positivo simples sobre um lugar.',
    },
    {
        "word": 'carino',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'carino'?",
        "translation": 'Bonitinho',
        "distractors": ['Longe', 'Caro', 'Ruim'],
        "explanation": 'Adjetivo informal usado para algo ou alguém agradável e fofo.',
    },
    {
        "word": 'Che bello!',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Che bello!'?",
        "translation": 'Que lindo!',
        "distractors": ['Isso é estranho!', 'Isso é difícil!', 'Isso é péssimo!'],
        "explanation": 'Expressão de entusiasmo diante de algo bonito.',
    },
    {
        "word": 'Fantastico!',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Fantastico!'?",
        "translation": 'Fantástico!',
        "distractors": ['Isso é estranho!', 'Isso é difícil!', 'Isso é péssimo!'],
        "explanation": 'Expressão de entusiasmo positivo, usada como elogio geral.',
    },
    {
        "word": 'Che peccato',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Che peccato'?",
        "translation": 'Que pena',
        "distractors": ['Que ótimo', 'Que engraçado', 'Que legal'],
        "explanation": 'Expressão de pesar ou decepção.',
    },
    {
        "word": 'Che peccato',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Che peccato'?",
        "translation": 'Que pena',
        "distractors": ['Que sorte', 'Que orgulho', 'Que alegria'],
        "explanation": 'Expressão usada para lamentar algo.',
    },
    {
        "word": 'Divertiti',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Divertiti'?",
        "translation": 'Divirta-se',
        "distractors": ['Tenha paciência', 'Tenha cuidado', 'Tenha sorte'],
        "explanation": 'Dito antes de alguém sair para se divertir.',
    },
    {
        "word": 'Vacci piano',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Vacci piano'?",
        "translation": 'Vai com calma',
        "distractors": ['Corre rápido', 'Trabalhe mais', 'Fique bravo'],
        "explanation": 'Usado para pedir que alguém desacelere ou tenha cautela.',
    },
    {
        "word": 'Rilassati',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Rilassati'?",
        "translation": 'Relaxa',
        "distractors": ['Corre rápido', 'Trabalhe mais', 'Fique bravo'],
        "explanation": 'Imperativo direto usado para pedir que alguém fique tranquilo.',
    },
    {
        "word": 'Anche a te',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Anche a te'?",
        "translation": 'A você também',
        "distractors": ['De jeito nenhum', 'Nunca mais', 'Ao contrário'],
        "explanation": "Usado para devolver um desejo bom de forma direta, ex.: 'boa sorte' -> 'anche a te'.",
    },
    {
        "word": 'Altrettanto',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Altrettanto'?",
        "translation": 'Igualmente',
        "distractors": ['De jeito nenhum', 'Nunca mais', 'Ao contrário'],
        "explanation": 'Forma mais formal de devolver um desejo bom a alguém.',
    },
    {
        "word": 'Ben fatto!',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ben fatto!'?",
        "translation": 'Bem feito!',
        "distractors": ['Que pena!', 'Cuidado!', 'Sinto muito!'],
        "explanation": 'Elogio direto por algo bem executado.',
    },
    {
        "word": 'Bravo!',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Bravo!'?",
        "translation": 'Bravo!',
        "distractors": ['Que pena!', 'Cuidado!', 'Sinto muito!'],
        "explanation": 'Elogio curto e informal, igual ao usado em português.',
    },
    {
        "word": 'Buon compleanno, divertiti!',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Buon compleanno, divertiti!'?",
        "translation": 'Feliz aniversário, divirta-se!',
        "distractors": ['Com licença, posso perguntar algo?', 'Desculpe, estou atrasado(a)', 'Tenha uma boa viagem'],
        "explanation": "Combina 'buon compleanno' com 'divertiti'.",
    },
    {
        "word": 'Buona fortuna, abbi cura di te!',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Buona fortuna, abbi cura di te!'?",
        "translation": 'Boa sorte, se cuida!',
        "distractors": ['Você pode me ajudar?', 'Sinto muitíssimo', 'Não se preocupe'],
        "explanation": "Combina 'buona fortuna' com 'abbi cura di te'.",
    },
    {
        "word": 'Come ti chiami?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Come ti chiami?'?",
        "translation": 'Qual é o seu nome?',
        "distractors": ['Quantos anos você tem?', 'Onde você mora?', 'De onde você é?'],
        "explanation": 'Pergunta básica para saber o nome de alguém.',
    },
    {
        "word": 'Mi chiamo...',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Mi chiamo...'?",
        "translation": 'Meu nome é...',
        "distractors": ['Eu sou de...', 'Eu tenho... anos', 'Eu moro em...'],
        "explanation": 'Resposta usada para dizer o próprio nome.',
    },
    {
        "word": 'Quanti anni hai?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Quanti anni hai?'?",
        "translation": 'Quantos anos você tem?',
        "distractors": ['Onde você mora?', 'Qual é o seu nome?', 'O que você faz?'],
        "explanation": 'Pergunta básica sobre idade.',
    },
    {
        "word": 'Ho ... anni',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Ho ... anni'?",
        "translation": 'Eu tenho ... anos',
        "distractors": ['Eu me chamo ...', 'Eu moro em ...', 'Eu sou de ...'],
        "explanation": 'Resposta usada para dizer a idade.',
    },
    {
        "word": 'Di dove sei?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Di dove sei?'?",
        "translation": 'De onde você é?',
        "distractors": ['O que você quer?', 'Quando você chega?', 'Como você está?'],
        "explanation": 'Pergunta sobre origem/nacionalidade.',
    },
    {
        "word": 'Sono del Brasile',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sono del Brasile'?",
        "translation": 'Eu sou do Brasil',
        "distractors": ['Eu moro perto', 'Eu gosto do Brasil', 'Eu vou ao Brasil'],
        "explanation": 'Resposta comum indicando o país de origem.',
    },
    {
        "word": 'Dove abiti?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Dove abiti?'?",
        "translation": 'Onde você mora?',
        "distractors": ['Como você vive?', 'Quando você chega?', 'Por que você mora aqui?'],
        "explanation": 'Pergunta básica sobre local de moradia.',
    },
    {
        "word": 'Abito a...',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Abito a...'?",
        "translation": 'Eu moro em...',
        "distractors": ['Eu vou a...', 'Eu gosto de...', 'Eu nasci em...'],
        "explanation": 'Resposta usada para dizer o local de moradia.',
    },
    {
        "word": 'Che lavoro fai?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Che lavoro fai?'?",
        "translation": 'O que você faz? (profissão)',
        "distractors": ['O que você quer?', 'Quando você trabalha?', 'Onde você está?'],
        "explanation": 'Pergunta comum sobre a profissão de alguém.',
    },
    {
        "word": 'Che ore sono?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Che ore sono?'?",
        "translation": 'Que horas são?',
        "distractors": ['Onde você está?', 'Que dia é hoje?', 'Quem é você?'],
        "explanation": 'Pergunta básica sobre o horário.',
    },
    {
        "word": 'Sono le due',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Sono le due'?",
        "translation": 'São duas horas',
        "distractors": ['É a sala dois', 'São duas pessoas', 'É o dia dois'],
        "explanation": 'Resposta comum indicando horário.',
    },
    {
        "word": 'Quanto costa?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Quanto costa?'?",
        "translation": 'Quanto custa?',
        "distractors": ['Onde fica?', 'Quantos são?', 'Quando é?'],
        "explanation": 'Pergunta comum sobre preço.',
    },
    {
        "word": "Dov'è il bagno?",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Dov'è il bagno?'?",
        "translation": 'Onde fica o banheiro?',
        "distractors": ['Onde fica a escola?', 'Onde fica o hotel?', 'Onde fica a saída?'],
        "explanation": 'Pergunta prática muito comum ao viajar.',
    },
    {
        "word": 'Puoi aiutarmi?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Puoi aiutarmi?'?",
        "translation": 'Você pode me ajudar?',
        "distractors": ['Você pode me ver?', 'Você pode me ouvir?', 'Você pode me pagar?'],
        "explanation": 'Pedido básico de ajuda.',
    },
    {
        "word": "Cos'è questo?",
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Cos'è questo?'?",
        "translation": 'O que é isso?',
        "distractors": ['Quando é isso?', 'Quem é este?', 'Onde está isso?'],
        "explanation": 'Pergunta básica sobre um objeto.',
    },
    {
        "word": 'Chi è quello/a?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Chi è quello/a?'?",
        "translation": 'Quem é aquele(a)?',
        "distractors": ['O que é aquilo?', 'Como está aquilo?', 'Onde está aquilo?'],
        "explanation": 'Pergunta básica sobre uma pessoa.',
    },
    {
        "word": 'Perché?',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Perché?'?",
        "translation": 'Por quê?',
        "distractors": ['Onde?', 'Quem?', 'Quando?'],
        "explanation": 'Pergunta básica pedindo uma razão.',
    },
    {
        "word": 'Perché',
        "part_of_speech": 'expressão',
        "tip": "Cosa significa 'Perché'?",
        "translation": 'Porque',
        "distractors": ['Quando', 'Onde', 'Quem'],
        "explanation": 'Usado para dar uma razão ou explicação.',
    },
    {
        "word": 'Come ti chiami? Mi chiamo Ana',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Come ti chiami? Mi chiamo Ana'?",
        "translation": 'Qual é o seu nome? Meu nome é Ana',
        "distractors": ['Entendi', 'Desculpe, foi meu erro, com licença', 'É um prazer (para mim)'],
        "explanation": 'Combina a pergunta e a resposta básica sobre nome.',
    },
    {
        "word": 'Di dove sei? Sono del Brasile',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Di dove sei? Sono del Brasile'?",
        "translation": 'De onde você é? Eu sou do Brasil',
        "distractors": ['Vai com calma', 'Que pena', 'Olá'],
        "explanation": 'Combina pergunta e resposta sobre origem/nacionalidade.',
    },
    {
        "word": 'Grazie mille davvero',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Grazie mille davvero'?",
        "translation": 'Muito obrigado mesmo',
        "distractors": ['Com certeza não', 'Sinto muito mesmo', 'De jeito nenhum mesmo'],
        "explanation": 'Combinação enfática de agradecimento.',
    },
    {
        "word": 'Mi dispiace, sono in ritardo',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Mi dispiace, sono in ritardo'?",
        "translation": 'Desculpe, estou atrasado(a)',
        "distractors": ['Obrigado, estou pronto', 'Com licença, estou aqui', 'Desculpe, estou cedo'],
        "explanation": 'Combinação comum ao chegar atrasado.',
    },
    {
        "word": 'Prego, entra',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Prego, entra'?",
        "translation": 'Por favor, entre',
        "distractors": ['Por favor, saia', 'Por favor, sente', 'Por favor, espere'],
        "explanation": 'Combinação usada para convidar alguém a entrar.',
    },
    {
        "word": 'Per favore, siediti',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Per favore, siediti'?",
        "translation": 'Por favor, sente-se',
        "distractors": ['Por favor, levante-se', 'Por favor, saia', 'Por favor, corra'],
        "explanation": 'Combinação usada para convidar alguém a se sentar.',
    },
    {
        "word": 'Per favore, aspetta un momento',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Per favore, aspetta un momento'?",
        "translation": 'Por favor, espere um momento',
        "distractors": ['Por favor, fique calado', 'Por favor, corra rápido', 'Por favor, vá agora'],
        "explanation": 'Combinação usada para pedir paciência.',
    },
    {
        "word": 'Sì, certo',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Sì, certo'?",
        "translation": 'Sim, claro',
        "distractors": ['Nunca, impossível', 'Não, de jeito nenhum', 'Talvez, não sei'],
        "explanation": 'Combinação afirmativa muito comum.',
    },
    {
        "word": 'No, grazie',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'No, grazie'?",
        "translation": 'Não, obrigado',
        "distractors": ['Claro que sim', 'Com certeza', 'Sim, por favor'],
        "explanation": 'Combinação usada para recusar educadamente.',
    },
    {
        "word": 'Scusa, mi scusi',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Scusa, mi scusi'?",
        "translation": 'Desculpe, com licença',
        "distractors": ['Prazer, igualmente', 'Tchau, até logo', 'Obrigado, de nada'],
        "explanation": 'Combinação comum ao pedir passagem educadamente.',
    },
    {
        "word": 'Ciao di nuovo',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Ciao di nuovo'?",
        "translation": 'Olá de novo',
        "distractors": ['Com licença agora', 'Tchau para sempre', 'Muito obrigado'],
        "explanation": 'Combinação usada ao reencontrar alguém no mesmo dia.',
    },
    {
        "word": 'Ci vediamo in giro',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Ci vediamo in giro'?",
        "translation": 'Nos vemos por aí',
        "distractors": ['Nunca mais te vejo', 'Muito prazer nisso', 'Bom dia para você'],
        "explanation": 'Despedida informal e casual.',
    },
    {
        "word": 'Bello vederti',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Bello vederti'?",
        "translation": 'Bom te ver',
        "distractors": ['Difícil te ver', 'Ruim te ver', 'Estranho te ver'],
        "explanation": 'Combinação amigável usada ao encontrar alguém.',
    },
    {
        "word": 'È stato bello parlare con te',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'È stato bello parlare con te'?",
        "translation": 'Foi bom falar com você',
        "distractors": ['Foi ruim falar com você', 'Não gostei de falar', 'Não quero falar mais'],
        "explanation": 'Combinação usada ao encerrar uma conversa agradável.',
    },
    {
        "word": 'Un momento, per favore',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Un momento, per favore'?",
        "translation": 'Só um momento, por favor',
        "distractors": ['Nunca mais espere', 'Corra rapidamente', 'Vá agora mesmo'],
        "explanation": 'Combinação usada para pedir uma pequena espera.',
    },
    {
        "word": 'Nessun problema',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Nessun problema'?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Impossível de resolver', 'Muito complicado', 'Um grande problema'],
        "explanation": 'Combinação informal usada como resposta tranquilizadora.',
    },
    {
        "word": 'Va bene allora',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Va bene allora'?",
        "translation": 'Tudo bem então',
        "distractors": ['Tudo errado então', 'Impossível assim', 'Nada bem assim'],
        "explanation": 'Combinação usada para concordar ou aceitar algo.',
    },
    {
        "word": 'Ok, mi sembra buono',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Ok, mi sembra buono'?",
        "translation": 'Ok, parece bom',
        "distractors": ['Não, parece ruim', 'Talvez, parece estranho', 'Nunca, parece caro'],
        "explanation": 'Combinação informal de concordância positiva.',
    },
    {
        "word": 'Subito',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Subito'?",
        "translation": 'Já',
        "distractors": ['Nunca', 'Talvez amanhã', 'Mais tarde'],
        "explanation": 'Advérbio curto e informal para algo imediato.',
    },
    {
        "word": 'Immediatamente',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Immediatamente'?",
        "translation": 'Imediatamente',
        "distractors": ['Nunca', 'Talvez amanhã', 'Mais tarde'],
        "explanation": 'Advérbio formal, cognato do português, para algo imediato.',
    },
    {
        "word": 'Per sicurezza',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Per sicurezza'?",
        "translation": 'Por segurança',
        "distractors": ['Sem motivo nenhum', 'Nunca mais', 'De qualquer jeito ruim'],
        "explanation": 'Usado para justificar uma precaução.',
    },
    {
        "word": 'Nel caso',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'Nel caso'?",
        "translation": 'Caso',
        "distractors": ['Sem motivo nenhum', 'Nunca mais', 'De qualquer jeito ruim'],
        "explanation": "Usado para introduzir uma condição hipotética, como 'caso precise'.",
    },
    {
        "word": 'A proposito',
        "part_of_speech": 'chunk',
        "tip": "Cosa significa 'A proposito'?",
        "translation": 'A propósito',
        "distractors": ['No final das contas', 'De jeito nenhum', 'Ao contrário disso'],
        "explanation": 'Combinação usada para introduzir um novo assunto.',
    },
    {
        "word": 'Ciao, mi chiamo Ana, piacere di conoscerti',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Ciao, mi chiamo Ana, piacere di conoscerti'?",
        "translation": 'Oi, meu nome é Ana, prazer em te conhecer',
        "distractors": ['São duas horas', 'Claro', 'Feliz aniversário'],
        "explanation": 'Combina saudação, apresentação de nome e cortesia.',
    },
    {
        "word": 'Buongiorno, come stai oggi?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Buongiorno, come stai oggi?'?",
        "translation": 'Bom dia, como você está hoje?',
        "distractors": ['Boa noite (ao chegar)', 'Obrigado(a) (informal)', 'Não, eu acho que não'],
        "explanation": 'Une a saudação matinal com a pergunta sobre o estado da pessoa.',
    },
    {
        "word": 'Mi dispiace, non capisco',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Mi dispiace, non capisco'?",
        "translation": 'Desculpe, eu não entendo',
        "distractors": ['Sim', 'Acontece', 'Bom dia a todos'],
        "explanation": 'Combina o pedido de desculpas com a falta de compreensão.',
    },
    {
        "word": 'Scusa, puoi aiutarmi, per favore?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, puoi aiutarmi, per favore?'?",
        "translation": 'Com licença, você pode me ajudar, por favor?',
        "distractors": ['Acontece', 'Quantos anos você tem?', 'Se cuida'],
        "explanation": "Combina 'scusa' com o pedido de ajuda educado.",
    },
    {
        "word": 'Grazie infinite, sei molto gentile',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Grazie infinite, sei molto gentile'?",
        "translation": 'Muito obrigado, você é muito gentil',
        "distractors": ['Tenha um bom dia', 'Prazer em te conhecer, qual é o seu nome?', 'Boa sorte'],
        "explanation": 'Combina agradecimento enfático com um elogio de cortesia.',
    },
    {
        "word": 'Piacere di conoscerti, come ti chiami?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Piacere di conoscerti, come ti chiami?'?",
        "translation": 'Prazer em te conhecer, qual é o seu nome?',
        "distractors": ['Até mais tarde', 'Sim, por favor, muito obrigado', 'Que pena'],
        "explanation": 'Combina a apresentação com a pergunta pelo nome.',
    },
    {
        "word": "Sono d'accordo con te, è vero",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Sono d'accordo con te, è vero'?",
        "translation": 'Eu concordo com você, isso é verdade',
        "distractors": ['Olá, bom dia, como você está?', 'Eu agradeço', 'Sim, claro'],
        "explanation": 'Une concordância com confirmação de veracidade.',
    },
    {
        "word": "Scusa, non sono d'accordo con questo",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, non sono d'accordo con questo'?",
        "translation": 'Desculpe, eu não concordo com isso',
        "distractors": ['Eu discordo, desculpe', 'Mandou bem!', 'Quando quiser'],
        "explanation": 'Combina desculpa com discordância educada.',
    },
    {
        "word": "Scusa, dov'è il bagno?",
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Scusa, dov'è il bagno?'?",
        "translation": 'Com licença, onde fica o banheiro?',
        "distractors": ['Posso?', 'Que pena', 'Onde fica o banheiro?'],
        "explanation": "Combina 'scusa' com a pergunta prática de localização.",
    },
    {
        "word": 'Puoi ripeterlo, per favore? Non capisco',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Puoi ripeterlo, per favore? Non capisco'?",
        "translation": 'Você pode repetir isso, por favor? Eu não entendo',
        "distractors": ['Eu concordo', 'Desculpe, foi meu erro', 'Vai com calma'],
        "explanation": 'Une o pedido de repetição com a explicação da dúvida.',
    },
    {
        "word": 'Va bene, non ti preoccupare, nessun problema',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Va bene, non ti preoccupare, nessun problema'?",
        "translation": 'Está tudo bem, não se preocupe, sem problema',
        "distractors": ['Boa sorte hoje, se cuida, até logo', 'Com licença, você pode me ajudar, por favor?', 'Sem problema nenhum'],
        "explanation": 'Reforça a tranquilização combinando três expressões parecidas.',
    },
    {
        "word": 'Buona fortuna oggi, abbi cura di te, a presto',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Buona fortuna oggi, abbi cura di te, a presto'?",
        "translation": 'Boa sorte hoje, se cuida, até logo',
        "distractors": ['Desculpe incomodar', 'A propósito', 'Não'],
        "explanation": 'Combina três expressões sociais de despedida positiva.',
    },
    {
        "word": 'Sì, per favore, grazie mille',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Sì, per favore, grazie mille'?",
        "translation": 'Sim, por favor, muito obrigado',
        "distractors": ['Agora está claro', 'Olá de novo', 'Por favor, sente-se'],
        "explanation": 'Combina aceitação educada com agradecimento enfático.',
    },
    {
        "word": 'Mi dispiace, è stata colpa mia, scusami',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Mi dispiace, è stata colpa mia, scusami'?",
        "translation": 'Desculpe, foi meu erro, com licença',
        "distractors": ['Entendi', 'Você está certo(a)', 'Fique à vontade'],
        "explanation": 'Combina desculpa, admissão de erro e pedido de licença.',
    },
    {
        "word": 'Ciao, buongiorno, come stai?',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Ciao, buongiorno, come stai?'?",
        "translation": 'Olá, bom dia, como você está?',
        "distractors": ['Eu acho que não', 'Muito obrigado(a) (informal)', 'Por favor'],
        "explanation": 'Une duas saudações com a pergunta padrão sobre o estado da pessoa.',
    },
    {
        "word": 'Grazie, e prego anche a te',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Grazie, e prego anche a te'?",
        "translation": 'Obrigado, e de nada também',
        "distractors": ['Sem problema nenhum', 'Tchau', 'Eu acho que não'],
        "explanation": "Combina agradecimento com a devolução de 'prego'.",
    },
    {
        "word": 'Piacere di conoscerti, a presto, ciao',
        "part_of_speech": 'mini-frase',
        "tip": "Cosa significa 'Piacere di conoscerti, a presto, ciao'?",
        "translation": 'Prazer em te conhecer, até logo, tchau',
        "distractors": ['Boa noite (ao dormir)', 'Eu moro em...', 'Feliz aniversário, divirta-se!'],
        "explanation": 'Une apresentação e despedida em uma sequência natural.',
    },
]


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
