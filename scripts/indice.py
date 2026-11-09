"""Gera um índice (títulos, capítulos, seções e subseções, com links para os artigos) no topo das
leis que têm essa divisão, no mesmo formato do índice do Código Tributário.

O índice fica num quadro "Índice", logo depois dos botões de download, e não entra nos arquivos
para baixar (o exportar.py tira os quadros). Rodar de novo substitui o índice anterior.
Uso: python scripts/indice.py [página.md ...]   (sem argumentos: todas as leis com 3+ divisões)
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
# O Código Tributário já traz o índice publicado com a própria lei
SEM_INDICE = {"codigo-tributario/lc-001-1991.md"}

TITULO = re.compile(r"^(#{1,5}) (.*?)\s*(\{[^}]*\})?\s*$")
ROTULO = re.compile(r"^(TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\b(.*)$", re.I)
NIVEL = {"TÍTULO": 0, "CAPÍTULO": 1, "SEÇÃO": 2, "SUBSEÇÃO": 3}
ANCORA_ART = re.compile(r"^\{ #((?:adct-)?art-(\d+)[^ }]*) \}$")
BLOCO = re.compile(r'\n!!! abstract "Índice"\n(    .*\n|\n(?=    ))+')


def divisoes(linhas):
    """Lista de [nível, rótulo, assunto, id, artigos] na ordem da página."""
    itens, atual, ultimo_era_art = [], None, False
    for l in linhas:
        if l.startswith("**Art."):
            ultimo_era_art = True
            continue
        m = ANCORA_ART.match(l)
        if m and ultimo_era_art:
            if atual is None:
                atual = [None, "", "Disposições iniciais", None, []]
                itens.append(atual)
            atual[4].append((m.group(1), m.group(2)))
        ultimo_era_art = False
        m = TITULO.match(l)
        if not m:
            continue
        texto, attrs = m.group(2), m.group(3) or ""
        ident = re.search(r"#([\w-]+)", attrs)
        rotulo, _, assunto = texto.partition(" — ")
        r = ROTULO.match(rotulo)
        nivel = NIVEL[r.group(1).upper().replace("TITULO", "TÍTULO")] if r else None
        if len(m.group(1)) == 1 and nivel is None:
            continue  # título da página
        atual = [nivel, rotulo.strip(), assunto.strip(), ident.group(1) if ident else None, []]
        itens.append(atual)
    return itens


def faixa(arts):
    if not arts:
        return ""
    link = lambda a: f"[{a[1]}](#{a[0]})"
    if len(arts) == 1:
        return link(arts[0])
    sep = " e " if len(arts) == 2 else " a "
    return link(arts[0]) + sep + link(arts[-1])


def tabela(itens):
    niveis = [i[0] for i in itens if i[0] is not None]
    base = min(niveis) if niveis else 0
    linhas = ["| Divisão | Assunto | Artigos |", "|---|---|---:|"]
    emendas = False
    for nivel, rotulo, assunto, ident, arts in itens:
        if rotulo.upper().startswith("EMENDA"):
            # Lei Orgânica: as emendas publicadas no fim viram uma linha só
            if not emendas:
                linhas.append(f"| **[Emendas](#{ident})** | **Emendas à Lei Orgânica publicadas no PDF** | |")
                emendas = True
            continue
        if nivel is None:
            rot = f"[{rotulo}](#{ident})" if ident else rotulo
            negrito = f"**{assunto}**" if assunto else ""
            linhas.append(f"| **{rot}** | {negrito} | {faixa(arts)} |" if rotulo else f"|  | {assunto} | {faixa(arts)} |")
            continue
        recuo = "&emsp;" * (nivel - base)
        nome = rotulo[:1].upper() + rotulo[1:].lower() if nivel else rotulo.upper()
        if nome in ("Capítulo", "Seção", "Subseção"):
            nome += " (sem número)"
        nome = re.sub(r"\b([ivxl]+|única|unica)$", lambda m: m.group(1).upper(), nome)
        nome = nome.replace("ÚNICA", "Única").replace("UNICA", "Única")
        if arts:
            linhas.append(f"| {recuo}{nome} | {assunto} | {faixa(arts)} |")
        else:
            linhas.append(f"| {recuo}**{nome}** | {f'**{assunto}**' if assunto else ''} | |")
    return linhas


def aplicar(pagina: Path):
    texto = BLOCO.sub("\n", pagina.read_text())
    itens = divisoes(texto.splitlines())
    if sum(1 for i in itens if i[0] is not None) < 3:
        return False
    bloco = '!!! abstract "Índice"\n' + "\n".join("    " + l for l in tabela(itens)) + "\n"
    m = re.search(r"^Baixar: .*$", texto, re.M)
    texto = texto[:m.end()] + "\n\n" + bloco + texto[m.end():]
    pagina.write_text(re.sub(r"\n{3,}", "\n\n", texto))
    return True


def main():
    paginas = [Path(p).resolve() for p in sys.argv[1:]] or sorted(DOCS.glob("*/*.md"))
    for p in paginas:
        rel = p.relative_to(DOCS).as_posix()
        if p.name == "index.md" or rel in SEM_INDICE or rel.startswith("baixar/"):
            continue
        if aplicar(p):
            print("índice:", rel)


if __name__ == "__main__":
    main()
