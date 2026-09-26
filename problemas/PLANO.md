# Plano: enunciados em LaTeX

Objetivo: recriar em LaTeX os 668 enunciados das 58 listas, um arquivo por problema em `problemas/<lista>/<n>.tex`, fiéis ao PDF (texto, fórmulas, itens e figuras), verificados por `scripts/build_tex.py`. O PDF continua sendo a fonte de verdade; a transcrição serve para exibir o enunciado no site (KaTeX), melhorar a busca e permitir reuso.

Estado: piloto com 7 problemas de 7 autores aprovado (texto igual, fórmulas iguais, figuras recortadas do PDF). Progresso por lista: `python3 scripts/build_tex.py --status`.

## Convenções

- Um arquivo por problema, `problemas/<id da lista>/<n>.tex`, onde `n` é a ordem no índice (`data/problems.js`); só o corpo do enunciado, sem título nem número. Primeira linha: `% id: <lista>-<n> | título: ... | fonte: <pdf>, p. <página>`.
- Texto idêntico ao original, inclusive erros de digitação, marcados com `% sic:` no fim da linha. Itens seguem o estilo do original: `\textbf{a)}` corrido quando o autor escreveu corrido, `enumerate` quando há lista recuada.
- Fórmulas em `amsmath`; símbolos como no original (`\cdot`/`\times`, `\epsilon`/`\varepsilon`, unidades em itálico se o autor escreveu em modo matemático). Equações destacadas em `\[ \]`; sistemas em `align*`.
- Figuras: recorte do próprio PDF em `problemas/<lista>/fig/<n>.png` (várias: `<n>-2.png`, ...), com a caixa em `problemas/figuras.json` e a legenda reproduzida em texto pequeno. Não redesenhar.
- Não transcrever: cabeçalhos, resumos teóricos, "fórmulas importantes", gabaritos (podem virar `gabarito.tex` numa fase posterior).
- Idioma como no original (há listas em inglês).

## Protocolo por lista

1. Renderizar as páginas (`build_tex.py` já faz recortes; para ler, gerar PNG das páginas a 2×).
2. Transcrever todos os problemas da lista; marcar figuras em `figuras.json`.
3. `python3 scripts/build_tex.py <ids>`: exigir compilação limpa, similaridade de texto ≥ 0,95 (as diferenças aceitáveis são hifenização, legendas e rótulos de fonte) e conferir cada `build/tex/<id>-cmp.png` lado a lado.
4. Commit por lista (`Transcreve <lista> (n problemas)`), push em `v2`.

Ritmo do piloto: 3–5 min por problema simples, 10–15 por problema longo com itens e figuras. Estimativa total: ~40 h de trabalho de agente; com uma lista por subagente em paralelo (4–6 por vez), algumas sessões.

## Fase A — ferramentas antes do volume

- [ ] Recorte automático do problema para a comparação (posição do título no layout do pdfminer, por coluna), deixando `recortes.json` só como ajuste manual.
- [ ] Detecção automática de figuras (objetos imagem e agrupamentos de caminhos vetoriais dentro da faixa do problema, via `pypdfium2`), preenchendo `figuras.json` para revisão.
- [ ] Normalizador do diff: juntar palavras hifenizadas na quebra de linha, ignorar legendas "Figura N" e rótulos de fonte, mostrar só diferenças reais.
- [ ] `--status` com similaridade mínima por lista e figuras pendentes (problemas cuja faixa tem imagem e o `.tex` não tem `\includegraphics`).
- [ ] Prompt de subagente: uma lista por agente, com as convenções acima e o ciclo transcrever → compilar → comparar → corrigir.

## Fase B — Modelo novo (2024–2025): «Problema N.», LaTeX limpo, uma figura por problema no máximo

| Lista | Autor | Probl. | Pág. | Imagens | Obs. | Feito |
|---|---|---:|---:|---:|---|---:|
| `2024-tavares-1` | Lucas Tavares | 12 | 2 | 7 |  | 1/12 |
| `2024-paulohenrique-1` | Paulo Henrique | 10 | 3 | 8 |  | 0/10 |
| `2024-paulohenrique-2` | Paulo Henrique | 10 | 3 | 4 |  | 0/10 |
| `2024-hemetrio-1` | Gabriel Hemétrio | 10 | 2 | 5 |  | 0/10 |
| `2024-hemetrio-2` | Gabriel Hemétrio | 24 | 5 | 16 |  | 0/24 |
| `2024-akira-1` | Akira Ito | 10 | 3 | 13 |  | 0/10 |
| `2024-baptista-1` | Gabriel Baptista | 10 | 3 | 11 |  | 0/10 |
| `2024-jonatas-1` | Jônatas Augusto | 10 | 3 | 14 |  | 0/10 |
| `2024-sena-1` | Rafael Sena | 10 | 5 | 16 | muitas figuras vetoriais | 0/10 |
| `2025-evers-1` | João Victor Evers | 10 | 3 | 6 |  | 0/10 |
| `2025-gurjao-1` | Arthur Gurjão | 7 | 3 | 5 |  | 1/7 |
| `2025-takashi-1` | Vitor Takashi | 12 | 4 | 13 |  | 0/12 |
| `2025-tavares-1` | Lucas Tavares | 5 | 6 | 6 |  | 0/5 |

## Fase C — 2020–2022: títulos criativos, duas colunas, mais figuras; termina com as listas longas e as em inglês

| Lista | Autor | Probl. | Pág. | Imagens | Obs. | Feito |
|---|---|---:|---:|---:|---|---:|
| `2020-maciel-1parte1` | Davi Maciel | 10 | 2 | 7 |  | 0/10 |
| `2020-maciel-1parte2` | Davi Maciel | 9 | 2 | 1 |  | 0/9 |
| `2020-maciel-2` | Davi Maciel | 9 | 2 | 6 |  | 0/9 |
| `2020-maciel-3` | Davi Maciel | 14 | 4 | 4 | gráfico com grade (figura) no problema 3 | 1/14 |
| `2020-maciel-4` | Davi Maciel | 15 | 2 | 2 |  | 0/15 |
| `2020-maciel-5` | Davi Maciel | 10 | 2 | 7 |  | 0/10 |
| `2020-maciel-6` | Davi Maciel | 10 | 2 | 8 |  | 0/10 |
| `2020-vinicius-1` | Vinícius Ferreira | 20 | 4 | 11 |  | 0/20 |
| `2020-vinicius-2` | Vinícius Ferreira | 11 | 3 | 4 |  | 0/11 |
| `2020-vinicius-3` | Vinícius Ferreira | 12 | 3 | 6 |  | 0/12 |
| `2020-ygor-1` | Ygor de Santana | 7 | 1 | 1 |  | 0/7 |
| `2020-ygor-2` | Ygor de Santana | 6 | 2 | 2 |  | 0/6 |
| `2020-capelo-1` | Gabriel Capelo | 21 | 5 | 3 |  | 0/21 |
| `2021-italo-1` | Antônio Ítalo | 14 | 5 | 7 |  | 0/14 |
| `2021-italo-2` | Antônio Ítalo | 12 | 3 | 4 |  | 1/12 |
| `2021-italo-3` | Antônio Ítalo | 9 | 3 | 2 | idem, resumo teórico | 0/9 |
| `2021-eduarda-1` | Eduarda Freitas | 8 | 2 | 0 | tem resumo teórico antes dos problemas (não transcrever) | 0/8 |
| `2021-felipe-1` | Felipe Ribeiro | 14 | 5 | 5 |  | 0/14 |
| `2021-nevoa-1` | Vinicius Névoa | 11 | 3 | 0 | idem, resumo teórico | 0/11 |
| `2022-ualype-1` | Ualype Uchôa | 8 | 3 | 8 | fórmulas importantes no topo (não transcrever) | 1/8 |
| `2022-ualype-2` | Ualype Uchôa | 10 | 4 | 9 |  | 0/10 |
| `2020-rafael-1` | Rafael Basto | 14 | 7 | 9 | mistura português e inglês | 0/14 |
| `2020-nevoa-1` | Vinicius Névoa | 10 | 5 | 0 | feita no Word: conferir fórmulas com cuidado | 0/10 |
| `2021-ponciano-1` | Matheus Ponciano | 15 | 14 | 15 | 14 p., muitos itens e fotos | 0/15 |
| `2021-ponciano-2` | Matheus Ponciano | 15 | 11 | 9 | em inglês | 0/15 |
| `2022-caio-1` | Caio Augusto | 4 | 11 | 14 | em inglês, 4 problemas longos com itens | 0/4 |

## Fase D — 2019: listas densas (Bastos, Luciano), estilo revtex; Bastos 5 por último (11 páginas, problemas longos, partes em inglês)

| Lista | Autor | Probl. | Pág. | Imagens | Obs. | Feito |
|---|---|---:|---:|---:|---|---:|
| `2019-timbo-1` | Rafael Timbó | 11 | 5 | 2 |  | 1/11 |
| `2019-timbo-2` | Rafael Timbó | 9 | 5 | 0 |  | 0/9 |
| `2019-timbo-3` | Rafael Timbó | 10 | 4 | 1 |  | 0/10 |
| `2019-timbo-4` | Rafael Timbó | 10 | 3 | 6 |  | 0/10 |
| `2019-timbo-5` | Rafael Timbó | 10 | 2 | 4 |  | 0/10 |
| `2019-timbo-6` | Rafael Timbó | 11 | 2 | 6 |  | 0/11 |
| `2019-timbo-7` | Rafael Timbó | 10 | 2 | 6 |  | 0/10 |
| `2019-timbo-8` | Rafael Timbó | 3 | 1 | 2 |  | 0/3 |
| `2019-timbo-9` | Rafael Timbó | 6 | 5 | 5 |  | 0/6 |
| `2019-paulo-1` | Paulo Kitayama | 11 | 8 | 8 |  | 0/11 |
| `2019-levy-1` | Levy Bruno | 20 | 7 | 17 |  | 0/20 |
| `2019-luciano-1` | Luciano Leão | 17 | 3 | 11 |  | 0/17 |
| `2019-luciano-2` | Luciano Leão | 15 | 3 | 10 |  | 0/15 |
| `2019-bastos-1` | Victor Bastos | 20 | 6 | 12 | 20 problemas, 12 figuras | 0/20 |
| `2019-bastos-2` | Victor Bastos | 15 | 6 | 9 |  | 0/15 |
| `2019-bastos-3` | Victor Bastos | 17 | 4 | 13 |  | 0/17 |
| `2019-bastos-4` | Victor Bastos | 15 | 3 | 1 |  | 1/15 |
| `2019-bastos-5dlc` | Victor Bastos | 5 | 2 | 5 |  | 0/5 |
| `2019-bastos-5` | Victor Bastos | 15 | 11 | 21 | 11 p., problemas longos de olimpíada, trechos em inglês | 0/15 |

## Fase E — uso no site

- Converter cada `.tex` em HTML (parágrafos, negrito, itens, figuras) com a matemática renderizada por KaTeX no painel do problema, no lugar do texto extraído que foi removido.
- Usar o texto limpo das transcrições na busca (hoje a busca usa o texto extraído do PDF).
- Opcional: gabaritos por lista e um PDF consolidado por lista gerado das transcrições.
