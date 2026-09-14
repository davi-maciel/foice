# FOICE

Listas de exercícios do FOICE, organizadas por edição das olimpíadas internacionais de física e por autor — e um banco de problemas que indexa todos os enunciados para busca por tema, autor, ano ou palavra-chave.

Site estático (sem build no deploy), hospedado na Vercel em https://ipho.com.br.

## Estrutura

- `index.html`, `assets/style.css`, `assets/app.js` — o site: busca instantânea, filtros por tema/ano/autor/dificuldade, leitor que abre o PDF na página do problema, sorteio de problema e progresso ("resolvido") salvo no navegador. A visão "Listas" mantém a organização original por ano e autor.
- `listas/<ano>/<Autor>/lista<ano><autor><n>.pdf` — os PDFs originais. O ano indica para qual edição da IPhO os alunos se preparavam.
- `data/catalog.json` — catálogo das listas: ano, autor, arquivo, rótulo e, opcionalmente, `hint` com o tema predominante da lista.
- `data/problems.js` — índice gerado: um registro por problema (título, página, tema, dificuldade quando o autor marcou, trecho do enunciado).
- `data/overrides.json` — correções manuais de tema ou título, por id de problema (`<ano>-<autor>-<lista>-<n>`).
- `scripts/build_index.py` e `scripts/pdftext.py` — extraem o texto dos PDFs e geram `data/problems.js`.

## Adicionar uma lista

1. Salve o PDF em `listas/<ano>/<Autor>/`, seguindo o padrão de nome.
2. Acrescente a entrada correspondente em `data/catalog.json`.
3. Instale a dependência uma vez (`pip install pdfminer.six`) e rode `python3 scripts/build_index.py --debug`.
4. Confira no terminal os problemas detectados; se um tema ou título saiu errado, corrija em `data/overrides.json` e rode de novo.
5. Faça commit do PDF, do catálogo e do `data/problems.js` gerado.

Os temas são atribuídos automaticamente por palavras-chave (com um viés para o tema predominante de cada lista), então podem conter erros — correções são bem-vindas.
