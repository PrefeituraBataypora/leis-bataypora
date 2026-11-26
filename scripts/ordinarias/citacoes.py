"""Põe links nas citações de outras leis municipais dentro do texto das leis ordinárias.

"Lei nº-270/93" vira [Lei nº-270/93](../1993/lei-270-1993.md), e "artigo 4º, ítem II da Lei nº-270/93" vira
[artigo 4º, ítem II da Lei nº-270/93](../1993/lei-270-1993.md#art-4) quando a página citada tem a âncora do artigo.
"Leis nº-187/91 e 212/92" ganha um link para cada número. O texto citado fica como está; só ganha o link.

Só liga para páginas que existem em docs/leis-ordinarias/AAAA/lei-N-AAAA.md (leis federais, como a 4.320/64, e
leis anteriores a 1983, que não estão no site, ficam sem link). Não mexe no cabeçalho da página, na ementa do topo,
nos títulos, nos avisos (!!!) nem em citações que já têm link. Pode rodar de novo sem duplicar links.
Uso: python scripts/ordinarias/citacoes.py [--teste] página.md ...   (--teste: só lista o que faria)
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
ORD = DOCS / "leis-ordinarias"

ARTIGO = (r"(?:[Aa]rt(?:igo|\.)\s*(?P<art>\d+)\s*(?:[º°]|o\.?)?"
          r"(?:,?\s*(?:§\s*\d+\s*[º°]?|[Pp]ar[áa]grafo\s+(?:\d+\s*[º°]?|[úu]nico)|[ií]tem\s+[IVXL]+|inciso\s+[IVXL]+"
          r"|al[íi]nea\s+\"?\w\"?)){0,2},?\s+d[ao]s?\s+)")
LEI = r"(?P<lei>[Ll][Ee][Ii](?P<pl>[Ss])?(?:\s+[Mm]unicipal)?\s*(?:[Nn]\s*[º°o*]?\.?)?\s*[-–]?\s*(?P<num>\d{1,4})/(?P<ano>\d{2,4}))"
CITA = re.compile(ARTIGO + "?" + LEI)
MAIS = re.compile(r"(?P<sep>\s*(?:,|\be\b)\s*)(?P<num>\d{1,4})/(?P<ano>\d{2,4})")
LINK = re.compile(r"\[[^\]]*\]\([^)]*\)")


def ano4(a: str) -> int:
    a = int(a)
    return a if a > 999 else (1900 + a if a >= 50 else 2000 + a)


def alvo(num: str, ano: str, art: str | None, pagina: Path):
    a = ano4(ano)
    dest = ORD / str(a) / f"lei-{int(num)}-{a}.md"
    if not dest.exists() or dest.resolve() == pagina.resolve():
        return None
    rel = Path("..") / str(a) / dest.name if a != int(pagina.parent.name) else Path(dest.name)
    url = rel.as_posix()
    if art and re.search(rf"\{{ #art-{int(art)}(?: [^}}]*)? \}}", dest.read_text()):
        url += f"#art-{int(art)}"
    return url


def ligar(linha: str, pagina: Path, achados: list) -> str:
    ocupado = [m.span() for m in LINK.finditer(linha)]
    livre = lambda i, j: not any(a < j and i < b for a, b in ocupado)
    saida, pos = [], 0
    for m in CITA.finditer(linha):
        if m.start() < pos or not livre(*m.span()):
            continue
        url = alvo(m.group("num"), m.group("ano"), m.group("art"), pagina)
        fim = m.end()
        trecho = f"[{m.group(0)}]({url})" if url else m.group(0)
        if url:
            achados.append((m.group(0), url))
        if m.group("pl"):  # "Leis nº-187/91 e 212/92": um link para cada número seguinte
            while (n := MAIS.match(linha, fim)) and livre(*n.span()):
                u = alvo(n.group("num"), n.group("ano"), None, pagina)
                txt = f"{n.group('num')}/{n.group('ano')}"
                trecho += n.group("sep") + (f"[{txt}]({u})" if u else txt)
                if u:
                    achados.append((txt, u))
                fim = n.end()
        saida.append(linha[pos:m.start()] + trecho)
        pos = fim
    return "".join(saida) + linha[pos:]


def aplicar(pagina: Path, teste=False) -> list:
    linhas = pagina.read_text().split("\n")
    achados, dentro_fm, topo = [], False, True
    for i, l in enumerate(linhas):
        if i == 0 and l == "---":
            dentro_fm = True
            continue
        if dentro_fm:
            dentro_fm = l != "---"
            continue
        if l.startswith("#"):
            continue
        if topo and l.startswith(">"):  # ementa do topo da página
            continue
        if l.startswith("Baixar: "):
            topo = False
        if l.startswith(("!!!", "    ", "**LEI", "Baixar: ")) or not l.strip():
            continue
        linhas[i] = ligar(l, pagina, achados)
    if achados and not teste:
        pagina.write_text("\n".join(linhas))
    return achados


def main():
    args = sys.argv[1:]
    teste = "--teste" in args
    for p in [Path(a) for a in args if a != "--teste" and Path(a).name != "index.md"]:
        for txt, url in aplicar(p, teste):
            print(f"{p.name}: {txt} -> {url}")


if __name__ == "__main__":
    main()
