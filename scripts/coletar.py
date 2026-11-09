"""Coleta os links de PDF das categorias de legislação do site da prefeitura.

Gera data/fontes.json e baixa os PDFs para .cache-leis/pdfs/ (fora do git).

Uso: python scripts/coletar.py
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://bataypora.ms.gov.br/cidadao/legislacao-municipal/"

# Categorias do protótipo: slug no site -> (pasta em docs/, nome exibido)
CATEGORIAS = {
    "lei-organica-do-municipio-de-bataypora": ("lei-organica", "Lei Orgânica"),
    "003-e-suas-alteracoes": ("estatuto-servidores", "Estatuto dos Servidores (LC 003/2001)"),
    "020-e-suas-alteracoes": ("plano-cargos", "Plano de Cargos e Carreiras (LC 020/2012)"),
    "codigo-tributario-municipal": ("codigo-tributario", "Código Tributário Municipal"),
    "codigo-de-posturas-municipal": ("codigo-posturas", "Código de Posturas Municipal"),
    "controladoria-geral": ("controladoria-geral", "Controladoria Geral"),
}

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / ".cache-leis" / "pdfs"
SAIDA = RAIZ / "data" / "fontes.json"

sessao = requests.Session()
sessao.headers["User-Agent"] = "leis-bataypora/0.1 (+https://github.com)"


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto.replace("lei-complementar", "lc").replace("lei-comp", "lc")


def links_da_categoria(slug: str) -> list[dict]:
    html = sessao.get(BASE + slug, timeout=60).text
    sopa = BeautifulSoup(html, "html.parser")
    vistos, itens = set(), []
    for a in sopa.select("a[href]"):
        url = urljoin(BASE, a["href"])
        if not url.lower().endswith(".pdf") or url in vistos:
            continue
        vistos.add(url)
        itens.append({
            "titulo": " ".join(a.get_text().split()),
            "titulo_link": a.get("title", "").strip(),
            "url": url,
        })
    return itens


def baixar(url: str) -> Path:
    destino = CACHE / url.rsplit("/", 1)[-1]
    if not destino.exists():
        r = sessao.get(url, timeout=300)
        r.raise_for_status()
        destino.write_bytes(r.content)
    return destino


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    # Mantém o que o converter.py anotou (nome final do arquivo e hash do texto gerado),
    # para ele continuar reconhecendo as páginas revisadas à mão
    lista_anterior = json.loads(SAIDA.read_text()) if SAIDA.exists() else []
    anteriores = {f["url"]: f for f in lista_anterior if f.get("url")}
    fontes = []
    for slug, (pasta, nome) in CATEGORIAS.items():
        usados = set()
        for item in links_da_categoria(slug):
            pdf = baixar(item["url"])
            arquivo = slugify(item["titulo"])
            while arquivo in usados:
                arquivo += "-b"
            usados.add(arquivo)
            fontes.append({
                **item,
                "categoria": pasta,
                "categoria_nome": nome,
                "pagina_origem": BASE + slug,
                "arquivo": f"{pasta}/{arquivo}.md",
                "pdf_local": pdf.name,
                "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "tamanho_bytes": pdf.stat().st_size,
                **{k: v for k, v in anteriores.get(item["url"], {}).items()
                   if k in ("arquivo", "hash_gerado", "ignorar")},
            })
            print(f"{pasta}: {item['titulo']} ({pdf.stat().st_size // 1024} KB)")
    # Leis acrescentadas a partir do .doc (não estão no site) não somem a cada coleta
    # (elas não têm url, então vêm da lista anterior inteira, não do dicionário por url)
    # e as leis adicionadas à mão a partir de um link de PDF que não está nas categorias do site
    fontes += [f for f in lista_anterior if f.get("origem") in ("doc", "manual")]
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(fontes)} PDFs em {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
