#!/usr/bin/env python3
"""Recorta cada problema do seu PDF em uma imagem única (data/crops/<id>.png).

A região de um problema vai do título dele até o título do seguinte (ou até o gabarito), seguindo as
colunas e as páginas: cada trecho contínuo (página, coluna) vira um retângulo; cabeçalhos, rodapés e
notas de rodapé ficam de fora; figuras vetoriais ou imagens que estejam na faixa do problema (inclusive
logo antes do primeiro ou depois do último texto) entram no retângulo. Os retângulos são renderizados
com pypdfium2 e empilhados numa imagem só. Também escreve data/crops.js com {id: [largura, altura]}.

Uso: python3 scripts/crop_problems.py [--scale 2.2] [--debug] [ids ou ids de lista...]
"""
import json, os, re, sys
import pypdfium2 as pdfium
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from pdftext import extract_rows
import build_index as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "crops"); os.makedirs(OUT, exist_ok=True)
DATA = json.loads(open(os.path.join(ROOT, "data", "problems.js"), encoding="utf-8").read()[len("window.FOICE = "):].rstrip().rstrip(";"))
LISTS = {l["id"]: l for l in DATA["lists"]}
CATALOG = {c["file"]: c for c in json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))}
FOOT_RE = re.compile(r"^(-?p[áa]gina \d+( de \d+)?-?|\d{1,2}|[∗†‡*]\s*.{0,24})$", re.I)
PAD = 4.0

def is_chrome(row, pg, author):
    t = row["text"].strip()
    if B.HEADER_RE.match(t) or FOOT_RE.match(t) or t == author: return True
    if len(t.split()) <= 3 and len(t) >= 4 and t in author: return True          # "Ualype", "Italo"
    if row["y0"] >= pg["top"] - 0.5 or row["y1"] <= pg["bottom"] + 0.5: return True  # zona de cabeçalho/rodapé
    if row["kind"] == "full" and (row["y0"] > pg["h"] * 0.93 or row["y1"] < pg["h"] * 0.07): return True
    return False

def content_zone(pdf, pi, pg):
    """(topo, base) da área útil: abaixo do filete de cabeçalho e acima do de rodapé, se existirem."""
    top, bottom = pg["h"] * 0.94, pg["h"] * 0.06
    for o in pdf[pi - 1].get_objects(max_depth=1):
        if o.type != 2: continue
        try: x0, y0, x1, y1 = bounds(o)
        except Exception: continue
        if x1 - x0 > 0.5 * pg["w"] and y1 - y0 < 3:
            if y0 > 0.85 * pg["h"]: top = min(top, y0 - 1)
            elif y1 < 0.15 * pg["h"]: bottom = max(bottom, y1 + 1)
    return top, bottom

def bounds(o):
    """(x0, y0, x1, y1) de um objeto da página, compatível com pypdfium2 4.x (get_pos) e 5.x (get_bounds)."""
    fn = getattr(o, "get_bounds", None) or getattr(o, "get_pos")
    b = fn()
    return (b.left, b.bottom, b.right, b.top) if hasattr(b, "left") else tuple(b)

def page_objects(pdf, pi, pg):
    """Caixas (x0, y0, x1, y1) de imagens e desenhos vetoriais da página, sem filetes de cabeçalho/rodapé."""
    boxes = []
    # só objetos de nível 0: os aninhados (dentro de form XObjects) têm coordenadas do próprio form,
    # não da página; o form em si (tipo 5) é a figura inteira.
    for o in pdf[pi - 1].get_objects(max_depth=1):
        if o.type not in (2, 3, 4, 5): continue
        try: x0, y0, x1, y1 = bounds(o)
        except Exception: continue
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0: continue
        if h < 6 and w > 0.5 * pg["w"]: continue            # filetes de cabeçalho/rodapé
        if w > 0.6 * pg["w"] and h > 0.6 * pg["h"]: continue  # fundo da página / molduras
        boxes.append((x0, y0, x1, y1))
    return boxes

def crop_problem(pdf, pages, flat, cols, objs, start, end, author):
    """Retângulos [(página, x0, y0, x1, y1)] do problema cujas linhas são flat[start:end]."""
    rows = [(k, *flat[k]) for k in range(start, end) if not is_chrome(flat[k][1], pages[flat[k][0] - 1], author)]
    if not rows: return []
    groups, cur = [], []
    for k, pi, r in rows:
        if cur and (pi, r["kind"]) != (cur[-1][1], cur[-1][2]["kind"]): groups.append(cur); cur = []
        cur.append((k, pi, r))
    groups.append(cur)
    rects = []
    for g in groups:
        pi, kind = g[0][1], g[0][2]["kind"]; pg = pages[pi - 1]
        cx0, cx1 = cols[(pi, kind)]
        top, bottom = g[0][2]["y1"], g[-1][2]["y0"]
        # limites verticais: linha anterior/seguinte da mesma coluna que não é deste problema
        col_rows = [(k, r) for k, p2, r in flat_rows_of(flat, pi, kind, pages, author)]
        above = [r["y0"] for k, r in col_rows if k < g[0][0] and r["y0"] >= top]
        below = [r["y1"] for k, r in col_rows if k > g[-1][0] and r["y1"] <= bottom]
        up_lim = min(above) if above else pg["top"]
        low_lim = max(below) if below else pg["bottom"]
        # figuras dentro da faixa [low_lim, up_lim], centradas na coluna e perto do texto do problema
        colw = cx1 - cx0
        lim0 = cx0 if kind == "right" else cx0 - 0.06 * colw   # nunca invade a outra coluna
        lim1 = cx1 if kind == "left" else cx1 + 0.06 * colw
        for (ox0, oy0, ox1, oy1) in objs[pi]:
            cx = (ox0 + ox1) / 2
            if not (cx0 - PAD <= cx <= cx1 + PAD) or (ox1 - ox0) > 1.3 * colw: continue
            if oy1 <= low_lim or oy0 >= up_lim: continue
            if oy0 > top + 60 or oy1 < bottom - 60: continue      # longe demais do texto: é de outro problema
            top = max(top, min(oy1, up_lim)); bottom = min(bottom, max(oy0, low_lim))
            cx0, cx1 = max(lim0, min(cx0, ox0)), min(lim1, max(cx1, ox1))
        rects.append((pi, max(0, cx0 - PAD), max(0, bottom - PAD), min(pg["w"], cx1 + PAD), min(pg["h"], top + PAD)))
    return rects

_col_cache = {}
def flat_rows_of(flat, pi, kind, pages, author):
    key = (id(flat), pi, kind)
    if key not in _col_cache:
        _col_cache[key] = [(k, p2, r) for k, (p2, r) in enumerate(flat) if p2 == pi and r["kind"] == kind and not is_chrome(r, pages[pi - 1], author)]
    return _col_cache[key]

def render_rects(pdf, rects, scale):
    pieces = []
    for pi, x0, y0, x1, y1 in rects:
        page = pdf[pi - 1]; w, h = page.get_size()
        img = page.render(scale=scale, crop=(x0, y0, w - x1, h - y1)).to_pil().convert("RGB")
        pieces.append(img)
    W = max(p.width for p in pieces); gap = int(6 * scale)
    H = sum(p.height for p in pieces) + gap * (len(pieces) - 1)
    out = Image.new("RGB", (W, H), (255, 255, 255)); y = 0
    for p in pieces:
        out.paste(p, ((W - p.width) // 2, y)); y += p.height + gap
    return out

def process_list(lid, wanted, scale, debug, crops):
    l = LISTS[lid]; path = os.path.join(ROOT, l["file"]); author = CATALOG[l["file"]]["author"]
    pages = extract_rows(path)
    texts = [[r["text"] for r in pg["rows"]] for pg in pages]
    probs, _, _ = B.parse_list(texts)
    flat = [(pi, r) for pi, pg in enumerate(pages, 1) for r in pg["rows"] if r["text"].strip()]
    pdf = pdfium.PdfDocument(path)
    for pi, pg in enumerate(pages, 1): pg["top"], pg["bottom"] = content_zone(pdf, pi, pg)
    objs = {pi: [b for b in page_objects(pdf, pi, pg) if b[1] < pg["top"] and b[3] > pg["bottom"]] for pi, pg in enumerate(pages, 1)}
    cols = {}
    for pi, pg in enumerate(pages, 1):
        for kind in ("left", "right", "full"):
            rs = [r for r in pg["rows"] if r["kind"] == kind and not is_chrome(r, pg, author)]
            if rs: cols[(pi, kind)] = (min(r["x0"] for r in rs), max(r["x1"] for r in rs))
        if (pi, "left") in cols and (pi, "right") in cols:   # colunas: até o meio da calha
            l0, l1 = cols[(pi, "left")]; r0, r1 = cols[(pi, "right")]; mid = (l1 + r0) / 2
            cols[(pi, "left")] = (l0, mid - 2); cols[(pi, "right")] = (mid + 2, r1)
    _col_cache.clear()
    for p in probs:
        pid = f"{lid}-{p['n']}"
        if wanted and pid not in wanted: continue
        rects = crop_problem(pdf, pages, flat, cols, objs, p["_row"], p["_row_end"], author)
        if not rects: print(f"!! {pid}: sem linhas"); continue
        img = render_rects(pdf, rects, scale)
        img = img.quantize(colors=128, method=Image.Quantize.FASTOCTREE)
        img.save(os.path.join(OUT, f"{pid}.png"), optimize=True)
        # tamanho da fonte do corpo (pt): mediana das linhas do problema sem o título
        sizes = sorted(r["size"] for k, (p2, r) in enumerate(flat) if p["_row"] < k < p["_row_end"] and not is_chrome(r, pages[p2 - 1], author) and len(r["text"]) > 20)
        pt = sizes[len(sizes) // 2] if sizes else flat[p["_row"]][1]["size"]
        crops[pid] = [img.width, img.height, round(pt, 1), scale]
        size = os.path.getsize(os.path.join(OUT, f"{pid}.png")) // 1024
        print(f"== {pid} {'/'.join(f'p{r[0]}' for r in rects)} {img.width}x{img.height} {size} KB" + (f"\n   {[(r[0], round(r[1]), round(r[2]), round(r[3]), round(r[4])) for r in rects]}" if debug else ""))

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--scale" in argv: i = argv.index("--scale"); argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    scale = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 2.2
    debug = "--debug" in sys.argv
    cj = os.path.join(ROOT, "data", "crops.js")
    crops = json.loads(open(cj).read()[len("window.FOICE_CROPS = "):].rstrip().rstrip(";")) if os.path.exists(cj) else {}
    by_list = {}
    for a in args or LISTS:
        lid = a if a in LISTS else a.rsplit("-", 1)[0]
        by_list.setdefault(lid, set())
        if a not in LISTS: by_list[lid].add(a)
    for lid, wanted in by_list.items(): process_list(lid, wanted, scale, debug, crops)
    open(cj, "w", encoding="utf-8").write("window.FOICE_CROPS = " + json.dumps(crops, separators=(",", ":")) + ";\n")
    print(len(crops), "recortes em data/crops.js")
