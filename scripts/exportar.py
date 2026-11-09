"""Gera versões para download de cada lei em docs/baixar/: Markdown, TXT, DOCX e PDF.

Lê as páginas de docs/ (já com as correções feitas à mão), tira o que é só do site
(cabeçalho YAML, avisos, botões, âncoras) e converte com Pandoc; o PDF passa pelo Typst.
O Markdown é salvo como .md.txt porque um .md dentro de docs/ viraria página do site;
o botão de download o entrega com o nome .md.

Requer: pypandoc_binary e typst (pip).
Uso: python scripts/exportar.py
"""

import re
import shutil
import subprocess
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypandoc
import typst

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
SAIDA = DOCS / "baixar"

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# Sem citações: "@" em texto de OCR viraria referência bibliográfica
ENTRADA = "markdown-citations"
# Linhas só de atributos ({ #art-1 }, { .centro }) e os botões de download só valem no site
SO_DO_SITE = re.compile(r"^\{:?\s*[#.][^}]*\}$|\.md-button", re.M)


def metadados(texto: str) -> dict:
    m = FRONT_MATTER.match(texto)
    dados = {}
    for linha in (m.group(1).splitlines() if m else []):
        chave, _, valor = linha.partition(":")
        dados[chave.strip()] = valor.strip().strip('"')
    return dados


def markdown_limpo(texto: str) -> str:
    dados = metadados(texto)
    corpo = FRONT_MATTER.sub("", texto)
    linhas, em_aviso = [], False
    for linha in corpo.splitlines():
        if linha.startswith("!!! "):
            em_aviso = True
            continue
        if em_aviso and (linha.startswith("    ") or not linha.strip()):
            continue
        em_aviso = False
        if SO_DO_SITE.search(linha):
            continue
        linhas.append(linha)
    corpo = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip() + "\n"
    # Links para artigos da própria página (#art-N) só existem no site: no arquivo viram texto
    corpo = re.sub(r"\[([^\]]+)\]\(#[^)]*\)", r"\1", corpo)

    # Nota de origem logo abaixo do título
    nota = f"*Texto em revisão, extraído por {dados.get('extracao', '?')}."
    if dados.get("fonte_pdf"):
        nota += f" PDF publicado pela prefeitura: <{dados['fonte_pdf']}>"
    nota += "*"
    titulo, _, resto = corpo.partition("\n")
    return f"{titulo}\n\n{nota}\n{resto}"


def modelo_docx(destino: Path) -> Path:
    """Modelo de estilos do Pandoc com o texto justificado (todos os estilos de
    parágrafo herdam de "Body Text")."""
    padrao = destino.with_name("padrao.docx")
    subprocess.run([pypandoc.get_pandoc_path(), "-o", str(padrao),
                    "--print-default-data-file", "reference.docx"], check=True)
    with zipfile.ZipFile(padrao) as origem, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as saida:
        for item in origem.infolist():
            dados = origem.read(item.filename)
            if item.filename == "word/styles.xml":
                estilos = dados.decode()
                corpo = re.search(r'<w:style [^>]*w:styleId="BodyText".*?</w:style>', estilos, re.S).group(0)
                # O Word exige w:jc depois de w:spacing/w:ind, ou seja, no fim do w:pPr
                novo = corpo.replace("</w:pPr>", '  <w:jc w:val="both" />\n    </w:pPr>', 1)
                dados = estilos.replace(corpo, novo).encode()
            saida.writestr(item, dados)
    padrao.unlink()
    return destino


def exportar(pagina: Path, modelo: Path):
    destino = SAIDA / pagina.relative_to(DOCS).with_suffix("")
    destino.parent.mkdir(parents=True, exist_ok=True)
    md = markdown_limpo(pagina.read_text())
    titulo = metadados(pagina.read_text()).get("title", pagina.stem)
    args = ["-M", "lang=pt-BR", "-M", f"pagetitle={titulo}"]

    Path(f"{destino}.md.txt").write_text(md)
    # Imagens (organogramas): no PDF e no Word entram pelo caminho completo do arquivo
    md = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)\)",
                lambda m: f"{m.group(1)}{(pagina.parent / m.group(2)).resolve()})", md)
    pypandoc.convert_text(md, "plain", format=ENTRADA, outputfile=f"{destino}.txt",
                          extra_args=args + ["--columns=90"])
    pypandoc.convert_text(md, "docx", format=ENTRADA, outputfile=f"{destino}.docx",
                          extra_args=args + [f"--reference-doc={modelo}"])
    typ = pypandoc.convert_text(md, "typst", format=ENTRADA,
                                extra_args=args + ["--standalone", "-V", "papersize=a4",
                                                   "-V", "fontsize=11pt", "-V", "margin.x=2.5cm",
                                                   "-V", "margin.y=2.5cm"])
    with tempfile.TemporaryDirectory() as tmp:
        fonte = Path(tmp) / "lei.typ"
        fonte.write_text(typ)
        typst.compile(str(fonte), output=f"{destino}.pdf", root="/")
    return pagina.relative_to(DOCS)


def main():
    shutil.rmtree(SAIDA, ignore_errors=True)
    paginas = [p for p in sorted(DOCS.glob("*/*.md")) if p.name != "index.md" and SAIDA not in p.parents]
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor() as pool:
        modelo = modelo_docx(Path(tmp) / "modelo.docx")
        for feito in pool.map(lambda p: exportar(p, modelo), paginas):
            print(f"exportado: {feito}")


if __name__ == "__main__":
    main()
