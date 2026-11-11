"""Leis ordinárias a partir dos .doc da prefeitura: saída do pandoc (.doc -> .docx -> markdown) -> texto no formato do site.

Pasta de trabalho do ano (LDIR), preparada antes:
  orig/  os .doc copiados da pasta da rede
  txt/   os .doc em texto (LibreOffice), usados só na conferência (check.py)
  md2/   os .doc em markdown: soffice --convert-to docx; pandoc -f docx -t markdown-smart-simple_tables-
         multiline_tables-grid_tables-fancy_lists+fancy_lists-header_attributes-bracketed_spans-native_spans-
         link_attributes-line_blocks --wrap=none
Uso: ANO=2005 LDIR=<pasta> python conv.py [número ...]   -> grava LDIR/out/lei-NNN-ANO.md
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

ANO = os.environ.get("ANO", "2005")
SCR = Path(os.environ.get("LDIR", "."))
MESES = {m: i + 1 for i, m in enumerate("janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}

ROT = re.compile(r"^(T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+([IVXL]+|[ÚU]NIC[OA])\b\s*[-–—.:]?\s*(.*)$", re.I)
ANEXO = re.compile(r"^ANEXO\s+([IVXL]+|\d+|[ÚU]NICO)\b\s*[-–—.:]?\s*(.*)$", re.I)
ART = re.compile(r"^Art(?:igo)?\.?\s*(\d+)\s*(?:[º°ºo]|\.º)?\s*(-[A-Z]\b)?\s*[.\-–—:]*\s*", re.I)
PAR = re.compile(r"^§\s*(\d+)\s*[º°o]?\s*[.\-–—:]*\s*")
UNICO = re.compile(r"^Par[áa]grafo\s+[úu]nico\s*[.\-–—:]*\s*", re.I)
INC = re.compile(r"^([IVXL]+)\s*[-–—]+\s*(?=\S)")
ALI = re.compile(r"^([a-z])\s*(?:\)\s*[-–—]?|[-–]\s)\s*")
NIVEL = {"TÍTULO": "##", "CAPÍTULO": "###", "SEÇÃO": "####", "SUBSEÇÃO": "#####"}
LISTA = re.compile(r"^\s*([IVXL]+|[a-z])([.)])\s+(?=\S)")
CARGO = re.compile(r"^(\d+)\s+(CC\s*\d+\s*-.*?)\s+R\\\$\s*([\d.,]+)$")
TOTAL = re.compile(r"^\*\*TOTAL\s*-\s*R\\\$\s*([\d.,]+)\*\*$")

# leis do orçamento em que o Word pôs cada coluna das tabelas numa célula só
ORCAMENTOS = {("681", "2005")}
# anexos desenhados no Word que viram imagem: (ano, lei) -> (começo do trecho a cortar, markdown no lugar)
MAPAS = {}
# arquivos extras (anexos em .doc separados) a juntar no fim da lei: (ano, lei) -> [nomes em md2/ ou "md:texto"]
EXTRAS = {}
# acertos pontuais no texto final: (ano, lei) -> [(trecho, novo)]
CORRECOES = {
    ("2005", "681"): [("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**")],
    ("2005", "656"): [("1.  Identificação do Projeto:", "1\\. Identificação do Projeto:"),
                      ("1.  \\- Título", "1.1 - Título"), ("2.  \\- Área", "1.2 - Área"), ("3.  \\- Público", "1.3 - Público"),
                      ("4.  \\- 100 pessoas", "1.4 - 100 pessoas"), ("5.  \\- Duração", "1.5 - Duração")],
    ("2005", "668"): [("> *“**Art 4º-** O Conselho Municipal do Meio Ambiente C.M.M.A será composto por representantes a saber:*\n\n"
                       "a) 08 (oito) do Poder Público;*\n\nb) 08 (oito) da Sociedade Civil.”*\n\n§ 1º ",
                       "> “Art 4º- O Conselho Municipal do Meio Ambiente C.M.M.A será composto por representantes a saber:\n>\n"
                       "> a) 08 (oito) do Poder Público;\n>\n> b) 08 (oito) da Sociedade Civil.”\n>\n> § 1º "),
                      ("\n\n§ 2º O exercício das funções", "\n>\n> § 2º O exercício das funções"),
                      ("Política Municipal do Meio Ambiente.*", "Política Municipal do Meio Ambiente."),
                      ("relevante interesse público.”*", "relevante interesse público.”")],
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def plano(s):
    """Texto sem a marcação do markdown, para reconhecer o que é cada parágrafo."""
    s = re.sub(r"^(>\s*)+", "", s.strip())
    s = re.sub(r"^#+\s*", "", s)
    s = s.replace("**", "").replace("\\", "")
    s = re.sub(r"(?<!\w)\*|\*(?!\w)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def tira_rotulo(md, n):
    """Tira do começo do parágrafo em markdown os primeiros n caracteres do texto plano (o rótulo)."""
    vistos, i = 0, 0
    while i < len(md) and vistos < n:
        c = md[i]
        if md.startswith("**", i):
            i += 2
            continue
        if c in "*\\" or (c == ">" and vistos == 0) or (c == " " and vistos == 0):
            i += 1
            continue
        vistos += 1
        i += 1
    resto = md[i:]
    resto = re.sub(r"^\s*\*\*\s*", "", resto) if md[:i].count("**") % 2 else resto
    resto = re.sub(r"^(\s|\*\*\s*\*\*|[-–—.:])+", "", resto)
    if resto.startswith("**") and resto.count("**") % 2:
        resto = resto[2:]
    return resto.strip()


def preparar(md):
    """Ajustes na saída do pandoc antes de separar os parágrafos."""
    md = md.replace("<!-- -->", "")
    # sobrescritos do Word (1^o^, 3^a^) viram os ordinais
    md = re.sub(r"\^(?:o|º)\.?\\?\s*\^", "º", md)
    md = re.sub(r"\^a\^", "ª", md)
    md = re.sub(r"\^([^\^\s]+)\^", r"\1", md)
    saida = []
    for b in re.split(r"\n\s*\n", md):
        b = re.sub(r"^#{7,}\s*", "", b)
        b = re.sub(r"^#{1,6}\s+(?=\**Art)", "", b)  # artigo formatado como título no Word
        if (m6 := re.match(r"^#{6}\s+(.+)$", b)) and maiusculo(m6.group(1)):
            b = f"**{m6.group(1).strip()}**"
        m = LISTA.match(b)
        if m and not b.lstrip().startswith("|"):
            # itens de lista numerados pelo Word viram incisos (I -) e alíneas (a)
            rot = f"{m.group(1)} -" if re.fullmatch(r"[IVXL]+", m.group(1)) else f"{m.group(1)})"
            b = rot + " " + "\n".join(l.strip() for l in b[m.end():].split("\n"))
        elif re.match(r"^ {2,}\S", b) and not b.lstrip().startswith(("|", "<")):
            b = "\n".join(l.strip() for l in b.split("\n"))
        saida.append(b)
    return "\n\n".join(saida)


def blocos(md):
    """Parágrafos do pandoc; citações (>) com vários parágrafos viram parágrafos separados."""
    saida = []
    for b in re.split(r"\n\s*\n", preparar(md).strip()):
        linhas = b.split("\n")
        if all(l.startswith(">") for l in linhas) and not any(re.match(r"^>\s*\|", l) for l in linhas):
            atual = []
            for l in linhas:
                l = re.sub(r"^(>\s?)+", "", l)
                if not l.strip():
                    if atual:
                        saida.append("\n".join(atual))
                    atual = []
                else:
                    atual.append(l)
            if atual:
                saida.append("\n".join(atual))
        else:
            saida.append(b)
    return [b.strip("\n") for b in saida if b.strip() and plano(b)]


def maiusculo(s):
    letras = [c for c in s if c.isalpha()]
    return len(letras) > 2 and all(c.isupper() for c in letras)


def data_lei(t):
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")\s+(?:de\s+)?(\d{4})", t, re.I)
    return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def tabela_de_colunas(html):
    """Tabelas do orçamento em que o Word pôs cada coluna numa célula só (itens com pontilhado | R$ | valores):
    vira uma tabela com uma linha por item. Itens sem pontilhado e sem valor (ex.: Poder Executivo) viram subtítulos."""
    cel = [[re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"<(?:p|h\d)[^>]*>(.*?)</(?:p|h\d)>", c, re.S)]
           for c in re.findall(r"<td[^>]*>(.*?)</td>", html, re.S)]
    rotulos, valores = cel[0], cel[-1]
    sobra = len(rotulos) - len(valores)
    linhas = ["| Especificação | Valor (R$) |", "|---|---:|"]
    v = iter(valores)
    for r in rotulos:
        nome = re.sub(r"\s*\.{2,}\s*$", "", r).strip()
        if sobra > 0 and "..." not in r:
            linhas.append(f"| **{nome}** | |")
            sobra -= 1
            continue
        val = next(v)
        if re.match(r"(?i)^total", nome) or re.match(r"^1\.[12]\s", nome):
            linhas.append(f"| **{nome}** | **{val}** |")
        else:
            linhas.append(f"| {nome} | {val} |")
    assert next(v, None) is None
    return "\n".join(linhas)


def tabelar_cargos(texto):
    """Listas de cargos comissionados (1 CC1- Secretário R$ 1.565,00) viram tabelas."""
    bs = texto.split("\n\n")
    out, i = [], 0
    while i < len(bs):
        if CARGO.match(bs[i]):
            linhas = ["| Qtde | Cargo | Vencimento |", "|---:|---|---:|"]
            while i < len(bs) and (CARGO.match(bs[i]) or re.fullmatch(r"(\\_)+", bs[i])):
                if m := CARGO.match(bs[i]):
                    linhas.append(f"| {m.group(1)} | {m.group(2)} | R\\$ {m.group(3)} |")
                i += 1
            if i < len(bs) and (m := TOTAL.match(bs[i])):
                linhas.append(f"| | **Total** | **R\\$ {m.group(1)}** |")
                i += 1
            out.append("\n".join(linhas))
            continue
        out.append(bs[i])
        i += 1
    return "\n\n".join(out)


def celulas(linha):
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def html_simples(html):
    """Tabela HTML do pandoc sem células mescladas e com um parágrafo por célula -> tabela Markdown
    (com a linha de título vazia; acertar_tabelas decide o título). Se não der, devolve o HTML."""
    if re.search(r"rowspan|colspan", html):
        return html
    linhas = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cels = []
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
            if len(re.findall(r"<(?:p|h\d)[^>]*>", c)) > 1 or re.search(r"<(?:ul|ol|table)", c):
                return html
            c = re.sub(r"</?(?:p|h\d)[^>]*>", "", c)
            c = re.sub(r"</?strong>", "**", c)
            c = re.sub(r"</?em>", "*", c)
            c = re.sub(r"<br\s*/?>", " ", c)
            if "<" in c:
                return html
            c = re.sub(r"\s+", " ", c).strip().replace("|", "\\|")
            c = re.sub(r"^\*\*\*\*$", "", c)
            cels.append(c)
        linhas.append(cels)
    if not linhas or len({len(l) for l in linhas}) != 1:
        return html
    n = len(linhas[0])
    out = ["| " + " | ".join([""] * n) + " |", "|" + "---|" * n]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def acertar_tabelas(texto):
    """Tabelas do Word sem linha de título: a primeira linha vira o título; uma tabela só com os títulos
    seguida de outra com as mesmas colunas vira uma tabela só."""
    def tabela(b):
        ls = b.split("\n")
        return b.startswith("|") and len(ls) >= 3 and re.match(r"^\|[\s:|-]+\|$", ls[1])

    bs = texto.split("\n\n")
    out = []
    i = 0
    while i < len(bs):
        b = bs[i]
        i += 1
        ls = b.split("\n")
        if not tabela(b) and not (b.startswith("|") and len(ls) == 2 and re.match(r"^\|[\s:|-]+\|$", ls[1])):
            out.append(b)
            continue
        prox = bs[i].split("\n") if i < len(bs) and tabela(bs[i]) else []
        if len(ls) == 2 and any(celulas(ls[0])) and prox and not any(celulas(prox[0])) \
                and len(celulas(prox[0])) == len(celulas(ls[0])):
            out.append("\n".join([ls[0], prox[1]] + prox[2:]))
            i += 1
            continue
        if not any(celulas(ls[0])):
            corpo = ls[2:]
            if len(corpo) == 1 and prox and not any(celulas(prox[0])) and len(celulas(prox[0])) == len(celulas(ls[0])):
                out.append("\n".join([corpo[0], prox[1]] + prox[2:]))
                i += 1
                continue
            if corpo:
                out.append("\n".join([corpo[0], ls[1]] + corpo[1:]))
                continue
        out.append(b)
    return "\n\n".join(out)


def ler_md2(nome):
    return next(f for f in (SCR / "md2").iterdir() if nfc(f.name) == nome).read_text()


def converter(num, extras=None):
    extras = EXTRAS.get((ANO, num), []) if extras is None else extras
    bs = blocos(ler_md2(f"LEI Nº {num}.{ANO}.md"))
    for e in extras:
        bs += blocos(e[3:] if e.startswith("md:") else ler_md2(e))
    # cabeçalho: título e ementa
    i = next(k for k, b in enumerate(bs) if re.match(rf"(?i)^lei\s+n[º°o]?\.?\s*{num}", plano(b)))
    titulo_doc = plano(bs[i])
    data = data_lei(titulo_doc)
    ementa = plano(bs[i + 1]).strip("“”\"' ")
    ementa = re.sub(r"[”\"]\.?$", "", ementa).strip()
    if not ementa.endswith("."):
        ementa += "."
    corpo = bs[i + 2:]

    out = [f"**{titulo_doc.rstrip('.')}.**\n{{ .centro }}", f"“{ementa[:-1]}”."]
    k = 0
    assinatura = []
    ultimo_art = 0
    anexos = []
    ancoras = set()

    def fecha_assinatura():
        if assinatura:
            out.append("\n".join(f"**{l}**" if j == 0 else l for j, l in enumerate(assinatura)) + "\n{ .centro }"
                       if len(assinatura) > 1 else f"**{assinatura[0]}**\n{{ .centro }}")
            assinatura.clear()

    while k < len(corpo):
        b = corpo[k]
        p = plano(b)
        tabela = b.lstrip().startswith(("|", "<"))
        # assinaturas: o pandoc transforma o nome e o cargo em títulos (## e #####)
        if re.match(r"^#{1,6}\s", b) and not ROT.match(p) and not ANEXO.match(p):
            if b.startswith("##### ") or b.startswith("###### ") and assinatura:
                assinatura.append(p)
            else:
                fecha_assinatura()
                assinatura.append(p)
            k += 1
            continue
        fecha_assinatura()
        if tabela:
            out.append(b)
        elif (m := ROT.match(p)) and len(p) < 120:
            tipo = m.group(1).upper()
            tipo = ("SUBSEÇÃO" if tipo.startswith("SUB") else "SEÇÃO" if tipo.startswith("SE")
                    else "TÍTULO" if tipo.startswith("T") else "CAPÍTULO")
            numero = m.group(2).upper().replace("UNICA", "ÚNICA").replace("UNICO", "ÚNICO")
            assunto = m.group(3)
            if not assunto and k + 1 < len(corpo) and maiusculo(plano(corpo[k + 1])) and not ROT.match(plano(corpo[k + 1])) \
                    and not ART.match(plano(corpo[k + 1])):
                assunto = plano(corpo[k + 1])
                k += 1
            out.append(f"{NIVEL[tipo]} {tipo} {numero}" + (f" — {assunto}" if assunto else "") + " { .centro }")
        elif (m := ANEXO.match(p)) and len(p) < 200 and ultimo_art:
            n = m.group(1).upper()
            assunto = m.group(2)
            if out and out[-1].startswith("## ANEXO"):
                # anexo de outra lei reproduzido dentro deste anexo (ex.: ANEXO I / ANEXO III DA LEI Nº 487/2001)
                out.append(f"**{p}**\n{{ .centro }}")
                k += 1
                continue
            if re.match(r"(?i)^DA LEI\b", assunto):
                assunto = ""
            if n.isdigit():
                n = "I II III IV V VI VII VIII IX X".split()[int(n) - 1]
            if not assunto and k + 1 < len(corpo) and maiusculo(plano(corpo[k + 1])) and len(plano(corpo[k + 1])) < 200 \
                    and not ANEXO.match(plano(corpo[k + 1])):
                assunto = plano(corpo[k + 1])
                k += 1
            ident = "anexo-" + n.lower().replace("ú", "u")
            if ident in anexos:
                ident += "-b"
            anexos.append(ident)
            out.append(f"## ANEXO {n}" + (f" — {assunto}" if assunto else "") + f" {{ #{ident} .centro }}")
        elif m := ART.match(p):
            n = int(m.group(1))
            suf = (m.group(2) or "").upper()
            rot = (f"Art. {n}º" if n < 10 else f"Art. {n}.") if not suf else f"Art. {n}{'º' if n < 10 else ''}{suf}."
            resto = tira_rotulo(b, m.end())
            ancora = f"art-{n}" + (suf.lower() if suf else "")
            while ancora in ancoras:
                ancora += "-b"
            ancoras.add(ancora)
            out.append(f"**{rot}** {resto}\n{{ #{ancora} }}")
            ultimo_art = n
        elif m := PAR.match(p):
            out.append(f"§ {m.group(1)}º {tira_rotulo(b, m.end())}")
        elif m := UNICO.match(p):
            out.append(f"Parágrafo único. {tira_rotulo(b, m.end())}")
        elif (m := INC.match(p)) and ultimo_art:
            out.append(f"{m.group(1)} - {tira_rotulo(b, m.end())}")
        elif (m := ALI.match(p)) and ultimo_art:
            out.append(f"{m.group(1)}) {tira_rotulo(b, m.end())}")
        elif re.match(r"^[“\"]Art", p):
            out.append("> " + re.sub(r"^(>\s*)+", "", b))
        else:
            out.append(re.sub(r"^(>\s*)+", "", b))
        k += 1
    fecha_assinatura()
    texto = "\n\n".join(out)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = tabelar_cargos(texto)
    if (num, ANO) in ORCAMENTOS:
        texto = re.sub(r"<table.*?</table>", lambda m: tabela_de_colunas(m.group(0)), texto, flags=re.S)
    else:
        texto = re.sub(r"<table.*?</table>", lambda m: html_simples(m.group(0)), texto, flags=re.S)
    texto = acertar_tabelas(texto)
    texto = re.sub(r"(\{ \.centro \}\n)+", "{ .centro }\n", texto)
    for a, b in CORRECOES.get((ANO, num), []):
        assert a in texto, (num, a)
        texto = texto.replace(a, b)
    texto = texto.replace("\\$", "$")  # o pandoc escapa o cifrão, mas o Markdown do site mostraria a barra
    # CPF e RG de pessoas citadas nas leis (doações, cessões) não vão para o site
    texto = re.sub(r"\d{3}\s?\.\s?\d{3}\s?\.\s?\d{3}\s?[-–]\s?\d{2}", "[omitido]", texto)
    texto = re.sub(r"\b[\dX.\-]*\d[\dX.\-]*\s?/\s?SSP\s?[/-]\s?[A-Z]{2}\b", "[omitido]", texto)  # RG: número/SSP/UF
    texto = texto.replace("RG [omitido] nº e", "RG [omitido] e").replace("[omitido] e [omitido]", "[omitidos]")
    # nome e cargo de quem assina em parágrafos separados viram um bloco só, centralizado
    texto = re.sub(r"\*\*([^*\n]+)\*\*(?:\n\{ \.centro \})?\n\n\*\*(Prefeito Municipal|Secretário|Secretária|Vice-Prefeito)\*\*(?:\n\{ \.centro \})?",
                   r"**\1**\n\2\n{ .centro }", texto)
    if (ANO, num) in MAPAS:
        corte, novo = MAPAS[(ANO, num)]
        assert corte in texto, (num, corte)
        texto = texto[:texto.index(corte)] + novo
    return dict(num=num, data=data, ementa=ementa, titulo_doc=titulo_doc, texto=texto)


def numeros():
    return sorted({m.group(1) for f in (SCR / "md2").iterdir()
                   if (m := re.match(rf"LEI Nº (\d+)\.{ANO}\.md$", nfc(f.name)))})


if __name__ == "__main__":
    (SCR / "out").mkdir(exist_ok=True)
    for n in sys.argv[1:] or numeros():
        r = converter(n)
        (SCR / "out" / f"lei-{n}-{ANO}.md").write_text(r["texto"] + "\n")
        print(n, r["data"], r["ementa"][:80])
