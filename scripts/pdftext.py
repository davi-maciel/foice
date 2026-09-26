"""Column-aware text extraction with OT1 accent merging (pdfminer)."""
import re, unicodedata
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTTextLine, LTChar, LTAnno, LAParams

COMB = {'´': '́', '`': '̀', 'ˆ': '̂', '˜': '̃', '¨': '̈', '¸': '̧', '˚': '̊', '¯': '̄'}
LIG = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ı': 'i', '’': "'", '“': '"', '”': '"', '”': '"', '“': '"'}

def _overlap(a, b):
    return max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))

def line_text(line):
    """Merge accent glyphs into their base letters by horizontal overlap."""
    objs = list(line)
    chars = [(i, o) for i, o in enumerate(objs) if isinstance(o, LTChar)]
    out = [None] * len(objs)
    marks = {}  # index of base char -> list of combining marks
    skip = set()
    for pos, (i, o) in enumerate(chars):
        t = o.get_text()
        if t in COMB:
            # candidate bases: previous and next LTChar
            cands = []
            if pos > 0: cands.append(chars[pos - 1])
            if pos + 1 < len(chars): cands.append(chars[pos + 1])
            cands = [(j, c) for j, c in cands if c.get_text() not in COMB and c.get_text().strip()]
            if cands:
                j, c = max(cands, key=lambda jc: _overlap(o, jc[1]))
                marks.setdefault(j, []).append(COMB[t])
                skip.add(i)
                if j < i:   # attached backwards (e.g. "C¸"): the gap after the glyph is an artifact
                    if i + 1 < len(objs) and isinstance(objs[i + 1], LTAnno): skip.add(i + 1)
                else:       # attached forwards: any gap between glyph and base is an artifact
                    for k in range(i + 1, j):
                        if isinstance(objs[k], LTAnno): skip.add(k)
                    # a space before the glyph is real only if the gap between the previous
                    # letter and the base letter is a genuine word space
                    if i - 1 >= 0 and isinstance(objs[i - 1], LTAnno) and pos > 0:
                        prev = chars[pos - 1][1]
                        if c.x0 - prev.x1 < 0.22 * max(c.size, 1):
                            skip.add(i - 1)
                continue
    s = []
    for i, o in enumerate(objs):
        if i in skip: continue
        if isinstance(o, LTChar):
            t = o.get_text()
            t = LIG.get(t, t)
            if i in marks:
                # 'ı' -> 'i' handled by LIG; attach marks
                t = t + "".join(marks[i])
            s.append(t)
        elif isinstance(o, LTAnno):
            s.append(o.get_text())
    text = "".join(s)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\(cid:\d+\)", "", text)
    # drop a space that pdfminer inserted right after a skipped accent glyph (e.g. "inscrit ível")
    return text.replace("\n", "").rstrip()

def page_lines(layout, gutter=18):
    """Lines of a page in reading order. Fragments that sit on the same row and close to each
    other (e.g. a LaTeX section number and its title) are merged into one line; two-column
    pages are read left column first."""
    raw = []
    for box in layout:
        if not isinstance(box, LTTextBox): continue
        for ln in box:
            if isinstance(ln, LTTextLine):
                t = line_text(ln)
                if not t.strip(): continue
                sizes = sorted(c.size for c in ln if isinstance(c, LTChar))
                size = sizes[len(sizes) // 2] if sizes else 10
                raw.append({"x0": ln.x0, "x1": ln.x1, "y0": ln.y0, "y1": ln.y1, "size": size, "parts": [(ln.x0, t)]})
    if not raw: return []
    mid = (layout.x0 + layout.x1) / 2
    def kind(r):
        if r["x0"] < mid - gutter and r["x1"] > mid + gutter: return "full"
        return "left" if (r["x0"] + r["x1"]) / 2 < mid else "right"
    kinds = [kind(r) for r in raw]
    # duas colunas de verdade: várias linhas à esquerda e várias à direita cujo início (x0) coincide;
    # equações centradas e fins de parágrafo curtos não se alinham assim.
    from collections import Counter
    wide = 0.3 * (layout.x1 - layout.x0)          # linha de texto de verdade, não fragmento de fórmula
    right_starts = Counter(round(r["x0"] / 3) for r, k in zip(raw, kinds) if k == "right" and r["x0"] > mid - gutter)
    # e as duas colunas precisam coexistir lado a lado: linhas à esquerda com uma linha à direita na mesma altura
    rights = [r for r, k in zip(raw, kinds) if k == "right"]
    side_by_side = sum(1 for r, k in zip(raw, kinds) if k == "left" and any(min(r["y1"], q["y1"]) - max(r["y0"], q["y0"]) > 2 for q in rights))
    two_col = kinds.count("left") >= 3 and bool(right_starts) and max(right_starts.values()) >= 3 and side_by_side >= 3
    # coluna esquerda justificada (muitas linhas terminando no mesmo x antes da calha) com algo à direita:
    # também é página de duas colunas, mesmo com a coluna direita quase vazia (ex.: só o gabarito)
    edges = Counter(round(r["x1"]) for r, k in zip(raw, kinds) if k == "left" and r["x1"] < mid + gutter and r["x1"] - r["x0"] >= wide)
    if edges and not two_col:
        edge, n_edge = edges.most_common(1)[0]
        n_right = sum(1 for r, k in zip(raw, kinds) if k == "right" and r["x0"] > edge + 4)
        if n_edge >= 5 and n_right >= 2: two_col = True
    # --- merge same-row fragments
    raw.sort(key=lambda r: -(r["y0"] + r["y1"]) / 2)
    rows = []
    for r in raw:
        target = None
        for row in rows[-12:]:
            ov = min(r["y1"], row["y1"]) - max(r["y0"], row["y0"])
            if ov <= 0.5 * min(r["y1"] - r["y0"], row["y1"] - row["y0"]): continue
            if two_col and kind(r) != kind(row): continue
            gap = max(r["x0"] - row["x1"], row["x0"] - r["x1"])
            numlike = lambda t: bool(re.fullmatch(r"(\d{1,2}(\.\d{1,2})?\.?|[IVX]{1,5}\.)", t.strip()))
            short = numlike(r["parts"][0][1]) or any(numlike(t) for _, t in row["parts"])
            if gap < (3.2 if short else 1.8) * max(r["size"], row["size"]):
                target = row; break
        if target:
            target["parts"].extend(r["parts"])
            target["x0"] = min(target["x0"], r["x0"]); target["x1"] = max(target["x1"], r["x1"])
            target["y0"] = min(target["y0"], r["y0"]); target["y1"] = max(target["y1"], r["y1"])
        else:
            rows.append(dict(r, parts=list(r["parts"])))
    for row in rows:
        row["text"] = re.sub(r"\s+", " ", " ".join(t for _, t in sorted(row["parts"]))).strip()
    # --- order rows
    rows.sort(key=lambda r: (-(r["y0"] + r["y1"]) / 2, r["x0"]))
    for r in rows: r["kind"] = kind(r) if two_col else "full"
    if not two_col:
        return rows
    out, block = [], []
    def flush():
        for side in ("left", "right"):
            out.extend(r for r in block if r["kind"] == side)
        block.clear()
    for r in rows:
        if r["kind"] == "full":
            flush(); out.append(r)
        else:
            block.append(r)
    flush()
    return out

def extract_rows(pdf):
    """Per page: {"w", "h", "rows": [{"text", "x0", "x1", "y0", "y1", "kind"}]} in reading order (PDF points, y up)."""
    pages = []
    for layout in extract_pages(pdf, laparams=LAParams(line_margin=0.3, char_margin=2.0, boxes_flow=0.5)):
        rows = page_lines(layout)
        pages.append({"w": layout.width, "h": layout.height,
                      "rows": [{k: r[k] for k in ("text", "x0", "x1", "y0", "y1", "kind", "size")} for r in rows]})
    return pages

def extract(pdf):
    """Return list of pages; each page is a list of text lines in reading order."""
    return [[r["text"] for r in pg["rows"]] for pg in extract_rows(pdf)]

if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        for i, p in enumerate(extract(f), 1):
            print(f"<<<PAGE {i}>>>")
            print("\n".join(p))
