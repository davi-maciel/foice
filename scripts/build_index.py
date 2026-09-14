#!/usr/bin/env python3
"""Build data/problems.js from the PDFs in listas/ and the catalog in data/catalog.json.

Usage:  python3 scripts/build_index.py            (needs: pip install pdfminer.six)
        python3 scripts/build_index.py --debug     (prints every list and problem found,
                                                    plus the near-duplicate report)

To add a list: put the PDF under listas/<ano>/<Autor>/, add an entry to data/catalog.json
(optionally with "hint": "<topic id>" when the whole list is about one topic), run this
script and commit data/problems.js together with the PDF. Manual corrections go in
data/overrides.json, keyed by problem id: {"2019-timbo-1-4": {"topic": "termo", "title": "..."}}.
Near-duplicate corrections go in data/similar_overrides.json (see "near-duplicates" below).
"""
import json, math, os, re, sys, unicodedata, datetime
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from pdftext import extract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG = "--debug" in sys.argv
PRIORITY = ["prob", "roman", "sub", "dot", "bare"]

# ----------------------------------------------------------------------------- helpers
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

ROMAN = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12,
         "XIII":13,"XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,"XIX":19,"XX":20}
STOP = {"de","do","da","dos","das","e","o","a","os","as","em","no","na","nos","nas","um","uma",
        "com","sem","por","para","que","ou","se","ao","à","é","the","of","and","in","on","to"}

def is_caps(t):
    letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", t)
    return len(letters) >= 3 and letters.isupper()

def smart_title(t):
    """'FOTO DO ANO' -> 'Foto do Ano' (keeps short vowel-less acronyms such as RLC, MHS)."""
    if not t or not is_caps(t) or not re.search(r"[A-ZÀ-Ú]{4}", t):
        return t
    out = []
    for i, w in enumerate(t.split()):
        wl = w.lower()
        if i > 0 and wl in STOP:
            out.append(wl)
        elif len(re.sub(r"[^A-ZÀ-Ú]", "", w)) <= 3 and not re.search(r"[AEIOUÀÁÂÃÉÊÍÓÔÕÚÇ]", w):
            out.append(w)
        else:
            out.append(w[0] + wl[1:])
    return " ".join(out)

HEADER_RE = re.compile(
    r"^(lista de exerc[ií]cios|seletiva de f[ií]sica.*|p[áa]gina \d+ de \d+|\d{1,2}|lista foice \d+.*|"
    r"foice \d+.*|foice.*lista \d+.*|\(mini\) lista foice.*|dlc - f\d.*|\(dated:.*\)|vers[ãa]o: .*|"
    r"lista \d+/.*|lista de exerc[ií]cios\s+\d+)$", re.I)

def clean_title(t):
    t = t.strip()
    stars = len(re.findall(r"[\*∗]", t))
    t = re.sub(r"[\*∗]+", "", t)
    t = re.sub(r"^[•!\s]+", "", t)
    t = t.strip(" .:-–—")
    t = re.sub(r"\s+", " ", t)
    return smart_title(t), (stars if 1 <= stars <= 4 else None)

# ----------------------------------------------------------------------------- heading styles
TITLE_START = r"[A-Za-zÀ-ÿͰ-Ͽ\*∗•!\"“'⃗¿¡]"
S_PROB  = re.compile(r"^(?:Problema|Quest[ãa]o|Exerc[ií]cio|Problem|Question)\s*(\d{1,2})\s*[\.\):\-–]?\s*(.*)$", re.I)
S_ROMAN = re.compile(r"^([IVX]{1,5})\.\s*(.*)$")
S_SUB   = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+(\S.*)$")
S_DOT   = re.compile(r"^(\d{1,2})\.\s+(\S.*)$")
S_BARE  = re.compile(r"^(\d{1,2})\s*(?:-\s*)?(" + TITLE_START + r".*)$")
S_BARE2 = re.compile(r"^(\d{1,2})\s+(\d\S*\s+[^=]*[A-Za-zÀ-ÿ][^=]*)$")     # "17 13+4 anos"
END_RE  = re.compile(r"^(?:\d+\s+)?(gabarito|respostas?|solu[çc][õo]es|answers?|solutions?)\s*[:\.]?\s*$", re.I)
THEORY_RE = re.compile(r"^(resumo te[óo]rico|f[óo]rmulas( importantes)?|problemas|problems|introdu[çc][ãa]o te[óo]rica)$", re.I)
ITEM_RE = re.compile(r"^\(?[a-h][\)\.]\s")

def candidates(style, line):
    """Return (number, rest, weak) if line is a heading candidate of this style."""
    s = line.strip()
    if style == "prob":
        m = S_PROB.match(s);  return (int(m.group(1)), m.group(2), False) if m else None
    if style == "roman":
        m = S_ROMAN.match(s)
        if m and m.group(1) in ROMAN and (m.group(2) == "" or m.group(2)[:1].isupper() or m.group(2)[:1].isdigit() or m.group(2)[:1] in "\"“'¿¡"):
            return (ROMAN[m.group(1)], m.group(2), False)
        return None
    if style == "sub":
        m = S_SUB.match(s);   return ((int(m.group(1)), int(m.group(2))), m.group(3), False) if m else None
    if style == "dot":
        m = S_DOT.match(s)
        if m and len(m.group(2)) <= 70 and "=" not in m.group(2) and not m.group(2)[:1].islower():
            return (int(m.group(1)), m.group(2), False)
        return None
    if style == "bare":
        m = S_BARE.match(s)
        if m and len(m.group(2)) <= 70 and "=" not in m.group(2):
            return (int(m.group(1)), m.group(2), False)
        m = S_BARE2.match(s)
        if m and len(m.group(2)) <= 70:
            return (int(m.group(1)), m.group(2), True)
        return None

def looks_like_title(rest):
    r = rest.strip()
    return bool(r) and len(r) <= 70 and not r[:1].islower() and "=" not in r

def accept(style, c, exp):
    """Does candidate c continue a chain expecting number exp? -> (ok, weight)"""
    num, rest, weak = c
    if style == "sub":
        return (looks_like_title(rest), 1.0)
    if num == exp:
        return (True, 1.0)
    if weak:
        return (False, 0)
    if num == exp + 1 and looks_like_title(rest):
        return (True, 0.5)
    if style == "prob" and exp < num <= exp + 2:
        return (True, 0.5)
    return (False, 0)

def chain_score(style, lines):
    exp, n, first = 1, 0.0, None
    for idx, (_, line) in enumerate(lines):
        c = candidates(style, line)
        if not c: continue
        ok, w = accept(style, c, exp)
        if ok:
            if first is None: first = idx
            n += w
            if style != "sub": exp = c[0] + 1
    return n, (first if first is not None else 10**9)

def parse_list(pages):
    """pages: list of list of lines. Returns (problems, gabarito_page, style)."""
    lines = [(pi, ln) for pi, page in enumerate(pages, 1) for ln in page if ln.strip()]
    scores = {st: chain_score(st, lines) for st in PRIORITY}
    style = min(PRIORITY, key=lambda st: (-scores[st][0], scores[st][1], PRIORITY.index(st)))
    if scores[style][0] == 0:
        return [], None, None
    problems, exp, gab_page = [], 1, None
    i = 0
    while i < len(lines):
        pi, line = lines[i]
        s = line.strip()
        if END_RE.match(s) and len(problems) >= 2:
            gab_page = pi; break
        c = candidates(style, s)
        ok = c is not None and accept(style, c, exp)[0]
        if not ok:
            if problems: problems[-1]["_body"].append((pi, s))
            i += 1; continue
        num, rest, _ = c
        if style != "sub": exp = num + 1
        title, body_first = None, None
        if style == "prob":
            body_first = rest
        else:
            title = rest
        j = i + 1
        if style != "prob":   # titles wrap in two-column layouts: glue continuation lines
            for _ in range(3):
                if j >= len(lines): break
                nxt = lines[j][1].strip()
                if candidates(style, nxt) or END_RE.match(nxt): break
                if not title:
                    title = nxt; j += 1; continue
                if re.fullmatch(r"[\*∗\s]+", nxt):
                    title += " " + nxt; j += 1; continue
                if title.endswith("-") and nxt:
                    keep = re.search(r"(^|\s)[A-Z]-$", title)
                    title = (title if keep else title[:-1]) + nxt; j += 1; continue
                if "=" in nxt or ITEM_RE.match(nxt): break
                if len(nxt) <= 40 and (nxt[:1].islower() or nxt[:1] in "⃗"):
                    title += " " + nxt; j += 1; continue
                if len(nxt) <= 32 and (re.search(r"[\*∗]\s*$", nxt) or nxt.endswith("-")):
                    title += " " + nxt; j += 1; continue
                if len(nxt) <= 40 and is_caps(title) and is_caps(nxt):
                    title += " " + nxt; j += 1; continue
                break
        label = f"{num[0]}.{num[1]}" if style == "sub" else str(num)
        stars = None
        if title is not None:
            title, stars = clean_title(title)
        if title and re.match(r"^estimated time", title, re.I): title = None
        kind = "theory" if title and THEORY_RE.match(title) else "problem"
        if kind == "theory": title = None
        problems.append({"n": len(problems) + 1, "label": label, "title": title or None, "stars": stars,
                         "page": pi, "kind": kind, "_body": ([(pi, body_first)] if body_first else [])})
        i = j
    problems = [p for p in problems if p["kind"] == "problem"]
    for k, p in enumerate(problems, 1): p["n"] = k
    return problems, gab_page, style

def join_body(body_lines, author):
    out = []
    for _, s in body_lines:
        s = s.strip()
        if not s or HEADER_RE.match(s) or s == author: continue
        if re.match(r"^(Figura|Figure|Fig\.)\s*\d+", s): continue
        out.append(s)
    text = ""
    for s in out:
        if text.endswith("-") and s[:1].islower():
            text = text[:-1] + s
        else:
            text = (text + " " + s) if text else s
    text = re.sub(r"\s+", " ", text).strip()
    source = None
    m = re.match(r"^\(([^()]{3,45})\)\s*", text)
    if m and re.search(r"[A-Za-z]", m.group(1)) and not re.match(r"^[a-h]$", m.group(1)):
        source, text = m.group(1).strip(), text[m.end():]
    return text, source

# ----------------------------------------------------------------------------- topics
TOPICS = [
    ("mecanica",     "Mecânica"),
    ("gravitacao",   "Gravitação"),
    ("fluidos",      "Fluidos"),
    ("termo",        "Termodinâmica"),
    ("eletro",       "Eletromagnetismo"),
    ("circuitos",    "Circuitos"),
    ("optica",       "Óptica"),
    ("ondas",        "Ondas e Oscilações"),
    ("relatividade", "Relatividade"),
    ("moderna",      "Física Moderna"),
]
KW = {
 "mecanica": {"atrito":3,"bloco":2,"rampa":2,"polia":3,"mola":1,"colis":2,"colide":2,"velocidade":1,"acelera":1,
              "momento angular":3,"momento de inercia":4,"inercia":2,"rola":2,"rolando":3,"rolamento":3,"escorreg":2,
              "torque":3,"rigid":3,"haste":2,"barra":1,"cilindro":1,"esfera":1,"corda":1,"pendulo":2,"projetil":3,
              "lancad":2,"lancamento":3,"trajetoria":2,"centro de massa":3,"forca":1,"impulso":2,"foguete":2,
              "queda":2,"gravidade":1,"coriolis":4,"giro":2,"precess":3,"nutac":3,"disco":1,"roda":2,
              "bola":1,"cunha":3,"tracao":2,"equilibrio":1,"estatica":2,"escada":2,"cicloide":2,
              "lagrang":3,"energia cinetica":2,"conserva":1,"atwood":4,"boomerang":3,"massa m":1,"massas":1,
              "friction":3,"rod":2,"rods":2,"pulley":3,"collision":3,"angular momentum":3,"moment of inertia":4,"rolling":3,
              "rolls":3,"torque":3,"hinge":3,"slippery":2,"slope":3,"block":2,"tension":1,"velocity":1,"mass":1,"wheel":2,
              "ball":1,"disk":1,"precession":3,"spin":1},
 "gravitacao": {"orbita":4,"orbital":3,"planeta":4,"satelite":4,"gravitacional":4,"kepler":5,"cometa":4,"estrela":2,
                "sol":2,"lua":3,"terra":1,"espaconave":1,"asteroide":4,"nuvem de poeira":2,"buraco negro":4,"gm":2,
                "excentricidade":4,"periel":4,"afel":4,"elipse":1,"escape":2,"maré":3,"mare":1,"forca central":4,
                "black hole":6,"orbit":4,"gravit":4,"planet":4,"schwarzschild":6,"mercurio":3,"mercury":3,"newtoniana":2},
 "fluidos": {"fluido":4,"liquido":2,"agua":1,"pressao":1,"densidade":1,"bernoulli":5,"viscos":4,"tensao superficial":5,
             "capilar":4,"bolha":4,"gota":3,"escoa":4,"vazao":4,"hidrost":5,"empuxo":4,"flutu":3,"navier":5,"vortice":4,
             "tubo":1,"jato":3,"mangueira":3,"poca":1,"menisco":4,"molha":3,"surfactante":4,"pelicula":3,
             "reynolds":4,"stokes":3,"arrasto":2,"sabao":3,"aquario":2,"piscina":2,"barco":2,"navio":2,"aerostato":4,"balao":3,
             "fluid":4,"liquid":2,"water":1,"surface tension":5,"viscosity":4,"bubble":4,"difusao":2,"angulo de contato":5},
 "termo": {"temperatura":2,"calor":3,"entropia":5,"gas":2,"gas ideal":4,"adiabat":4,"isoterm":4,"carnot":5,"ciclo":3,
           "rendimento":3,"eficiencia":2,"pistao":3,"vapor":3,"evapora":3,"conden":2,"fusao":2,"ebuli":3,"boltzmann":4,
           "estatistic":4,"microestado":5,"particao":4,"maxwell":1,"van der waals":5,"calor especifico":4,"capacidade termica":4,
           "conducao":2,"condutividade termica":5,"radiacao termica":4,"corpo negro":4,"stefan":4,"difusao":3,"mol ":2,
           "mols":2,"kb":1,"nrt":3,"isobar":4,"isocor":4,"expansao":2,"compress":2,"termometro":3,"kelvin":2,"celsius":2,
           "saturacao":3,"umidade":4,"equiparticao":5,"debye":4,"ising":5,"fonon":3,"virial":3,"mistura":2,"grau de liberdade":4,
           "heat":3,"entropy":5,"temperature":2,"thermodynamic":4,"ideal gas":4,"termodinamic":4,"termic":2,"probabilidade":2},
 "eletro": {"carga":3,"campo eletrico":5,"potencial eletrico":4,"capacitor":4,"capacitancia":4,"dielet":4,"condutor":3,
            "campo magnetico":5,"dipolo":4,"solenoide":5,"espira":5,"inducao":4,"indutancia":4,"fluxo magnetico":5,
            "corrente":2,"lorentz":2,"ampere":3,"biot":4,"savart":4,"gauss":3,"coulomb":4,"eletrost":5,"magnet":3,
            "ima":3,"imã":3,"permeabilidade":4,"permissividade":4,"polariza":2,"eletron":2,"proton":1,"ion":1,
            "carga imagem":5,"metodo das imagens":5,"faraday":4,"fem":3,"supercondut":4,"plasma":2,"cargas":3,
            "eletrico":2,"magnetico":3,"esferas condutoras":4,"casca":2,"placas paralelas":3,"hall":3,"ciclotron":4,
            "onda eletromagnetica":3,"poynting":5,"radiacao":2,"antena":3,"giromagnet":4,"carregad":3,"aterrad":4,
            "charge":3,"electric field":5,"magnetic field":5,"capacitor":3,"inductance":4,"dipole":4,"ferromagnet":4,"coil":3,"dielectric":4},
 "circuitos": {"resistor":5,"resistencia":3,"circuito":5,"bateria":4,"diodo":5,"voltagem":4,"amperimetro":5,
               "voltimetro":5,"malha":3,"rlc":5,"rc ":3,"lc ":2,"indutor":4,"capacitor":1,"corrente":1,"fonte":2,
               "ohm":4,"kirchhoff":5,"thevenin":5,"transformador":4,"impedancia":5,"lampada":4,"gerador":3,"potencia dissipada":4,
               "fio":1,"resistores":5,"equivalente":2,"chave":3,"interruptor":4,"led":3,"transistor":5,"ddp":3,"tensao u":2,
               "circuit":5,"resistor":5,"voltage":4,"battery":4,"switch":3},
 "optica": {"lente":5,"espelho":5,"refra":4,"reflex":3,"indice de refracao":5,"foco":3,"focal":4,"imagem":3,"raio de luz":3,
            "raios":2,"luz":2,"interferen":5,"difra":5,"fenda":5,"franja":5,"polariz":3,"prisma":5,"dioptro":5,"snell":5,
            "optic":4,"optico":4,"objetiva":3,"ocular":3,"telescop":4,"microscop":4,"fotografia":3,"camera":2,"olho":2,
            "arco-iris":4,"iris":2,"laser":3,"comprimento de onda":2,"fermat":3,"miragem":4,"caminho optico":5,"lupa":4,
            "cor ":2,"cores":2,"espectro":2,"holograf":5,"bragg":3,"rede de difracao":5,"anel de newton":5,"michelson":5,
            "fabry":5,"perot":5,"vidro":2,"transparente":2,"feixe":2,"virtual":2,"real":1,"presbiopia":4,"miopia":4,
            "lens":5,"mirror":5,"refract":4,"interferen":5,"diffract":5,"light ray":3,"wavelength":3,"beam":2,"photon":1},
 "ondas": {"onda":4,"oscila":4,"frequencia":2,"modo normal":5,"modos normais":5,"batimento":5,"doppler":5,"som":4,
           "sonor":4,"acustic":5,"corda vibr":5,"harmonic":3,"ressonancia":5,"amortec":4,"periodo":1,"pendulo":2,
           "mola":2,"vibra":3,"estacionaria":4,"tsunami":3,"ondas no mar":3,"propaga":3,"fase":1,"amplitude":2,
           "fourier":4,"pacote de onda":4,"dispersao":3,"velocidade de grupo":5,"onda de choque":4,"slinky":3,"mach":3,
           "wave":4,"standing wave":5,"normal mode":5,"frequenc":2,"oscillat":4,"string":3,"sound":4,"resonan":4,"pequenas oscila":5},
 "relatividade": {"relativ":5,"lorentz":4,"referencial inercial":3,"referencial":2,"velocidade da luz":4,"foton":2,"gama":1,"γ":2,
                  "dilatacao":5,"contracao":4,"tempo proprio":5,"comprimento proprio":6,"quadrivetor":5,"quadri":4,"massa de repouso":5,
                  "energia de repouso":5,"aniquil":4,"antimateria":4,"positron":3,"mev":2,"gev":2,"minkowski":5,
                  "simultan":3,"paradoxo dos gemeos":5,"gemeos":4,"c2":3,"mc2":4,"c = 1":4,"ultrarelativ":5,"thomas":3,"rapidez":3,
                  "compton":3,"muon":4,"decaimento":2,"espaconave":2,"aceleracao propria":6,"limiar":4,"reacao":2,"reacoes":2,
                  "antiproton":4,"pion":4,"neutron":1,"instavel":2,"tempo de vida":3,"trem":1,"observador":2,"laboratorio":2,
                  "relativistic":5,"speed of light":4,"rest mass":5,"astronaut":2,"proper":2,"invariante":2},
 "moderna": {"quant":4,"foton":3,"bohr":5,"atomo":4,"atomic":3,"nucle":4,"decai":3,"radioativ":5,"meia-vida":5,
             "eletronvolt":3,"ev":2,"planck":5,"de broglie":5,"schrodinger":5,"funcao de onda":5,"tunel":4,"fotoeletric":5,
             "compton":4,"espectro de":2,"nivel de energia":4,"niveis de energia":4,"estado fundamental":5,"spin":3,
             "fermi":4,"bose":4,"semicondut":4,"neutrino":4,"hidrogenio":1,"raios-x":4,"raio x":4,"raios x":4,"laser":2,
             "particula":1,"schottky":4,"debye":2,"solido de einstein":4,"incerteza":4,"heisenberg":5,"fissao":5,"fusao nuclear":5,
             "quantum":5,"photon":3,"nucleus":4,"atom":3,"phonon":3,"emissao":2,"absorcao":2,"h ":0,"hbar":4,"ℏ":4,"eletron":1}
}
KW_RE = {t: [(re.compile(r"(?<![a-z])" + re.escape(k.strip()).replace("\\ ", "\\s+")), w) for k, w in kws.items() if w > 0] for t, kws in KW.items()}

def topic_scores(text):
    t = strip_accents(text.lower())
    sc = {}
    for topic, pats in KW_RE.items():
        s = 0.0
        for rx, w in pats:
            n = len(rx.findall(t))
            if n: s += w * min(n, 4) ** 0.7
        sc[topic] = s
    return sc

def normalize(sc):
    tot = sum(sc.values())
    return {k: (v / tot if tot else 0.0) for k, v in sc.items()}

# ----------------------------------------------------------------------------- near-duplicates
# Many problems come back in a later year: same statement with a new title, a reworded
# statement, or the same problem with extra sub-items. Two scores decide whether a pair is
# the same problem, both computed on "title + text" reduced to content words:
#   cos   cosine over TF-IDF of word unigrams + bigrams — catches rewordings;
#   cont  containment = shared word 3-grams / 3-grams of the SHORTER text — catches a
#         version that kept the original statement and added items to it.
# A pair is accepted when cos >= SIM_COS, or when cont >= SIM_CONT and the cosine is at
# least SIM_CONT_COS (containment alone drifts on short statements). Thresholds were tuned
# by reading the `--debug` report; see README.md ("Problemas parecidos") before moving them.
# Character 5-grams were tried instead of word 3-grams and scored *worse*: pairs such as
# "esfera uniformemente polarizada / magnetizada" are different problems written in almost
# the same words, and character n-grams cannot tell them apart.
SIM_MIN_TOKENS = 8    # statements shorter than this are too generic to compare at all
SIM_COS = 0.41        # cosine above which a pair is the same problem
SIM_CONT = 0.45       # containment above which a pair is the same problem ...
SIM_CONT_COS = 0.30   # ... provided the cosine is at least this
SIM_SAME_LIST = 0.75  # two problems of the same list need this much (lists repeat themes)
SIM_MAX = 8           # most similar problems kept per problem
SIM_BIG_GROUP = 6     # components bigger than this are flagged in the --debug report
SIM_REPORT = 0.28     # candidates printed in the report, accepted or not

SIM_STOP = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas para com sem
sob sobre entre ate apos ante contra desde perante e ou mas que se como quando onde qual quais quanto
quanta quantos quantas cujo cuja cujos cujas ao aos ha eh ser sao foi era eram sendo esta estao estava
seja sejam tem tinha ter teve havia haja pode podem possa poderia deve devem devera devemos sua seu
suas seus dele dela deles delas este esta estes estas esse essa esses essas aquele aquela aqueles
aquelas isso isto aquilo mesmo mesma mesmos mesmas outro outra outros outras todo toda todos todas
cada qualquer algum alguma alguns algumas nenhum nenhuma muito muita muitos muitas pouco pouca poucos
poucas mais menos tao tanto tambem ja nao sim so somente apenas entao assim ainda depois antes agora
sempre nunca aqui ali la lhe me te nos vos eles elas voce eu tu ele ela seguinte seguintes
respectivamente caso casos valor valores forma modo maneira termos funcao dada dado dados dadas
determine calcule mostre encontre obtenha considere suponha assuma expresse estime prove demonstre
explique descreva indique verifique deduza derive ache faca sabendo dica obs nota figura fig figuras
tabela problema questao exercicio item itens letra parte partes resposta respostas ponto pontos
the of and in on to an is are be was were that this these those with for from by at as it its if
when where which what how show find determine calculate consider assume suppose let given prove
express obtain compute derive explain describe hint note figure table problem question item answer
part parts point points can may must should will would there their they them you your we our
""".split())

def sim_tokens(text):
    """'title + text' -> content words: no accents, digits, punctuation, LaTeX residue or stopwords."""
    t = strip_accents(text.lower())
    t = re.sub(r"\\[a-z]+", " ", t)      # LaTeX commands left in the extracted text
    t = re.sub(r"[^a-z]+", " ", t)       # digits, punctuation, greek letters, symbols
    return [w for w in t.split() if len(w) > 1 and w not in SIM_STOP]

def sim_terms(toks):
    return toks + [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)]

def sim_vectors(docs):
    """TF-IDF vectors (dicts term -> weight), L2-normalised."""
    n = len(docs)
    df = Counter()
    for terms in docs:
        df.update(set(terms))
    vecs = []
    for terms in docs:
        tf = Counter(terms)
        v = {t: (1 + math.log(c)) * (math.log((n + 1) / (df[t] + 1)) + 1.0) for t, c in tf.items()}
        norm_ = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm_ for t, x in v.items()})
    return vecs, df

def sim_shingles(toks, k=3):
    if len(toks) < k:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}

def sim_pairs(problems, excluded):
    """Score every candidate pair. Returns [(i, j, cos, cont, ok, why)] sorted by score."""
    toks = [sim_tokens((p["title"] or "") + " . " + (p["text"] or "")) for p in problems]
    vecs, df = sim_vectors([sim_terms(t) for t in toks])
    shs = [sim_shingles(t) for t in toks]
    n = len(problems)
    # candidate generation: two problems must share a reasonably rare term to be worth scoring
    inv = defaultdict(list)
    for i, v in enumerate(vecs):
        if len(toks[i]) < SIM_MIN_TOKENS:
            continue
        for t in v:
            if df[t] <= max(3, n // 4):
                inv[t].append(i)
    cand = set()
    for docs in inv.values():
        for a in range(len(docs)):
            for b in range(a + 1, len(docs)):
                cand.add((docs[a], docs[b]))
    out = []
    for i, j in cand:
        va, vb = (vecs[i], vecs[j]) if len(vecs[i]) <= len(vecs[j]) else (vecs[j], vecs[i])
        cos = sum(w * vb.get(t, 0.0) for t, w in va.items())
        inter = len(shs[i] & shs[j])
        cont = inter / min(len(shs[i]), len(shs[j])) if shs[i] and shs[j] else 0.0
        score = max(cos, cont)
        if score < SIM_REPORT:
            continue
        pid = tuple(sorted((problems[i]["id"], problems[j]["id"])))
        ok, why = True, ""
        if pid in excluded:
            ok, why = False, "na lista de exclusões"
        elif cos < SIM_COS and not (cont >= SIM_CONT and cos >= SIM_CONT_COS):
            ok, why = False, "abaixo do limiar"
        elif problems[i]["list"] == problems[j]["list"] and score < SIM_SAME_LIST:
            ok, why = False, "mesma lista, score baixo"
        out.append((i, j, cos, cont, ok, why))
    out.sort(key=lambda r: -max(r[2], r[3]))
    return out

def attach_similar(problems, lists, excluded, debug=False):
    """Fill p['similar'] and p['group'] in place. Returns (n_pairs, n_groups)."""
    by_list = {l["id"]: l for l in lists}
    scored = sim_pairs(problems, excluded)
    neigh = defaultdict(list)
    parent = list(range(len(problems)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    accepted = 0
    for i, j, cos, cont, ok, _ in scored:
        if not ok:
            continue
        accepted += 1
        s = round(max(cos, cont), 3)
        neigh[i].append((j, s)); neigh[j].append((i, s))
        parent[find(i)] = find(j)
    comps = defaultdict(list)
    for i in range(len(problems)):
        if neigh[i]:
            comps[find(i)].append(i)
    groups = {}
    for k, (_, members) in enumerate(sorted(comps.items(), key=lambda kv: kv[1][0]), 1):
        gid = f"g{k}"
        for i in members:
            groups[i] = gid
    for i, p in enumerate(problems):
        near = sorted(neigh[i], key=lambda x: (-x[1], problems[x[0]]["id"]))[:SIM_MAX]
        p["similar"] = [{"id": problems[j]["id"], "score": s} for j, s in near]
        p["group"] = groups.get(i)
    if debug:
        print(f"\n{'='*100}\n## problemas parecidos — {accepted} pares aceitos de {len(scored)} candidatos"
              f" (cos>={SIM_COS} ou cont>={SIM_CONT} com cos>={SIM_CONT_COS})")
        for i, j, cos, cont, ok, why in scored:
            a, b = problems[i], problems[j]
            la, lb = by_list[a["list"]], by_list[b["list"]]
            flag = "OK " if ok else "-- "
            print(f"{flag} cos={cos:.3f} cont={cont:.3f}{'' if ok else '   (' + why + ')'}")
            for p, l in ((a, la), (b, lb)):
                print(f"      {p['id']:<26} {l['author']:<14} {l['year']} {l['label']:<16} {p['title'] or '—'}")
        sizes = Counter()
        for i, gid in groups.items():
            sizes[gid] += 1
        print(f"\n## {len(sizes)} grupos: "
              + ", ".join(f"{count} com {size} problemas" for size, count in sorted(Counter(sizes.values()).items())))
        for gid, n in sizes.most_common():
            if n <= SIM_BIG_GROUP:
                continue
            print(f"   ATENÇÃO grupo grande ({n}): " + ", ".join(p["id"] for p in problems if p.get("group") == gid))
    return accepted, len(set(groups.values()))

# ----------------------------------------------------------------------------- main
def main():
    catalog = json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))
    overrides = {}
    ov_path = os.path.join(ROOT, "data", "overrides.json")
    if os.path.exists(ov_path):
        overrides = json.load(open(ov_path, encoding="utf-8"))
    sim_excluded = set()
    sim_path = os.path.join(ROOT, "data", "similar_overrides.json")
    if os.path.exists(sim_path):
        sim_ov = json.load(open(sim_path, encoding="utf-8"))
        sim_excluded = {tuple(sorted(pair)) for pair in sim_ov.get("exclude", [])}
    authors, lists, problems = {}, [], []
    months = ["janeiro","fevereiro","marco","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
    for entry in catalog:
        path = entry["file"]
        folder = path.split("/")[2]
        authors[folder] = entry["author"]
        base = os.path.splitext(os.path.basename(path))[0]
        suffix = re.sub(r"^lista\d{4}[a-z]+", "", base) or "1"
        lid = f"{entry['year']}-{folder.lower()}-{suffix}"
        pages = extract(os.path.join(ROOT, path))
        probs, gab, style = parse_list(pages)
        head = " ".join(pages[0][:8]) if pages else ""
        headn = strip_accents(head.lower())
        date = None
        m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+de|,)?\s+(\d{4})", headn)
        if m and m.group(2) in months:
            date = f"{m.group(3)}-{months.index(m.group(2))+1:02d}-{int(m.group(1)):02d}"
        else:
            m = re.search(r"\(dated:\s*([a-z]+)\s+(\d{4})\)", headn) or re.search(r"\b([a-z]{4,9})\s+(?:de\s+)?(20\d\d)\b", headn)
            if m and m.group(1)[:3] in [x[:3] for x in months]:
                date = f"{m.group(2)}-{[x[:3] for x in months].index(m.group(1)[:3])+1:02d}"
        lst = {"id": lid, "year": entry["year"], "author": folder, "label": entry["label"], "file": path,
               "pages": len(pages), "date": date, "gabaritoPage": gab, "problems": len(probs)}
        lists.append(lst)
        raw = []
        for p in probs:
            body, source = join_body(p.pop("_body"), entry["author"])
            p["text"], p["source"] = body[:900], source
            raw.append(topic_scores((p["title"] or "") + " " + body))
        # list-level prior: problems + header of the PDF + optional catalog hint
        prior = {t: 0.0 for t, _ in TOPICS}
        for sc in raw:
            for t, v in normalize(sc).items(): prior[t] += v
        for t, v in normalize(topic_scores(head)).items(): prior[t] += 2.0 * v
        if entry.get("hint"): prior[entry["hint"]] += max(3.0, 0.5 * len(probs))
        prior = normalize(prior)
        for p, sc in zip(probs, raw):
            own = normalize(sc)
            final = {t: own[t] + 0.6 * prior[t] for t in own}
            topic = max(final, key=final.get) if any(final.values()) else "mecanica"
            pid = f"{lid}-{p['n']}"
            ov = overrides.get(pid, {})
            rec = {"id": pid, "list": lid, "n": p["n"], "label": p["label"], "title": ov.get("title", p["title"]),
                   "stars": p["stars"], "page": p["page"], "topic": ov.get("topic", topic), "source": p["source"], "text": p["text"]}
            problems.append(rec)
        if DEBUG:
            print(f"\n## {path}  style={style} problems={len(probs)} gabarito={gab} date={date}")
            for p in problems[-len(probs):] if probs else []:
                src = f" ({p['source']})" if p["source"] else ""
                print(f"   {p['label']:>4} p{p['page']} [{p['topic']:<12}] {'*'*(p['stars'] or 0):<4} {p['title'] or '—'}{src}  | {p['text'][:70]}")
    n_pairs, n_groups = attach_similar(problems, lists, sim_excluded, debug=DEBUG)
    out = {"generated": datetime.date.today().isoformat(), "topics": [{"id": t, "label": l} for t, l in TOPICS],
           "authors": authors, "lists": lists, "problems": problems}
    js = "window.FOICE = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(os.path.join(ROOT, "data", "problems.js"), "w", encoding="utf-8").write(js)
    print(f"{len(lists)} listas, {len(problems)} problemas -> data/problems.js ({len(js)//1024} KB)")
    print(f"{n_pairs} pares parecidos em {n_groups} grupos"
          + (f", {len(sim_excluded)} excluídos à mão" if sim_excluded else ""))
    print(Counter(p["topic"] for p in problems).most_common())
    print("lists with < 3 problems:", [(l['file'], l['problems']) for l in lists if l['problems'] < 3])

if __name__ == "__main__":
    main()
