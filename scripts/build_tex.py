#!/usr/bin/env python3
"""Compila as transcrições em LaTeX de problemas/ e compara cada uma com o PDF original.

Uso:  python3 scripts/build_tex.py [ids...]        (sem ids: todos os problemas/<lista>/<n>.tex)
Requer: tectonic (brew install tectonic), pypdfium2 e pillow (pip install pypdfium2 pillow), pdfminer.six.

Para cada problema:
  1. recorta as figuras listadas em problemas/figuras.json para problemas/<lista>/fig/<n>.png;
  2. envolve problemas/<lista>/<n>.tex com problemas/preamble.tex e compila em build/tex/<id>.pdf;
  3. extrai o texto do PDF compilado e do problema original e imprime a similaridade e as palavras que diferem;
  4. monta build/tex/<id>-cmp.png: recorte do PDF original (esquerda, definido em problemas/recortes.json) e a
     transcrição compilada (direita), para conferência visual.
"""
import difflib, glob, json, os, re, subprocess, sys, unicodedata
from PIL import Image, ImageOps
import pypdfium2 as pdfium
sys.path.insert(0, os.path.dirname(__file__))
from pdftext import extract
import build_index as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROB = os.path.join(ROOT, "problemas"); OUT = os.path.join(ROOT, "build", "tex")
os.makedirs(OUT, exist_ok=True)
DATA = json.loads(open(os.path.join(ROOT, "data", "problems.js"), encoding="utf-8").read()[len("window.FOICE = "):].rstrip().rstrip(";"))
PROBLEMS = {p["id"]: p for p in DATA["problems"]}; LISTS = {l["id"]: l for l in DATA["lists"]}
CATALOG = {c["file"]: c for c in json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))}
FIGS = json.load(open(os.path.join(PROB, "figuras.json"), encoding="utf-8"))
CROPS = json.load(open(os.path.join(PROB, "recortes.json"), encoding="utf-8"))

def render(pdf_path, page, scale=3.0, box=None):
    pdf = pdfium.PdfDocument(pdf_path)
    img = pdf[page - 1].render(scale=scale).to_pil().convert("RGB")
    if box:
        w, h = img.size
        img = img.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    return img

def trim(img, pad=18):
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageOps.invert(Image.blend(img, bg, 0)).convert("L").point(lambda v: 255 if v > 12 else 0)
    bbox = diff.getbbox()
    if not bbox: return img
    return img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad)))

_full_cache = {}
def original_text(pid):
    """Texto completo do enunciado original (o data/problems.js guarda só 900 caracteres)."""
    p = PROBLEMS[pid]; l = LISTS[p["list"]]
    if l["file"] not in _full_cache:
        pages = extract(os.path.join(ROOT, l["file"]))
        probs, _, _ = B.parse_list(pages)
        _full_cache[l["file"]] = {q["n"]: B.join_body(q["_body"], CATALOG[l["file"]]["author"])[0] for q in probs}
    return _full_cache[l["file"]].get(p["n"], "")

def norm_words(t):
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"\(cid:\d+\)", "", t)
    t = re.sub(r"[“”\"'`´]", "", t)
    t = re.sub(r"[^\w%]+", " ", t)   # deixa só palavras e números
    return [w.lower() for w in t.split() if re.search(r"[a-zA-ZÀ-ÿ]{2,}", w)]  # ignora símbolos soltos e números

def compare_text(pid, mine_pdf):
    mine = " ".join(" ".join(pg) for pg in extract(mine_pdf))
    a, b = norm_words(original_text(pid)), norm_words(mine)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal": diffs.append(f"{tag}: «{' '.join(a[i1:i2])}» → «{' '.join(b[j1:j2])}»")
    return sm.ratio(), diffs

def build(pid):
    lid, n = pid.rsplit("-", 1)
    tex = os.path.join(PROB, lid, f"{n}.tex")
    if not os.path.exists(tex): print(f"!! {pid}: {tex} não existe"); return
    l = LISTS[lid]; src_pdf = os.path.join(ROOT, l["file"])
    # 1. figuras
    if pid in FIGS:
        f = FIGS[pid]; os.makedirs(os.path.join(PROB, lid, "fig"), exist_ok=True)
        render(src_pdf, f["page"], scale=4.0, box=f["box"]).save(os.path.join(PROB, lid, "fig", f"{n}.png"))
    # 2. compilar
    wrapper = os.path.join(OUT, f"{pid}.tex")
    open(wrapper, "w", encoding="utf-8").write(
        open(os.path.join(PROB, "preamble.tex"), encoding="utf-8").read()
        + f"\\graphicspath{{{{{os.path.join(PROB, lid)}/}}}}\n\\begin{{document}}\n\\input{{{tex}}}\n\\end{{document}}\n")
    r = subprocess.run(["tectonic", "-X", "compile", "--outdir", OUT, wrapper], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"!! {pid}: erro de compilação\n" + "\n".join(r.stderr.splitlines()[-12:])); return
    mine_pdf = os.path.join(OUT, f"{pid}.pdf")
    # 3. texto
    ratio, diffs = compare_text(pid, mine_pdf)
    # 4. imagem lado a lado
    left_parts = [render(src_pdf, c["page"], 3.0, c["box"]) for c in CROPS.get(pid, [])]
    right = trim(render(mine_pdf, 1, 3.0))
    if left_parts:
        lw = max(im.width for im in left_parts); lh = sum(im.height for im in left_parts) + 10 * (len(left_parts) - 1)
        left = Image.new("RGB", (lw, lh), (255, 255, 255)); y = 0
        for im in left_parts: left.paste(im, (0, y)); y += im.height + 10
        # mesma altura de linha aproximada: ajusta a direita para a largura da esquerda
        right = right.resize((lw, int(right.height * lw / right.width)))
        H = max(left.height, right.height)
        cmp_img = Image.new("RGB", (lw * 2 + 40, H + 20), (200, 200, 200))
        cmp_img.paste(left, (10, 10)); cmp_img.paste(right, (lw + 30, 10))
    else:
        cmp_img = right
    cmp_img.save(os.path.join(OUT, f"{pid}-cmp.png"))
    print(f"== {pid}: texto {ratio:.3f}" + ("" if not diffs else "\n   " + "\n   ".join(diffs[:12])))
    st_path = os.path.join(OUT, "status.json")
    st = json.load(open(st_path)) if os.path.exists(st_path) else {}
    st[pid] = {"ratio": round(ratio, 3), "diffs": len(diffs)}
    json.dump(st, open(st_path, "w"), indent=0)

def status():
    """Tabela por lista: transcritos/total e similaridade mínima registrada no último build."""
    st_path = os.path.join(OUT, "status.json")
    st = json.load(open(st_path)) if os.path.exists(st_path) else {}
    tot_done = 0
    print(f"{'lista':<24} {'feito':>7}  {'sim. mín.':>9}")
    for l in DATA["lists"]:
        ids = [p["id"] for p in DATA["problems"] if p["list"] == l["id"]]
        done = [i for i in ids if os.path.exists(os.path.join(PROB, l["id"], f"{i.rsplit('-', 1)[1]}.tex"))]
        tot_done += len(done)
        ratios = [st[i]["ratio"] for i in done if i in st]
        if done: print(f"{l['id']:<24} {len(done):>3}/{len(ids):<3}  {min(ratios) if ratios else float('nan'):>9.3f}")
    print(f"{'total':<24} {tot_done:>3}/{len(DATA['problems'])}")

if __name__ == "__main__":
    if "--status" in sys.argv: status(); sys.exit()
    ids = sys.argv[1:] or sorted(os.path.basename(os.path.dirname(t)) + "-" + os.path.splitext(os.path.basename(t))[0]
                                 for t in glob.glob(os.path.join(PROB, "*", "*.tex")))
    for pid in ids: build(pid)
