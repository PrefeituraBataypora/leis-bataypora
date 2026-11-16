"""Gera as páginas das 34 Leis Complementares que faltavam no site, a partir dos .doc da pasta da prefeitura.

Pasta de trabalho (LCDIR, padrão ~/Documents/leis-bataypora-fontes/leis-complementares):
  orig_raw/  os arquivos da pasta da prefeitura, com o nome original
  docx/, md2/  os .doc convertidos (soffice -> docx; pandoc com as mesmas opções das leis ordinárias, --wrap=none),
               com o nome "LEI COMP 0NN.AAAA"

O texto passa pelo mesmo conversor das leis ordinárias (scripts/ordinarias/conv.py), que formata artigos,
parágrafos, incisos, títulos, tabelas e assinaturas e tira CPF e RG. A LC 065/2024 não tem .doc legível e vem
transcrita do PDF digitalizado (LC_065_TEXTO). Nas leis alteradas por estas LCs entra uma nota no topo, avisando
que as mudanças ainda não estão incorporadas ao texto.

Uso: python montar_lcs_novas.py ; depois: python indice.py (índice das páginas com títulos e capítulos)
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "ordinarias"))
import converter  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
FONTES_PATH = RAIZ / "data" / "fontes.json"
LCDIR = Path(os.environ.get("LCDIR", Path.home() / "Documents/leis-bataypora-fontes/leis-complementares"))
os.environ.setdefault("LDIR", str(LCDIR))
import conv  # noqa: E402

LEGIS = "https://bataypora.ms.gov.br/cidadao/legislacao-municipal"

CATEGORIAS = {
    "estatuto-servidores": (
        "Estatuto dos Servidores (LC 003/2001)",
        [76, 80],
    ),
    "plano-cargos": (
        "Plano de Cargos e Carreiras (LC 020/2012)",
        [67, 73, 79],
    ),
    "plano-cargos-magisterio": (
        "Plano de Cargos do Magistério (LC 018/2011)",
        [6, 9, 14, 16, 56, 61, 66, 75, 77],
    ),
    "codigo-tributario": (
        "Código Tributário Municipal",
        [7, 11, 15, 30, 46, 49, 51, 52, 54, 58, 62, 69, 74, 78],
    ),
    "estrutura-administrativa": (
        "Estrutura Administrativa",
        [63, 81],
    ),
    "leis-complementares": (
        "Leis Complementares",
        [40, 41, 43, 65],
    ),
}

NUM_TO_CAT: dict[int, tuple[str, str]] = {}
for cat_slug, (cat_nome, nums) in CATEGORIAS.items():
    for n in nums:
        NUM_TO_CAT[n] = (cat_slug, cat_nome)

NOTAS_ANULACAO = {
    77: (
        '!!! warning "Anulação de publicação"\n'
        "    Há registro de anulação de publicação referente a esta Lei Complementar "
        "no Diário Oficial (Edição nº 4070, de 10 de abril de 2026, páginas 68 e 69)."
    ),
    78: (
        '!!! warning "Anulação de publicação"\n'
        "    Há registro de anulação de publicação referente a esta Lei Complementar "
        "no Diário Oficial (Edição nº 4093, de 15 de maio de 2026, páginas 69 a 74)."
    ),
}

# revogação indicada só no nome do arquivo da pasta da prefeitura (como nas leis ordinárias)
REVOGACAO_ARQUIVO = {
    6: "REVOGADA LEI COMP. 018.2011", 9: "REVOGADA LEI COMP. 022.2013",
    14: "REVOGAÇÃO TACITA LEI COMP. 018.2011", 16: "REVOGADA LEI COMP. 018.2011",
}

# leis alteradas por estas LCs (alvo -> [número da LC que altera]); a nota avisa que o texto do alvo não foi atualizado
ALTERACOES = {
    "codigo-tributario/lc-001-1991.md": [74],
    "estatuto-servidores/lc-003-2001.md": [76, 80],
    "plano-cargos-magisterio/lc-006-2002.md": [14, 16],
    "codigo-tributario/lc-007-2002.md": [11, 15],
    "plano-cargos-magisterio/lc-018-2011.md": [56, 61, 66, 75, 77],
    "plano-cargos/lc-020-2012.md": [79],
    "codigo-tributario/lc-051-2020.md": [52],
    "plano-cargos/lc-064-2024.md": [67],
}
EMENTA_065 = "Altera dispositivos na Lei Complementar nº 102/88, revoga a Lei nº 1.359/2024, e dá outras providências."

LC_065_TEXTO = """**Lei Complementar nº 65, de 30 de outubro de 2024.**
{ .centro }

> *"Altera dispositivos na [Lei Complementar nº 102/88](../leis-ordinarias/1988/lei-102-1988.md), revoga a [Lei nº 1.359/2024](../leis-ordinarias/2024/lei-1359-2024.md), e dá outras providências".*

O Exmo. Sr. Prefeito Municipal de Batayporã, Estado de Mato Grosso do Sul, Sr. Germino da Roz Silva, no uso e gozo de suas atribuições legais:

Faz saber que a CÂMARA MUNICIPAL aprovou o Projeto de Lei de autoria do Poder Legislativo, e eu sanciono e promulgo a seguinte Lei:

**Art. 1º** Altera-se a alínea "a" do artigo 47 da [Lei Complementar nº 102/88](../leis-ordinarias/1988/lei-102-1988.md), passando a vigorar com a seguinte redação:

> *"Art. 47º. Os afastamentos mínimos previstos serão:*
>
> *a) Afastamento frontal: 2,00m (dois metros); com possibilidade de edificação de varanda a partir de 1,50 (um metro e cinquenta centímetros) quando se tratar de edificação residencial.*
>
> *(...)"*

**Art. 2º** As regulamentações necessárias para o fiel cumprimento desta lei, poderão ser efetuadas por meio de Decreto do Poder Executivo Municipal.

**Art. 3º** As despesas decorrentes da aplicação da presente Lei correrão por conta de dotações próprias constantes no orçamento vigente do Legislativo Municipal.

**Art. 4º** Fica revogada a [Lei Municipal nº. 1.359 de 30 de março de 2024](../leis-ordinarias/2024/lei-1359-2024.md).

**Art. 5º** Esta Lei entrará em vigor na data de sua publicação.

Câmara Municipal de Batayporã/MS, 30 de outubro de 2024.

VANDERLEY RODRIGUES PEDROSO
{ .centro }

Vice-Presidente
{ .centro }
"""


def arquivo_original(num: int) -> str:
    nomes = sorted(f.name for f in (LCDIR / "orig_raw").iterdir() if re.match(rf"LEI COMP\.? ?0*{num}\.", f.name))
    bons = [n for n in nomes if not re.search(r"(?i)-A4|EXTRATO|C[óo]pia|COMPILAD|REDUZIDA|PAPEL|ANULAÇÃO", n)]
    return next((n for n in bons if n.lower().endswith(".doc")), bons[0] if bons else nomes[0])


def data_br(data: str) -> str:
    a, m, d = data.split("-")
    meses = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()
    return f"{'1º' if d == '01' else int(d)} de {meses[int(m) - 1]} de {a}"


def inserir_nota(alvo: Path, nota: str):
    texto = alvo.read_text()
    if nota.split("\n", 1)[1] in texto:
        return  # já inserida
    i = texto.index("\nBaixar: ")
    alvo.write_text(re.sub(r"\n{3,}", "\n\n", texto[:i] + "\n" + nota + "\n" + texto[i:]))


def main() -> None:
    fontes: list[dict] = json.loads(FONTES_PATH.read_text(encoding="utf-8"))
    md_files = sorted((LCDIR / "md2").glob("LEI COMP *.md"))
    assert len(md_files) == 34, f"Esperado 34 arquivos em {LCDIR / 'md2'}, encontrado {len(md_files)}"
    novas, paginas = [], {}
    for md_path in md_files:
        m = re.match(r"LEI COMP (\d+)\.(\d{4})\.md$", md_path.name)
        num, ano = int(m.group(1)), m.group(2)
        cat_slug, cat_nome = NUM_TO_CAT[num]
        arquivo = f"{cat_slug}/lc-{num:03d}-{ano}.md"
        fonte_doc = arquivo_original(num)
        if num == 65:
            corpo, data, ementa = LC_065_TEXTO, "2024-10-30", EMENTA_065
            extracao = "PDF digitalizado da prefeitura (transcrição)"
            aviso = ("Transcrito do PDF digitalizado da prefeitura, porque o .doc não tem o texto legível, e **ainda em "
                     f"revisão**. Esta lei não está publicada na [página de legislação da prefeitura]({LEGIS}).")
        else:
            conv.ANO = ano
            r = conv.converter(str(num), complementar=True)
            corpo, data, ementa = r["texto"], r["data"], r["ementa"]
            extracao = "documento .doc da prefeitura"
            aviso = ("Transcrito do arquivo .doc da prefeitura e **ainda em revisão**. Esta lei não está publicada na "
                     f"[página de legislação da prefeitura]({LEGIS}); por isso não há PDF para conferir.")
        titulo = f"Lei Complementar nº {num:03d}/{ano}"
        partes = ["---", f"title: {converter.yaml_str(titulo)}", f"data: {data}", f"ementa: {converter.yaml_str(ementa)}",
                  f"extracao: {converter.yaml_str(extracao)}",
                  f"fonte_doc: {converter.yaml_str(fonte_doc + ' (arquivo da prefeitura)')}", "revisao: pendente",
                  "hide:", "  - toc", "---", "", f"# {titulo}", "", f"> {ementa}", "",
                  f'!!! warning "Texto em revisão"\n    {aviso}']
        if num in NOTAS_ANULACAO:
            partes += ["", NOTAS_ANULACAO[num]]
        if num in REVOGACAO_ARQUIVO:
            partes += ["", '!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no '
                       f"nome “{REVOGACAO_ARQUIVO[num]}”, isto é, revogada pela Lei Complementar nº "
                       f"{REVOGACAO_ARQUIVO[num].split('COMP. ')[1].replace('.', '/')}."]
        partes += ["", converter.botoes_download(arquivo), "", corpo.rstrip(), ""]
        destino = DOCS / arquivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("\n".join(partes), encoding="utf-8")
        paginas[num] = (arquivo, titulo, data)
        novas.append({
            "titulo": f"LEI COMPLEMENTAR {num:03d}-{ano}", "titulo_link": f"LEI COMPLEMENTAR {num:03d}-{ano}",
            "categoria": cat_slug, "categoria_nome": cat_nome, "arquivo": arquivo, "titulo_detectado": titulo,
            "ementa": ementa, "data": data, "extracao": "doc" if num != 65 else "PDF",
            "fonte_doc": fonte_doc + " (arquivo da prefeitura)",
        })
        print(f"OK {arquivo} ({data})")

    for alvo, lcs in ALTERACOES.items():
        for n in lcs:
            arquivo, titulo, data = paginas[n]
            link = os.path.relpath(DOCS / arquivo, (DOCS / alvo).parent)
            inserir_nota(DOCS / alvo, f'!!! info "Alterada pela {titulo}"\n    Esta lei foi alterada pela '
                                      f"[{titulo}]({link}), de {data_br(data)}. As mudanças ainda não estão "
                                      "incorporadas ao texto abaixo.")

    feitas = {f["arquivo"] for f in novas}
    fontes = [f for f in fontes if f["arquivo"] not in feitas] + novas
    FONTES_PATH.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for cat_slug, (cat_nome, _) in CATEGORIAS.items():
        converter.gerar_indice(cat_slug, cat_nome, [f for f in fontes if f["categoria"] == cat_slug and not f.get("ignorar")])
    converter.gerar_nav(fontes)
    print(f"Concluído: {len(novas)} leis complementares.")


if __name__ == "__main__":
    main()
