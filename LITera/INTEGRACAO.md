# LITera — protótipo separado

Esta pasta é independente do projeto LIT English. Para abrir o protótipo, abra `index.html` no navegador ou sirva a pasta com um servidor estático local.

## O que está implementado
- Tela de login sem criação de conta.
- Acesso de demonstração configurável para uma única conta de professor em `config.js`.
- Área do professor com campos para título, autor, nível, texto e imagem/capa; a imagem selecionada mostra uma prévia local.
- Botões de “Ler” e “Frases salvas” aparecem desativados, sem navegação.
- Publicação e persistência ainda não implementadas: o botão “Publicar texto” permanece desativado.
- Layout responsivo para desktop e celular.

## Credenciais para testar
Edite `config.js` e altere `teacherEmail`, `teacherPassword` e `teacherDisplayName`.

**Segurança:** a verificação atual é apenas para protótipo e ocorre no navegador. Não publique com credenciais reais. Para produção, autenticação deve ser feita pelo backend, com senha armazenada como hash e sessão/token validado no servidor.

## Colocar o botão LITera antes de “Teste de Inglês” na landing page existente
No arquivo `lit_english_frontend/index.html`, dentro de `.landing-header-actions`, adicione este link imediatamente antes do link `#teste-ingles-link`:

```html
<a href="../../LITera/index.html" class="btn-solid-primary">LITera</a>
```

Ajuste o caminho conforme o local em que a pasta `LITera` for publicada. Como esta entrega foi solicitada separada do projeto, nenhum arquivo original do LIT English foi alterado.
