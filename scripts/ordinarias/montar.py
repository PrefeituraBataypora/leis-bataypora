"""Monta as páginas das leis ordinárias de um ano em docs/leis-ordinarias/ANO (a partir do conv.py),
põe as notas nas páginas de anos anteriores alteradas por elas e atualiza fontes, índices e menu.

Uso: ANO=2006 LDIR=<pasta de trabalho do ano> python montar.py
Depois: python scripts/indice.py docs/leis-ordinarias/ANO/lei-*.md   (índice nas leis com títulos e capítulos)
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import conv  # noqa: E402

ANO, SCR, nfc = conv.ANO, conv.SCR, conv.nfc
RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"
sys.path.insert(0, str(RAIZ / "scripts"))
import converter  # noqa: E402

PASTA = f"leis-ordinarias/{ANO}"
NOME = f"Leis Ordinárias de {ANO}"
LEGIS = "https://bataypora.ms.gov.br/cidadao/legislacao-municipal"
# último número de lei de cada ano já no site (para achar o ano de uma lei pelo número)
ULTIMA = {"2001": 541, "2002": 577, "2003": 621, "2004": 639, "2005": 683, "2006": 721}


def ano_da(num):
    return next(a for a, u in sorted(ULTIMA.items()) if int(num) <= u)


def L(num, alvo="", de=None):
    """Link relativo para outra lei ordinária, a partir de uma página do ano `de` (padrão: o ano montado)."""
    ano, de = ano_da(num), de or ANO
    return ("" if ano == de else f"../{ano}/") + f"lei-{num}-{ano}.md{alvo}"


ESTATUTO = "../../estatuto-servidores/lc-003-2001.md"
POSTURAS = "../../codigo-posturas/lc-008-2003.md"


def config_2005():
    # PDFs da pasta da rede publicados junto: (lei, ano) -> (arquivo, observação[, rótulo])
    PDFS = {}

    # notas no topo das páginas deste ano
    NOTAS = {
        "644": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                '“REVOGADA PELI LEI COMP. 013.2013”, isto é, revogada pela Lei Complementar nº 013/2013, que ainda não está neste site.'],
    }

    # citações que viram links nas páginas deste ano: lei -> [(trecho, novo)]
    LINKS = {
        "640": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "641": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "645": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "647": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "678": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "682": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "644": [("a Lei nº 510/2001", f"a [Lei nº 510/2001]({L('510')})")],
        "656": [("a Lei nº 626/2004", f"a [Lei nº 626/2004]({L('626')})")],
        "662": [("a Lei Municipal de nº 513/2001", f"a [Lei Municipal de nº 513/2001]({L('513')})"),
                ("da Lei nº 513/2001", f"da [Lei nº 513/2001]({L('513', '#art-2')})")],
        "665": [("Lei Municipal nº 651/2005", f"[Lei Municipal nº 651/2005]({L('651')})")],
        "668": [("O artigo 4º da Lei nº 494/2001", f"O [artigo 4º da Lei nº 494/2001]({L('494', '#art-4')})")],
    }

    # notas em páginas de anos anteriores: (lei alterada, onde, nota); onde = "topo" ou a linha depois da qual entra
    EXTERNAS = [
        ("510", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 7º da Lei nº 644/2005]({L("644", "#art-7", "2001")}), de 16 de março de 2005.'),
        ("513", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pela '
         f'[Lei nº 662/2005]({L("662", "", "2001")}), de 8 de julho de 2005, porque o beneficiário não cumpriu o que a doação exigia.'),
        ("626", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 10 da Lei nº 656/2005]({L("656", "#art-10", "2004")}), de 1º de junho de 2005, que criou de novo o Projeto Alimentar de Inclusão.'),
        ("494", "topo", '!!! info "Alterada pela Lei nº 668/2005"\n    O [art. 4º](#art-4) recebeu nova redação pela '
         f'[Lei nº 668/2005]({L("668", "", "2001")}), de 30 de agosto de 2005.'),
        ("494", "{ #art-4 }", '!!! info "Redação dada pela Lei nº 668/2005"\n    Nova redação deste artigo, dada pelo '
         f'[art. 1º da Lei nº 668/2005]({L("668", "#art-1", "2001")}):\n\n'
         '    Art 4º- O Conselho Municipal do Meio Ambiente C.M.M.A será composto por representantes a saber:\n\n'
         '    a) 08 (oito) do Poder Público;\n\n    b) 08 (oito) da Sociedade Civil.\n\n'
         '    § 1º A Presidência do Conselho Municipal do Meio Ambiente C.M.M.A caberá ao Coordenador Municipal que tiver a '
         'Coordenação Executiva da Política Municipal do Meio Ambiente.\n\n'
         '    § 2º O exercício das funções dos membros do Conselho Municipal do Meio Ambiente C.M.M.A será gratuito, por '
         'tratar-se de relevante interesse público.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def redacao(num, lei, artigo):
    """Nota com a nova redação citada pela lei `num` deste ano (a citação “Art ...” do texto convertido)."""
    texto = conv.converter(num)["texto"]
    cit = next(b for b in texto.split("\n\n") if b.startswith("> “"))
    paragrafos = [l[2:] for l in cit.split("\n") if l.startswith("> ")]
    return (f'!!! info "Redação dada pela Lei nº {num}/{ANO}"\n    Nova redação deste artigo, dada pelo '
            f"[art. {artigo} da Lei nº {num}/{ANO}]({lei}):\n\n" + "\n\n".join("    " + x for x in paragrafos))


def config_2006():
    PDFS = {("719", "2006"): ("lei-719-2006.pdf", "", "versão em PDF do documento, impressa do Word")}
    NOTAS = {}
    revogadas = "529/2001, 530/2001, 547/2002, 583/2003 e 623/2004"
    LINKS = {
        "685": [("Lei Municipal nº 680/2005", f"[Lei Municipal nº 680/2005]({L('680')})")],
        "686": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "704": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "694": [("Lei nº 496/2001", f"[Lei nº 496/2001]({L('496')})")],
        "696": [("Lei nº 502/2001", f"[Lei nº 502/2001]({L('502')})"), ("Lei 502/2001", f"[Lei 502/2001]({L('502')})"),
                (revogadas, ", ".join(f"[{n}]({L(n[:3])})" for n in revogadas[:-11].split(", ")) + f" e [623/2004]({L('623')})")],
        "698": [("Lei Municipal nº 685/2006", f"[Lei Municipal nº 685/2006]({L('685')})")],
        "714": [("Lei nº 490/2001", f"[Lei nº 490/2001]({L('490', '#art-3')})")],
        "715": [("Lei nº 497/2001", f"[Lei nº 497/2001]({L('497', '#art-1')})")],
        "717": [("Lei nº 709/2006", f"[Lei nº 709/2006]({L('709', '#art-1')})")],
    }
    EXTERNAS = [
        ("502", "topo", '!!! info "Anexos substituídos pela Lei nº 696/2006"\n    As tabelas dos Anexos I, II e III passaram a '
         f'vigorar conforme os anexos da [Lei nº 696/2006]({L("696", "", "2001")}), de 10 de maio de 2006, que também revogou '
         f'as Leis nº {revogadas}.'),
        ("496", "topo", '!!! info "Prazo prorrogado pela Lei nº 694/2006"\n    O prazo da permuta de comodato do [art. 1º](#art-1) '
         f'foi prorrogado por mais 6 (seis) anos pela [Lei nº 694/2006]({L("694", "", "2001")}), de 24 de abril de 2006.'),
        ("490", "topo", '!!! info "Alterada pela Lei nº 714/2006"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 714/2006]({L("714", "", "2001")}), de 22 de novembro de 2006.'),
        ("490", "{ #art-3 }", redacao("714", L("714", "#art-1", "2001"), "1º")),
        ("497", "topo", '!!! info "Alterada pela Lei nº 715/2006"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 715/2006]({L("715", "", "2001")}), de 22 de novembro de 2006.'),
        ("497", "{ #art-1 }", redacao("715", L("715", "#art-1", "2001"), "1º")),
        ("685", "topo", '!!! info "Alterada pela Lei nº 698/2006"\n    As autorizações, determinações e benefícios concedidos '
         'por esta lei à Usina Cristal Açúcar e Álcool Ltda foram transferidos para a Usina Laguna – Álcool e Açúcar Ltda pela '
         f'[Lei nº 698/2006]({L("698")}), de 17 de maio de 2006.'),
        ("709", "topo", '!!! info "Alterada pela Lei nº 717/2006"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 717/2006]({L("717")}), de 6 de dezembro de 2006.'),
        ("709", "{ #art-1 }", redacao("717", L("717", "#art-1"), "1º")),
    ]
    for n, ano in [("529", "2001"), ("530", "2001"), ("547", "2002"), ("583", "2003"), ("623", "2004")]:
        EXTERNAS.append((n, "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
                         f'[art. 6º da Lei nº 696/2006]({L("696", "#art-6", ano)}), de 10 de maio de 2006.'))
    return PDFS, NOTAS, LINKS, EXTERNAS


PDFS, NOTAS, LINKS, EXTERNAS = {"2005": config_2005, "2006": config_2006}[ANO]()


def titulo_nota(nota):
    return nota.split("\n", 1)[0]


def inserir_externa(num, onde, nota):
    pagina = DOCS / "leis-ordinarias" / ano_da(num) / f"lei-{num}-{ano_da(num)}.md"
    texto = pagina.read_text()
    corpo = nota.split("\n", 1)[1]
    if corpo in texto:
        return  # já inserida
    if onde == "topo":
        i = texto.index("\nBaixar: ")
        texto = texto[:i] + "\n" + nota + "\n" + texto[i:]
    else:
        assert texto.count(onde) == 1, (num, onde)
        texto = texto.replace(onde, onde + "\n\n" + nota)
    pagina.write_text(re.sub(r"\n{3,}", "\n\n", texto))
    print("nota em", pagina.relative_to(DOCS), "|", titulo_nota(nota))


def fonte_doc(num):
    nomes = sorted(nfc(f.name) for f in (SCR / "orig").iterdir())
    if f"LEI Nº {num}.{ANO}.doc" in nomes:
        return f"LEI Nº {num}.{ANO}.doc"
    # arquivos com sufixo no nome (ex.: "LEI Nº 680.2005-PPA.doc"), sem contar as cópias -A4
    return next(n for n in nomes if n.startswith(f"LEI Nº {num}.{ANO}-") and "-A4" not in n)


def main():
    nums = sorted(m.group(1) for f in (SCR / "out").iterdir() if (m := re.match(rf"lei-(\d+)-{ANO}\.md", f.name)))
    (DOCS / PASTA).mkdir(parents=True, exist_ok=True)
    fontes_novas = []
    for num in nums:
        r = conv.converter(num)
        texto = r["texto"]
        for a, b in LINKS.get(num, []):
            assert a in texto, (num, a)
            texto = texto.replace(a, b)
        titulo, slug, doc = f"Lei nº {num}/{ANO}", f"lei-{num}-{ANO}", fonte_doc(num)
        if (num, ANO) in PDFS:
            arq, obs, *rot = PDFS[(num, ANO)]
            rot = rot[0] if rot else "cópia assinada e escaneada"
            extracao = "documento .doc da prefeitura, conferido com a " + ("cópia assinada" if "assinada" in rot else "versão em PDF")
            aviso = (f'Transcrito do arquivo .doc da prefeitura, conferido com a [{rot}](../../assets/{slug}/{arq}){obs}, '
                     f'e **ainda em revisão**. Esta lei não está publicada na [página de legislação da prefeitura]({LEGIS}).')
        else:
            extracao = "documento .doc da prefeitura"
            aviso = ('Transcrito do arquivo .doc da prefeitura e **ainda em revisão**. Esta lei não está publicada na '
                     f'[página de legislação da prefeitura]({LEGIS}); por isso não há PDF para conferir.')
        cab = ["---", f'title: "{titulo}"', f"data: {r['data']}", f"ementa: {converter.yaml_str(r['ementa'])}",
               f'extracao: "{extracao}"', f"fonte_doc: {converter.yaml_str(doc + ' (arquivo da prefeitura)')}",
               "revisao: pendente", "hide:", "  - toc", "---", "", f"# {titulo}", "", f"> {r['ementa']}", "",
               f'!!! warning "Texto em revisão"\n    {aviso}', ""]
        for n in NOTAS.get(num, []):
            cab += [n, ""]
        cab += [converter.botoes_download(f"{PASTA}/{slug}.md"), ""]
        (DOCS / PASTA / f"{slug}.md").write_text("\n".join(cab) + "\n" + texto.rstrip() + "\n")
        fontes_novas.append({
            "origem": "doc", "titulo": titulo, "titulo_detectado": titulo, "url": None, "pdf_local": None,
            "fonte_doc": doc + " (arquivo da prefeitura)", "categoria": PASTA, "categoria_nome": NOME,
            "pagina_origem": None, "arquivo": f"{PASTA}/{slug}.md", "ementa": r["ementa"], "data": r["data"],
            "extracao": "doc"})
    for (num, ano), (arq, *_) in PDFS.items():
        if ano == ANO:
            destino = DOCS / "assets" / f"lei-{num}-{ano}"
            destino.mkdir(parents=True, exist_ok=True)
            pdf = next(f for f in (SCR / "orig").iterdir() if f.suffix.lower() == ".pdf" and f" {num}." in nfc(f.name))
            shutil.copy(pdf, destino / arq)
    for num, onde, nota in EXTERNAS:
        inserir_externa(num, onde, nota)
    arq = RAIZ / "data" / "fontes.json"
    fontes = [f for f in json.loads(arq.read_text()) if f["categoria"] != PASTA] + fontes_novas
    arq.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n")
    converter.gerar_indice(PASTA, NOME, fontes_novas)
    converter.gerar_indice_grupo("leis-ordinarias", fontes)
    converter.gerar_nav(fontes)
    print(ANO, len(fontes_novas), "leis")


if __name__ == "__main__":
    main()
