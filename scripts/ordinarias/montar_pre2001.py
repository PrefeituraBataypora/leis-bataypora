"""Gera as páginas das leis ordinárias anteriores a 2001 (1983–2000) a partir do OCR das cópias escaneadas.

Pasta de trabalho (PRE2001, padrão ~/Documents/leis-bataypora-fontes/pre2001):
  orig_raw/  os PDFs escaneados da pasta da prefeitura (LEI Nº001.83.pdf ...)
  ocr_txt/   o OCR de cada PDF (Vision do macOS, ocr.swift), mesmo nome com .txt
  pdf_site/  os PDFs comprimidos para o site (Ghostscript, 110 dpi em tons de cinza), copiados para docs/assets/
  com_documentos.txt  PDFs cujo OCR cita CPF, CIC, RG ou cédula de identidade: a cópia escaneada não vai para o site,
                      porque numa imagem o número não pode ser apagado

Página com "revisao: manual" no cabeçalho (revista à mão contra a cópia escaneada) não é reescrita: fica como está, e a
ementa e a data do índice e do data/fontes.json vêm dela.

Uso: python montar_pre2001.py
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import converter  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"
PRE2001 = Path(os.environ.get("PRE2001", Path.home() / "Documents/leis-bataypora-fontes/pre2001"))
OCR_DIR = PRE2001 / "ocr_txt"

MESES = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03", "margo": "03", "abril": "04", "maio": "05",
    "junho": "06", "julho": "07", "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12",
}
# ementas que a extração automática não acha ou que o OCR estragou, lidas no OCR e corrigidas só nos erros óbvios
# de reconhecimento; o que não dá para ler fica marcado. (número, ano) -> ementa
EMENTAS = {
    ("2", "1983"): "Autoriza o Poder Executivo Municipal a efetuar operação de crédito com [ilegível] financeira nacional e "
                   "abrir crédito especial até o valor de Cr$ 20.000.000,00 (vinte milhões de cruzeiros), e dá outras providências.",
    ("39", "1985"): "Autoriza o Sr. Prefeito Municipal a se constituir em depositário fiel, perante a Justiça Federal em Mato Grosso do Sul.",
    ("101", "1988"): "Estima a Receita e fixa a Despesa do Município de Bataiporã, Estado de Mato Grosso do Sul, para o exercício financeiro de 1989.",
    ("102", "1988"): "Código de Obras Municipal.",
    ("139", "1990"): "Dispõe sobre aquisição e doação de imóvel, e dá outras providências.",
    ("150", "1990"): "Estima a Receita e fixa a Despesa do Município de Batayporã-MS, para o exercício financeiro de 1991.",
    ("198", "1992"): "Dispõe sobre denominação de Vila, e dá outras providências.",
    ("211", "1992"): "Dispõe sobre doação de material de construção e prestação de serviços, para construção de Casas "
                     "Populares, e dá outras providências.",
    ("327", "1995"): "Estima a Receita e fixa a Despesa do Município de Batayporã, para o exercício financeiro de 1996.",
    ("328", "1995"): "Estima a Receita e fixa a Despesa do Fundo Municipal de Saúde, para o exercício financeiro de 1996.",
    ("330", "1995"): "Denomina o Posto de Saúde da Fazenda Santa Ilídia, e dá outras providências.",
    ("391", "1998"): "Estabelece subvenção social a Entidade Assistencial, que especifica e dá outras providências.",
    ("439", "1999"): "Institui o prêmio “Diploma do Mérito Esportivo”, e dá outras providências.",
    ("128", "1990"): None,  # ementa ilegível no OCR ("Servidores Picos pais, o outras providências")
    ("259", "1993"): None,  # ementa ilegível no OCR ("ida. uino de 1905, e da outras providen")
}
# notas no topo de leis alteradas depois (número, ano) -> [nota]
NOTAS = {
    ("102", "1988"): ['!!! info "Alterada pela Lei Complementar nº 065/2024"\n    A alínea “a” do art. 47 recebeu nova redação '
                      'pela [Lei nº 1.359/2024](../2024/lei-1359-2024.md) (depois revogada) e pela [Lei Complementar nº '
                      '065/2024](../../leis-complementares/lc-065-2024.md), que chamam esta lei de “Lei Complementar '
                      '102/88”. A nova redação está numa nota logo abaixo da alínea.'],
}
# caracteres que o OCR põe no lugar de aspas e borrões (o português só usa o Latin-1 e esta pontuação)
PERMITIDOS = re.compile(r"[^\x00-\xff“”‘’–—•…]")


def redigir(texto: str) -> str:
    """CPF, CIC e RG de pessoas citadas nas leis não vão para o site (no corpo e na ementa)."""
    texto = re.sub(r"\b\d{3}\s*[.,]\s*\d{3}\s*[.,]\s*\d{3}\s*[-–]\s*\d{2}\b", "[omitido]", texto)
    texto = re.sub(r"(?:C\.?\s*I\.?\s*C\.?|CPF)\s*[.:º°n-]*\s*(?:\[omitido\]|\d[\d.\-/\s]{7,16})",
                   lambda m: m.group(0).split()[0] + " [omitido]", texto, flags=re.I)
    texto = re.sub(r"\bR\.?\s*G\.?\s*(?:n[º°.]*)?\s*[-.:]*\s*\d[\d.\-]*\s*(?:/\s*)?(?:SSP|SEJUSP|SESP)\s*[/-]?\s*[A-Z]{2}",
                   "RG [omitido]", texto, flags=re.I)
    texto = re.sub(r"\bR\.?\s*G\.?\s*(?:n[º°.]*)?\s*[-.:]*\s*\d[\d.\-]{4,}(?:\s*(?:/\s*)?(?:SSP|SEJUSP|SESP)\b)?",
                   "RG [omitido]", texto, flags=re.I)
    return re.sub(r"(\[omitido\])(?:\s*\[omitido\])+", r"\1", texto)  # "CIC.-[omitido] [omitido]"


def extrair_num_ano(nome: str) -> tuple[str, str]:
    m = re.match(r"LEI\s*(?:N[º°]?\s*)?(\d+)[-.\s]+(\d{2,4})", nome, re.I)
    assert m, nome
    ano = m.group(2)
    return str(int(m.group(1))), ("19" + ano if len(ano) == 2 else ano)


def extrair_data(linhas: list[str], ano: str) -> str | None:
    """Dia e mês do cabeçalho ("De 27 de abril de 1983."). O ano vem do número da lei: o OCR troca dígitos (1933 por
    1983, "1.987") e às vezes põe o ano em outra linha. Sem dia e mês legíveis, fica sem data (antes ficava 1º de
    janeiro, uma data inventada)."""
    padrao = re.compile(rf"(?i)\b(\d{{1,2}})\s*[º°o]?\s+(?:de\s*:?\s*)?({'|'.join(MESES)})")
    topo = linhas[:25]
    # primeiro as linhas do cabeçalho ("De ..." ou "LEI Nº ..., de ..."), para não pegar uma data citada no texto
    for l in [l for l in topo if re.match(r"(?i)^\s*(de\s+\d|(projeto de )?le[it]\s*n)", l)] + topo:
        if m := padrao.search(l):
            dia = int(m.group(1))
            return f"{ano}-{MESES[m.group(2).lower()]}-{dia:02d}" if 1 <= dia <= 31 else None
    return None


def nome_proprio(linha: str) -> bool:
    """Linha que é só (parte do) nome do prefeito: maiúsculas, poucas palavras, sem verbo de ementa."""
    s = re.sub(r"[^\wÀ-ú ]", "", linha).strip()
    return bool(s) and s.upper() == s and len(s.split()) <= 4 and not re.match(
        r"(DISP|AUTORIZ|ALTER|CRIA|INSTITU|CONCED|ABRE|DENOMIN|FIXA|ESTABELEC|DECLAR|REVOG|REAJUST|APROV|ESTIM|ORÇA)", s)


def extrair_ementa(linhas: list[str]) -> str | None:
    """A ementa fica entre a linha da data (ou do "LEI Nº") e a linha do prefeito ("..., Prefeito Municipal")."""
    cab = re.compile(r"(?i)^(prefeitura|estado de|c\.?\s*g\.?\s*c|bataip|bataypor|de$|lei\s*n|de\s+\d|\d{1,2}\s+de\s)")
    fim = re.compile(r"(?i)prefeit[oa]|fa[çc]o saber|faz saber|c[âa]mara municipal aprovou|presidente da c[âa]mara")
    lei = next((i for i, l in enumerate(linhas[:30]) if re.match(r"(?i)^\s*(?:projeto de )?le[it]\s*n", l)), None)
    if lei is None:
        return None
    inicio = lei + 1
    # a data costuma vir logo abaixo do número (ou na mesma linha); é a primeira, não a do fecho da lei
    for i in range(max(0, lei - 3), min(len(linhas), lei + 6)):
        if re.search(r"(?i)\bde\s+([a-zç]+)\s+de\s+\d{4}", linhas[i]):
            inicio = max(inicio, i + 1)
            break
    buf = []
    for l in linhas[inicio:inicio + 15]:
        s = l.strip()
        if not s or cab.match(s) and not buf:
            continue
        if fim.search(s) or re.match(r"(?i)^(art|artigo)\b", s):
            break
        buf.append(s)
    while buf and nome_proprio(buf[-1]):
        buf.pop()  # "JOÃO" / "JAMIL MELLA, Prefeito..." quebrado em duas linhas
    if not buf:
        return None
    em = " ".join(buf)
    # sobra do cabeçalho antes da ementa ("MUNICIPAL DE BATAYPORA ... De 28 de janeiro de 1994. Dispõe ...")
    meses = "|".join(MESES)
    datas = list(re.finditer(rf"(?i)\b(?:{meses})\s+de(?:\s+\d{{4}}\.?)?", em))
    if datas and re.search(r"(?i)CGC|C\.G\.C|Estado de Mato|MUNICIPAL|BATAYPOR", em[:datas[-1].start()]):
        em = em[datas[-1].end():]
    em = re.sub(r"^(?:BATAYPOR[AÃ]|BATAIPOR[AÃ])\s+", "", em.strip())
    if re.search(r"PAGE|ÍNDICE|\bDr\.", em):
        return None
    em = re.sub(r"(\w)-\s+(\w)", r"\1\2", em)  # hifenização do fim de linha
    em = PERMITIDOS.sub("", em)
    em = re.sub(r"^[^A-Za-zÀ-ú]+", "", em)  # aspas e borrões antes da primeira palavra
    em = re.sub(r"^[a-z](?=[A-ZÁÉÍÓÚ])", "", em)  # "iDispõe": resto de uma aspa
    # a ementa termina em "providências"; o que vem depois é a linha do prefeito que o OCR não separou
    em = re.sub(r"(provid[êe]n\s*cias)\w*\W.*$|(provid[êe]n\s*cias)\w*$", lambda m: (m.group(1) or m.group(2)) + ".",
                em, flags=re.I)
    em = re.sub(r"[\"“”'!]+", "", em)
    em = re.sub(r"\s+", " ", em).strip(" ,;")
    if len(em) < 15 or not re.match(r"[A-ZÀ-Ú]", em, re.I):
        return None
    return em[0].upper() + em[1:] + ("" if em.endswith(".") else ".")


def limpar_ocr(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"\n*-*\s*PAGE\s*-*\n*", "\n", texto)
    texto = PERMITIDOS.sub("", texto)
    texto = redigir(texto)
    inicio_disp = re.compile(
        r"^(?:Art\.?\s*\d+|Artigo\s+\d+|§\s*\d+|Par[áa]grafo\s+[úu]nico|"
        r"[IVXLCDM]+\s*[-–.]\s|[a-z]\)\s|"
        r"CAP[ÍI]TULO\s|T[ÍI]TULO\s|SE[ÇC][ÃA]O\s|ANEXO\s|"
        r"Bataypor[ãa]|Bataipor[ãa]|Prefeitura|PREFEITURA|LEI\s+N|Fa[çc]o\s+saber|"
        r"Registre-se|Publique-se|Mando\s+a\s+todos)",
        re.I,
    )
    paragrafos: list[str] = []
    atual = ""
    for raw in texto.splitlines():
        s = raw.strip()
        if not s:
            if atual:
                paragrafos.append(atual)
                atual = ""
            continue
        if inicio_disp.match(s):
            if atual:
                paragrafos.append(atual)
            atual = s
        elif atual.endswith("-") and len(atual) > 2 and atual[-2].isalpha():
            atual = atual[:-1] + s
        elif atual:
            atual += " " + s
        else:
            atual = s
    if atual:
        paragrafos.append(atual)

    vistos: set[str] = set()
    out: list[str] = []
    for p in paragrafos:
        m = re.match(r"^((?:Art\.?|Artigo)\s*(\d+)[º°.]?)\s*[-–.]?\s*(.*)$", p, re.I)
        if m:
            n = m.group(2)
            cab = f"**Art. {n}º**" if int(n) < 10 else f"**Art. {n}.**"
            aid = f"art-{n}"
            while aid in vistos:
                aid += "-b"
            vistos.add(aid)
            out.append(f"{cab} {m.group(3).strip()}".rstrip() + f"\n{{ #{aid} }}")
        else:
            out.append(p)
    return "\n\n".join(out)


def main():
    com_documentos = set((PRE2001 / "com_documentos.txt").read_text().split("\n")) - {""}
    por_ano: dict[str, list[dict]] = {}
    for arq in sorted(OCR_DIR.glob("*.txt")):
        num, ano = extrair_num_ano(arq.name)
        bruto = arq.read_text(encoding="utf-8", errors="replace")
        linhas = bruto.splitlines()
        data = extrair_data(linhas, ano)
        ementa = EMENTAS[(num, ano)] if (num, ano) in EMENTAS else extrair_ementa(linhas)
        ementa = redigir(ementa) if ementa else None
        corpo = limpar_ocr(bruto)
        titulo, slug, pasta = f"Lei nº {num}/{ano}", f"lei-{num}-{ano}", f"leis-ordinarias/{ano}"
        destino = DOCS / pasta
        destino.mkdir(parents=True, exist_ok=True)
        pagina = destino / f"{slug}.md"
        revisada = pagina.exists() and re.search(r"^revisao: manual$", pagina.read_text(), re.M)
        if revisada:  # revista à mão contra a cópia escaneada: a página fica como está; ementa e data vêm dela
            cab_atual = pagina.read_text().split("\n---\n", 1)[0]
            m = re.search(r'^ementa: "(.*)"$', cab_atual, re.M)
            ementa = m.group(1).replace('\\"', '"') if m else ementa
            m = re.search(r"^data: (\S+)$", cab_atual, re.M)
            data = m.group(1) if m else data

        pdf = PRE2001 / "pdf_site" / f"{arq.stem}.pdf"
        if arq.stem in com_documentos:
            fonte = ("Texto obtido por OCR da cópia escaneada da prefeitura; pode conter falhas de reconhecimento. "
                     "A cópia escaneada não é publicada porque traz números de documentos pessoais, que não podem ser "
                     "apagados numa imagem.")
        else:
            assert pdf.exists(), pdf
            (DOCS / "assets" / slug).mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, DOCS / "assets" / slug / f"{slug}.pdf")
            fonte = (f"Texto obtido por OCR da [cópia escaneada](../../assets/{slug}/{slug}.pdf) da prefeitura; "
                     "pode conter falhas de reconhecimento. Na dúvida, vale a cópia escaneada.")
        if not ementa:
            fonte += " A ementa não pôde ser lida no documento digitalizado."
        if not data:
            fonte += " A data não pôde ser lida no documento digitalizado."
        em_txt = ementa or "Ementa não identificada no documento digitalizado."
        cab = ["---", f"title: {converter.yaml_str(titulo)}"] + ([f"data: {data}"] if data else []) + [
            f"ementa: {converter.yaml_str(em_txt)}", 'extracao: "OCR de cópia escaneada"',
            f"fonte_doc: {converter.yaml_str(arq.stem + '.pdf (cópia escaneada da prefeitura)')}",
            "revisao: pendente", "hide:", "  - toc", "---", "", f"# {titulo}", "", f"> {em_txt}", "",
            f'!!! warning "Texto em revisão"\n    {fonte}', ""] + [x for n in NOTAS.get((num, ano), []) for x in (n, "")] + [
            converter.botoes_download(f"{pasta}/{slug}.md"), ""]
        if not revisada:
            pagina.write_text("\n".join(cab) + "\n" + corpo + "\n", encoding="utf-8")
        por_ano.setdefault(ano, []).append({
            "origem": "pdf-ocr", "titulo": titulo, "titulo_detectado": titulo, "url": None, "pdf_local": None,
            "fonte_doc": arq.stem + ".pdf (cópia escaneada da prefeitura)", "categoria": pasta,
            "categoria_nome": f"Leis Ordinárias — {ano}", "pagina_origem": None, "arquivo": f"{pasta}/{slug}.md",
            "ementa": ementa, "data": data, "extracao": "OCR",
        })

    arq_fontes = RAIZ / "data" / "fontes.json"
    pastas_novas = {f"leis-ordinarias/{a}" for a in por_ano}
    fontes = [f for f in json.loads(arq_fontes.read_text()) if f["categoria"] not in pastas_novas]
    for ano in sorted(por_ano):
        novas = sorted(por_ano[ano], key=lambda x: int(re.search(r"lei-(\d+)-", x["arquivo"]).group(1)))
        fontes.extend(novas)
        converter.gerar_indice(f"leis-ordinarias/{ano}", f"Leis Ordinárias — {ano}", novas)
        print(ano, len(novas), "leis")
    arq_fontes.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n")
    converter.gerar_indice_grupo("leis-ordinarias", fontes)
    converter.gerar_nav(fontes)


if __name__ == "__main__":
    main()
