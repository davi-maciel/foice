# FOICE

Listas de exercícios do FOICE, organizadas por edição das olimpíadas internacionais de física e por autor — e um banco de problemas que indexa todos os enunciados para busca por tema, autor, ano ou palavra-chave.

Site estático (sem build no deploy), hospedado na Vercel em https://ipho.com.br.

## Estrutura

- `index.html`, `assets/base.css`, `assets/ui/*.css`, `assets/app.js` — o site: busca instantânea, filtros por tema/ano/autor/dificuldade, leitor que abre o PDF na página do problema, sorteio de problema e progresso ("resolvido") salvo no navegador. A visão "Listas" mantém a organização original por ano e autor.
- `listas/<ano>/<Autor>/lista<ano><autor><n>.pdf` — os PDFs originais. O ano indica para qual edição da IPhO os alunos se preparavam.
- `data/catalog.json` — catálogo das listas: ano, autor, arquivo, rótulo e, opcionalmente, `hint` com o tema predominante da lista.
- `data/problems.js` — índice gerado: um registro por problema (título, página, tema, dificuldade quando o autor marcou, trecho do enunciado, problemas parecidos).
- `data/overrides.json` — correções manuais de tema ou título, por id de problema (`<ano>-<autor>-<lista>-<n>`).
- `data/similar_overrides.json` — pares que o cálculo de semelhança acha parecidos mas que não são o mesmo problema.
- `scripts/build_index.py` e `scripts/pdftext.py` — extraem o texto dos PDFs e geram `data/problems.js`.

## Adicionar uma lista

1. Salve o PDF em `listas/<ano>/<Autor>/`, seguindo o padrão de nome.
2. Acrescente a entrada correspondente em `data/catalog.json`.
3. Instale a dependência uma vez (`pip install pdfminer.six`) e rode `python3 scripts/build_index.py --debug`.
4. Confira no terminal os problemas detectados; se um tema ou título saiu errado, corrija em `data/overrides.json` e rode de novo. No fim da saída vem o relatório de problemas parecidos (veja abaixo).
5. Faça commit do PDF, do catálogo e do `data/problems.js` gerado.

Os temas são atribuídos automaticamente por palavras-chave (com um viés para o tema predominante de cada lista), então podem conter erros — correções são bem-vindas.

## Problemas parecidos

Muitos problemas reaparecem anos depois: o mesmo enunciado com outro título, uma versão reescrita, ou o mesmo problema com itens a mais. O `build_index.py` detecta esses casos e grava, em cada problema de `data/problems.js`, `similar` (até 8 vizinhos, `{id, score}`, do mais parecido para o menos) e `group` (um id compartilhado pelos membros do mesmo agrupamento). No site, o painel de detalhes lista os "Problemas parecidos" e os cards ganham um selo "N versões".

Como a comparação é feita, a partir de `título + enunciado` sem acentos, números, pontuação, resíduo de LaTeX nem palavras vazias:

- **`cos`** — cosseno sobre TF-IDF de unigramas e bigramas de palavras. Pega enunciados reescritos.
- **`cont`** — *containment*: 3-gramas de palavras em comum dividido pelo número de 3-gramas do texto **mais curto**. Pega a versão que manteve o enunciado original e acrescentou itens.

Um par é aceito quando `cos >= SIM_COS`, ou quando `cont >= SIM_CONT` e o cosseno é pelo menos `SIM_CONT_COS` (sozinho, o containment escorrega em enunciados curtos). Enunciados com menos de `SIM_MIN_TOKENS` palavras de conteúdo ("Calcule o rendimento do ciclo termodinâmico da figura") são genéricos demais e ficam de fora; dois problemas da *mesma* lista precisam de `SIM_SAME_LIST`, bem mais alto, porque uma lista repete o tema o tempo todo. Os grupos são as componentes conexas dos pares aceitos.

### Como calibrar os limiares

As constantes estão todas juntas no topo da seção "near-duplicates" de `scripts/build_index.py`. Depois de mexer nelas:

1. Rode `python3 scripts/build_index.py --debug` e leia o relatório no fim da saída: ele mostra **todos** os candidatos com os dois scores, título, autor e ano, marcados `OK` (aceito) ou `--` (com o motivo da recusa). Um componente com mais de `SIM_BIG_GROUP` membros vem sinalizado com `ATENÇÃO` — quase sempre é sinal de limiar frouxo.
2. Confira os pares no limite, nos dois sentidos: os últimos `OK` e os primeiros `--`.
3. Par errado que passou: acrescente-o a `data/similar_overrides.json` (`{"exclude": [["id1", "id2"], ...]}`) e rode de novo. Precisão importa mais do que recall aqui: é melhor perder uma repetição do que afirmar que dois problemas diferentes são o mesmo.

Os limiares atuais foram ajustados lendo esse relatório par a par. Duas coisas que ficaram claras no caminho:

- **5-gramas de caracteres funcionam pior que 3-gramas de palavras** para o containment. Problemas como "esfera uniformemente polarizada" e "esfera uniformemente magnetizada" são problemas *diferentes* escritos quase com as mesmas letras, e os n-gramas de caracteres não os separam.
- **Traduções não batem.** As listas em inglês (Caio 2022, Rafael 2020, Ponciano 2021 lista 2) não são reconhecidas como iguais às suas versões em português, porque a comparação é sobre palavras. É uma limitação aceita: encontrar esses pares exigiria tradução ou embeddings, e o site não tem build nem dependência externa.

## Aparências (UIs)

O mesmo HTML e o mesmo `app.js` servem seis aparências, trocadas pelo seletor "UI" no cabeçalho (a escolha fica salva no navegador e vai no `#ui=` da URL). `assets/base.css` tem só a mecânica compartilhada (painel, acessibilidade, resets); cada arquivo em `assets/ui/` é uma UI completa e independente, com suas próprias fontes (Google Fonts) e sem JavaScript extra:

| Arquivo | Ideia | Inspiração |
| --- | --- | --- |
| `atual.css` | papel quente, cartões, dourado | design original do banco |
| `jornal.css` | índice editorial em colunas, serifa, filetes, vermelho de tinta | sumário das Feynman Lectures, Typewolf, Public Domain Review |
| `terminal.css` | mono, uma linha por problema, âmbar sobre azul-noite | Advent of Code, U.S. Graphics, Brutalist Websites, arquivo do Project Euler |
| `suico.css` | grotesca enorme, grade de 1px, preto/branco + um vermelho | Grilli Type, Klim, sites tipográficos do Siteinspire |
| `cartaz.css` | bordas grossas, sombras duras, amarelo/azul/vermelho, formas | faixas do catálogo Klim, cartazes Bauhaus, neobrutalismo do Land-book |
| `biblioteca.css` | verde-couro e dourado, Garamond, sumário com pontilhado | Stripe Press, Whole Earth Index, sumários impressos |

Para criar outra: copie um arquivo de `assets/ui/`, acrescente o nome à lista `UIS` em `index.html` (script inline) e em `assets/app.js`, e uma `<option>` no seletor.
