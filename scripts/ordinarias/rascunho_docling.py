"""Rascunho de revisão de uma lei escaneada (1983–2000) a partir de duas leituras de OCR, para conferir só o que diverge.

Junta duas leituras independentes da mesma cópia escaneada:
  - Docling (OCR RapidOCR + análise de layout): acerta a estrutura — parágrafos na ordem certa, §§ separados, tabelas,
    texto fora das assinaturas — mas perde acentos e cedilhas ("construcão", "Orcamento");
  - OCR do macOS (Vision, ocr_txt/ de montar_pre2001.py): acerta acentos, mas embaralha a ordem perto das assinaturas.

O rascunho usa a estrutura do Docling e devolve os acentos com o vocabulário da leitura do Vision. Também corrige os erros
que se repetem nas cópias datilografadas: o "º" sublinhado lido como 9/Q/Ω/2/0 ("Artigo 19-" → "Artigo 1º"), "i" no
lugar de "1", o "§" lido como S/5/6, os nomes do Prefeito e do Secretário. Cada parágrafo é comparado com a leitura do
Vision; o que não bate (ou tem caractere estranho, ou é tabela) vira um recorte PNG só daquela região da página, para
conferir na imagem sem abrir a página inteira.

Saída em PRE2001/rascunhos/lei-N-AAAA/:
  rascunho.md   corpo da página no formato do site (cabeçalho, ementa, artigos com âncora, §§, assinaturas)
  conferir.md   lista do que conferir: recorte, motivo e o trecho do rascunho
  r-NN.png      recortes das regiões duvidosas (150 dpi, tons de cinza)
O JSON do Docling fica em PRE2001/docling/ (cache: a segunda execução não roda o OCR de novo).

Requer: docling instalado num ambiente à parte (DOCLING, padrão PRE2001/../.venv-docling/bin/docling) e pdftoppm/pdfinfo.
Uso: python3 rascunho_docling.py N AAAA        (ex.: python3 rascunho_docling.py 188 1992)
"""
import difflib
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

PRE2001 = Path(os.environ.get("PRE2001", Path.home() / "Documents/leis-bataypora-fontes/pre2001"))
DOCLING = os.environ.get("DOCLING", str(PRE2001.parent / ".venv-docling/bin/docling"))
LIMIAR = 0.88  # fração mínima de palavras do parágrafo que precisam aparecer na leitura do Vision
DPI = 150

# Nomes que aparecem nas assinaturas e no preâmbulo, na grafia correta (chave: sem acento, só letras)
NOMES = {
    "JERCEEUSEBIODESOUZA": "JERCÉ EUSÉBIO DE SOUZA",
    "JOSEANTONIOFRUTUOSO": "JOSÉ ANTONIO FRUTUOSO",
}
CARGOS = ("Prefeito Municipal", "Secretário")
# Fecho padrão (gestão 1989–1992). Tudo depois de "Prefeitura Municipal de ..., aos ..." é trocado por ele e a região
# inteira vai para um recorte, porque as assinaturas por cima do texto confundem as duas leituras.
FECHO = [
    "Dr. JERCÉ EUSÉBIO DE SOUZA\n{ .centro }\n\nPrefeito Municipal\n{ .centro }",
    "Registrada em livro próprio do Deptº Geral de Administração, e afixada em local de costume em data acima citada.",
    "JOSÉ ANTONIO FRUTUOSO\n{ .centro }\n\nSecretário\n{ .centro }",
]
# Palavras curtas que existem; outras de até 3 letras costumam ser lixo do OCR perto das assinaturas ("poy", "eo")
CURTAS = set(
    "a o e é à ao aos as os às da das do dos de em no na nos nas num um uma por com se que ou sua seu suas seus sem até "
    "já não são lei art mês dia dias ano ser foi há mil cr ltda ms nº vr fgts clt dr sr srª bem tal só via lhe fé vez "
    "sob três dez seis sete oito nove dois duas cem ou tão mas nem fim pôr eu dá lá pé ele ela meu".split())
ORDINAL = "9QΩ20oº°ª"  # como o "º" sublinhado da máquina de escrever costuma sair no OCR


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def chave(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", sem_acento(w).lower())


CURTAS_CHAVES = {chave(w) for w in CURTAS}


def dicionario() -> Counter:
    """Vocabulário das páginas do site (português jurídico já revisto), em cache em PRE2001/vocabulario.json."""
    cache = PRE2001 / "vocabulario.json"
    docs = Path(__file__).resolve().parents[2] / "docs"
    if cache.exists() and cache.stat().st_mtime > max(p.stat().st_mtime for p in docs.glob("leis-ordinarias/*/index.md")):
        return Counter(json.loads(cache.read_text()))
    formas = Counter()
    for pag in docs.glob("**/*.md"):
        if "baixar" in pag.parts:
            continue
        formas.update(w for w in re.findall(r"[A-Za-zÀ-ÿ]{2,}", pag.read_text()) if not w.isupper() or len(w) > 3)
    cache.write_text(json.dumps(formas, ensure_ascii=False))
    return formas


DIC = Counter()
DIC_CHAVES = Counter()


# ---------------------------------------------------------------- leituras

def ler_docling(pdf: Path, nome: str) -> dict:
    cache = PRE2001 / "docling" / f"{nome}.json"
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        tmp = cache.parent / "tmp"
        tmp.mkdir(exist_ok=True)
        alvo = tmp / "entrada.pdf"
        alvo.write_bytes(pdf.read_bytes())
        subprocess.run([DOCLING, "convert", str(alvo), "--to", "json", "--ocr-mode", "full_page",
                        "--image-export-mode", "placeholder", "--output", str(tmp)],
                       check=True, capture_output=True)
        (tmp / "entrada.json").rename(cache)
        alvo.unlink()
    return json.loads(cache.read_text())


def itens_em_ordem(doc: dict):
    """Textos e tabelas do Docling na ordem de leitura (segue body.children, abrindo os grupos)."""
    def resolver(ref):
        _, tipo, i = ref["$ref"].split("/")
        return tipo, doc[tipo][int(i)]

    def andar(no):
        for filho in no.get("children", []):
            tipo, item = resolver(filho)
            if tipo == "groups":
                yield from andar(item)
            elif tipo in ("texts", "tables"):
                yield tipo, item
                if tipo == "texts":
                    yield from andar(item)
            elif tipo == "pictures":  # assinaturas: o Docling põe o texto em volta como legenda da figura
                yield from andar(item)

    yield from andar(doc["body"])


def celula(c: str, corrigir=None) -> str:
    """Erros típicos das tabelas datilografadas: S6→SG, 0f→01, "20. Grau"→"2º Grau", "ba. Série"→"6ª Série"."""
    c = re.sub(r"\bS6\b", "SG", c)
    c = re.sub(r"\b0[fFlI]\b", "01", c)
    c = re.sub(r"\b(?:[iI1l]o?|1[0oº])\.?\s*(?=Grau)", "1º ", c)
    c = re.sub(r"\b2[0oº]\.?\s*(?=Grau)", "2º ", c)
    c = re.sub(r"\b([1-8]|b)\s*[aª]\.?\s*(?=Série)", lambda m: ("6" if m.group(1) == "b" else m.group(1)) + "ª ", c)
    c = re.sub(r"\bdo\s+(?:[iI1l]o?|1[0oº])\.?\s*(?=Grau)", "do 1º ", c)
    c = re.sub(r"(?<=[a-zà-ú])- (?=[a-zà-ú])", "", c)  # "Adminis- tração" → "Administração"
    c = re.sub(r"\s{2,}", " ", c).strip()
    return corrigir(c) if corrigir else c


def texto_tabela(t: dict, corrigir=None) -> str:
    grade = t["data"].get("grid") or []
    linhas = [[celula(c.get("text", "").strip(), corrigir) for c in linha] for linha in grade]
    if not linhas:
        return ""
    n = max(len(l) for l in linhas)
    linhas = [l + [""] * (n - len(l)) for l in linhas]
    md = ["| " + " | ".join(linhas[0]) + " |", "|" + "---|" * n]
    md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n".join(md)


# ---------------------------------------------------------------- correções de texto

class Acentos:
    """Devolve acentos e cedilhas às palavras do Docling usando a grafia da leitura do Vision."""

    COMUNS = ("providências município municípios publicação afixação disposições contrário orçamento orçamentárias "
              "necessário execução função funções seção área até após câmara ação já são não será serão também "
              "parágrafo único índice construção habitação econômica ônus domínio públicos público concluídas "
              "infra-estrutura autorização conveniência através secretário administração prefeitura batayporã "
              "faço lei então vigência máximo mínimo período previstos imóvel imóveis é à às").split()

    def __init__(self, texto_vision: str):
        formas, simples = defaultdict(Counter), Counter()
        dic = [w for w, c in DIC.items() if c >= 3 for _ in range(min(c, 20) // 3)]
        for w in re.findall(r"[\wÀ-ÿ-]+", texto_vision) + self.COMUNS * 2 + dic:
            if sem_acento(w) != w:
                formas[chave(w)][w.lower()] += 1
            else:
                simples[chave(w)] += 1
        # "da"/"dá", "as"/"às": só acentua quando a forma acentuada predomina na leitura do Vision
        self.formas = {k: c.most_common(1)[0][0] for k, c in formas.items() if sum(c.values()) > simples[k]}

    def palavra(self, w: str) -> str:
        forma = self.formas.get(chave(w))
        if not forma or len(chave(w)) < 2 or w.lower() == forma:
            return w
        if w.isupper() and len(w) > 1:
            return forma.upper()
        if w[0].isupper():
            return forma[0].upper() + forma[1:]
        return forma

    def __call__(self, s: str) -> str:
        return re.sub(r"[^\s\"'()“”,.;:!?/]+", lambda m: self.palavra(m.group(0)), s)


def limpar(s: str) -> str:
    s = s.replace("Ω", "º").translate(str.maketrans("äöòèìùÄÖÎ", "ãõóéíúÃÕI"))
    s = re.sub(r"(?<=[aeiouáéíóúâêô])c(?=ão|ões|ã\b)", "ç", s)           # construcão → construção
    s = re.sub(r"(?<=[AEIOUÁÉÍÓÚÂÊÔ])C(?=ÃO|ÕES)", "Ç", s)
    s = re.sub(r"(?<![A-Za-zÀ-ÿ])(?=[\diIO.,]*\d)[\diIO][\diIO.,]*(?![A-Za-zÀ-ÿ])|(?<![A-Za-zÀ-ÿ])[iI](?=º)",
               lambda m: m.group(0).replace("i", "1").replace("I", "1").replace("O", "0"), s)      # i992, ii.440, iº → 1992, 11.440, 1º
    s = re.sub(r"\b([nN])[9QΩ°o]\s*[-–.]\s*(?=\d)", lambda m: m.group(1) + "º-", s)
    s = re.sub(r"\b([nN])[0O]\s*[-–]\s*(?=\d)", lambda m: m.group(1) + "º-", s)        # n0-176   # n9-176 → nº-176
    s = re.sub(r"(?<=\d)[O](?=\d|\b)", "0", s)                           # 4O → 40
    s = re.sub(r"\b[O0][iI]\b", "01", s)                                   # "De Oi de julho"
    s = re.sub(r"(?<![\d.,])\b0(?= [A-Za-zÀ-ú])|\b0(?=s\b)", "O", s)                              # "0 terreno" → "O terreno"
    s = re.sub(r"\bN[O0Q9o]\s*[-–]?\s*(?=\d)", "Nº-", s)                # NO-40, N9-188
    s = re.sub(r"(?<=\d)m2\b|\bm2\b", "m²", s)
    s = re.sub(r"(?<![\w.])i(?=\s*%)", "1", s)                              # i% → 1%
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"(?<=[\d%²])\(", " (", s)                                # 50%(cinquenta → 50% (cinquenta
    s = re.sub(r"\b([Rr]evogam-se|revogadas|de acordo com) às\b", r"\1 as", s)
    s = re.sub(r"^Às despesas", "As despesas", s)
    s = re.sub(r"Batayporã\s*-?\s*[mM][sS]\b", "Batayporã-MS", s)
    s = re.sub(r"\)(?=[a-zà-ú])", ") ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def numero_rotulo(tok: str, esperado: int):
    """Lê o número de "Art. 19" / "i2" / "10" sabendo qual artigo se espera; devolve (número, certo?)."""
    t = tok.translate(str.maketrans("iIlOS", "11105"))
    cands = []
    if t[-1:] in ORDINAL and len(t) > 1 and t[:-1].isdigit():
        cands.append(int(t[:-1]))
    if t.isdigit():
        cands.append(int(t))
    if esperado in cands:
        return esperado, True
    return (cands[0] if cands else esperado), False


ART = re.compile(r"^\s*(Art(?:igo)?)\.?\s*([0-9iIlOS]{0,4}[" + ORDINAL + r"]?)\s*[ºª°]?\s*[-–.:]+\s*")
PAR = re.compile(r"^\s*(?:§|S|s|5|6|B)\s*([0-9iIl]{1,2})[" + ORDINAL + r"]?\s*[-–.]+\s*")


# ---------------------------------------------------------------- palavras e nomes

class Palavras:
    """Conserta palavras que o Docling grudou ou leu mal, usando as palavras da leitura do Vision."""

    def __init__(self, texto_vision: str):
        ws = re.findall(r"[\wÀ-ÿ]+", desfazer_hifen(texto_vision)) + Acentos.COMUNS
        self.mudancas = []  # palavras trocadas por aproximação: o bloco vai para conferência
        self.chaves = Counter(chave(w) for w in ws)
        self.por_chave = {}
        for w in ws:
            self.por_chave.setdefault(chave(w), w)

    def conhece(self, w: str) -> bool:
        return self.chaves[chave(w)] > 0 or DIC_CHAVES[chave(w)] >= 2

    def palavra(self, w: str) -> str:
        k = chave(w)
        if len(k) < 5 or self.conhece(w) or not w.isalpha():
            return w
        for c in range(2, len(k)):  # "ENGENHARIAE" → "ENGENHARIA E", "dolivro" → "do livro"
            a, b = k[:c], k[c:]
            if self.chaves[a] and self.chaves[b] and (len(b) > 1 or b in ("e", "a", "o")):
                return w[:c] + " " + w[c:]
        perto = difflib.get_close_matches(k, [x for x in self.chaves if abs(len(x) - len(k)) <= 2], n=1, cutoff=0.8)
        if perto and (perto[0] + "s" == k or k + "s" == perto[0] or perto[0].rstrip("s") == k.rstrip("s")):
            perto = None  # singular/plural: a palavra do Docling provavelmente está certa
        if perto and (k.startswith(perto[0]) or perto[0].startswith(k) or self.chaves[perto[0]] < 2 and len(perto[0]) < len(k)):
            perto = None  # o Vision tem só o pedaço da palavra cortada no fim da linha
        if perto:  # "acAma" → "acima"
            certo = self.por_chave[perto[0]]
            self.mudancas.append(f"{w}→{certo}")
            return certo.upper() if w.isupper() else (certo[0].upper() + certo[1:] if w[0].isupper() else certo.lower())
        return w

    def colar(self, s: str) -> str:
        """Junta palavras partidas pela hifenização da linha ("aten dimento", "reda- ção", "per mitida")."""
        def junta(m):
            a, b = m.group(1), m.group(2)
            if self.chaves[chave(a + b)] and not (self.chaves[chave(a)] and self.chaves[chave(b)] and len(a) > 3 and len(b) > 3):
                return a + b
            ka, kb, kab = chave(a), chave(b), chave(a + b)
            if DIC_CHAVES[kab] >= 2 and (DIC_CHAVES[ka] < 2 or DIC_CHAVES[kb] < 2) and kb not in CURTAS_CHAVES:
                return a + b  # "even tos" → "eventos": a palavra inteira existe no vocabulário do site
            if (not self.chaves[chave(a)] and not self.chaves[chave(b)] and len(b) <= 6 and len(a) >= 2
                    and chave(b) not in CURTAS_CHAVES):
                return a + b  # duas metades desconhecidas: palavra partida na quebra de linha ("even tos")
            return m.group(0)
        return re.sub(r"([A-Za-zÀ-ÿ]+)-? ([a-zà-ÿ]+)", junta, s)

    def __call__(self, s: str) -> str:
        return re.sub(r"[A-Za-zÀ-ÿ]+", lambda m: self.palavra(m.group(0)), self.colar(s))


def desfazer_hifen(s: str) -> str:
    return re.sub(r"(?<=[a-zà-ú])-\s*\n\s*(?=[a-zà-ú])", "", s)


def assinatura(t: str):
    """'Dr.JERCE EUSEBIO DE SOUZA Prefeito Municipal' → nome e cargo em linhas centradas; None se não for assinatura."""
    if "," in t or len(t) > 70:
        return None
    cargo = next((c for c in CARGOS if chave(c) in chave(t)), None)
    resto = re.sub(r"(?i)" + r"\s*".join(re.escape(x) for x in sem_acento(cargo)), "", sem_acento(t)) if cargo else t
    k = chave(resto).upper()
    dr = k.startswith("DR")
    k = k[2:] if dr else k
    melhor = max(NOMES, key=lambda n: difflib.SequenceMatcher(None, n, k).ratio())
    if difflib.SequenceMatcher(None, melhor, k).ratio() < 0.8:
        return None
    linhas = [("Dr. " if dr else "") + NOMES[melhor]] + ([cargo] if cargo else [])
    return "\n\n".join(l + "\n{ .centro }" for l in linhas)


def nomes_no_texto(t: str) -> str:
    """Corrige os nomes conhecidos dentro do texto (preâmbulo), tolerando espaços e acentos perdidos."""
    for k, certo in NOMES.items():
        padrao = r"\s*".join(f"[{c}{''.join(v for v in 'ÁÀÂÃÉÊÍÓÔÕÚÇ' if sem_acento(v) == c)}]" for c in k)
        t = re.sub(padrao, certo, t)
    return t


# ---------------------------------------------------------------- montagem

FIM_FRASE = re.compile(r"[.:;!?\"”]\s*$")


def juntar(itens):
    """Junta itens de texto que o Docling partiu no meio da frase ("...Sistema" + "Mnanceiro da Habitação.")."""
    saida = []
    for tipo, it in itens:
        txt = it.get("text", "").strip() if tipo == "texts" else ""
        ant = saida[-1] if saida else None
        if (tipo == "texts" and ant and ant["tipo"] == "texts" and txt and not FIM_FRASE.search(ant["texto"])
                and not re.match(r"^(De \S+ de|L\.?\s*EI\b|PREFEITURA|Estado de)", ant["texto"])
                and not ART.match(txt) and not PAR.match(txt) and not txt.startswith(("Parágrafo", "Prefeitura Municipal de"))
                and (ant["prov"][-1]["page_no"] == it["prov"][0]["page_no"] or re.match(r"[a-zà-ú]", txt))):
            ant["texto"] += " " + txt
            ant["prov"].append(it["prov"][0])
            continue
        if tipo == "texts" and re.fullmatch(r"[a-zà-ÿ]{1,6}[:.,;]?", txt):
            alvo = next((x for x in reversed(saida[-4:]) if x["tipo"] == "texts" and re.search(r"[a-zà-ÿ]-$", x["texto"])), None)
            if alvo:
                alvo["texto"] = alvo["texto"][:-1] + txt
                continue
        partes = re.split(r"\s(?=Prefeitura Municipal de [^,]{0,30},\s*a[oq]s?\b)", txt, maxsplit=1) if tipo == "texts" else [txt]
        for parte in partes:  # "Revogam-se ... contrário. Prefeitura Municipal de ..., aos" num item só
            saida.append({"tipo": tipo, "texto": parte, "item": it, "prov": list(it.get("prov", []))})
    return saida


def main():
    n, ano = sys.argv[1], sys.argv[2]
    aa = ano[2:]
    base = f"LEI Nº{int(n):03d}.{aa}"
    pdf = PRE2001 / "orig_raw" / f"{base}.pdf"
    vision = desfazer_hifen((PRE2001 / "ocr_txt" / f"{base}.txt").read_text())
    nome = f"lei-{n}-{ano}"
    saida = PRE2001 / "rascunhos" / nome
    saida.mkdir(parents=True, exist_ok=True)
    for velho in saida.glob("r-*.png"):
        velho.unlink()

    DIC.update(dicionario())
    DIC_CHAVES.update({k: 0 for k in ()})
    for w, c in DIC.items():
        DIC_CHAVES[chave(w)] += c
    doc = ler_docling(pdf, nome)
    acentos, palavras = Acentos(vision), Palavras(vision)
    itens = [(tp, it) for tp, it in itens_em_ordem(doc)
             if tp == "tables" or (it.get("text", "").strip() and it.get("label") not in ("page_header", "page_footer", "picture"))]

    blocos = []  # (texto markdown, provs, motivo para conferir ou None)
    esperado_art, esperado_par = 1, 1
    viu_lei = viu_ementa = False
    for b in juntar(itens):
        provs = b["prov"]
        if b["tipo"] == "tables":
            blocos.append((texto_tabela(b["item"], lambda c: limpar(palavras(acentos(c)))), provs, "tabela"))
            continue
        bruto = b["texto"]
        d = re.search(r"De \d{1,2} de [a-zç]+ de \d\.?\d{3}", bruto) if not viu_ementa else None
        if d and not re.search(r"LEI\s*N", bruto):
            blocos.append((f"@@DATA {d.group(0)}@@", provs, None))
            continue
        if not viu_lei and not viu_ementa and re.search(r"^(PREFEITURA|Estado de Mato|CGC)", bruto, re.I) \
                and not re.search(r"LEI\s*N", bruto):
            continue
        if not viu_lei and not viu_ementa and len(bruto) < 20 and not re.match(r"^De \d", bruto):
            continue  # linha da LEI ilegível ("L9 392"): o número vem do nome do arquivo
        palavras.mudancas = []
        t = limpar(palavras(acentos(nomes_no_texto(limpar(bruto)))))
        motivo = None

        m = re.search(r"LEI\s*N\S*?\s*-?\s*(\d+)\s*/\s*(\d+)", t) if not viu_lei else None
        if m:
            viu_lei = True
            blocos.append((f"@@LEI {m.group(1)}/{m.group(2)}@@", provs, None))
            d = re.search(r"De \d{1,2} de [a-zç]+ de \d\.?\d{3}", t, re.I)
            if d:
                blocos.append((f"@@DATA {d.group(0)}@@", provs, None))
            continue
        if not viu_ementa and re.match(r"^De \d", t):
            blocos.append((f"@@DATA {t.rstrip('.')}@@", provs, None))
            continue
        if not viu_ementa and (t.startswith(('"', "“")) or re.match(
                r"^(Disp|Autoriza|Cria|Institui|Concede|Estima|Altera|Revoga|Fixa|Denomina|Reestrutura)", t)):
            viu_ementa = True
            t = t.strip("\"“” ")
            t = t[0].upper() + t[1:] if t else t

        ma = ART.match(t)
        mp = PAR.match(t) if not ma else None
        if ma:
            num, ok = numero_rotulo(ma.group(2), esperado_art)
            rot = "Artigo" if ma.group(1) == "Artigo" else "Art."
            if not ok:
                motivo = f"número do artigo (esperado {esperado_art}, lido {ma.group(2)})"
            esperado_art, esperado_par = num + 1, 1
            t = f"**{rot} {num}{'º' if num < 10 else ''}** - {t[ma.end():]}\n{{ #art-{num} }}"
        elif mp:
            num, ok = numero_rotulo(mp.group(1), esperado_par)
            if not ok:
                motivo = f"número do parágrafo (esperado §{esperado_par}, lido {mp.group(1)})"
            esperado_par = num + 1
            t = f"§{num}º - {t[mp.end():]}"
        t = re.sub(r"^Par[aá]grafo [uú]nico\s*[-–]?\s*", "Parágrafo único - ", t)
        assin = assinatura(t)
        if assin:
            t = assin

        # confronto com a leitura do Vision (sobre o texto cru do Docling, antes das correções)
        pal = [chave(w) for w in re.findall(r"[\wÀ-ÿ]+", bruto) if len(chave(w)) >= 3]
        if pal and not motivo and not assin:
            achadas = sum(1 for w in pal if palavras.chaves[w])
            if achadas / len(pal) < LIMIAR:
                motivo = f"leituras divergem ({achadas}/{len(pal)} palavras batem)"
        if not motivo and palavras.mudancas:
            motivo = "palavra trocada por aproximação: " + ", ".join(palavras.mudancas)
        sem_par = [w for w in re.findall(r"[A-Za-zÀ-ÿ]+", t) if not palavras.conhece(w) and chave(w) not in ("art", "artigo") and w.lower() not in CURTAS]
        sem_par += [w for w in re.findall(r"(?<![\wº-])[A-Za-zÀ-ÿ]{1,3}(?![\w-])", t)
                    if w.lower() not in CURTAS and not re.fullmatch(r"[IVXLC]+|[A-Z]{2,4}", w)]
        if not motivo and not assin and (any(len(w) >= 2 for w in sem_par) or len(sem_par) >= 2):
            motivo = "palavras sem par na leitura do Vision: " + ", ".join(sem_par[:6])
        if not motivo and re.search(r"\b(?:artigo|art\.)\s+\d[09]\b", t, re.I):
            motivo = "artigo citado terminado em 0: pode ser o \"º\" lido como 0 (artigo 40 ou 49 = 4º?)"
        if not motivo and re.search(r"\b\d?9 de (janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|"
                                    r"novembro|dezembro)", t) and not t.startswith(("Prefeitura", "**LEI")):
            motivo = "data com dia terminado em 9: pode ser o \"º\" lido como 9 (19 de março = 1º de março?)"
        if not motivo and re.search(r"[^\x00-\x7fÀ-ÿ²ºª§“”–]", t):
            motivo = "caractere estranho"
        blocos.append((t, provs, motivo))

    notas = []
    textos = [b[0] for b in blocos]
    if not any("Prefeito Municipal\n{ .centro }" in x for x in textos) and re.search(r"Prefeito\s+M", vision.split("aos")[-1]):
        i = next((k for k, x in enumerate(textos) if x.startswith("Registrada")), len(blocos))
        dr = "Dr. " if re.search(r"Dr\.?\s*JERC", vision) else ""
        antes = next((b for b in reversed(blocos[:i]) if b[0].startswith("Prefeitura") and b[1]), None)
        depois = blocos[i] if i < len(blocos) and blocos[i][1] else None
        prov = []
        if antes and depois and antes[1][-1]["page_no"] == depois[1][0]["page_no"]:
            a, d = antes[1][-1], depois[1][0]
            prov = [{"page_no": a["page_no"], "bbox": {"l": 150, "r": 530, "t": a["bbox"]["b"], "b": d["bbox"]["t"]}}]
        blocos.insert(i, (f"{dr}{NOMES['JERCEEUSEBIODESOUZA']}\n{{ .centro }}\n\nPrefeito Municipal\n{{ .centro }}", prov,
                          "assinatura do Prefeito completada pelo nome conhecido" if prov else None))
        notas.append("assinatura do Prefeito completada pelo nome conhecido (o Docling não a leu)")
    if not any("Secretário\n{ .centro }" in x for x in textos) and re.search(r"Sec\w*t[aá]rio|FRUTUOSO", vision):
        blocos.append((f"{NOMES['JOSEANTONIOFRUTUOSO']}\n{{ .centro }}\n\nSecretário\n{{ .centro }}", [], None))
        notas.append("assinatura do Secretário completada pelo nome conhecido (o Docling não a leu)")

    # "artigo 29" numa lei de 11 artigos é o "2º" com o º lido como 9 (ou 0); a lei citada fica de fora
    total = esperado_art - 1
    def ordinal(m):
        num = int(m.group(2) + m.group(3))
        return f"{m.group(1)} {m.group(2)}º" if num > total else m.group(0)
    blocos = [(re.sub(r"\b([Aa]rt(?:igo|\.)?)\s+([1-9])([09])\b(?![^.;]{0,25}\b(?:Lei|Decreto|Constitui|ADCT|Ato)\b)",
                      ordinal, t) if not t.startswith("**") else t, pv, mt) for t, pv, mt in blocos]

    # fecho: troca o que vem depois de "Prefeitura Municipal de ..., aos" pelo modelo e recorta a região toda
    k = next((k for k in range(len(blocos) - 1, -1, -1) if re.match(r"^Prefeitura Municipal de .*\b(aos?|ag|aq)\b", blocos[k][0], re.I)), None)
    if k is not None:
        # o fecho vai até o fim da página (ou o começo da seguinte); anexos e quadros depois dele ficam
        pk = blocos[k][1][0]["page_no"] if blocos[k][1] else 0
        fim = k + 1
        while fim < len(blocos):
            b = blocos[fim]
            pg = b[1][0]["page_no"] if b[1] else pk
            if pg > pk + 1 or (pg > pk and (b[2] == "tabela" or re.match(r"^(ANEXO|QUADRO|TABELA|#)", b[0], re.I))) \
                    or b[2] == "tabela" or re.match(r"^(ANEXO|QUADRO|TABELA)", b[0], re.I):
                break
            fim += 1
        provs = [p for b in blocos[k:fim] for p in b[1]]
        fecho = [(x, [], None) for x in FECHO]
        if provs:
            fecho[0] = (FECHO[0], provs, "fecho padrão: conferir data, assinaturas e registro")
        blocos = blocos[:k + 1] + fecho + blocos[fim:]
        notas[:] = [x for x in notas if "assinatura" not in x]

    # assinaturas na ordem do original: Prefeito depois do fecho "Prefeitura ..., aos", Secretário no fim
    prefeito = [b for b in blocos if b[0].endswith("Prefeito Municipal\n{ .centro }")]
    secretario = [b for b in blocos if b[0].endswith("Secretário\n{ .centro }")]
    resto = [b for b in blocos if b not in prefeito and b not in secretario]
    i = next((k for k, b in enumerate(resto) if b[0].startswith("Registrada")), len(resto))
    j = i + 1 if i < len(resto) else len(resto)  # Secretário logo depois do registro, antes de anexos
    blocos = resto[:i] + prefeito[:1] + resto[i:j] + secretario[:1] + resto[j:]

    lei = next((b[0] for b in blocos if b[0].startswith("@@LEI")), None)
    data = next((b[0] for b in blocos if b[0].startswith("@@DATA")), None)
    corpo = [f"**LEI Nº-{lei[6:-2] if lei else f'{n}/{aa}'}, {data[7:-2] if data else 'De ...'}.**\n{{ .centro }}"]
    corpo += [b[0] for b in blocos if not b[0].startswith("@@")]

    # recortes: uma região por bloco duvidoso (por página), juntando as vizinhas para gastar menos imagens
    regioes = []
    for texto, provs, motivo in blocos:
        if not motivo:
            continue
        for pag in sorted({p["page_no"] for p in provs}):
            bb = [p["bbox"] for p in provs if p["page_no"] == pag]
            reg = {"pag": pag, "l": min(x["l"] for x in bb), "t": max(x["t"] for x in bb), "r": max(x["r"] for x in bb),
                   "b": min(x["b"] for x in bb), "motivos": [motivo], "textos": [texto]}
            u = regioes[-1] if regioes else None
            if u and u["pag"] == pag and u["b"] - reg["t"] < 40:
                u.update(l=min(u["l"], reg["l"]), r=max(u["r"], reg["r"]), b=min(u["b"], reg["b"]))
                u["motivos"].append(motivo)
                u["textos"].append(texto)
            else:
                regioes.append(reg)

    px = 0
    linhas = [f"# Conferir — {nome}", "", f"{len(regioes)} recorte(s). Rascunho: rascunho.md", ""]
    linhas += [f"- {x}" for x in notas] + ([""] if notas else [])
    for i, r in enumerate(regioes, 1):
        arq = saida / f"r-{i:02d}.png"
        dpi = 110 if r["motivos"][0].startswith(("fecho", "tabela")) else DPI  # texto padrão e tabelas: basta menos
        w, h = recortar(pdf, r["pag"], r["l"], r["t"], r["r"], r["b"], arq, dpi)
        px += w * h
        linhas += [f"## r-{i:02d}.png — página {r['pag']} ({w}×{h} px)", "", "Motivo: " + "; ".join(r["motivos"]), ""]
        linhas += ["    " + l for tx in r["textos"] for l in tx.splitlines()] + [""]
    (saida / "rascunho.md").write_text("\n\n".join(corpo) + "\n")
    (saida / "conferir.md").write_text("\n".join(linhas) + "\n")
    print(f"{nome}: {len(blocos)} blocos, {len(regioes)} recortes (~{px // 750} tokens de imagem) → {saida}")


def recortar(pdf: Path, pag: int, l, t, r, b, saida: Path, dpi: int = DPI):
    info = subprocess.run(["pdfinfo", "-f", str(pag), "-l", str(pag), str(pdf)], capture_output=True, text=True).stdout
    H = float(re.search(r"Page\s+\d+\s+size:\s+[\d.]+ x ([\d.]+)", info).group(1))
    k = dpi / 72
    x, y = int(max(l - 6, 0) * k), int(max(H - t - 6, 0) * k)
    w, h = int((r - l + 12) * k), int((t - b + 12) * k)
    subprocess.run(["pdftoppm", "-q", "-r", str(dpi), "-gray", "-f", str(pag), "-l", str(pag), "-x", str(x), "-y", str(y),
                    "-W", str(w), "-H", str(h), "-png", "-singlefile", str(pdf), str(saida.with_suffix(""))], check=True)
    return w, h


if __name__ == "__main__":
    main()
