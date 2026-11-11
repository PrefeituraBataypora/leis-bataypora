"""Confere a saída do conv.py com o texto do .doc: numeração dos artigos, palavras que faltam e marcação que sobrou.

Uso: ANO=2005 LDIR=<pasta> python check.py [-v]
"""
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ANO = os.environ.get("ANO", "2005")
SCR = Path(os.environ.get("LDIR", "."))
fs = {unicodedata.normalize("NFC", f.name): f for f in (SCR / "txt").iterdir()}


def palavras(s):
    s = re.sub(r"<[^>]+>", " ", s.replace("\\", ""))
    return Counter(w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+", s))


for f in sorted((SCR / "out").iterdir()):
    n = f.name.split("-")[1]
    t = f.read_text()
    arts = [int(x) for x in re.findall(r"\{ #art-(\d+)", t)]
    a = palavras(fs[f"LEI Nº {n}.{ANO}.txt"].read_text(encoding="utf-8-sig"))
    b = palavras(re.sub(r"\{[^}]*\}", "", t))
    falta, sobra = a - b, b - a
    prob = []
    if arts != list(range(1, len(arts) + 1)):
        prob.append(f"arts {arts}")
    if sum(falta.values()):
        prob.append(f"faltam {sum(falta.values())}: {list(falta.items())[:10]}")
    if sum(sobra.values()) and "-v" in sys.argv:
        prob.append(f"sobram {sum(sobra.values())}: {list(sobra.items())[:10]}")
    for l in t.split("\n"):
        if l.startswith("#") and "{" not in l:
            prob.append("título: " + l[:60])
        if l.startswith(">"):
            prob.append("citação: " + l[:60])
        if l.count("**") % 2 and not l.startswith("|"):
            prob.append("negrito: " + l[:70])
        if re.match(r"^\s*\d+\.\s", l):
            prob.append("lista num: " + l[:60])
    if prob:
        print("##", n)
        for p in prob[:12]:
            print("  ", p)
