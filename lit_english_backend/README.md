# LIT English — Backend

## Como rodar

1. Crie um ambiente virtual (recomendado):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # no Windows: venv\Scripts\activate
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Rode o servidor:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Acesse a documentação interativa (Swagger) no navegador:
   ```
   http://127.0.0.1:8000/docs
   ```

   Lá você já consegue testar tudo visualmente, sem precisar de curl ou Postman.

## O que já funciona

### Autenticação
- `POST /auth/register` — cria um usuário (professor ou aluno)
  - Professor → aprovado automaticamente
  - Aluno → fica com `is_approved: false` até o professor aprovar
- `POST /auth/login` — faz login e retorna um token JWT
  - No Swagger, use o botão **Authorize** (cadeado) e cole o e-mail/senha
  - No curl: `curl -X POST http://127.0.0.1:8000/auth/login -d "username=SEU_EMAIL&password=SUA_SENHA"`
- `GET /auth/me` — retorna os dados do usuário logado (precisa do token)

### Admin (professor)
- `GET /admin/students` — lista todos os alunos
- `PATCH /admin/students/{id}/approve` — aprova o acesso de um aluno
- `PATCH /admin/students/{id}/revoke` — bloqueia o acesso de um aluno

### Flashcards
- Professor: CRUD completo (`POST /flashcards`, `GET /flashcards`, `PUT /flashcards/{id}`, `DELETE /flashcards/{id}`)
- Aluno: revisão com SM-2 (`GET /flashcards/review/next`, `POST /flashcards/review/{id}`), limite de 15 cards a cada 12h
- "Meu Vocabulário" é simplesmente a listagem de Flashcards — inclui os criados manualmente pelo professor e os gerados automaticamente pelo QA

### TTS (pronúncia em áudio)
- `GET /tts/speak?text=...` — retorna um MP3 com a pronúncia em inglês do texto enviado (precisa de token, qualquer usuário aprovado pode usar)
- O backend funciona como proxy para o serviço de TTS neural do Google Translate (gratuito, sem chave de API), evitando o bloqueio de CORS que ocorre ao chamar esse serviço direto do navegador
- Os áudios mais usados ficam em cache em memória no processo do servidor
- Usado pelo botão de "ouvir pronúncia" na tela de revisão de flashcards. Se o serviço estiver indisponível, o frontend cai automaticamente para a Web Speech API nativa do navegador

### Read and Listen
- Professor: CRUD de textos (`POST /texts`, `GET /texts`, `PUT /texts/{id}`, `DELETE /texts/{id}`) — cada texto tem título, nível CEFR (`A1`–`C2`), texto em inglês e tradução em português
- Aluno: lista e lê os textos (`GET /texts`, `GET /texts/{id}`)

### Exercícios (fill the blank / tradução)
- Professor: CRUD (`POST /exercises`, `GET /exercises`, `PUT /exercises/{id}`, `DELETE /exercises/{id}`)
- Aluno: pratica (`GET /exercises/practice`) e envia resposta (`POST /exercises/{id}/check`) — cada tentativa de um aluno é registrada automaticamente
- Professor: histórico completo de tentativas (`GET /exercises/submissions`, filtrável por `student_id` e/ou `exercise_id`) — mostra resposta, se acertou e quando

### QA (exclusivo do professor)
O QA não é acessado pelos alunos — é uma ferramenta do professor para usar durante a aula, ao vivo:
- `POST /qa/questions/bulk` — cola uma lista de perguntas (uma por linha) e cadastra todas de uma vez
- `GET /qa/questions` — lista todas as perguntas cadastradas
- `DELETE /qa/questions/{id}` — remove uma pergunta
- `GET /qa/questions/random` — sorteia uma pergunta do banco para fazer ao aluno
- `POST /qa/answers` — registra o que o aluno respondeu (em inglês) + tradução/contexto opcional.
  Isso cria automaticamente um **Flashcard** (front = resposta do aluno, back = tradução/contexto),
  que passa a aparecer em "Meu Vocabulário"
- `GET /qa/answers` — histórico de respostas registradas, filtrável por `student_id`

## Banco de dados

Um arquivo `lit_english.db` (SQLite) será criado automaticamente na primeira vez que você rodar o servidor. Pode deletar esse arquivo a qualquer momento para resetar tudo.

## Novidades da v18

- **Histórico de exercícios em um bloco só por envio**: ao enviar (ou reenviar) os mesmos exercícios para vários alunos de uma vez, agora é criado **um único lote** no histórico, vinculado a todos os alunos selecionados — em vez de um lote repetido por aluno.
- **Excluir lote do histórico**: `DELETE /exercises/batches/{batch_id}` remove o registro do histórico (não revoga os exercícios já atribuídos aos alunos).
- **Editar exercício**: `PATCH /exercises/{exercise_id}` permite editar título, frase, resposta correta, tradução etc. A edição reflete em todos os lotes do histórico que contêm esse exercício.
- **Submissões "OK — Visualizado" agora é permanente**: `POST /exercises/submissions/dismiss` marca o grupo aluno+dia como visualizado no banco, então ele não reaparece mesmo depois de atualizar a página.

## Próximas etapas

1. ✅ Autenticação (professor / aluno, aprovação manual)
2. ✅ Painel do professor: aprovar/bloquear alunos
3. ✅ Flashcards (CRUD do professor + revisão SM-2 do aluno)
4. ✅ Read and Listen (textos + tradução, TTS no navegador)
5. ✅ Exercícios (fill the blank / tradução) + histórico de submissões
6. ✅ QA (banco de perguntas do professor + registro de respostas + geração automática de flashcard)
7. ⏳ Frontend

