# LIT English — Frontend

Frontend simples em HTML, CSS e JS puro (sem build, sem framework).

## O que já está pronto

- **Login** (`index.html`) — autentica no backend (`POST /auth/login`), busca o usuário logado (`GET /auth/me`) e trata os casos de conta pendente de aprovação e de login como professor.
- **Revisar** (`revisar.html`) — tela de revisão de flashcards com SM-2, em layout centralizado e ampliado:
  - busca a fila do dia (`GET /flashcards/review/next`)
  - vira o card, toca a pronúncia em inglês com voz neural (via endpoint `/tts/speak` do backend, que usa o serviço gratuito de TTS do Google Translate); se o backend ou a internet falharem, cai automaticamente para a Web Speech API nativa do navegador
  - envia a avaliação do aluno (`POST /flashcards/review/{id}`) com os botões Esqueci / Difícil / Ok / Fácil
  - trata os estados de "sem cards agora", "limite de revisões atingido" e "revisão concluída"
- **Read and Listen** (`textos.html`, aluno) — lista os textos disponíveis (`GET /texts`) como cartões com título e nível CEFR; ao clicar em um, abre o texto completo (`GET /texts/{id}`) com tradução opcional e um player de áudio (play/pause) que usa o `/tts/speak` do backend, dividindo o texto em frases para contornar o limite de caracteres do TTS e tocá-las em sequência.
- **Exercícios** (`exercicios.html`) — carrossel de flashcards de exercícios (fill in the blank, listen and type, speaking), um por vez, do mais antigo para o mais novo. Cada exercício tem botão "Confirmar" (trava a resposta/áudio) e depois "Enviar" (corrige com o backend e mostra o resultado), avançando para o próximo ao confirmar.
- **Painel do professor** (`professor.html`) — Flashcards (criar/editar/excluir), Read and Listen (criar/editar/excluir textos com título, nível CEFR, texto em inglês e tradução), Exercícios (criar/atribuir/ver submissões) e Configurações (que inclui a aprovação/bloqueio de alunos).

O menu do aluno é simples: Revisar, Exercícios, Read and Listen e Meu Vocabulário. O item "Meu Vocabulário" ainda não tem página própria e mostra um aviso de "em construção". O botão "Sair" faz logout (tanto para aluno quanto para professor).

## Como rodar

1. Suba o backend (na pasta `lit_english_backend`):
   ```bash
   uvicorn app.main:app --reload
   ```
   Ele sobe em `http://127.0.0.1:8000` por padrão.

2. Confira a URL configurada em `js/api.js`:
   ```js
   const API_BASE_URL = "http://127.0.0.1:8000";
   ```
   Ajuste aqui se o backend estiver rodando em outro endereço.

3. Abra `index.html` diretamente no navegador (duplo clique) ou sirva a pasta com um servidor estático simples, por exemplo:
   ```bash
   python3 -m http.server 5500
   ```
   e acesse `http://127.0.0.1:5500`.

4. Crie um usuário pelo Swagger do backend (`/docs` → `POST /auth/register`) — um professor (aprovado automaticamente) e um aluno. Aprove o aluno em `PATCH /admin/students/{id}/approve` e cadastre alguns flashcards em `POST /flashcards` (ou um texto em `POST /texts`). Depois faça login com o aluno no frontend para testar a revisão e a leitura.

## Estrutura

```
lit_english_frontend/
├── index.html        → tela de login
├── revisar.html       → tela de revisão (sidebar + flashcards)
├── exercicios.html     → tela de exercícios do aluno (carrossel tipo flashcard)
├── textos.html        → tela "Read and Listen" do aluno (lista de textos + leitor/player)
├── professor.html     → painel do professor (flashcards, textos, exercícios, configurações)
├── css/
│   └── style.css      → estilos e tokens visuais (cores, tipografia, layout)
└── js/
    ├── api.js          → comunicação com o backend (login, fetch autenticado)
    ├── icons.js         → ícones SVG usados nas telas
    ├── login.js         → lógica da tela de login
    ├── revisar.js       → lógica da tela de revisão
    ├── exercicios.js     → lógica da tela de exercícios do aluno
    ├── textos.js         → lógica da tela "Read and Listen" do aluno
    └── professor.js      → lógica do painel do professor
```
