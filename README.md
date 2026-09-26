# FOICE

Listas de exercícios do FOICE, organizadas por edição das olimpíadas internacionais de física e por autor — e um banco de problemas que indexa todos os enunciados para busca por tema, autor, ano ou palavra-chave.

Site estático (sem build no deploy), hospedado na Vercel em https://ipho.com.br.

## Estrutura

- `index.html`, `assets/style.css`, `assets/app.js` — o site: busca instantânea, filtros por tema/ano/autor/dificuldade, leitor que abre o PDF na página do problema, sorteio de problema e progresso ("resolvido") salvo no navegador. A visão "Listas" mantém a organização original por ano e autor.
- `listas/<ano>/<Autor>/lista<ano><autor><n>.pdf` — os PDFs originais. O ano indica para qual edição da IPhO os alunos se preparavam.
- `data/catalog.json` — catálogo das listas: ano, autor, arquivo, rótulo e, opcionalmente, `hint` com o tema predominante da lista.
- `data/problems.js` — índice gerado: um registro por problema (título, página, tema, dificuldade quando o autor marcou, trecho do enunciado, problemas parecidos).
- `data/overrides.json` — correções manuais de tema ou título, por id de problema (`<ano>-<autor>-<lista>-<n>`).
- `data/similar_overrides.json` — pares que o cálculo de semelhança acha parecidos mas que não são o mesmo problema.
- `scripts/build_index.py` e `scripts/pdftext.py` — extraem o texto dos PDFs e geram `data/problems.js`.
- `problemas/<lista>/<n>.tex` — transcrições em LaTeX dos enunciados (piloto), com `problemas/preamble.tex`, as figuras recortadas dos PDFs em `problemas/<lista>/fig/` e os metadados de recorte em `problemas/figuras.json` e `problemas/recortes.json`.
- `data/crops/<id>.png` e `data/crops.js` — recorte de cada problema no seu PDF (título até o título seguinte, seguindo colunas e páginas), gerado por `scripts/crop_problems.py`; o painel mostra esse recorte e, sem ele, cai no visualizador de PDF.
- `scripts/build_tex.py` — compila cada transcrição (Tectonic) e a compara com o PDF original: similaridade do texto extraído, lista de palavras que diferem e uma imagem lado a lado em `build/tex/<id>-cmp.png`.

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

## Recortes dos problemas

`python3 scripts/crop_problems.py [ids ou listas]` (precisa de `pip install pypdfium2 pillow`) localiza cada problema pelas posições dos títulos no layout, junta os trechos de cada coluna/página numa imagem só, inclui as figuras da faixa (inclusive as que o LaTeX empurrou para o topo da coluna seguinte) e exclui cabeçalhos, rodapés, notas, títulos de seção e o gabarito. Sem argumentos, recorta os 668 problemas (~18 MB em `data/crops/`). `--audit` confere, sem gravar, se alguma linha do problema ficou de fora ou se alguma linha de outro problema entrou; `--debug` imprime os retângulos. Regenerar depois de mexer no parser (`build_index.py`), porque os índices vêm dele.

## Design

Grade internacional: Archivo, preto e branco com um vermelho só para estado, filetes de 1px formando a tabela, números grandes marcando o ritmo. Inspirações: Grilli Type, Klim e os sites tipográficos do Siteinspire. As cores são estruturais e nunca identificam temas.

## Transcrições em LaTeX

Os PDFs foram feitos em LaTeX, mas os fontes não estão no repositório; `problemas/` recria os enunciados um a um. Cada arquivo `problemas/<lista>/<n>.tex` contém só o corpo do enunciado, começa com um comentário `% id: ... | fonte: ...` e mantém o texto do original (erros de digitação ficam marcados com `% sic`). Para conferir:

```
brew install tectonic && pip install pypdfium2 pillow
python3 scripts/build_tex.py                 # todos
python3 scripts/build_tex.py 2020-maciel-3-1 # um só
```

O script imprime a similaridade do texto (as diferenças normais são hifenização e legendas) e grava `build/tex/<id>-cmp.png` com o recorte do PDF à esquerda e a transcrição à direita. Figuras entram como recortes do próprio PDF, definidos em `problemas/figuras.json`.
