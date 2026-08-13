"""
Script de seed: cria OU ATUALIZA as palavras da tela "Aprender" via API
(upsert). Como o campo `student_ids` é OPCIONAL (ver
VocabWordCreate/create_vocab_word), não enviamos ele aqui de propósito — a
API atribui a palavra automaticamente a TODOS os alunos aprovados no
momento **que tenham a mesma língua-alvo** (campo `language`, abaixo —
'frances' aqui), e o backend garante que qualquer aluno aprovado
depois (em admin.approve_student) dessa mesma língua também receba as
mesmas palavras. Ou seja: rodar este script envia o lote inteiro pra TODOS
os alunos de Acesso Especial com língua-alvo francês agora, de uma vez, sem precisar selecionar aluno
por aluno.

COMPORTAMENTO DE UPSERT (criar, atualizar ou deixar como está):
Antes de enviar cada item de WORDS, o script busca em GET /vocab-words se
já existe uma palavra com o mesmo texto (`word`, sem diferenciar
maiúscula/minúscula), a mesma LANGUAGE e a mesma `translation` (algumas
palavras se repetem com sentidos diferentes — por isso a tradução também
entra na chave, senão uma sobrescreveria a outra). A partir daí:
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

ANTES do upsert, o script também remove (se existirem) as palavras
listadas em LEGACY_WORDS_TO_REMOVE — usado aqui para apagar a citação de
teste ("Savoir étant sublime...") que havia sido cadastrada antes desta
lista completa existir. É seguro rodar o script de novo depois: se essas
palavras já não existirem mais, ele simplesmente não faz nada nesse passo.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_vocab_words_frances.py

Este arquivo contém as 200 palavras/expressões da Parte 1 (nível A1)
em FRANCÊS, extraídas do baralho de flashcards fornecido pelo professor.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Língua-alvo deste lote de palavras. Alunos do curso normal são sempre
# "ingles"; alunos de Acesso Especial usam o target_language do cadastro
# (ex.: "frances").
LANGUAGE = 'frances'

# Palavras antigas (cadastradas manualmente/como teste) que devem ser
# REMOVIDAS antes do upsert, se ainda existirem. Compara por texto da
# palavra + language (sem diferenciar maiúscula/minúscula).
LEGACY_WORDS_TO_REMOVE = [
    "Savoir étant sublime, apprendre sera doux.",
]

# ---------------------------------------------------------------------------
# Parte 1 (A1) — 200 palavras/expressões, extraídas do baralho de
# flashcards em FRANCÊS. `tip` é a pergunta/contexto mostrado
# ANTES de responder; `explanation` só aparece DEPOIS, no verso do card,
# junto com a resposta certa.
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": 'Salut',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Salut » ?",
        "translation": 'Oi',
        "distractors": ['Sim', 'Não', 'Adeus'],
        "explanation": '\'Salut\' é a forma mais informal e comum de cumprimentar em francês, usada entre amigos.',
    },
    {
        "word": 'Bonjour (Saudação)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonjour (Saudação) » ?",
        "translation": 'Olá',
        "distractors": ['Por favor', 'Tchau', 'Obrigado'],
        "explanation": '\'Bonjour\' é a saudação padrão em francês, usada a qualquer hora do dia até o entardecer — serve tanto como \'olá\' quanto como \'bom dia\'.',
    },
    {
        "word": 'Bonjour (Dia)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonjour (Dia) » ?",
        "translation": 'Bom dia',
        "distractors": ['Boa noite', 'Boa tarde', 'Até logo'],
        "explanation": 'O francês não tem uma expressão separada para \'bom dia\': \'Bonjour\' já cobre a manhã inteira, até o fim da tarde.',
    },
    {
        "word": 'Bon après-midi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bon après-midi » ?",
        "translation": 'Boa tarde',
        "distractors": ['Bom dia', 'Boa sorte', 'Boa noite'],
        "explanation": 'Diferente do português, \'Bon après-midi\' é usado sobretudo como despedida (\'tenha uma boa tarde\'), não como cumprimento ao chegar — pra chegar à tarde, os franceses continuam dizendo \'Bonjour\'.',
    },
    {
        "word": 'Bonsoir',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonsoir » ?",
        "translation": 'Boa noite (ao chegar)',
        "distractors": ['Bom dia', 'Boa noite (ao dormir)', 'Boa tarde'],
        "explanation": 'Usado para cumprimentar a partir do fim da tarde/à noite, não ao se despedir para dormir.',
    },
    {
        "word": 'Bonne nuit',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonne nuit » ?",
        "translation": 'Boa noite (ao dormir/despedir)',
        "distractors": ['Boa tarde', 'Boa noite (ao chegar)', 'Bom dia'],
        "explanation": 'Usado ao se despedir à noite, geralmente antes de dormir — nunca como cumprimento ao chegar.',
    },
    {
        "word": 'Hé !',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « Hé ! » ?",
        "translation": 'Ei / Oi',
        "distractors": ['Tchau', 'Sim', 'Desculpa'],
        "explanation": 'Interjeição informal de espanto/chamado, equivalente direto ao \'Ehi\' italiano e ao \'Ei\' em português.',
    },
    {
        "word": 'Comment vas-tu ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Comment vas-tu ? » ?",
        "translation": 'Como você está?',
        "distractors": ['O que você quer?', 'Onde você está?', 'Quem é você?'],
        "explanation": 'Pergunta comum logo após cumprimentar alguém, na forma informal (\'tu\').',
    },
    {
        "word": 'Je vais bien, merci',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je vais bien, merci » ?",
        "translation": 'Estou bem, obrigado(a)',
        "distractors": ['Eu não sei', 'Estou cansado', 'Não estou bem'],
        "explanation": 'Resposta comum e educada para \'Comment vas-tu?\'.',
    },
    {
        "word": 'Enchanté(e) de te rencontrer',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Enchanté(e) de te rencontrer » ?",
        "translation": 'Prazer em te conhecer',
        "distractors": ['Com licença', 'Até mais', 'Muito obrigado'],
        "explanation": 'Usado ao conhecer alguém pela primeira vez; \'Enchanté(e)\' sozinho também funciona.',
    },
    {
        "word": 'Bienvenue',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bienvenue » ?",
        "translation": 'Bem-vindo(a)',
        "distractors": ['Cuidado', 'Adeus', 'Desculpe'],
        "explanation": 'Usado para receber alguém em um lugar.',
    },
    {
        "word": 'Salut, comment vas-tu ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Salut, comment vas-tu ? » ?",
        "translation": 'Salut, comment vas-tu ?',
        "distractors": ['Excuse-moi, pardon', 'Merci beaucoup', 'Bonne nuit, à bientôt'],
        "explanation": 'Combina a saudação \'Salut\' com a pergunta \'Comment vas-tu?\'.',
    },
    {
        "word": 'Comment ça va ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Comment ça va ? » ?",
        "translation": 'Como vai? / E aí?',
        "distractors": ['Muito obrigado', 'Com certeza', 'Boa noite'],
        "explanation": 'Tradução direta de \'come va?\' — pergunta informal e muito comum sobre como a pessoa está.',
    },
    {
        "word": 'Ça fait longtemps !',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ça fait longtemps ! » ?",
        "translation": 'Quanto tempo!',
        "distractors": ['Nunca te vi', 'Vejo você amanhã', 'Eu não te conheço'],
        "explanation": 'Usado ao reencontrar alguém depois de muito tempo.',
    },
    {
        "word": 'Bonjour à tous',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Bonjour à tous » ?",
        "translation": 'Bonjour à tous',
        "distractors": ['Bon après-midi, monsieur', 'Enchanté de vous rencontrer tous', 'Bonne nuit à tous'],
        "explanation": 'Saudação usada para um grupo de pessoas.',
    },
    {
        "word": 'Au revoir',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Au revoir » ?",
        "translation": 'Adeus / Tchau',
        "distractors": ['Obrigado', 'Desculpa', 'Olá'],
        "explanation": 'Forma padrão de se despedir em francês, em qualquer situação.',
    },
    {
        "word": 'Salut',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « Salut » ?",
        "translation": 'Tchau',
        "distractors": ['Sim', 'Por favor', 'Oi'],
        "explanation": 'Assim como em italiano, \'salut\' em francês também é usado pra se despedir, não só para cumprimentar.',
    },
    {
        "word": 'À plus tard',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « À plus tard » ?",
        "translation": 'Até mais tarde',
        "distractors": ['Bom dia', 'Nunca mais te vejo', 'Muito prazer'],
        "explanation": 'Usado ao se despedir esperando ver a pessoa novamente ainda no mesmo dia.',
    },
    {
        "word": 'À bientôt',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « À bientôt » ?",
        "translation": 'Até logo / Até breve',
        "distractors": ['Com licença', 'Até nunca', 'Boa sorte'],
        "explanation": 'Despedida indicando que o reencontro será em breve.',
    },
    {
        "word": 'À demain',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « À demain » ?",
        "translation": 'Até amanhã',
        "distractors": ['Bom dia', 'Boa noite', 'Até a próxima semana'],
        "explanation": 'Despedida usada quando o reencontro será no dia seguinte.',
    },
    {
        "word": 'Prends soin de toi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Prends soin de toi » ?",
        "translation": 'Se cuida',
        "distractors": ['Vem cá', 'Espera aí', 'Fica tranquilo'],
        "explanation": 'Despedida amigável, desejando bem-estar à pessoa.',
    },
    {
        "word": 'Bonne journée',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonne journée » ?",
        "translation": 'Tenha um bom dia',
        "distractors": ['Boa sorte', 'Tenha uma boa noite', 'Bom apetite'],
        "explanation": 'Despedida educada usada durante o dia, bem comum no francês do dia a dia.',
    },
    {
        "word": 'Bonne nuit',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonne nuit » ?",
        "translation": 'Tenha uma boa noite',
        "distractors": ['Até logo', 'Muito prazer', 'Tenha um bom dia'],
        "explanation": 'Despedida usada à noite, geralmente antes de dormir — mesma expressão do item 6, aqui como desejo.',
    },
    {
        "word": 'Adieu',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Adieu » ?",
        "translation": 'Adeus (formal)',
        "distractors": ['Obrigado', 'Com licença', 'Oi (informal)'],
        "explanation": 'Forma mais formal e definitiva de dizer adeus — sugere que não haverá reencontro, diferente de \'au revoir\'.',
    },
    {
        "word": 'On se voit plus tard',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « On se voit plus tard » ?",
        "translation": 'Nos vemos depois',
        "distractors": ['Bom dia para você', 'Nunca te vi antes', 'Com muito prazer'],
        "explanation": 'Despedida informal e literal (\'on se voit\' = \'nos vemos\', \'plus tard\' = \'depois\'), comum entre amigos.',
    },
    {
        "word": 'À plus tard, salut !',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « À plus tard, salut ! » ?",
        "translation": 'À plus tard, salut !',
        "distractors": ['Merci infiniment !', 'Enchanté de te rencontrer !', 'Bonjour, salut !'],
        "explanation": 'Combina duas despedidas comuns em sequência.',
    },
    {
        "word": 'Prends soin de toi, à bientôt',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Prends soin de toi, à bientôt » ?",
        "translation": 'Prends soin de toi, à bientôt',
        "distractors": ['Bienvenue, enchanté de te rencontrer', 'Excuse-moi, pardon s\'il te plaît', 'Bonjour, comment vas-tu'],
        "explanation": 'Une duas expressões de despedida amigáveis.',
    },
    {
        "word": 'Merci',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci » ?",
        "translation": 'Obrigado(a)',
        "distractors": ['Desculpa', 'Por favor', 'De nada'],
        "explanation": 'Forma padrão de agradecer em francês.',
    },
    {
        "word": 'Merci',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « Merci » ?",
        "translation": 'Obrigado(a) (informal)',
        "distractors": ['Por favor', 'Com licença', 'Adeus'],
        "explanation": 'Mesma palavra usada em contextos formais e informais em francês.',
    },
    {
        "word": 'Merci beaucoup',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci beaucoup » ?",
        "translation": 'Muito obrigado(a)',
        "distractors": ['Por favor, não', 'Com certeza', 'Sinto muito'],
        "explanation": 'Forma mais enfática de agradecer.',
    },
    {
        "word": 'Merci bien',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci bien » ?",
        "translation": 'Muito obrigado(a) (informal)',
        "distractors": ['Boa sorte', 'Desculpe muito', 'Sem problema'],
        "explanation": 'Forma informal de agradecer, comum no dia a dia (não confundir com sarcasmo, que depende do tom de voz).',
    },
    {
        "word": 'Merci infiniment',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci infiniment » ?",
        "translation": 'Muitíssimo obrigado(a)',
        "distractors": ['Com licença', 'De jeito nenhum', 'Não se preocupe'],
        "explanation": 'Agradecimento bastante caloroso e enfático.',
    },
    {
        "word": 'Je l\'apprécie',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je l'apprécie » ?",
        "translation": 'Eu aprecio isso / Eu agradeço',
        "distractors": ['Eu sinto muito', 'Eu não sei', 'Eu não quero'],
        "explanation": 'Tradução literal de \'lo apprezzo\' — forma um pouco mais pessoal de expressar gratidão.',
    },
    {
        "word": 'Merci pour ton aide',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci pour ton aide » ?",
        "translation": 'Obrigado pela sua ajuda',
        "distractors": ['Obrigado pela comida', 'Desculpe pelo problema', 'Por favor, me ajude'],
        "explanation": 'Agradecimento específico por uma ajuda recebida.',
    },
    {
        "word": 'Merci d\'être venu(e)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Merci d'être venu(e) » ?",
        "translation": 'Obrigado por vir',
        "distractors": ['Obrigado por esperar', 'Desculpe por chegar tarde', 'Por favor, entre'],
        "explanation": 'Agradecimento por alguém ter comparecido.',
    },
    {
        "word": 'Merci infiniment pour tout',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Merci infiniment pour tout » ?",
        "translation": 'Merci infiniment pour tout',
        "distractors": ['Aide-moi avec ça, s\'il te plaît', 'Excuse-moi pour tout ce que tu as fait', 'Enchanté de te rencontrer aujourd\'hui'],
        "explanation": 'Combina \'merci infiniment\' com \'pour tout\'.',
    },
    {
        "word": 'Merci beaucoup, j\'apprécie',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Merci beaucoup, j'apprécie » ?",
        "translation": 'Merci beaucoup, j\'apprécie',
        "distractors": ['Bonjour, à plus tard', 'Désolé, excuse-moi', 'S\'il te plaît, aucun problème'],
        "explanation": 'Une duas expressões de agradecimento diferentes.',
    },
    {
        "word": 'De rien',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « De rien » ?",
        "translation": 'De nada',
        "distractors": ['Com licença', 'Muito obrigado', 'Sinto muito'],
        "explanation": 'Resposta padrão a um agradecimento.',
    },
    {
        "word": 'Pas de problème',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pas de problème » ?",
        "translation": 'Sem problema',
        "distractors": ['De jeito nenhum', 'Há um problema', 'Não entendi'],
        "explanation": 'Resposta informal a um agradecimento.',
    },
    {
        "word": 'Ne t\'inquiète pas / Tranquille',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ne t'inquiète pas / Tranquille » ?",
        "translation": 'Não se preocupe / Tranquilo',
        "distractors": ['Muito obrigado', 'Estou preocupado', 'Com certeza'],
        "explanation": 'Resposta informal e tranquila a um agradecimento.',
    },
    {
        "word": 'Il n\'y a pas de quoi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Il n'y a pas de quoi » ?",
        "translation": 'Não há de quê',
        "distractors": ['Fale mais alto', 'Não fale comigo', 'Diga de novo'],
        "explanation": 'Resposta educada indicando que não é necessário agradecer.',
    },
    {
        "word": 'C\'est un plaisir (pour moi)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est un plaisir (pour moi) » ?",
        "translation": 'É um prazer (para mim)',
        "distractors": ['Sinto muito por isso', 'É um problema meu', 'Não é da minha conta'],
        "explanation": 'Resposta educada e calorosa a um agradecimento.',
    },
    {
        "word": 'Quand tu veux',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Quand tu veux » ?",
        "translation": 'Quando quiser / Sempre que precisar',
        "distractors": ['Nunca mais', 'Talvez', 'Às vezes'],
        "explanation": 'Resposta informal indicando disponibilidade futura.',
    },
    {
        "word": 'Bien sûr, aucun problème',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bien sûr, aucun problème » ?",
        "translation": 'Claro, sem problema',
        "distractors": ['Talvez amanhã', 'Desculpe, não posso', 'Não, obrigado'],
        "explanation": 'Resposta afirmativa e tranquila a um pedido ou agradecimento.',
    },
    {
        "word": 'De rien, aucun problème',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « De rien, aucun problème » ?",
        "translation": 'De rien, aucun problème',
        "distractors": ['S\'il te plaît, excuse-moi maintenant', 'Merci beaucoup vraiment', 'Je suis désolé pour ça'],
        "explanation": 'Combina duas respostas comuns a agradecimentos.',
    },
    {
        "word": 'Pardon',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pardon » ?",
        "translation": 'Desculpa',
        "distractors": ['De nada', 'Obrigado', 'Por favor'],
        "explanation": 'Forma curta e comum de pedir desculpas, também usada pra pedir passagem.',
    },
    {
        "word": 'Je suis désolé(e)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je suis désolé(e) » ?",
        "translation": 'Eu sinto muito / Desculpe',
        "distractors": ['Eu não sei', 'Eu concordo', 'Eu estou feliz'],
        "explanation": 'Forma mais completa de pedir desculpas.',
    },
    {
        "word": 'Excuse-moi / Excusez-moi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Excuse-moi / Excusez-moi » ?",
        "translation": 'Com licença',
        "distractors": ['Vá embora', 'Muito obrigado', 'Boa sorte'],
        "explanation": 'Usado para pedir licença ou chamar atenção educadamente (\'excusez-moi\' é a forma formal/plural).',
    },
    {
        "word": 'Je vous prie de m\'excuser',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je vous prie de m'excuser » ?",
        "translation": 'Eu peço desculpas (formal)',
        "distractors": ['Eu agradeço muito', 'Eu concordo totalmente', 'Eu não entendo nada'],
        "explanation": 'Forma bem formal de pedir desculpas, usada em situações profissionais.',
    },
    {
        "word": 'C\'est de ma faute',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est de ma faute » ?",
        "translation": 'Foi meu erro',
        "distractors": ['Meu prazer', 'Boa ideia', 'Sua vez'],
        "explanation": 'Usado para admitir um erro cometido.',
    },
    {
        "word": 'Je suis vraiment désolé(e)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je suis vraiment désolé(e) » ?",
        "translation": 'Sinto muitíssimo',
        "distractors": ['Estou de acordo', 'Estou com pressa', 'Estou muito feliz'],
        "explanation": 'Forma enfática de pedir desculpas.',
    },
    {
        "word": 'Désolé de te déranger',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Désolé de te déranger » ?",
        "translation": 'Desculpe incomodar',
        "distractors": ['Vamos comemorar', 'Obrigado por ajudar', 'Prazer em conhecer'],
        "explanation": 'Usado antes de interromper ou pedir algo a alguém.',
    },
    {
        "word": 'Je ne voulais pas dire ça',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je ne voulais pas dire ça » ?",
        "translation": 'Eu não quis dizer isso / Não foi intencional',
        "distractors": ['Eu concordo com você', 'Eu não te conheço', 'Eu quis dizer isso mesmo'],
        "explanation": 'Usado para explicar que algo não foi proposital.',
    },
    {
        "word": 'Je suis désolé, excuse-moi',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je suis désolé, excuse-moi » ?",
        "translation": 'Je suis désolé, excuse-moi',
        "distractors": ['Merci, de rien', 'Bonjour, enchanté de te rencontrer', 'À plus tard, prends soin de toi'],
        "explanation": 'Combina duas expressões usadas para pedir desculpas educadamente.',
    },
    {
        "word": 'Pardon, c\'était de ma faute',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Pardon, c'était de ma faute » ?",
        "translation": 'Pardon, c\'était de ma faute',
        "distractors": ['Merci, c\'était ton idée', 'Bienvenue, c\'était amusant', 'Salut, c\'était sympa'],
        "explanation": 'Combina \'pardon\' com a admissão de erro \'c\'était de ma faute\'.',
    },
    {
        "word": 'C\'est bon',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est bon » ?",
        "translation": 'Está tudo bem',
        "distractors": ['Não está bem', 'Está errado', 'É impossível'],
        "explanation": 'Resposta comum aceitando um pedido de desculpas.',
    },
    {
        "word": 'Tout va bien / Tranquille',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Tout va bien / Tranquille » ?",
        "translation": 'Está tudo bem / Tranquilo',
        "distractors": ['Não é possível', 'Está péssimo', 'Está caro'],
        "explanation": 'Resposta tranquila a um pedido de desculpas.',
    },
    {
        "word": 'Aucun problème du tout',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Aucun problème du tout » ?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Há um grande problema', 'Não aceito desculpas', 'Estou muito bravo'],
        "explanation": 'Resposta tranquilizadora e enfática.',
    },
    {
        "word": 'Ne t\'inquiète pas pour ça',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ne t'inquiète pas pour ça » ?",
        "translation": 'Não se preocupe com isso',
        "distractors": ['Pense bastante nisso', 'Fale sobre isso agora', 'Preocupe-se muito com isso'],
        "explanation": 'Resposta usada para tranquilizar alguém após um erro.',
    },
    {
        "word": 'C\'est bon comme ça',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est bon comme ça » ?",
        "translation": 'Tudo bem / Está certo',
        "distractors": ['Isso é impossível', 'Isso é caro', 'Isso está errado'],
        "explanation": 'Resposta aceitando desculpas de forma tranquila.',
    },
    {
        "word": 'Il n\'y a pas de mal',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Il n'y a pas de mal » ?",
        "translation": 'Nenhum mal foi feito',
        "distractors": ['Foi um grande problema', 'Isso doeu muito', 'Muito mal foi feito'],
        "explanation": 'Resposta indicando que não houve consequência negativa.',
    },
    {
        "word": 'Ça arrive',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ça arrive » ?",
        "translation": 'Acontece',
        "distractors": ['É impossível', 'Nunca acontece', 'É sua culpa'],
        "explanation": 'Resposta tranquilizadora, indicando que erros são normais.',
    },
    {
        "word": 'C\'est bon, ne t\'inquiète pas',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « C'est bon, ne t'inquiète pas » ?",
        "translation": 'C\'est bon, ne t\'inquiète pas',
        "distractors": ['Merci, à bientôt', 'Excuse-moi, je suis désolé', 'Bonne nuit, dors bien'],
        "explanation": 'Combina duas expressões que aceitam desculpas e tranquilizam.',
    },
    {
        "word": 'S\'il te plaît',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « S'il te plaît » ?",
        "translation": 'Por favor',
        "distractors": ['Obrigado', 'De nada', 'Desculpa'],
        "explanation": 'Usado para fazer pedidos de forma educada, na forma informal (\'s\'il vous plaît\' é a formal).',
    },
    {
        "word": 'Pourrais-tu, s\'il te plaît ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pourrais-tu, s'il te plaît ? » ?",
        "translation": 'Você poderia, por favor?',
        "distractors": ['Você sabe disso?', 'Você já fez isso?', 'Você gosta disso?'],
        "explanation": 'Forma educada de fazer um pedido.',
    },
    {
        "word": 'Aimerais-tu... ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Aimerais-tu... ? » ?",
        "translation": 'Você gostaria de...?',
        "distractors": ['Você fez...?', 'Você sabe...?', 'Você já tem...?'],
        "explanation": 'Usado para oferecer algo educadamente.',
    },
    {
        "word": 'Après toi / Vas-y d\'abord',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Après toi / Vas-y d'abord » ?",
        "translation": 'Depois de você / Vá primeiro',
        "distractors": ['Junto comigo', 'Antes de mim', 'Longe de mim'],
        "explanation": 'Expressão educada usada para ceder a vez a alguém.',
    },
    {
        "word": 'Je peux ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je peux ? » ?",
        "translation": 'Posso?',
        "distractors": ['Eu sei?', 'Eu devo?', 'Eu quero?'],
        "explanation": 'Usado para pedir permissão educadamente; \'puis-je?\' é a versão mais formal.',
    },
    {
        "word": 'Excuse-moi, s\'il te plaît',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Excuse-moi, s'il te plaît » ?",
        "translation": 'Com licença, por favor',
        "distractors": ['Prazer em conhecer', 'De nada, tranquilo', 'Muito obrigado mesmo'],
        "explanation": 'Combinação educada para pedir licença.',
    },
    {
        "word": 'Si ça ne te dérange pas',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Si ça ne te dérange pas » ?",
        "translation": 'Se você não se importar',
        "distractors": ['Se você estiver ocupado', 'Se você quiser brigar', 'Se você não gostar'],
        "explanation": 'Usado para suavizar um pedido educadamente.',
    },
    {
        "word": 'Ça te dérangerait de... ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ça te dérangerait de... ? » ?",
        "translation": 'Você se importaria de...?',
        "distractors": ['Você já foi lá?', 'Você tem certeza?', 'Você gostaria de comer?'],
        "explanation": 'Forma educada de pedir algo a alguém.',
    },
    {
        "word": 'C\'est très gentil de ta part',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est très gentil de ta part » ?",
        "translation": 'Isso é muito gentil da sua parte',
        "distractors": ['Isso é muito estranho', 'Isso é muito difícil', 'Isso é muito caro'],
        "explanation": 'Elogio educado usado para agradecer um gesto gentil.',
    },
    {
        "word": 'Avec plaisir',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Avec plaisir » ?",
        "translation": 'Com prazer',
        "distractors": ['Com pressa', 'Com raiva', 'Com medo'],
        "explanation": 'Resposta educada indicando disposição em ajudar.',
    },
    {
        "word": 'Pardon / Excusez-moi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pardon / Excusez-moi » ?",
        "translation": 'Perdão / Com licença',
        "distractors": ['Fale mais baixo', 'Espere um pouco', 'Vá embora agora'],
        "explanation": 'Forma educada de pedir desculpas ou chamar atenção.',
    },
    {
        "word": 'Excuse-moi de t\'interrompre',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Excuse-moi de t'interrompre » ?",
        "translation": 'Desculpe interromper',
        "distractors": ['Vamos continuar', 'Prazer em conhecer', 'Obrigado por esperar'],
        "explanation": 'Usado antes de interromper alguém educadamente.',
    },
    {
        "word": 'Pourrais-tu m\'aider, s\'il te plaît ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Pourrais-tu m'aider, s'il te plaît ? » ?",
        "translation": 'Pourrais-tu m\'aider, s\'il te plaît ?',
        "distractors": ['Je suis désolé pour ça', 'Tu es très gentil aujourd\'hui', 'Merci pour ton aide'],
        "explanation": 'Combina \'pourrais-tu\' com \'s\'il te plaît\' para um pedido educado.',
    },
    {
        "word": 'Excuse-moi, je peux demander quelque chose ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Excuse-moi, je peux demander quelque chose ? » ?",
        "translation": 'Excuse-moi, je peux demander quelque chose ?',
        "distractors": ['Enchanté de te rencontrer ici', 'Je suis désolé, je ne sais pas', 'Merci de m\'avoir demandé'],
        "explanation": 'Combina \'excuse-moi\' com \'je peux\' para pedir permissão.',
    },
    {
        "word": 'Aimerais-tu de l\'aide ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Aimerais-tu de l'aide ? » ?",
        "translation": 'Aimerais-tu de l\'aide ?',
        "distractors": ['Pourrais-tu me donner ça ?', 'Merci beaucoup pour tout', 'Je suis désolé pour le dérangement'],
        "explanation": 'Usa \'aimerais-tu\' para oferecer algo de forma educada.',
    },
    {
        "word": 'Oui',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « Oui » ?",
        "translation": 'Sim',
        "distractors": ['Nunca', 'Não', 'Talvez'],
        "explanation": 'Resposta afirmativa básica.',
    },
    {
        "word": 'Non',
        "part_of_speech": 'palavra',
        "tip": "Que signifie « Non » ?",
        "translation": 'Não',
        "distractors": ['Sim', 'Sempre', 'Claro'],
        "explanation": 'Resposta negativa básica.',
    },
    {
        "word": 'Oui, s\'il te plaît',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Oui, s'il te plaît » ?",
        "translation": 'Sim, por favor',
        "distractors": ['Não, obrigado', 'Nunca mais', 'Talvez depois'],
        "explanation": 'Resposta afirmativa educada, comum ao aceitar algo.',
    },
    {
        "word": 'Non, merci',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Non, merci » ?",
        "translation": 'Não, obrigado',
        "distractors": ['Com certeza', 'Sim, por favor', 'Claro que sim'],
        "explanation": 'Resposta negativa educada, comum ao recusar algo.',
    },
    {
        "word": 'Bien sûr',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bien sûr » ?",
        "translation": 'Claro',
        "distractors": ['De jeito nenhum', 'Nunca', 'Talvez não'],
        "explanation": 'Resposta afirmativa informal e muito comum.',
    },
    {
        "word": 'Certainement / Évidemment',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Certainement / Évidemment » ?",
        "translation": 'Claro / Com certeza',
        "distractors": ['Talvez amanhã', 'Eu não sei', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa mais enfática que \'bien sûr\'.',
    },
    {
        "word": 'Pas vraiment / Pas trop',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pas vraiment / Pas trop » ?",
        "translation": 'Não muito / Nem tanto',
        "distractors": ['Muito obrigado', 'Sempre é assim', 'Com certeza sim'],
        "explanation": 'Resposta que suaviza uma negação.',
    },
    {
        "word": 'Je pense que oui',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je pense que oui » ?",
        "translation": 'Eu acho que sim',
        "distractors": ['Eu não me importo', 'Eu nunca soube disso', 'Eu tenho certeza que não'],
        "explanation": 'Resposta afirmativa com certo grau de incerteza.',
    },
    {
        "word": 'Je pense que non',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je pense que non » ?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu adoro isso', 'Com certeza absoluta', 'Eu tenho certeza que sim'],
        "explanation": 'Resposta negativa com certo grau de incerteza.',
    },
    {
        "word": 'Peut-être',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Peut-être » ?",
        "translation": 'Talvez',
        "distractors": ['Com certeza', 'Sempre', 'Nunca'],
        "explanation": 'Resposta indicando incerteza.',
    },
    {
        "word": 'Sûrement / Décidément',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Sûrement / Décidément » ?",
        "translation": 'Com certeza / Definitivamente',
        "distractors": ['Eu não sei', 'De jeito nenhum', 'Talvez não'],
        "explanation": 'Tradução literal, com os cognatos diretos de \'sicuramente\' e \'decisamente\' em francês.',
    },
    {
        "word": 'Absolument pas',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Absolument pas » ?",
        "translation": 'De jeito nenhum',
        "distractors": ['Eu acho que sim', 'Talvez sim', 'Com certeza sim'],
        "explanation": 'Resposta negativa muito enfática.',
    },
    {
        "word": 'J\'imagine que oui',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « J'imagine que oui » ?",
        "translation": 'Eu imagino que sim (meio incerto)',
        "distractors": ['Eu tenho certeza absoluta', 'Eu nunca faria isso', 'Isso é impossível'],
        "explanation": 'Tradução literal de \'immagino di sì\' — resposta afirmativa hesitante, informal.',
    },
    {
        "word": 'Oui, bien sûr que je peux',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Oui, bien sûr que je peux » ?",
        "translation": 'Oui, bien sûr que je peux',
        "distractors": ['Non, je pense que non', 'Désolé, je ne peux pas le faire', 'Peut-être, je ne suis pas sûr'],
        "explanation": 'Combina \'oui\' com \'bien sûr\' para uma resposta afirmativa forte.',
    },
    {
        "word": 'Non, je pense que non',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Non, je pense que non » ?",
        "translation": 'Non, je pense que non',
        "distractors": ['Sûrement, absolument oui', 'Oui, bien sûr que oui', 'Bien sûr, aucun problème'],
        "explanation": 'Combina \'non\' com \'je pense que non\' para suavizar a negação.',
    },
    {
        "word": 'Je comprends',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je comprends » ?",
        "translation": 'Eu entendo',
        "distractors": ['Eu não entendo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para indicar que algo foi compreendido.',
    },
    {
        "word": 'Je ne comprends pas',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je ne comprends pas » ?",
        "translation": 'Eu não entendo',
        "distractors": ['Eu concordo', 'Eu sei disso', 'Eu entendo tudo'],
        "explanation": 'Usado para indicar que algo não foi compreendido.',
    },
    {
        "word": 'J\'ai compris / Je vois',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « J'ai compris / Je vois » ?",
        "translation": 'Entendi / Estou vendo',
        "distractors": ['Eu discordo', 'Eu esqueci tudo', 'Eu não vejo nada'],
        "explanation": 'Expressão informal para indicar compreensão.',
    },
    {
        "word": 'Peux-tu répéter ça ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Peux-tu répéter ça ? » ?",
        "translation": 'Você pode repetir isso?',
        "distractors": ['Você pode parar agora?', 'Você pode ir embora?', 'Você pode me ajudar?'],
        "explanation": 'Usado para pedir que algo seja dito novamente.',
    },
    {
        "word": 'Peux-tu parler lentement ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Peux-tu parler lentement ? » ?",
        "translation": 'Você pode falar devagar?',
        "distractors": ['Você pode falar rápido?', 'Você pode parar de falar?', 'Você pode falar baixo?'],
        "explanation": 'Pedido comum para facilitar a compreensão.',
    },
    {
        "word": 'Qu\'est-ce que ça veut dire ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Qu'est-ce que ça veut dire ? » ?",
        "translation": 'O que isso significa?',
        "distractors": ['Onde isso está?', 'Quem fez isso?', 'Quando isso ocorre?'],
        "explanation": 'Pergunta usada para pedir o significado de algo.',
    },
    {
        "word": 'Je n\'en ai aucune idée',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je n'en ai aucune idée » ?",
        "translation": 'Não faço ideia',
        "distractors": ['Eu sei exatamente', 'Eu concordo totalmente', 'Eu tenho certeza'],
        "explanation": 'Expressão usada quando não se sabe algo.',
    },
    {
        "word": 'Désolé, je n\'ai pas compris',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Désolé, je n'ai pas compris » ?",
        "translation": 'Desculpe, não entendi isso',
        "distractors": ['Desculpe, eu entendi tudo', 'Obrigado, ficou claro', 'Com certeza eu sei'],
        "explanation": 'Usado educadamente quando algo não foi compreendido.',
    },
    {
        "word": 'Pourrais-tu expliquer ça ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pourrais-tu expliquer ça ? » ?",
        "translation": 'Você poderia explicar isso?',
        "distractors": ['Você poderia parar isso?', 'Você poderia comprar isso?', 'Você poderia esquecer isso?'],
        "explanation": 'Pedido educado de explicação.',
    },
    {
        "word": 'Maintenant c\'est clair',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Maintenant c'est clair » ?",
        "translation": 'Agora está claro',
        "distractors": ['Isso é impossível', 'Isso está errado', 'Ainda não está claro'],
        "explanation": 'Usado após entender algo que antes era confuso.',
    },
    {
        "word": 'Je suis confus(e)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je suis confus(e) » ?",
        "translation": 'Estou confuso(a)',
        "distractors": ['Estou com pressa', 'Estou tranquilo', 'Estou feliz'],
        "explanation": 'Usado para expressar confusão ou falta de clareza.',
    },
    {
        "word": 'Qu\'est-ce que tu as dit ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Qu'est-ce que tu as dit ? » ?",
        "translation": 'O que você disse?',
        "distractors": ['Quando você vem?', 'Onde você está?', 'Quem disse isso?'],
        "explanation": 'Pergunta usada quando não se ouviu ou entendeu algo.',
    },
    {
        "word": 'Désolé, peux-tu répéter, s\'il te plaît ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Désolé, peux-tu répéter, s'il te plaît ? » ?",
        "translation": 'Désolé, peux-tu répéter, s\'il te plaît ?',
        "distractors": ['J\'ai compris, c\'est très clair', 'Merci, maintenant je comprends', 'Aucun problème, ne t\'inquiète pas'],
        "explanation": 'Combina \'désolé\' com o pedido \'peux-tu répéter\'.',
    },
    {
        "word": 'Je ne comprends pas, peux-tu m\'aider ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je ne comprends pas, peux-tu m'aider ? » ?",
        "translation": 'Je ne comprends pas, peux-tu m\'aider ?',
        "distractors": ['Merci, c\'était très clair', 'Maintenant je comprends tout', 'Bien sûr, aucun problème'],
        "explanation": 'Une a falta de compreensão a um pedido de ajuda.',
    },
    {
        "word": 'Pourrais-tu parler lentement, s\'il te plaît ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Pourrais-tu parler lentement, s'il te plaît ? » ?",
        "translation": 'Pourrais-tu parler lentement, s\'il te plaît ?',
        "distractors": ['Je te comprends très bien', 'Pourrais-tu arrêter de parler maintenant ?', 'Merci d\'avoir parlé vite'],
        "explanation": 'Combina \'pourrais-tu\' com \'parler lentement\' e \'s\'il te plaît\'.',
    },
    {
        "word": 'Je suis d\'accord',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je suis d'accord » ?",
        "translation": 'Eu concordo',
        "distractors": ['Eu discordo', 'Eu não sei', 'Eu esqueci'],
        "explanation": 'Usado para expressar concordância.',
    },
    {
        "word": 'Je ne suis pas d\'accord',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je ne suis pas d'accord » ?",
        "translation": 'Eu discordo',
        "distractors": ['Eu concordo', 'Eu entendo', 'Eu gosto'],
        "explanation": 'Usado para expressar discordância.',
    },
    {
        "word": 'C\'est vrai',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est vrai » ?",
        "translation": 'Isso é verdade',
        "distractors": ['Isso é estranho', 'Isso é caro', 'Isso é falso'],
        "explanation": 'Usado para confirmar que algo é verdadeiro.',
    },
    {
        "word": 'Ce n\'est pas vrai',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ce n'est pas vrai » ?",
        "translation": 'Isso não é verdade',
        "distractors": ['Isso é fácil', 'Isso é verdade', 'Isso é interessante'],
        "explanation": 'Usado para negar que algo é verdadeiro.',
    },
    {
        "word": 'Tu as raison',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Tu as raison » ?",
        "translation": 'Você está certo(a)',
        "distractors": ['Você está errado', 'Você está cansado', 'Você está atrasado'],
        "explanation": 'Usado para concordar com o que alguém disse.',
    },
    {
        "word": 'Tu as tort',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Tu as tort » ?",
        "translation": 'Você está errado(a)',
        "distractors": ['Você está certo', 'Você está bem', 'Você está pronto'],
        "explanation": 'Usado para discordar do que alguém disse.',
    },
    {
        "word": 'Exactement',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Exactement » ?",
        "translation": 'Exatamente',
        "distractors": ['Talvez', 'De jeito nenhum', 'Eu não sei'],
        "explanation": 'Usado para concordar fortemente com algo.',
    },
    {
        "word": 'Je ne crois pas',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je ne crois pas » ?",
        "translation": 'Eu acho que não',
        "distractors": ['Eu tenho certeza que sim', 'Com certeza absoluta', 'Eu concordo plenamente'],
        "explanation": 'Usado para discordar de forma suave.',
    },
    {
        "word": 'Moi aussi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Moi aussi » ?",
        "translation": 'Eu também',
        "distractors": ['Eu não', 'Nunca', 'Nem eu'],
        "explanation": 'Usado para concordar dizendo que a mesma coisa se aplica a você.',
    },
    {
        "word": 'Moi non plus',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Moi non plus » ?",
        "translation": 'Eu também não / Nem eu',
        "distractors": ['Eu também', 'Sempre eu', 'Eu sim'],
        "explanation": 'Usado para concordar com uma afirmação negativa.',
    },
    {
        "word": 'Je ne suis pas sûr(e)',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je ne suis pas sûr(e) » ?",
        "translation": 'Eu não tenho certeza',
        "distractors": ['Eu concordo totalmente', 'Eu discordo totalmente', 'Eu tenho certeza absoluta'],
        "explanation": 'Usado para expressar incerteza diante de uma opinião.',
    },
    {
        "word": 'Ça a du sens',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Ça a du sens » ?",
        "translation": 'Justo / Faz sentido',
        "distractors": ['Isso é impossível', 'Isso é injusto', 'Isso é errado'],
        "explanation": 'Usado para aceitar um argumento de forma parcial ou informal.',
    },
    {
        "word": 'Je suis d\'accord avec toi',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je suis d'accord avec toi » ?",
        "translation": 'Je suis d\'accord avec toi',
        "distractors": ['Je ne te comprends pas', 'Je ne suis pas d\'accord avec ça', 'Je suis désolé pour ça'],
        "explanation": 'Combina \'je suis d\'accord\' com \'avec toi\'.',
    },
    {
        "word": 'Je ne suis pas d\'accord, désolé',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je ne suis pas d'accord, désolé » ?",
        "translation": 'Je ne suis pas d\'accord, désolé',
        "distractors": ['Tu as raison, exactement', 'C\'est vrai, bien sûr', 'Je suis d\'accord, merci'],
        "explanation": 'Une \'je ne suis pas d\'accord\' com um pedido de desculpas educado.',
    },
    {
        "word": 'Tu as raison, je suis d\'accord',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Tu as raison, je suis d'accord » ?",
        "translation": 'Tu as raison, je suis d\'accord',
        "distractors": ['Merci beaucoup, salut', 'Je suis désolé, excuse-moi', 'Tu as tort, je ne suis pas d\'accord'],
        "explanation": 'Combina \'tu as raison\' com \'je suis d\'accord\' para reforçar a concordância.',
    },
    {
        "word": 'Félicitations',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Félicitations » ?",
        "translation": 'Parabéns',
        "distractors": ['Boa sorte', 'De nada', 'Sinto muito'],
        "explanation": 'Usado para parabenizar alguém.',
    },
    {
        "word": 'Bonne chance',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bonne chance » ?",
        "translation": 'Boa sorte',
        "distractors": ['Bem-vindo', 'Parabéns', 'Desculpa'],
        "explanation": 'Usado para desejar sorte a alguém.',
    },
    {
        "word": 'Joyeux anniversaire',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Joyeux anniversaire » ?",
        "translation": 'Feliz aniversário',
        "distractors": ['Parabéns pelo trabalho', 'Bem-vindo', 'Boa sorte'],
        "explanation": 'Expressão usada para celebrar o aniversário de alguém.',
    },
    {
        "word": 'À tes souhaits',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « À tes souhaits » ?",
        "translation": 'Saúde (após espirro)',
        "distractors": ['Bom apetite', 'Parabéns', 'Boa sorte'],
        "explanation": 'Dito educadamente quando alguém espirra (literalmente \'aos seus desejos\').',
    },
    {
        "word": 'Santé / Tchin-tchin',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Santé / Tchin-tchin » ?",
        "translation": 'Saúde (brinde) / Tim-tim',
        "distractors": ['Adeus para sempre', 'Com licença', 'Sinto muito'],
        "explanation": 'Usado em brindes; \'tchin-tchin\' é a forma bem informal, dita ao bater os copos — o mesmo \'tim-tim\' usado em português.',
    },
    {
        "word": 'Bon appétit',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bon appétit » ?",
        "translation": 'Bom apetite',
        "distractors": ['Boa viagem', 'Bom trabalho', 'Boa sorte'],
        "explanation": 'Dito antes de alguém começar a comer — muito comum na cultura francesa.',
    },
    {
        "word": 'Bon voyage',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bon voyage » ?",
        "translation": 'Tenha uma boa viagem / Viagem segura',
        "distractors": ['Feliz aniversário', 'Boa sorte no trabalho', 'Bom apetite'],
        "explanation": 'Dito antes de alguém viajar.',
    },
    {
        "word": 'Bon rétablissement',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bon rétablissement » ?",
        "translation": 'Melhoras',
        "distractors": ['Parabéns', 'Boa sorte', 'Bom apetite'],
        "explanation": 'Desejo de melhora para alguém doente.',
    },
    {
        "word": 'Bon retour',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bon retour » ?",
        "translation": 'Bem-vindo de volta',
        "distractors": ['Sinto muito', 'Boa viagem', 'Até logo'],
        "explanation": 'Usado ao receber alguém que retornou de uma viagem.',
    },
    {
        "word": 'Fais comme chez toi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Fais comme chez toi » ?",
        "translation": 'Fique à vontade / Sinta-se em casa',
        "distractors": ['Espere lá fora', 'Fique de pé', 'Vá embora agora'],
        "explanation": 'Usado para deixar um convidado confortável.',
    },
    {
        "word": 'C\'est sympa ici',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est sympa ici » ?",
        "translation": 'Aqui é legal / bacana',
        "distractors": ['Aqui é longe', 'Aqui é caro', 'Aqui é ruim'],
        "explanation": 'Comentário positivo simples sobre um lugar.',
    },
    {
        "word": 'C\'est fantastique !',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « C'est fantastique ! » ?",
        "translation": 'Isso é ótimo!',
        "distractors": ['Isso é estranho!', 'Isso é difícil!', 'Isso é péssimo!'],
        "explanation": 'Tradução literal de \'fantastico\' — expressão de entusiasmo positivo.',
    },
    {
        "word": 'Quel dommage',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Quel dommage » ?",
        "translation": 'Que pena',
        "distractors": ['Que ótimo', 'Que engraçado', 'Que legal'],
        "explanation": 'Expressão de pesar ou decepção.',
    },
    {
        "word": 'Dommage',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Dommage » ?",
        "translation": 'Que pena',
        "distractors": ['Que sorte', 'Que orgulho', 'Que alegria'],
        "explanation": 'Forma mais curta e informal de lamentar algo, muito usada no dia a dia.',
    },
    {
        "word": 'Amuse-toi bien',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Amuse-toi bien » ?",
        "translation": 'Divirta-se',
        "distractors": ['Tenha paciência', 'Tenha cuidado', 'Tenha sorte'],
        "explanation": 'Dito antes de alguém sair para se divertir.',
    },
    {
        "word": 'Vas-y doucement / Détends-toi',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Vas-y doucement / Détends-toi » ?",
        "translation": 'Vai com calma / Relaxa',
        "distractors": ['Corre rápido', 'Trabalhe mais', 'Fique bravo'],
        "explanation": 'Usado para pedir que alguém fique tranquilo.',
    },
    {
        "word": 'Toi de même',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Toi de même » ?",
        "translation": 'Igualmente',
        "distractors": ['De jeito nenhum', 'Nunca mais', 'Ao contrário'],
        "explanation": 'Usado para devolver um desejo bom a alguém.',
    },
    {
        "word": 'Bien joué !',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Bien joué ! » ?",
        "translation": 'Boa! / Mandou bem!',
        "distractors": ['Que pena!', 'Cuidado!', 'Sinto muito!'],
        "explanation": 'Expressão informal para elogiar algo bem feito.',
    },
    {
        "word": 'Joyeux anniversaire, amuse-toi bien !',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Joyeux anniversaire, amuse-toi bien ! » ?",
        "translation": 'Joyeux anniversaire, amuse-toi bien !',
        "distractors": ['Bonne chance, à bientôt !', 'Bon rétablissement, prends soin de toi !', 'Bon retour, content de te voir !'],
        "explanation": 'Combina \'joyeux anniversaire\' com \'amuse-toi bien\'.',
    },
    {
        "word": 'Bonne chance, prends soin de toi !',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Bonne chance, prends soin de toi ! » ?",
        "translation": 'Bonne chance, prends soin de toi !',
        "distractors": ['Joyeux anniversaire, bon appétit !', 'Bon voyage, santé !', 'Félicitations, bon retour !'],
        "explanation": 'Combina \'bonne chance\' com \'prends soin de toi\'.',
    },
    {
        "word": 'Comment tu t\'appelles ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Comment tu t'appelles ? » ?",
        "translation": 'Qual é o seu nome?',
        "distractors": ['Quantos anos você tem?', 'Onde você mora?', 'De onde você é?'],
        "explanation": 'Pergunta básica para saber o nome de alguém.',
    },
    {
        "word": 'Je m\'appelle...',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je m'appelle... » ?",
        "translation": 'Meu nome é...',
        "distractors": ['Eu sou de...', 'Eu tenho... anos', 'Eu moro em...'],
        "explanation": 'Resposta usada para dizer o próprio nome.',
    },
    {
        "word": 'Quel âge as-tu ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Quel âge as-tu ? » ?",
        "translation": 'Quantos anos você tem?',
        "distractors": ['Onde você mora?', 'Qual é o seu nome?', 'O que você faz?'],
        "explanation": 'Pergunta básica sobre idade.',
    },
    {
        "word": 'J\'ai ... ans',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « J'ai ... ans » ?",
        "translation": 'Eu tenho ... anos',
        "distractors": ['Eu me chamo ...', 'Eu moro em ...', 'Eu sou de ...'],
        "explanation": 'Resposta usada para dizer a idade (literalmente \'eu tenho ... anos\').',
    },
    {
        "word": 'D\'où viens-tu ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « D'où viens-tu ? » ?",
        "translation": 'De onde você é?',
        "distractors": ['O que você quer?', 'Quando você chega?', 'Como você está?'],
        "explanation": 'Pergunta sobre origem/nacionalidade.',
    },
    {
        "word": 'Je viens du Brésil',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Je viens du Brésil » ?",
        "translation": 'Eu sou do Brasil',
        "distractors": ['Eu moro perto', 'Eu gosto do Brasil', 'Eu vou ao Brasil'],
        "explanation": 'Resposta comum indicando o país de origem.',
    },
    {
        "word": 'Où habites-tu ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Où habites-tu ? » ?",
        "translation": 'Onde você mora?',
        "distractors": ['Como você vive?', 'Quando você chega?', 'Por que você mora aqui?'],
        "explanation": 'Pergunta básica sobre local de moradia.',
    },
    {
        "word": 'J\'habite à...',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « J'habite à... » ?",
        "translation": 'Eu moro em...',
        "distractors": ['Eu vou a...', 'Eu gosto de...', 'Eu nasci em...'],
        "explanation": 'Resposta usada para dizer o local de moradia.',
    },
    {
        "word": 'Qu\'est-ce que tu fais dans la vie ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Qu'est-ce que tu fais dans la vie ? » ?",
        "translation": 'O que você faz? (profissão)',
        "distractors": ['O que você quer?', 'Quando você trabalha?', 'Onde você está?'],
        "explanation": 'Pergunta comum sobre a profissão de alguém.',
    },
    {
        "word": 'Quelle heure est-il ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Quelle heure est-il ? » ?",
        "translation": 'Que horas são?',
        "distractors": ['Onde você está?', 'Que dia é hoje?', 'Quem é você?'],
        "explanation": 'Pergunta básica sobre o horário.',
    },
    {
        "word": 'Il est deux heures',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Il est deux heures » ?",
        "translation": 'São duas horas',
        "distractors": ['É a sala dois', 'São duas pessoas', 'É o dia dois'],
        "explanation": 'Resposta comum indicando horário.',
    },
    {
        "word": 'Combien ça coûte ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Combien ça coûte ? » ?",
        "translation": 'Quanto custa?',
        "distractors": ['Onde fica?', 'Quantos são?', 'Quando é?'],
        "explanation": 'Pergunta comum sobre preço.',
    },
    {
        "word": 'Où sont les toilettes ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Où sont les toilettes ? » ?",
        "translation": 'Onde fica o banheiro?',
        "distractors": ['Onde fica a escola?', 'Onde fica o hotel?', 'Onde fica a saída?'],
        "explanation": 'Pergunta prática muito comum ao viajar; em francês, \'toilettes\' é sempre no plural.',
    },
    {
        "word": 'Peux-tu m\'aider ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Peux-tu m'aider ? » ?",
        "translation": 'Você pode me ajudar?',
        "distractors": ['Você pode me ver?', 'Você pode me ouvir?', 'Você pode me pagar?'],
        "explanation": 'Pedido básico de ajuda.',
    },
    {
        "word": 'Qu\'est-ce que c\'est ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Qu'est-ce que c'est ? » ?",
        "translation": 'O que é isso?',
        "distractors": ['Quando é isso?', 'Quem é este?', 'Onde está isso?'],
        "explanation": 'Pergunta básica sobre um objeto.',
    },
    {
        "word": 'Qui est-ce ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Qui est-ce ? » ?",
        "translation": 'Quem é aquele(a)?',
        "distractors": ['O que é aquilo?', 'Como está aquilo?', 'Onde está aquilo?'],
        "explanation": 'Pergunta básica sobre uma pessoa.',
    },
    {
        "word": 'Pourquoi ?',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Pourquoi ? » ?",
        "translation": 'Por quê?',
        "distractors": ['Onde?', 'Quem?', 'Quando?'],
        "explanation": 'Pergunta básica pedindo uma razão.',
    },
    {
        "word": 'Parce que',
        "part_of_speech": 'expressão',
        "tip": "Que signifie « Parce que » ?",
        "translation": 'Porque',
        "distractors": ['Quando', 'Onde', 'Quem'],
        "explanation": 'Usado para dar uma razão ou explicação.',
    },
    {
        "word": 'Comment tu t\'appelles ? Je m\'appelle Ana',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Comment tu t'appelles ? Je m'appelle Ana » ?",
        "translation": 'Comment tu t\'appelles ? Je m\'appelle Ana',
        "distractors": ['Quel âge as-tu ? Je vais bien', 'Quelle heure est-il ? Il est tard', 'D\'où viens-tu ? J\'habite ici'],
        "explanation": 'Combina a pergunta e a resposta básica sobre nome.',
    },
    {
        "word": 'D\'où viens-tu ? Je viens du Brésil',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « D'où viens-tu ? Je viens du Brésil » ?",
        "translation": 'D\'où viens-tu ? Je viens du Brésil',
        "distractors": ['Comment vas-tu ? Je vais bien', 'Qu\'est-ce que tu fais dans la vie ? Je travaille ici', 'Comment tu t\'appelles ? Je suis Ana'],
        "explanation": 'Combina pergunta e resposta sobre origem/nacionalidade.',
    },
    {
        "word": 'Merci beaucoup vraiment',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Merci beaucoup vraiment » ?",
        "translation": 'Muito obrigado mesmo',
        "distractors": ['Com certeza não', 'Sinto muito mesmo', 'De jeito nenhum mesmo'],
        "explanation": 'Combinação enfática de agradecimento.',
    },
    {
        "word": 'Je suis désolé, je suis en retard',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Je suis désolé, je suis en retard » ?",
        "translation": 'Desculpe, estou atrasado(a)',
        "distractors": ['Obrigado, estou pronto', 'Com licença, estou aqui', 'Desculpe, estou cedo'],
        "explanation": 'Combinação comum ao chegar atrasado.',
    },
    {
        "word": 'Je t\'en prie, entre',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Je t'en prie, entre » ?",
        "translation": 'Por favor, entre',
        "distractors": ['Por favor, saia', 'Por favor, sente', 'Por favor, espere'],
        "explanation": 'Combinação usada para convidar alguém a entrar.',
    },
    {
        "word": 'Assieds-toi, s\'il te plaît',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Assieds-toi, s'il te plaît » ?",
        "translation": 'Por favor, sente-se',
        "distractors": ['Por favor, levante-se', 'Por favor, saia', 'Por favor, corra'],
        "explanation": 'Combinação usada para convidar alguém a se sentar.',
    },
    {
        "word": 'Attends un moment, s\'il te plaît',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Attends un moment, s'il te plaît » ?",
        "translation": 'Por favor, espere um momento',
        "distractors": ['Por favor, fique calado', 'Por favor, corra rápido', 'Por favor, vá agora'],
        "explanation": 'Combinação usada para pedir paciência.',
    },
    {
        "word": 'Oui, bien sûr',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Oui, bien sûr » ?",
        "translation": 'Sim, claro',
        "distractors": ['Nunca, impossível', 'Não, de jeito nenhum', 'Talvez, não sei'],
        "explanation": 'Combinação afirmativa muito comum.',
    },
    {
        "word": 'Non, merci',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Non, merci » ?",
        "translation": 'Não, obrigado',
        "distractors": ['Claro que sim', 'Com certeza', 'Sim, por favor'],
        "explanation": 'Combinação usada para recusar educadamente.',
    },
    {
        "word": 'Pardon, excuse-moi',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Pardon, excuse-moi » ?",
        "translation": 'Desculpe, com licença',
        "distractors": ['Prazer, igualmente', 'Tchau, até logo', 'Obrigado, de nada'],
        "explanation": 'Combinação comum ao pedir passagem educadamente.',
    },
    {
        "word": 'Re-salut',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Re-salut » ?",
        "translation": 'Olá de novo',
        "distractors": ['Com licença agora', 'Tchau para sempre', 'Muito obrigado'],
        "explanation": 'Forma bem informal e comum de cumprimentar alguém que você já viu no mesmo dia.',
    },
    {
        "word": 'On se voit dans le coin',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « On se voit dans le coin » ?",
        "translation": 'Nos vemos por aí',
        "distractors": ['Nunca mais te vejo', 'Muito prazer nisso', 'Bom dia para você'],
        "explanation": 'Despedida informal e casual.',
    },
    {
        "word": 'Content de te voir',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Content de te voir » ?",
        "translation": 'Bom te ver',
        "distractors": ['Difícil te ver', 'Ruim te ver', 'Estranho te ver'],
        "explanation": 'Combinação amigável usada ao encontrar alguém.',
    },
    {
        "word": 'C\'était sympa de parler avec toi',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « C'était sympa de parler avec toi » ?",
        "translation": 'Foi bom falar com você',
        "distractors": ['Foi ruim falar com você', 'Não gostei de falar', 'Não quero falar mais'],
        "explanation": 'Combinação usada ao encerrar uma conversa agradável.',
    },
    {
        "word": 'Un instant, s\'il te plaît',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Un instant, s'il te plaît » ?",
        "translation": 'Só um momento, por favor',
        "distractors": ['Nunca mais espere', 'Corra rapidamente', 'Vá agora mesmo'],
        "explanation": 'Combinação usada para pedir uma pequena espera.',
    },
    {
        "word": 'Aucun problème',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Aucun problème » ?",
        "translation": 'Sem problema nenhum',
        "distractors": ['Impossível de resolver', 'Muito complicado', 'Um grande problema'],
        "explanation": 'Combinação informal usada como resposta tranquilizadora.',
    },
    {
        "word": 'D\'accord alors',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « D'accord alors » ?",
        "translation": 'Tudo bem então',
        "distractors": ['Tudo errado então', 'Impossível assim', 'Nada bem assim'],
        "explanation": 'Combinação usada para concordar ou aceitar algo.',
    },
    {
        "word": 'D\'accord, ça a l\'air bien',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « D'accord, ça a l'air bien » ?",
        "translation": 'Ok, parece bom',
        "distractors": ['Não, parece ruim', 'Talvez, parece estranho', 'Nunca, parece caro'],
        "explanation": 'Combinação informal de concordância positiva.',
    },
    {
        "word": 'Certainement / D\'accord',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Certainement / D'accord » ?",
        "translation": 'Com certeza / Pode deixar',
        "distractors": ['Nunca mais', 'Talvez amanhã', 'De jeito nenhum'],
        "explanation": 'Resposta afirmativa informal e descontraída.',
    },
    {
        "word": 'Tout de suite / Immédiatement',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Tout de suite / Immédiatement » ?",
        "translation": 'Imediatamente / Agora mesmo',
        "distractors": ['Nunca', 'Talvez amanhã', 'Mais tarde'],
        "explanation": 'Combinação que indica ação imediata.',
    },
    {
        "word": 'Par précaution / Au cas où',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « Par précaution / Au cas où » ?",
        "translation": 'Só por precaução / Só para garantir',
        "distractors": ['Sem motivo nenhum', 'Nunca mais', 'De qualquer jeito ruim'],
        "explanation": 'Combinação usada para indicar precaução.',
    },
    {
        "word": 'À propos',
        "part_of_speech": 'chunk',
        "tip": "Que signifie « À propos » ?",
        "translation": 'A propósito',
        "distractors": ['No final das contas', 'De jeito nenhum', 'Ao contrário disso'],
        "explanation": 'Combinação usada para introduzir um novo assunto.',
    },
    {
        "word": 'Salut, je m\'appelle Ana, enchantée de te rencontrer',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Salut, je m'appelle Ana, enchantée de te rencontrer » ?",
        "translation": 'Salut, je m\'appelle Ana, enchantée de te rencontrer',
        "distractors": ['Salut, à demain, prends soin de toi', 'Merci beaucoup, de rien', 'Pardon, excuse-moi, je suis en retard'],
        "explanation": 'Combina saudação, apresentação de nome e cortesia.',
    },
    {
        "word": 'Bonjour, comment vas-tu aujourd\'hui ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Bonjour, comment vas-tu aujourd'hui ? » ?",
        "translation": 'Bonjour, comment vas-tu aujourd\'hui ?',
        "distractors": ['Merci, de rien à toi aussi', 'Bonne nuit, à demain', 'Pardon, je ne te comprends pas'],
        "explanation": 'Une a saudação matinal com a pergunta sobre o estado da pessoa.',
    },
    {
        "word": 'Je suis désolé, je ne comprends pas',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je suis désolé, je ne comprends pas » ?",
        "translation": 'Je suis désolé, je ne comprends pas',
        "distractors": ['Merci, je comprends bien', 'Aucun problème, c\'est bon ainsi', 'Enchanté de te rencontrer aujourd\'hui'],
        "explanation": 'Combina o pedido de desculpas com a falta de compreensão.',
    },
    {
        "word": 'Excuse-moi, peux-tu m\'aider, s\'il te plaît ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Excuse-moi, peux-tu m'aider, s'il te plaît ? » ?",
        "translation": 'Excuse-moi, peux-tu m\'aider, s\'il te plaît ?',
        "distractors": ['Je suis désolé, je ne peux pas aider', 'Merci pour ton aide aujourd\'hui', 'De rien, aucun problème'],
        "explanation": 'Combina \'excuse-moi\' com o pedido de ajuda educado.',
    },
    {
        "word": 'Merci infiniment, tu es très gentil',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Merci infiniment, tu es très gentil » ?",
        "translation": 'Merci infiniment, tu es très gentil',
        "distractors": ['Bonjour, tu es très fatigué', 'Désolé, c\'est très impoli', 'À bientôt, c\'est très loin'],
        "explanation": 'Combina agradecimento enfático com um elogio de cortesia.',
    },
    {
        "word": 'Enchanté de te rencontrer, comment tu t\'appelles ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Enchanté de te rencontrer, comment tu t'appelles ? » ?",
        "translation": 'Enchanté de te rencontrer, comment tu t\'appelles ?',
        "distractors": ['Merci beaucoup, aucun problème', 'Adieu pour toujours, on ne se reverra jamais', 'Je suis désolé, excuse-moi s\'il te plaît'],
        "explanation": 'Combina a apresentação com a pergunta pelo nome.',
    },
    {
        "word": 'Je suis d\'accord avec toi, c\'est vrai',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je suis d'accord avec toi, c'est vrai » ?",
        "translation": 'Je suis d\'accord avec toi, c\'est vrai',
        "distractors": ['Je suis désolé, c\'est une erreur', 'Merci, de rien maintenant', 'Je ne suis pas d\'accord, ce n\'est pas vrai'],
        "explanation": 'Une concordância com confirmação de veracidade.',
    },
    {
        "word": 'Désolé, je ne suis pas d\'accord avec ça',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Désolé, je ne suis pas d'accord avec ça » ?",
        "translation": 'Désolé, je ne suis pas d\'accord avec ça',
        "distractors": ['Enchanté de te rencontrer, vraiment', 'Merci, je suis totalement d\'accord avec toi', 'De rien, c\'est très vrai'],
        "explanation": 'Combina desculpa com discordância educada.',
    },
    {
        "word": 'Excusez-moi, où sont les toilettes ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Excusez-moi, où sont les toilettes ? » ?",
        "translation": 'Excusez-moi, où sont les toilettes ?',
        "distractors": ['Merci, les toilettes sont belles', 'Je suis désolé, je ne te connais pas', 'S\'il te plaît, entre et assieds-toi'],
        "explanation": 'Combina \'excusez-moi\' com a pergunta prática de localização.',
    },
    {
        "word": 'Peux-tu répéter, s\'il te plaît ? Je ne comprends pas',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Peux-tu répéter, s'il te plaît ? Je ne comprends pas » ?",
        "translation": 'Peux-tu répéter, s\'il te plaît ? Je ne comprends pas',
        "distractors": ['Aucun problème, ne t\'inquiète pas', 'Je comprends tout, merci', 'Enchanté de te rencontrer, vraiment'],
        "explanation": 'Une o pedido de repetição com a explicação da dúvida.',
    },
    {
        "word": 'C\'est bon, ne t\'inquiète pas, aucun problème',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « C'est bon, ne t'inquiète pas, aucun problème » ?",
        "translation": 'C\'est bon, ne t\'inquiète pas, aucun problème',
        "distractors": ['Merci, c\'est très gentil', 'Excuse-moi, j\'ai besoin de ton aide', 'Je suis désolé, c\'est un gros problème'],
        "explanation": 'Reforça a tranquilização combinando três expressões parecidas.',
    },
    {
        "word": 'Bonne chance aujourd\'hui, prends soin de toi, à bientôt',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Bonne chance aujourd'hui, prends soin de toi, à bientôt » ?",
        "translation": 'Bonne chance aujourd\'hui, prends soin de toi, à bientôt',
        "distractors": ['Merci, de rien, salut', 'Joyeux anniversaire, bon retour, santé', 'Pardon, excuse-moi, je suis en retard'],
        "explanation": 'Combina três expressões sociais de despedida positiva.',
    },
    {
        "word": 'Oui, s\'il te plaît, merci beaucoup',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Oui, s'il te plaît, merci beaucoup » ?",
        "translation": 'Oui, s\'il te plaît, merci beaucoup',
        "distractors": ['Peut-être plus tard, je ne suis pas sûr', 'Non, merci, je n\'en veux pas', 'Je suis désolé, je ne peux pas l\'accepter'],
        "explanation": 'Combina aceitação educada com agradecimento enfático.',
    },
    {
        "word": 'Je suis désolé, c\'était de ma faute, excuse-moi',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Je suis désolé, c'était de ma faute, excuse-moi » ?",
        "translation": 'Je suis désolé, c\'était de ma faute, excuse-moi',
        "distractors": ['Enchanté de vous rencontrer, vraiment monsieur', 'De rien, aucun problème ici', 'Merci, c\'était très gentil'],
        "explanation": 'Combina desculpa, admissão de erro e pedido de licença.',
    },
    {
        "word": 'Salut, bonjour, comment vas-tu ?',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Salut, bonjour, comment vas-tu ? » ?",
        "translation": 'Salut, bonjour, comment vas-tu ?',
        "distractors": ['Pardon, excuse-moi, je suis en retard', 'Au revoir, bonne nuit, prends soin de toi maintenant', 'Merci beaucoup, de rien à toi aussi'],
        "explanation": 'Une duas saudações com a pergunta padrão sobre o estado da pessoa.',
    },
    {
        "word": 'Merci, et de rien à toi aussi',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Merci, et de rien à toi aussi » ?",
        "translation": 'Merci, et de rien à toi aussi',
        "distractors": ['Au revoir, et on se revoit aussi', 'S\'il te plaît, et aide-moi aussi', 'Pardon, et excuse-moi aussi'],
        "explanation": 'Combina agradecimento com a devolução de \'de rien\'.',
    },
    {
        "word": 'Enchanté de te rencontrer, à bientôt, salut',
        "part_of_speech": 'mini-frase',
        "tip": "Que signifie « Enchanté de te rencontrer, à bientôt, salut » ?",
        "translation": 'Enchanté de te rencontrer, à bientôt, salut',
        "distractors": ['Bonjour, comment vas-tu aujourd\'hui', 'Merci beaucoup, aucun problème maintenant', 'Pardon, excuse-moi, je ne sais pas'],
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


def _remove_legacy_words(api_base_url: str, headers: dict, language: str) -> int:
    """
    Apaga (se existirem) as palavras listadas em LEGACY_WORDS_TO_REMOVE
    para a LANGUAGE atual. Compara só por texto da palavra (case-insensitive),
    já que essas entradas antigas não faziam parte do lote novo.
    """
    if not LEGACY_WORDS_TO_REMOVE:
        return 0
    resp = requests.get(f"{api_base_url}/vocab-words", headers=headers)
    resp.raise_for_status()
    legacy_lower = {w.strip().lower() for w in LEGACY_WORDS_TO_REMOVE}
    removed = 0
    for w in resp.json():
        if w["language"].strip().lower() != language.strip().lower():
            continue
        if w["word"].strip().lower() not in legacy_lower:
            continue
        r = requests.delete(f"{api_base_url}/vocab-words/{w['id']}", headers=headers)
        if r.status_code in (200, 204):
            print(f"Removido (legado): '{w['word']}' (id={w['id']})")
            removed += 1
        else:
            print(f"Falha ao remover legado '{w['word']}' (id={w['id']}): {r.status_code} {r.text}")
    return removed


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

    print("Removendo palavras de teste/legado (se existirem)...")
    n_removed = _remove_legacy_words(API_BASE_URL, headers, LANGUAGE)
    if n_removed == 0:
        print("Nenhuma palavra de teste/legado encontrada (já removida ou nunca existiu).")

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
        f"\nConcluído. Removido(s) legado(s): {n_removed} | "
        f"Criado: {summary['Criado']} | "
        f"Atualizado: {summary['Atualizado']} | "
        f"Inalterado: {summary['Inalterado']}"
    )


if __name__ == "__main__":
    main()
