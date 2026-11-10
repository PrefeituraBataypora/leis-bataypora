"""Converte os PDFs listados em data/fontes.json para Markdown em docs/.

Para cada página: usa o texto embutido do PDF quando ele é legível; senão
faz OCR (Tesseract, português) e fica com a versão de melhor qualidade.
O texto bruto de cada página fica em cache em .cache-leis/texto/.

Páginas editadas à mão (revisões) não são sobrescritas: o script guarda em
data/fontes.json o hash do que gerou e só reescreve arquivos que continuam iguais.

Requer: poppler (pdftotext, pdftoppm, pdfinfo) e tesseract com idioma "por".
Uso: python scripts/converter.py [--forcar]
     --forcar  gera de novo todas as páginas, apagando as edições feitas à mão
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PDFS = RAIZ / ".cache-leis" / "pdfs"
CACHE_TEXTO = RAIZ / ".cache-leis" / "texto"
DOCS = RAIZ / "docs"
FONTES = RAIZ / "data" / "fontes.json"

# PDFs sem número de lei: URL -> (título, nome do arquivo, data)
SEM_NUMERO = {
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_29092025102438.pdf":
        ("Lei Orgânica do Município de Batayporã", "lei-organica", "1990-04-05"),
    # Coletânea de emendas de 1990 a 2024; a data é a da emenda mais recente
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_29092025102502.pdf":
        ("Emendas à Lei Orgânica", "emendas", "2024-03-18"),
}

# PDFs em que o identificador automático erra (o texto cita outra lei antes do próprio número,
# ou o número saiu ilegível): título, nome do arquivo e data conferidos à mão
IDENTIFICADAS = {
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_25092025083657.pdf":
        ("Lei Complementar nº 020/2012", "lc-020-2012", "2012-04-04"),
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_25092025084418.pdf":
        ("Lei Complementar nº 025/2013", "lc-025-2013", "2013-10-16"),
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_24092025103655.pdf":
        ("Lei Complementar nº 045/2019", "lc-045-2019", "2019-12-19"),
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_24092025105520.pdf":
        ("Lei Complementar nº 064/2024", "lc-064-2024", "2024-07-17"),
    # No site o link se chama "Lei Complementar 073", mas o PDF é a LC 072/2025
    "https://ecrie.com.br/sistema/conteudos/arquivo/a_222_0_1_26092025104051.pdf":
        ("Lei Complementar nº 072/2025", "lc-072-2025", "2025-09-17"),
}

MESES = {m: i for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}
DATA = re.compile(r"\bde\s+(\d{1,2})\s*[º°o]?\s+de\s+([a-zç]+)\s+de\s+(\d\.?\d{3})", re.I)

PALAVRA = re.compile(r"^[(\"“'«]?[A-Za-zÀ-ÿ]{2,}[)\"”'».,;:!?]*$")
COMUNS = {"de", "a", "o", "que", "e", "do", "da", "em", "para", "com", "no", "na",
          "os", "as", "dos", "das", "por", "ao", "se", "ou", "art", "lei", "municipal"}

CABECALHOS = re.compile(
    r"^(prefeitura municipal de bataypor|estado d[eo] mato grosso do sul|"
    r"c\.?g\.?c\.?|cnpj|c[âa]mara municipal de bataypor|mato grosso do sul$|"
    r"\d{1,3}$|p[áa]gina \d+)", re.I)
RODAPES = re.compile(r"CEP:?\s*79\.?760|fone|\bfax\b|\btel\.?\s*\(67\)|www\.bataypora", re.I)

ESTRUTURA = re.compile(
    r"^(art(\.|igo)\s*\d|§|par[áa]grafo [úu]nico|[IVXL]{1,6}\s*[-–—.)]|[a-z]\)\s|"
    r"t[íi]tulo\s+[IVXL]+|cap[íi]tulo\s+[IVXL]+|se[çc][ãa]o\s+[IVXL]+|subse[çc][ãa]o)", re.I)
TITULO_SECAO = re.compile(r"^(t[íi]tulo|cap[íi]tulo|livro)\s+[IVXL]+\b", re.I)
SUBSECAO = re.compile(r"^(sub)?se[çc][ãa]o\s+[IVXL]+\b", re.I)
ARTIGO = re.compile(r"^(art(?:\.|igo)\s*(\d+)\s*(?:[º°o]|\.o)?(?:-[A-Z]\b)?\.?)\s*[-–—.]?\s*", re.I)


def qualidade(texto: str) -> float:
    """Nota de 0 a 1: quanto do texto parece português legível."""
    tokens = texto.split()
    if len(tokens) < 15:
        return 0.0
    boas = sum(1 for t in tokens if PALAVRA.match(t))
    comuns = sum(1 for t in tokens if t.lower().strip(".,;:") in COMUNS)
    return 0.7 * boas / len(tokens) + 0.3 * min(1.0, comuns / len(tokens) / 0.25)


def texto_embutido(pdf: Path, pagina: int) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", "-f", str(pagina), "-l", str(pagina), str(pdf), "-"],
        capture_output=True, text=True).stdout


def texto_ocr(pdf: Path, pagina: int) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "p"
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-singlefile",
                        "-f", str(pagina), "-l", str(pagina), str(pdf), str(base)],
                       check=True, capture_output=True)
        return subprocess.run(["tesseract", f"{base}.png", "-", "-l", "por"],
                              capture_output=True, text=True,
                              env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout


def extrair_pagina(args) -> tuple[str, str]:
    """Devolve (texto, método) de uma página, usando o cache quando existe."""
    pdf, pagina = args
    cache = CACHE_TEXTO / pdf.stem / f"{pagina:04d}.json"
    if cache.exists():
        dados = json.loads(cache.read_text())
        return dados["texto"], dados["metodo"]
    texto, metodo = texto_embutido(pdf, pagina), "texto"
    if qualidade(texto) < 0.75:
        ocr = texto_ocr(pdf, pagina)
        if qualidade(ocr) > qualidade(texto):
            texto, metodo = ocr, "ocr"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"texto": texto, "metodo": metodo}, ensure_ascii=False))
    return texto, metodo


def paginas(pdf: Path) -> int:
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))


def paragrafos(texto_paginas: list[str]) -> list[str]:
    """Junta as linhas quebradas pelo PDF em parágrafos."""
    saida, atual = [], []

    def fecha():
        if atual:
            saida.append(" ".join(atual))
            atual.clear()

    recuo_anterior = 0
    for texto in texto_paginas:
        for bruta in texto.splitlines():
            linha = " ".join(bruta.split())
            recuo = len(bruta) - len(bruta.lstrip())
            if not linha:
                fecha()
                continue
            if (CABECALHOS.match(linha) and len(linha) < 80) or (RODAPES.search(linha) and len(linha) < 160):
                continue
            if re.search(r"\.{5,}", linha):  # linha de sumário impresso; o site já gera o índice
                continue
            # Recuo abre parágrafo, exceto em blocos centralizados (linhas seguidas todas recuadas)
            novo_por_recuo = recuo >= 5 and (recuo_anterior < 5 or (atual and atual[-1][-1:] in ".:;"))
            if novo_por_recuo or ESTRUTURA.match(linha):
                fecha()
            recuo_anterior = recuo
            if atual and atual[-1].endswith("-") and linha[:1].islower():
                atual[-1] = atual[-1][:-1] + linha
            else:
                atual.append(linha)
    fecha()
    return saida


def para_markdown(pars: list[str]) -> str:
    linhas, ids = [], set()
    i = 0
    while i < len(pars):
        p = pars[i]
        if (m := TITULO_SECAO.match(p) or SUBSECAO.match(p)) and len(p) < 150:
            nivel = "##" if TITULO_SECAO.match(p) else "###"
            rotulo, resto = p[:m.end()], p[m.end():].strip(" -–—")
            if not resto and i + 1 < len(pars):
                # O nome da seção costuma vir na linha seguinte, curto e em caixa alta
                nome = pars[i + 1]
                if len(nome) < 120 and not ESTRUTURA.match(nome) and not nome.endswith("."):
                    resto, i = nome, i + 1
            linhas.append(f"{nivel} {rotulo} — {resto}" if resto else f"{nivel} {rotulo}")
        elif m := ARTIGO.match(p):
            rotulo = " ".join(m.group(1).split())
            ancora = f"art-{m.group(2)}"
            sufixo = ""
            if ancora not in ids:
                ids.add(ancora)
                sufixo = f"\n{{ #{ancora} }}"
            linhas.append(f"**{rotulo}** {p[m.end():]}{sufixo}")
        else:
            linhas.append(p.replace("*", r"\*").replace("_", r"\_"))
        i += 1
    return "\n\n".join(linhas) + "\n"


def identificar(texto: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Procura no início do texto o título (Lei nº X/AAAA), um slug, a ementa e a data."""
    inicio = " ".join(texto[:4000].split())
    titulo = slug = ementa = data = None
    e = re.search(r"[“\"]\s*((?:disp[õo]e|altera|institui|estabelece|cria|autoriza|acrescenta|"
                  r"revoga|regulamenta|d[áa] nova reda)[^”\"]{10,600}?)[”\"]", inicio, re.I)
    if not e:
        e = re.search(r"((?:disp[õo]e|altera|institui)\s+sobre[^.]{10,600}?provid[êe]ncias\.?)", inicio, re.I)
    if e:
        ementa = " ".join(e.group(1).split()).rstrip(".") + "."
    # O número da própria lei vem antes da ementa; depois dela aparecem as leis citadas
    m = re.search(r"\blei\s+(complementar\s+)?(?:municipal\s+)?n\s*[º°oO.]*[\s.,]*(\d{1,3}(?:\.\d{3})?|\d{4})\s*"
                  r"(?:[/.-]\s*(\d{2,4})|,?\s*de\s+\d{1,2}\s*[º°]?\s+de\s+[a-zç]+\s+de\s+(\d{4}))",
                  inicio[:e.start()] if e else inicio, re.I)
    if m:
        num, ano = int(m.group(2).replace(".", "")), m.group(3) or m.group(4)
        if len(ano) == 2:
            ano = ("19" if int(ano) > 50 else "20") + ano
        tipo = "Lei Complementar" if m.group(1) else "Lei"
        # Leis com 4 dígitos levam ponto de milhar no título ("Lei nº 1.131/2016")
        numero = f"{num:03d}" if num < 1000 else f"{num:,}".replace(",", ".")
        titulo = f"{tipo} nº {numero}/{ano}"
        slug = f"{'lc' if m.group(1) else 'lei'}-{num:03d}-{ano}"
        # A data da lei vem logo depois do número ("nº 003/2001 de 30 de novembro de 2001")
        d = DATA.search(inicio, m.start(), m.end() + 60)
        if d and d.group(2).lower().replace("marco", "março") in MESES:
            mes = MESES[d.group(2).lower().replace("marco", "março")]
            data = f"{d.group(3).replace('.', '')}-{mes:02d}-{int(d.group(1)):02d}"
    return titulo, slug, ementa, data


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def gerar_pagina(fonte: dict, texto_paginas: list[str], metodos: list[str]) -> str:
    n_ocr = metodos.count("ocr")
    if n_ocr == 0:
        metodo = "texto do PDF"
    elif n_ocr == len(metodos):
        metodo = "OCR"
    else:
        metodo = f"misto ({n_ocr} de {len(metodos)} páginas por OCR)"
    titulo = fonte["titulo_detectado"] or fonte["titulo"].title()
    cab = [
        "---",
        f"title: {yaml_str(titulo)}",
        f"data: {fonte['data'] or ''}",
        f"titulo_no_site: {yaml_str(fonte['titulo'])}",
        f"ementa: {yaml_str(fonte['ementa'] or '')}",
        f"fonte_pdf: {fonte['url']}",
        f"pagina_origem: {fonte['pagina_origem']}",
        f"sha256: {fonte['sha256']}",
        f"paginas: {len(metodos)}",
        f"extracao: {yaml_str(metodo)}",
        "revisao: pendente",
        "hide:",
        "  - toc",
        "---",
        "",
        f"# {titulo}",
        "",
    ]
    if fonte["ementa"]:
        cab += [f"> {fonte['ementa']}", ""]
    aviso = "Texto em revisão"
    cab += [
        f'!!! warning "{aviso}"',
        f"    Extraído por {metodo} e **ainda em revisão**. Veja também o "
        f"[PDF publicado pela prefeitura]({fonte['url']}) "
        f"([página de origem]({fonte['pagina_origem']})).",
        "",
        botoes_download(fonte["arquivo"]),
        "",
    ]
    if fonte["titulo_detectado"] and not mesmo_numero(fonte["titulo"], fonte["titulo_detectado"]):
        cab += [
            '!!! note "Divergência no site"',
            f"    No site da prefeitura este PDF aparece com o nome \"{fonte['titulo']}\", "
            f"mas o documento é a {fonte['titulo_detectado']}.",
            "",
        ]
    return "\n".join(cab) + "\n" + para_markdown(paragrafos(texto_paginas))


def botoes_download(arquivo: str) -> str:
    """Botões para os arquivos gerados por scripts/exportar.py em docs/baixar/."""
    # caminho relativo à página (leis de categorias com subpastas, como leis-ordinarias/2001, ficam mais fundo)
    subir = "../" * (len(Path(arquivo).parts) - 1)
    base = f"{subir}baixar/{arquivo.removesuffix('.md')}"
    nome = Path(arquivo).stem
    # O Markdown fica salvo como .md.txt (um .md em docs/ viraria página); o download o renomeia
    formatos = [("PDF", ".pdf", ".pdf"), ("Word (.docx)", ".docx", ".docx"),
                ("Texto (.txt)", ".txt", ".txt"), ("Markdown (.md)", ".md.txt", ".md")]
    return "Baixar: " + " ".join(
        f'[{rotulo}]({base}{ext}){{ .md-button download="{nome}{ext_final}" }}'
        for rotulo, ext, ext_final in formatos)


def mesmo_numero(titulo_site: str, titulo_pdf: str) -> bool:
    num_site = re.findall(r"\d+", titulo_site)
    num_pdf = re.search(r"nº (\d+)", titulo_pdf)
    return not num_pdf or (bool(num_site) and int(num_site[0]) == int(num_pdf.group(1)))


def gerar_indice(categoria: str, nome: str, leis: list[dict]):
    linhas = ["---", f"title: {yaml_str(nome)}", "hide:", "  - toc", "---", "", f"# {nome}", "",
              "| Norma | Data | Ementa | Extração |", "|---|---|---|---|"]
    for f in sorted(leis, key=lambda f: f["arquivo"]):
        link = Path(f["arquivo"]).name
        titulo = f["titulo_detectado"] or f["titulo"].title()
        ementa = (f["ementa"] or "—").replace("|", "\\|")
        data = "/".join(reversed(f["data"].split("-"))) if f.get("data") else "—"
        linhas.append(f"| [{titulo}]({link}) | {data} | {ementa} | {f['extracao']} |")
    (DOCS / categoria / "index.md").write_text("\n".join(linhas) + "\n")


def titulo_pagina(pagina: Path) -> str:
    m = re.search(r'^title: "?(.*?)"?$', pagina.read_text(), re.M)
    return m.group(1) if m else pagina.parent.name


def subpastas(grupo: str) -> list[str]:
    """Subpastas de um grupo (ex.: os anos de leis-ordinarias), as que têm index.md, em ordem."""
    return sorted(p.parent.name for p in (DOCS / grupo).glob("*/index.md"))


def gerar_indice_grupo(grupo: str, fontes: list[dict]):
    """Página de entrada de um grupo de categorias (ex.: Leis Ordinárias), com cada subpasta e quantas leis tem."""
    pagina = DOCS / grupo / "index.md"
    nome = titulo_pagina(pagina)
    texto = pagina.read_text()
    linhas = ["| Ano | Leis |", "|---|---:|"]
    for sub in subpastas(grupo):
        n = sum(1 for f in fontes if f["categoria"] == f"{grupo}/{sub}")
        linhas.append(f"| [{sub}]({sub}/index.md) | {n or '—'} |")
    # a tabela fica entre as marcas; o texto antes e depois é editado à mão
    inicio, fim = "<!-- lista-inicio -->", "<!-- lista-fim -->"
    if inicio not in texto:
        texto = texto.rstrip() + f"\n\n{inicio}\n{fim}\n"
    a, b = texto.index(inicio) + len(inicio), texto.index(fim)
    pagina.write_text(texto[:a] + "\n" + "\n".join(linhas) + "\n" + texto[b:])
    print(f"índice do grupo {nome}")


def gerar_nav(fontes: list[dict]):
    """Reescreve o nav do zensical.toml (entre as marcas nav-inicio e nav-fim).

    Categorias com subpasta (ex.: leis-ordinarias/2001) ficam dentro de um item do grupo (Leis Ordinárias),
    com uma entrada por subpasta que tenha index.md, mesmo as que ainda não têm leis.
    """
    config = RAIZ / "zensical.toml"
    texto = config.read_text()
    # leis marcadas com "ignorar" não têm página: no menu virariam itens que não levam a lugar nenhum
    fontes = [f for f in fontes if not f.get("ignorar")]
    linhas = ["nav = [", '  { "Início" = "index.md" },']
    grupos_feitos = set()
    for cat in dict.fromkeys(f["categoria"] for f in fontes):
        if "/" in cat:
            grupo = cat.split("/")[0]
            if grupo in grupos_feitos:
                continue
            grupos_feitos.add(grupo)
            linhas.append(f"  {{ {yaml_str(titulo_pagina(DOCS / grupo / 'index.md'))} = [")
            linhas.append(f'    "{grupo}/index.md",')
            for sub in subpastas(grupo):
                leis = sorted((f for f in fontes if f["categoria"] == f"{grupo}/{sub}"), key=lambda f: f["arquivo"])
                linhas.append(f"    {{ {yaml_str(sub)} = [")
                linhas.append(f'      "{grupo}/{sub}/index.md",')
                linhas += [f'      "{f["arquivo"]}",' for f in leis]
                linhas.append("    ] },")
            linhas.append("  ] },")
            continue
        leis = sorted((f for f in fontes if f["categoria"] == cat), key=lambda f: f["arquivo"])
        linhas.append(f"  {{ {yaml_str(leis[0]['categoria_nome'])} = [")
        linhas.append(f'    "{cat}/index.md",')
        linhas += [f'    "{f["arquivo"]}",' for f in leis]
        linhas.append("  ] },")
    linhas.append("]")
    inicio = texto.index("# nav-inicio\n") + len("# nav-inicio\n")
    fim = texto.index("# nav-fim")
    config.write_text(texto[:inicio] + "\n".join(linhas) + "\n" + texto[fim:])


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def pode_sobrescrever(destino: Path, novo: str, hash_gerado: str | None) -> bool:
    """Só reescreve páginas que ninguém editou à mão desde a última vez que foram geradas.

    hash_gerado é o hash do texto que o script escreveu da última vez; se o arquivo
    não bate com ele (nem com o texto novo), alguém o revisou e ele é preservado.
    """
    if not destino.exists():
        return True
    atual = destino.read_text()
    return atual == novo or sha256(atual) == hash_gerado


def main():
    forcar = "--forcar" in sys.argv[1:]
    preservadas = []
    todas = json.loads(FONTES.read_text())
    # Leis marcadas com "ignorar": true ficam fora do site (não geram página, índice nem menu)
    fontes = [f for f in todas if not f.get("ignorar")]
    tarefas = []
    # Leis sem PDF (origem "doc") vêm só do .doc da prefeitura: entram no índice e no menu,
    # mas não são extraídas nem geradas aqui
    com_pdf = [f for f in fontes if f.get("pdf_local")]
    for f in com_pdf:
        pdf = PDFS / f["pdf_local"]
        f["_pdf"], f["_paginas"] = pdf, paginas(pdf)
        tarefas += [(pdf, p) for p in range(1, f["_paginas"] + 1)]
    print(f"{len(tarefas)} páginas em {len(com_pdf)} PDFs")

    with ProcessPoolExecutor() as pool:
        resultados = dict(zip(tarefas, pool.map(extrair_pagina, tarefas, chunksize=2)))

    usados = {f["arquivo"].removesuffix(".md") for f in fontes if not f.get("pdf_local")}
    for f in com_pdf:
        res = [resultados[(f["_pdf"], p)] for p in range(1, f["_paginas"] + 1)]
        textos, metodos = [r[0] for r in res], [r[1] for r in res]
        f["titulo_detectado"], slug, f["ementa"], f["data"] = identificar("\n".join(textos[:3]))
        if f["url"] in SEM_NUMERO:
            # Documentos sem número próprio: o identificador acharia leis citadas no texto
            f["titulo_detectado"], slug, f["data"] = SEM_NUMERO[f["url"]]
            f["ementa"] = None
        elif f["url"] in IDENTIFICADAS:
            f["titulo_detectado"], slug, f["data"] = IDENTIFICADAS[f["url"]]
        pasta = f["categoria"]
        slug = slug or Path(f["arquivo"]).stem
        while f"{pasta}/{slug}" in usados:
            slug += "-b"
        usados.add(f"{pasta}/{slug}")
        f["arquivo"] = f"{pasta}/{slug}.md"
        f["extracao"] = "OCR" if metodos.count("ocr") == len(metodos) else (
            "texto" if "ocr" not in metodos else "misto")
        destino = DOCS / f["arquivo"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        novo = gerar_pagina(f, textos, metodos)
        if not forcar and not pode_sobrescrever(destino, novo, f.get("hash_gerado")):
            preservadas.append(f["arquivo"])
            # O índice mostra a origem que a página editada declara (ex.: refeita a partir do .doc)
            pagina = destino.read_text()
            if re.search(r"^extracao: .*\.doc", pagina, re.M):
                f["extracao"] = "doc"
            # ...e a ementa revisada na página, no lugar da que o OCR leu do PDF
            if m := re.search(r'^ementa: "(.+)"$', pagina, re.M):
                f["ementa"] = m.group(1).replace('\\"', '"')
            continue
        destino.write_text(novo)
        f["hash_gerado"] = sha256(novo)
        print(f"{f['arquivo']}: {f['extracao']}, {len(metodos)} pág")

    for cat in dict.fromkeys(f["categoria"] for f in fontes):
        leis = [f for f in fontes if f["categoria"] == cat]
        gerar_indice(cat, leis[0]["categoria_nome"], leis)
    for grupo in dict.fromkeys(c.split("/")[0] for c in (f["categoria"] for f in fontes) if "/" in c):
        gerar_indice_grupo(grupo, fontes)
    gerar_nav(fontes)

    for f in com_pdf:
        del f["_pdf"], f["_paginas"]
    FONTES.write_text(json.dumps(todas, ensure_ascii=False, indent=2) + "\n")

    if preservadas:
        print(f"\n{len(preservadas)} página(s) editada(s) à mão foram mantidas como estão:")
        for arquivo in preservadas:
            print(f"  docs/{arquivo}")
        print("Para gerar de novo a partir do PDF (e perder as edições), use --forcar.")


if __name__ == "__main__":
    main()
