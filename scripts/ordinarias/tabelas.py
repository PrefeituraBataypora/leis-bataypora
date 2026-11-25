"""Tabelas das leis escaneadas: CSV, conferência automática dos números e geração do Markdown.

As tabelas lidas pelo Docling viram CSV (rascunhos/lei-N-AAAA/t-NN.csv). A revisão corrige células do CSV, sem
reescrever a tabela, e o Markdown é gerado a partir dele. Antes de pedir conferência na imagem, os números são
checados aqui:
  - total da linha = soma das colunas numéricas anteriores (quando a última coluna se chama TOTAL ou quando a regra
    vale para a maioria das linhas);
  - linha TOTAL = soma das linhas de cima, coluna a coluna;
  - coluna em progressão (escala de referências): cada valor mantém a mesma razão do anterior;
  - percentual × base = valor (representação de 30% a 55% etc.), quando há coluna de %.
Só as linhas que falham vão para recorte; tabela sem números para conferir vai inteira.
"""
import csv
import re
import statistics
from pathlib import Path

NUM = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?(?![\d])|(?<![\d.,])\d+,\d{2}(?![\d])|(?<![\d.,])\d{5,}(?![\d.,])")


def valor(c: str):
    """'1.168.175.844' → 1168175844; '41.036,40' → 41036.40; texto → None."""
    c = c.replace("CR$", "").replace("Cr$", "").strip(" -.")
    m = NUM.fullmatch(c) or re.fullmatch(r"\d+", c)
    if not m:
        return None
    inteiro, _, dec = c.partition(",")
    return int(inteiro.replace(".", "")) + (int(dec) / 10 ** len(dec) if dec else 0)


def espalhar(linha: list[str]) -> list[str]:
    """Célula com vários números e vizinhas vazias ('78.963.744 1.067.534.400 1.168.175.844' + '' + ''): redistribui."""
    linha = list(linha)
    for i, c in enumerate(linha):
        nums = NUM.findall(c)
        if len(nums) < 2 or NUM.sub("", c).strip(" .-CR$"):
            continue
        k = len(nums)
        antes = 0
        while i - antes - 1 >= 0 and not linha[i - antes - 1].strip():
            antes += 1
        depois = 0
        while i + depois + 1 < len(linha) and not linha[i + depois + 1].strip():
            depois += 1
        if antes + depois + 1 >= k:
            ini = i - min(antes, k - 1)  # prefere ocupar as vazias da esquerda (o Docling junta no fim)
            for j in range(ini, i + depois + 1):
                linha[j] = ""
            for j, num in enumerate(nums):
                linha[ini + j] = num
    return linha


def normalizar(linhas: list[list[str]]) -> list[list[str]]:
    """Espalha números grudados, junta colunas de texto repetidas e linhas só de texto que continuam a de baixo."""
    linhas = [espalhar(l) for l in linhas]
    if not linhas:
        return linhas
    n = max(len(l) for l in linhas)
    linhas = [l + [""] * (n - len(l)) for l in linhas]
    h = cabecalho(linhas)
    # coluna com o mesmo cabeçalho da anterior e sem números: o Docling partiu a célula de texto em duas
    j = 1
    while j < len(linhas[0]):
        mesmo = h and all(linhas[k][j].strip() == linhas[k][j - 1].strip() for k in range(h))
        sem_num = all(valor(l[j]) is None for l in linhas[h:])
        if mesmo and sem_num:
            for l in linhas[h:]:
                l[j - 1] = " ".join(dict.fromkeys(x for x in (l[j - 1].strip(), l[j].strip()) if x))
            for l in linhas:
                del l[j]
        else:
            j += 1
    # linha só de texto no meio dos dados: começo do rótulo da linha de baixo ("2-Outros Recur-" + "sos ...")
    saida, pendente = [], ""
    for i, l in enumerate(linhas):
        if i >= h and not _numericas(l) and i + 1 < len(linhas) and _numericas(linhas[i + 1]):
            pendente = " ".join(x.strip() for x in l if x.strip())
            continue
        if pendente:
            l = [(pendente + " " + l[0]).strip()] + l[1:]
            pendente = ""
        saida.append(l)
    return [[re.sub(r"(?<=[a-zà-ú])- (?=[a-zà-ú])", "", c) for c in l] for l in saida]


def ler_csv(p: Path) -> list[list[str]]:
    with open(p, newline="") as f:
        return [l for l in csv.reader(f)]


def gravar_csv(p: Path, linhas: list[list[str]]):
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(linhas)


def _numericas(linha):
    return [(j, valor(c)) for j, c in enumerate(linha) if valor(c) is not None]


def cabecalho(linhas):
    """Quantas linhas do topo são cabeçalho (sem números de valor)."""
    h = 0
    for l in linhas:
        if any(valor(c) is not None and not re.fullmatch(r"(19|20)\d\d", c.strip()) for c in l[1:]):
            break
        h += 1
    return h


def validar(linhas: list[list[str]]):
    """Lista de (índice da linha, motivo) que falham; None se não há regra numérica que se aplique."""
    h = cabecalho(linhas)
    dados = list(range(h, len(linhas)))
    falhas, regras = {}, 0
    eh_total = lambda l: bool(re.match(r"\s*\**\s*TOTA", l[0] if l else "", re.I))

    # 1) total da linha = soma das outras colunas numéricas
    cab_total = h and any(re.search(r"TOTAL", c, re.I) for c in linhas[h - 1][-1:])
    candidatas = [i for i in dados if len(_numericas(linhas[i])) >= 3]
    ok_linha = [i for i in candidatas if abs(sum(v for _, v in _numericas(linhas[i])[:-1]) - _numericas(linhas[i])[-1][1]) < 0.02]
    if candidatas and (cab_total or len(ok_linha) >= max(2, len(candidatas) * 0.6)):
        regras += 1
        for i in candidatas:
            if i not in ok_linha:
                falhas.setdefault(i, []).append("total da linha não fecha")

    # 2) linha TOTAL = soma das linhas acima (desde o cabeçalho ou o TOTAL anterior)
    ini = h
    for i in dados:
        if eh_total(linhas[i]):
            acima = [k for k in range(ini, i) if not eh_total(linhas[k])]
            for j, v in _numericas(linhas[i]):
                soma = sum((valor(linhas[k][j]) or 0) for k in acima if j < len(linhas[k]))
                if soma:
                    regras += 1
                    if abs(soma - v) >= 0.02:
                        falhas.setdefault(i, []).append(f"total da coluna {j + 1} não fecha (soma {soma:,.2f})")
            ini = i + 1

    # 3) coluna em progressão geométrica (escala de referências)
    ncol = max(len(l) for l in linhas) if linhas else 0
    for j in range(ncol):
        col = [(i, valor(linhas[i][j])) for i in dados if j < len(linhas[i]) and valor(linhas[i][j])]
        if len(col) < 8:
            continue
        razoes = [b / a for (_, a), (_, b) in zip(col, col[1:]) if a]
        med = statistics.median(razoes)
        if med <= 1.0 or sum(abs(r - med) < 0.002 for r in razoes) < len(razoes) * 0.7:
            continue
        regras += 1
        for k in range(1, len(col)):
            if abs(col[k][1] / col[k - 1][1] - med) >= 0.002:
                # o valor errado quebra a razão com o anterior e com o seguinte
                prox_ok = k + 1 < len(col) and abs(col[k + 1][1] / col[k][1] - med) < 0.002
                falhas.setdefault(col[k - 1 if prox_ok else k][0], []).append("valor fora da progressão da escala")

    # 4) percentual × base = valor (ex.: representação de 30% sobre o vencimento)
    for i in dados:
        l = linhas[i]
        for j, c in enumerate(l):
            if re.fullmatch(r"\d{1,2}", c.strip()) and 0 < j < len(l) - 1:
                base, v = valor(l[j - 1]), valor(l[j + 1])
                if base and v:
                    regras += 1
                    if abs(base * int(c) / 100 - v) >= 1.01:  # arredondado para cruzeiros inteiros
                        falhas.setdefault(i, []).append(f"{c}% de {l[j - 1]} não dá {l[j + 1]}")
    if not regras:
        return None
    return sorted((i, "; ".join(dict.fromkeys(m))) for i, m in falhas.items())


def markdown(linhas: list[list[str]]) -> str:
    if not linhas:
        return ""
    n = max(len(l) for l in linhas)
    linhas = [l + [""] * (n - len(l)) for l in linhas]
    h = max(1, cabecalho(linhas))
    cab = []
    for j in range(n):  # cabeçalho de várias linhas (célula mesclada repetida pelo Docling): junta sem repetir
        partes = list(dict.fromkeys(linhas[k][j].strip() for k in range(h) if linhas[k][j].strip()))
        cab.append(" ".join(partes))
    num = [j for j in range(n) if sum(valor(l[j]) is not None for l in linhas[h:]) > len(linhas[h:]) / 2]
    sep = "|" + "".join("---:|" if j in num else "---|" for j in range(n))
    corpo = ["| " + " | ".join(c.replace("|", "/") for c in l) + " |" for l in linhas[h:]]
    return "\n".join(["| " + " | ".join(cab) + " |", sep] + corpo)
