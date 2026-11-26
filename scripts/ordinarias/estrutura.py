"""Marca as divisões das leis escaneadas como títulos Markdown, no formato da Lei 271/1993, para o indice.py montar
o índice da página:
  "Capítulo I DO SISTEMA DE PESSOAL"   →  ## CAPÍTULO I — DO SISTEMA DE PESSOAL { .centro }
  (o mesmo para TÍTULO, SEÇÃO e SUBSEÇÃO; com TÍTULO na lei, os capítulos descem um nível)
  parágrafo de anexo ("ANEXO II" + linhas do título em maiúsculas, ou "ANEXO IV (ANEXO III DA LEI 271/93)")
                                        →  ## ANEXO II — TÍTULO DO ANEXO { .centro }
Só pega parágrafos inteiros (a divisão sozinha numa linha, como no rascunho do Docling). Pode rodar de novo.
Uso: python scripts/ordinarias/estrutura.py página.md ...
"""
import re
import sys
from pathlib import Path

DIV = re.compile(r"^(CAP[IÍ]TULO|T[IÍ]TULO|SE[CÇ][AÃ]O|SUBSE[CÇ][AÃ]O)\s+([IVXL]+|[ÚU]NIC[OA])\b\.?\s*[-–—:]?\s*(.*)$", re.I)
ANEXO = re.compile(r"^(ANEXO\s+[IVXL]+|QUADRO\s+\d+)\b(.*)$")
NOME = {"CAPITULO": "CAPÍTULO", "TITULO": "TÍTULO", "SECAO": "SEÇÃO", "SUBSECAO": "SUBSEÇÃO"}


def sem_acento(s):
    return s.upper().translate(str.maketrans("ÍÇÃ", "ICA"))


def maiusculas(s):
    letras = [c for c in s if c.isalpha()]
    return letras and sum(c.isupper() for c in letras) >= 0.8 * len(letras)


def aplicar(pagina: Path) -> int:
    texto = pagina.read_text()
    blocos = texto.split("\n\n")
    tem_titulo = any(DIV.match(b) and sem_acento(DIV.match(b).group(1)) == "TITULO" for b in blocos if "\n" not in b)
    base = {"TITULO": 2, "CAPITULO": 3 if tem_titulo else 2, "SECAO": 4 if tem_titulo else 3,
            "SUBSECAO": 5 if tem_titulo else 4}
    n = 0
    for i, b in enumerate(blocos):
        if b.startswith(("#", "|", "!!!", "    ", "**", ">", "{", "---")):
            continue
        m = DIV.match(b) if "\n" not in b else None
        if m:
            tipo = sem_acento(m.group(1))
            assunto = m.group(3).strip().rstrip(".").upper()
            rot = f"{NOME[tipo]} {m.group(2).upper()}"
            blocos[i] = f"{'#' * base[tipo]} {rot}{' — ' + assunto if assunto else ''} {{ .centro }}"
            n += 1
            continue
        linhas = [l.strip() for l in b.split("\n") if l.strip()]
        if not linhas or len(linhas) > 6 or any(len(l) > 120 for l in linhas) or not all(maiusculas(l) for l in linhas):
            continue
        k = next((j for j, l in enumerate(linhas) if re.match(r"^ANEXO\s+[IVXL]+\b", l)), None)
        if k is None and len(linhas) == 1 and re.match(r"^QUADRO\s+\d+\b", linhas[0]):
            k = 0  # quadro sem anexo ("QUADRO 2 QUADRO DE PESSOAL ... MAGISTÉRIO")
        if k is None:
            continue
        m = ANEXO.match(linhas[k])
        resto = [m.group(2).strip()] if m.group(2).strip() else []
        resto += [l for j, l in enumerate(linhas) if j != k]
        cauda = " — ".join(resto)
        cauda = (" " + cauda) if cauda.startswith("(") else (" — " + cauda) if cauda else ""
        blocos[i] = f"## {m.group(1)}{cauda} {{ .centro }}"
        n += 1
    if n:
        pagina.write_text("\n\n".join(blocos))
    return n


def main():
    for a in sys.argv[1:]:
        p = Path(a)
        if p.name != "index.md" and (k := aplicar(p)):
            print(f"{p.name}: {k} divisões")


if __name__ == "__main__":
    main()
