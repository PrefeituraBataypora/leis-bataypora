"""Risca o texto dos artigos revogados (como no site do Planalto): o artigo inteiro, com parágrafos e incisos, até o
próximo artigo, fica com a classe .revogado (CSS em docs/stylesheets/extra.css); o rótulo "Art. Nº" fica sem risco.

Acha os artigos pelas notas que já explicam a revogação:
  - nota logo depois do artigo: "Revogado", "Artigo revogado", "Revogado pela ...";
  - nota no topo que cita os artigos com link (#art-N): "Art. 4º revogado", "Parcialmente revogada ...".
Lei revogada por inteiro (nota "Lei revogada" no topo): todo o texto da lei é riscado, menos as notas.

Pode rodar de novo sobre páginas prontas sem mudar nada. Rode depois de montar as páginas (montar.py, indice.py).
Uso: python scripts/revogados.py [páginas .md ...]   (sem argumentos: todas as páginas de docs/)
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
DEPOIS = re.compile(r'^!!! (?:danger|info) "(?:Revogado|Artigo revogado|Revogado pela [^"]*)"')
TOPO = re.compile(r'^!!! (?:danger|info) "(?:Art\. \d+º? revogado|Parcialmente revogada[^"]*)"')
ARTIGO = re.compile(r"^\*\*Art\. ")


def nota(b: str) -> bool:
    return b.startswith("!!! ") or b.startswith("    ")  # admonition e seus parágrafos recuados


def marcar(b: str) -> str:
    """Classe .revogado no parágrafo; fora dos artigos, também .tudo (risca até o negrito do começo, que nos artigos
    é o rótulo "Art. Nº" e fica sem risco)."""
    cls = ".revogado" if ARTIGO.match(b) else ".revogado .tudo"
    linhas = b.split("\n")
    attr = re.fullmatch(r"\{ (.*) \}", linhas[-1])
    if attr:
        if ".revogado" not in attr.group(1).split():
            linhas[-1] = "{ " + attr.group(1) + " " + cls + " }"
        return "\n".join(linhas)
    return b + "\n{ " + cls + " }"


def artigo_inteiro(bs: list[str], i: int) -> list[int]:
    """Índices dos parágrafos do artigo que começa em bs[i] (até o próximo artigo, título ou anexo)."""
    idx = [i]
    for j in range(i + 1, len(bs)):
        b = bs[j]
        if ARTIGO.match(b) or b.startswith("#"):
            break
        if nota(b) or b.lstrip().startswith(("<table", "|", "<div")):
            continue
        idx.append(j)
    return idx


def marcar_qualquer(b: str) -> str:
    """Parágrafo, citação, título ou tabela de uma lei revogada por inteiro."""
    if b.startswith("#"):  # título: o atributo fica na mesma linha
        if ".revogado" in b.split("\n")[0]:
            return b
        primeira, *resto = b.split("\n")
        m = re.search(r" \{ (.*) \}$", primeira)
        primeira = (primeira[:m.start()] + " { " + m.group(1) + " .revogado }") if m else primeira + " { .revogado }"
        return "\n".join([primeira] + resto)
    if b.lstrip().startswith("<table"):
        return b if 'class="revogado"' in b else re.sub(r"<table(?![^>]*class=)", '<table class="revogado"', b)
    if b.lstrip().startswith("|"):  # tabela Markdown não aceita atributo: vai dentro de um <div class="revogado">
        return f'{ABRE}\n\n{b}\n\n</div>'
    return marcar(b)


ABRE = '<div class="revogado" markdown>'


def aplicar(pagina: Path) -> bool:
    original = pagina.read_text()
    texto = original.rstrip("\n")  # sem a quebra do fim do arquivo, o último parágrafo é tratado como os outros
    bs = texto.split("\n\n")
    if any(b.startswith('!!! danger "Lei revogada"') for b in bs):
        # revogada por inteiro: tudo depois da linha "Baixar:" (o corpo da lei), menos as notas
        ini = next((k for k, b in enumerate(bs) if b.startswith("Baixar: ")), None)
        if ini is not None:
            def ja_feito(k, b):  # tabela já dentro do <div class="revogado">, e as linhas do próprio <div>
                return b.startswith((ABRE, "</div>")) or (b.lstrip().startswith("|") and k > 0 and bs[k - 1] == ABRE)
            novo = "\n\n".join(b if k <= ini or nota(b) or not b.strip() or ja_feito(k, b) else marcar_qualquer(b)
                                 for k, b in enumerate(bs))
            if novo + "\n" != original:
                pagina.write_text(novo + "\n")
                return True
        return False
    alvos: set[int] = set()
    for k, b in enumerate(bs):
        if DEPOIS.match(b):
            # o artigo é o último "**Art." antes da nota (a nota pode vir depois de um parágrafo do artigo)
            i = next((x for x in range(k - 1, -1, -1) if ARTIGO.match(bs[x])), None)
            if i is not None:
                alvos.update(artigo_inteiro(bs, i))
        elif TOPO.match(b):
            corpo = "\n\n".join(bs[k:k + 1] + [x for x in bs[k + 1:k + 4] if x.startswith("    ")])
            for n in re.findall(r"\(#art-(\d+)\)", corpo):
                i = next((x for x, y in enumerate(bs) if ARTIGO.match(y) and y.rstrip().endswith(f"{{ #art-{n} }}")
                          or ARTIGO.match(y) and re.search(rf"\{{ #art-{n}(?: [^}}]*)? \}}$", y)), None)
                if i is not None:
                    alvos.update(artigo_inteiro(bs, i))
    novo = "\n\n".join(marcar(b) if k in alvos else b for k, b in enumerate(bs))
    if novo + "\n" != original:
        pagina.write_text(novo + "\n")
        return True
    return False


def main():
    paginas = [Path(p) for p in sys.argv[1:]] or [p for p in DOCS.glob("**/*.md") if "baixar" not in p.parts]
    for p in sorted(paginas):
        if aplicar(p):
            print("revogados riscados:", p)


if __name__ == "__main__":
    main()
