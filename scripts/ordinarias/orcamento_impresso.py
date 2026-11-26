"""Anexos impressos pelo sistema orçamentário (ORC051, ORC058, ORC069, ORC072, ORC806): separa o cabeçalho de cada
quadro em linhas, como na cópia (formato feito à mão na Lei 299/1994):
  ORC072 - SISTEMA ORCAMENTARIO QUADRO DE DETALHAMENTO DE DESPESAS
  PREFEITURA MUNICIPAL DE BATAYPORA - M EXERCICIO DE 1995 PAG.: 1
  (linha em branco)  ORGAO ... / UNIDADE ...
  (linha em branco)  FUNCAO ... / PROGRAMA ... / SUB-PROGRAMA ... / PROJETO/ATIVIDADE ...
Linhas do mesmo grupo terminam com dois espaços (quebra de linha do Markdown). Um cabeçalho de colunas grudado no texto
("Codigo Especificacao ... Categoria Economica 3590.00.00 Outras Receitas 1.500,00") vira tabela.
Parágrafos já separados ficam como estão; pode rodar de novo.
Uso: python scripts/ordinarias/orcamento_impresso.py página.md ...
"""
import re, sys
from pathlib import Path

CORTE = re.compile(r" (?=PREFEITURA MUNICIPAL|ORGAO(?= ?:| \d)|UNIDADE(?= ?:| \d)|FUNCAO \d|PROGRAMA \d|PROGRAMA DE TRABALHO|SUB-PROGRAMA \d"
                   r"|PROJETO/ATIVIDADE \d|RESUMO GERAL|NATUREZA DA DESPESA|RECEITA(?= Codigo|$)|DESPESA Cr\$)")
GRUPO = {"ORGAO": 1, "UNIDADE": 1, "FUNCAO": 2, "PROGRAMA": 2, "SUB-PROGRAMA": 2, "PROJETO/ATIVIDADE": 2}


def separa(b: str) -> str:
    fim = b[len(b.rstrip("\n")):]
    b = b.rstrip("\n")
    b = b.replace("(ANEXO 2 LEI 432 ", "(ANEXO 2 LEI 4320) ")
    if "\n" in b and re.match(r"ORC\d{3} ", b):  # já separado (à mão): cada linha termina com dois espaços
        return "  \n".join(l.rstrip() for l in b.split("\n")) + fim
    # cabeçalho de colunas grudado (quadro sem tabela no rascunho): vira tabela; linha de dados, se houver, vai junto
    m = re.search(r" (Codigo Especificacao \w+ \w+ Categoria Economica)( .*)?$", b)
    tab = ""
    if m:
        cols = m.group(1).replace("Categoria Economica", "Categoria_Economica").split()
        cols = [c.replace("_", " ") for c in cols]
        tab = "| " + " | ".join(cols) + " |\n|---|---|---:|---:|---:|"
        if m.group(2):
            d = re.match(r" (\S+) (.+?) ([\d.]+,\d\d)$", m.group(2))
            tab += f"\n| {d.group(1)} | {d.group(2)} |  | {d.group(3)} |  |"
        b = b[:m.start()]
    if "\n" in b or not re.match(r"(ORC\d{3}|ORGAO|FUNCAO) ", b):
        return b + fim
    partes = CORTE.split(b)
    grupos, atual, g_atual = [], [], None
    for p in partes:
        chave = p.split(" ")[0]
        g = GRUPO.get(chave, 0 if not atual else g_atual)
        if chave == "PROGRAMA" and p.startswith("PROGRAMA DE TRABALHO"):
            g = 0
        if atual and g != g_atual:
            grupos.append(atual); atual = []
        atual.append(p.strip()); g_atual = g
    grupos.append(atual)
    return "\n\n".join("  \n".join(gr) for gr in grupos) + ("\n\n" + tab if tab else "") + fim


for a in sys.argv[1:]:
    p = Path(a); t = p.read_text()
    novo = "\n\n".join(separa(b) for b in t.split("\n\n"))
    if novo != t:
        p.write_text(novo); print("cabeçalhos separados:", p.name)


# --- linhas de identificação (ORGAO, UNIDADE, FUNCAO, PROGRAMA, SUB-PROGRAMA, PROJETO/ATIVIDADE) num quadro com bordas ---
# "PROJETO/ATIVIDADE 1001 - AQUISICAO DE ... 9.008,00" → PROJETO/ATIVIDADE 1001 | AQUISICAO DE ... | 9.008,00
CAB = re.compile(r"^((?:ORGAO|UNIDADE|FUNCAO|PROGRAMA|SUB-PROGRAMA|PROJETO/ATIVIDADE)\s*:?\s*[\d.]+)\s*-\s*(.*?)"
                 r"(?:\s+([\d.]+,\d\d))?\s*$")


def quadro(ms) -> str:
    """Linhas de identificação num quadro com bordas (tabela HTML sem cabeçalho de colunas), acima da planilha."""
    def td(x, direita=False):
        return f'<td style="text-align:right">{x}</td>' if direita else f"<td>{x}</td>"
    linhas = [f"<tr>{td(re.sub(r'[ ]+', ' ', m.group(1)))}{td(m.group(2).strip())}{td(m.group(3) or '', True)}</tr>"
              for m in ms]
    return '<table class="orc-cabecalho">\n' + "\n".join(linhas) + "\n</table>"


def cabecalhos_em_quadro(texto: str) -> str:
    """As linhas ORGAO/UNIDADE/FUNCAO/PROGRAMA/SUB-PROGRAMA/PROJETO/ATIVIDADE de cada quadro do sistema orçamentário
    viram um quadro com bordas logo acima da planilha (1ª coluna: rótulo e número; 2ª: descrição; 3ª: valor).
    Títulos soltos ("NATUREZA DA DESPESA") ficam como texto, na ordem."""
    saida = []
    for b in texto.split("\n\n"):
        if b.startswith(("**", "#", "!!!", "    ", "|", "<")):
            saida.append(b)
            continue
        linhas = [l.rstrip() for l in b.split("\n")]
        ms = [CAB.match(l.strip()) for l in linhas]
        if not any(ms):
            saida.append(b)
            continue
        grupo, texto_solto = [], []
        for l, m in zip(linhas, ms):
            if m:
                if texto_solto:
                    saida.append("  \n".join(texto_solto)); texto_solto = []
                grupo.append(m)
            elif l.strip():
                if grupo:
                    saida.append(quadro(grupo)); grupo = []
                texto_solto.append(l.strip())
        if grupo:
            saida.append(quadro(grupo))
        if texto_solto:
            saida.append("  \n".join(texto_solto))
    # quadros seguidos (ORGAO/UNIDADE e FUNCAO/.../PROJETO) formam um quadro só
    return "\n\n".join(saida).replace('</table>\n\n<table class="orc-cabecalho">\n', "")


# --- linhas do topo de cada página do sistema orçamentário num quadro com bordas ---
#   | ORC072 - SISTEMA ORCAMENTARIO         | QUADRO DE DETALHAMENTO DE DESPESAS |         |
#   | PREFEITURA MUNICIPAL DE BATAYPORA - M | EXERCICIO DE 1995                  | PAG.: 1 |
SIS = re.compile(r"^(ORC\d{3}\s*-\s*SISTEMA ORCAMENTARIO)\s*(.*?)\s*(\([^)]*\)|PAG\.:\s*\d+)?$")
PREF = re.compile(r"^(PREFEITURA MUNICIPAL DE BATAYPORA(?:\s*-\s*MS?\b)?)\s*(.*?)\s*((?:EMISSAO\s*:\s*\S+\s*)?PAG\.:\s*\d+)?$")


def topo_em_quadro(texto: str) -> str:
    saida = []
    for b in texto.split("\n\n"):
        linhas = [l.strip() for l in b.split("\n") if l.strip()]
        m1 = SIS.match(linhas[0]) if linhas else None
        m2 = PREF.match(linhas[1]) if m1 and len(linhas) > 1 else None
        if not (m1 and m2):
            saida.append(b)
            continue
        def td(x, direita=False):
            x = re.sub(r"\s+", " ", x or "").strip()
            return f'<td style="text-align:right">{x}</td>' if direita else f"<td>{x}</td>"
        saida.append('<table class="orc-topo">\n'
                     f"<tr>{td(m1.group(1))}{td(m1.group(2))}{td(m1.group(3), True)}</tr>\n"
                     f"<tr>{td(m2.group(1))}{td(m2.group(2))}{td(m2.group(3), True)}</tr>\n</table>")
        if linhas[2:]:  # títulos que vêm depois ("RECEITA", "RESUMO GERAL DA DESPESA") ficam como texto
            saida.append("  \n".join(linhas[2:]))
    return "\n\n".join(saida)


if __name__ == "__main__":
    for a in sys.argv[1:]:
        p = Path(a); t = p.read_text()
        novo = topo_em_quadro(cabecalhos_em_quadro(t))
        if novo != t:
            p.write_text(novo); print("cabeçalhos em quadro:", p.name)
