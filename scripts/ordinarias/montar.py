"""Monta as páginas das leis ordinárias de um ano em docs/leis-ordinarias/ANO (a partir do conv.py),
põe as notas nas páginas de anos anteriores alteradas por elas e atualiza fontes, índices e menu.

Uso: ANO=2006 LDIR=<pasta de trabalho do ano> python montar.py
Depois: python scripts/indice.py docs/leis-ordinarias/ANO/lei-*.md   (índice nas leis com títulos e capítulos)
        python scripts/revogados.py                                  (risca os artigos revogados)
"""
import json
import re
import shutil
import sys
import zipfile
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
ULTIMA = {"2001": 541, "2002": 577, "2003": 621, "2004": 639, "2005": 683, "2006": 721, "2007": 750, "2008": 794, "2009": 834, "2010": 890, "2011": 946, "2012": 999, "2013": 1050, "2014": 1086, "2015": 1115, "2016": 1137, "2017": 1169, "2018": 1193, "2019": 1224, "2020": 1247, "2021": 1268, "2022": 1311, "2023": 1348, "2024": 1371, "2025": 1419, "2026": 1456}


def ano_da(num):
    return next(a for a, u in sorted(ULTIMA.items()) if int(num) <= u)


# leis ordinárias que já estão no site em outra seção (convertidas antes, do PDF da página da prefeitura):
# não ganham página repetida em leis-ordinarias/ANO; o índice do ano e os links apontam para a página que já existe
OUTRA_SECAO = {"1131": "controladoria-geral/lei-1131-2016.md"}


def L(num, alvo="", de=None):
    """Link relativo para outra lei ordinária, a partir de uma página do ano `de` (padrão: o ano montado)."""
    ano, de = ano_da(num), de or ANO
    if num in OUTRA_SECAO:
        return f"../../{OUTRA_SECAO[num]}{alvo}"
    return ("" if ano == de else f"../{ano}/") + f"lei-{num}-{ano}.md{alvo}"


ESTATUTO = "../../estatuto-servidores/lc-003-2001.md"
POSTURAS = "../../codigo-posturas/lc-008-2003.md"
TRIBUTARIO = "../../codigo-tributario/lc-001-1991.md"


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


def redacao(num, lei, artigo, idx=0):
    """Nota com a nova redação citada pela lei `num` deste ano (a citação “Art ...” do texto convertido)."""
    bs = conv.converter(num)["texto"].split("\n\n")
    inicio = [i for i, b in enumerate(bs) if b.startswith("> “")][idx]
    # a citação pode vir partida em volta de tabelas (que ficam fora do ">"): segue até o fecha-aspas
    paragrafos = []
    for b in bs[inicio:]:
        if b.lstrip().startswith(("<table", "|")):
            paragrafos.append(f"*(tabela: ver o texto da Lei nº {num}/{ANO})*")
            continue
        if not b.startswith("> "):
            break
        paragrafos += [l[2:] for l in b.split("\n") if l.startswith("> ")]
        if re.search(r"(?:[”\"]\.?|\(NR\))\s*$", paragrafos[-1]):
            break
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


def config_2007():
    PDFS = {("740", "2007"): ("lei-740-2007.pdf", "", "versão em PDF do documento, impressa do Word")}
    NOTAS = {
        "749": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                '“REVOGADA PELA LEI N. 1090.2015”, isto é, revogada pela Lei nº 1.090/2015, que ainda não está neste site.'],
    }
    LINKS = {
        "724": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "726": [("Lei Municipal nº 680/2005", f"[Lei Municipal nº 680/2005]({L('680')})")],
        "727": [("Lei Municipal nº 684/2006", f"[Lei Municipal nº 684/2006]({L('684')})"),
                ("Lei Municipal nº 680/2005", f"[Lei Municipal nº 680/2005]({L('680')})")],
        "728": [("Lei Municipal nº 680/2005", f"[Lei Municipal nº 680/2005]({L('680')})")],
        "729": [("Lei nº 502/2001", f"[Lei nº 502/2001]({L('502')})"),
                ("Lei 502/2001", f"[Lei 502/2001]({L('502')})"),
                ("Lei nº 696/2006", f"[Lei nº 696/2006]({L('696')})")],
        "731": [("Lei nº 728/2007", f"[Lei nº 728/2007]({L('728')})")],
        "732": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei Municipal nº 729/2007", f"[Lei Municipal nº 729/2007]({L('729')})"),
                ("Lei Complementar nº 03/2001", f"[Lei Complementar nº 03/2001]({ESTATUTO})")],
        "733": [("Lei nº 687/2006", f"[Lei nº 687/2006]({L('687', '#anexo-unico')})")],
        "739": [("Lei nº 725/2007", f"[Lei nº 725/2007]({L('725', '#art-2')})")],
        "744": [("Lei nº 696/2006", f"[Lei nº 696/2006]({L('696')})")],
    }
    EXTERNAS = [
        ("502", "topo", '!!! info "Anexos substituídos pela Lei nº 729/2007"\n    As tabelas dos Anexos I, II e III passaram a '
         f'vigorar conforme os anexos da [Lei nº 729/2007]({L("729", "", "2001")}), de 2 de maio de 2007, que também revogou a '
         f'[Lei nº 696/2006]({L("696", "", "2001")}).'),
        ("696", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 12 da Lei nº 729/2007]({L("729", "#art-12", "2006")}), de 2 de maio de 2007.'),
        ("696", "topo", '!!! info "Alterada pela Lei nº 744/2007"\n    A [Lei nº 744/2007]'
         f'({L("744", "", "2006")}), de 3 de outubro de 2007, transformou um cargo de Auxiliar de Serviços Gerais em Atendente de Creche '
         'nas Tabelas 4 e 8 do [Anexo I](#anexo-i).'),
        ("687", "topo", '!!! info "Alterada pela Lei nº 733/2007"\n    O [Anexo Único](#anexo-unico) foi alterado pela '
         f'[Lei nº 733/2007]({L("733", "", "2006")}), de 4 de julho de 2007, que excluiu 1 cargo de Assistente Especializado (TCT-2) '
         'e criou 1 cargo de Assistente Técnico I (TCT-3).'),
        ("725", "topo", '!!! info "Alterada pela Lei nº 739/2007"\n    O [art. 2º](#art-2) recebeu nova redação pela '
         f'[Lei nº 739/2007]({L("739")}), de 21 de agosto de 2007.'),
        ("725", "{ #art-2 }", redacao("739", L("739", "#art-1"), "1º")),
        ("729", "topo", '!!! info "Alterada pela Lei nº 732/2007"\n    A '
         f'[Lei nº 732/2007]({L("732")}), de 12 de junho de 2007, criou cargos nas Tabelas 1 e 4 do [Anexo I](#anexo-i).'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2008():
    PDFS = {}
    NOTAS = {
        "786": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                '“REVOGADA PELA LEI N. 1090.2015”, isto é, revogada pela Lei nº 1.090/2015, que ainda não está neste site.'],
    }
    LINKS = {
        "751": [("Lei nº 490/2001", f"[Lei nº 490/2001]({L('490', '#art-3')})"),
                ("Lei nº 714/2006", f"[Lei nº 714/2006]({L('714')})")],
        "752": [("Lei nº 689/2006", f"[Lei nº 689/2006]({L('689', '#art-1')})")],
        "753": [("Lei nº 688/2006", f"[Lei nº 688/2006]({L('688', '#art-2')})")],
        "756": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})")],
        "758": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})")],
        "760": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})")],
        "763": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "764": [("Lei Municipal nº 712/2006", f"[Lei Municipal nº 712/2006]({L('712')})"),
                ("Lei Municipal nº. 712/2006", f"[Lei Municipal nº. 712/2006]({L('712')})")],
        "765": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "776": [("Lei 684/2006", f"[Lei 684/2006]({L('684')})"),
                ("Lei Municipal de nº 684/2006", f"[Lei Municipal de nº 684/2006]({L('684')})")],
        "783": [("Lei Municipal nº 748/2007", f"[Lei Municipal nº 748/2007]({L('748')})"),
                ("Lei Municipal nº. 748/2007", f"[Lei Municipal nº. 748/2007]({L('748')})")],
        "786": [("os artigos 3º e 5º da Lei nº 749/2007", f"os artigos 3º e 5º da [Lei nº 749/2007]({L('749')})"),
                ("O artigo 3º da Lei nº 749/2007", f"O [artigo 3º da Lei nº 749/2007]({L('749', '#art-3')})"),
                ("O artigo 5º da Lei nº 749/2007", f"O [artigo 5º da Lei nº 749/2007]({L('749', '#art-5')})")],
        "790": [("Lei nº 603/2003", f"[Lei nº 603/2003]({L('603', '#art-1')})")],
        "792": [("Lei nº 502/2001", f"[Lei nº 502/2001]({L('502')})"),
                ("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729')})"),
                ("Lei nº 687/2006", f"[Lei nº 687/2006]({L('687')})"),
                ("Lei nº 733/2007", f"[Lei nº 733/2007]({L('733')})"),
                ("Lei nº 740/2007", f"[Lei nº 740/2007]({L('740')})"),
                ("638/2004, de 16/12/2004, 687/2006", f"[638/2004]({L('638')}), de 16/12/2004, [687/2006]({L('687')})")],
    }
    EXTERNAS = [
        ("490", "topo", '!!! info "Alterada pela Lei nº 751/2008"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 751/2008]({L("751", "", "2001")}), de 14 de fevereiro de 2008, que revogou a [Lei nº 714/2006]({L("714", "", "2001")}).'),
        ("490", "{ #art-3 }", redacao("751", L("751", "#art-1", "2001"), "1º")),
        ("714", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 751/2008]({L("751", "#art-2", "2006")}), de 14 de fevereiro de 2008.'),
        ("689", "topo", '!!! info "Alterada pela Lei nº 752/2008"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 752/2008]({L("752", "", "2006")}), de 14 de fevereiro de 2008.'),
        ("689", "{ #art-1 }", redacao("752", L("752", "#art-1", "2006"), "1º")),
        ("688", "topo", '!!! info "Alterada pela Lei nº 753/2008"\n    O [art. 2º](#art-2) recebeu nova redação pela '
         f'[Lei nº 753/2008]({L("753", "", "2006")}), de 14 de fevereiro de 2008.'),
        ("688", "{ #art-2 }", redacao("753", L("753", "#art-1", "2006"), "1º")),
        ("729", "topo", '!!! info "Alterada pelas Leis nº 756, 758 e 760/2008"\n    O [Anexo I](#anexo-i) foi alterado pela '
         f'[Lei nº 756/2008]({L("756", "", "2007")}), de 12 de março de 2008 (Tabelas 4 e 6), pela '
         f'[Lei nº 758/2008]({L("758", "", "2007")}), de 24 de março de 2008 (Tabela 1), e pela '
         f'[Lei nº 760/2008]({L("760", "", "2007")}), de 24 de março de 2008 (Tabela 5).'),
        ("712", "topo", '!!! info "Alterada pela Lei nº 764/2008"\n    A '
         f'[Lei nº 764/2008]({L("764", "", "2006")}), de 9 de abril de 2008, autorizou a permuta do imóvel doado por esta lei, '
         'mantendo as obrigações aqui previstas.'),
        ("684", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pela '
         f'[Lei nº 776/2008]({L("776", "", "2006")}), de 26 de junho de 2008.'),
        ("748", "topo", '!!! info "Alterada pela Lei nº 783/2008"\n    A '
         f'[Lei nº 783/2008]({L("783", "", "2007")}), de 20 de agosto de 2008, autorizou a permuta do imóvel doado por esta lei, '
         'mantendo as obrigações aqui previstas.'),
        ("749", "topo", '!!! info "Alterada pela Lei nº 786/2008"\n    Os [arts. 3º](#art-3) e [5º](#art-5) receberam nova redação pela '
         f'[Lei nº 786/2008]({L("786", "", "2007")}), de 9 de setembro de 2008.'),
        ("749", "{ #art-3 }", redacao("786", L("786", "#art-1", "2007"), "1º", 0)),
        ("749", "{ #art-5 }", redacao("786", L("786", "#art-2", "2007"), "2º", 1)),
        ("603", "topo", '!!! info "Alterada pela Lei nº 790/2008"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 790/2008]({L("790", "", "2003")}), de 19 de novembro de 2008.'),
        ("603", "{ #art-1 }", redacao("790", L("790", "#art-1", "2003"), "1º")),
        ("638", "topo", '!!! info "Cargos extintos pela Lei nº 792/2008"\n    O '
         f'[art. 36 da Lei nº 792/2008]({L("792", "#art-36", "2004")}), de 16 de dezembro de 2008, que reorganizou a estrutura '
         'administrativa da Prefeitura, extinguiu a partir de 31 de dezembro de 2008 todos os cargos criados por esta lei.'),
        ("687", "topo", '!!! info "Cargos extintos pela Lei nº 792/2008"\n    O '
         f'[art. 36 da Lei nº 792/2008]({L("792", "#art-36", "2006")}), de 16 de dezembro de 2008, extinguiu a partir de '
         '31 de dezembro de 2008 todos os cargos criados por esta lei.'),
        ("733", "topo", '!!! info "Cargos extintos pela Lei nº 792/2008"\n    O '
         f'[art. 36 da Lei nº 792/2008]({L("792", "#art-36", "2007")}), de 16 de dezembro de 2008, extinguiu a partir de '
         '31 de dezembro de 2008 todos os cargos criados por esta lei.'),
        ("740", "topo", '!!! info "Alterada pela Lei nº 792/2008"\n    Pelo '
         f'[art. 27 da Lei nº 792/2008]({L("792", "#art-27", "2007")}), de 16 de dezembro de 2008, a Coordenadoria Especial da '
         'Mulher (CEMU) passou a ser vinculada à Secretaria Municipal de Promoção Social e Trabalho.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2009():
    PDFS = {}
    NOTAS = {
        "812": ['!!! info "Alterada pela Lei nº 830/2009"\n    O [Anexo II](#anexo-ii) (Unidade Orçamentária 042 — Ensino Fundamental) '
                'foi alterado pela [Lei nº 830/2009](lei-830-2009.md), de 2 de dezembro de 2009.'],
        "818": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                '“REVOGADA PELA LEI 1089.2015”, isto é, revogada pela Lei nº 1.089/2015, que ainda não está neste site.'],
    }
    LINKS = {
        "796": [("Lei nº 712/2006", f"[Lei nº 712/2006]({L('712')})")],
        "801": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei Municipal nº 729/2007", f"[Lei Municipal nº 729/2007]({L('729')})"),
                ("Lei Complementar nº 03/2001", f"[Lei Complementar nº 03/2001]({ESTATUTO})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "802": [("alteração da Lei nº 792/2008", f"alteração da [Lei nº 792/2008]({L('792')})"),
                ("O inciso V do art. 3º da Lei nº 792/2008", f"O [inciso V do art. 3º da Lei nº 792/2008]({L('792', '#art-3')})"),
                ("Anexos nº - III (três) – Quadro Demonstrativo de Cargos Comissionados da Prefeitura Municipal de Batayporã-MS, e IV (quatro) – Quadro Demonstrativo de Distribuição de Cargos Comissionados da Lei nº 792/2008",
                 f"[Anexos nº - III (três)]({L('792', '#anexo-iii')}) – Quadro Demonstrativo de Cargos Comissionados da Prefeitura Municipal de Batayporã-MS, e [IV (quatro)]({L('792', '#anexo-iv')}) – Quadro Demonstrativo de Distribuição de Cargos Comissionados da [Lei nº 792/2008]({L('792')})"),
                ("ANEXO III DA LEI Nº 792/2008", f"ANEXO III DA [LEI Nº 792/2008]({L('792', '#anexo-iii')})"),
                ("ANEXO IV DA LEI Nº 792/2008", f"ANEXO IV DA [LEI Nº 792/2008]({L('792', '#anexo-iv')})")],
        "804": [("Lei nº 490/2001", f"[Lei nº 490/2001]({L('490', '#art-3')})"),
                ("Lei nº 751/2008", f"[Lei nº 751/2008]({L('751')})")],
        "805": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "807": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "808": [("Lei nº 691/2006", f"[Lei nº 691/2006]({L('691', '#art-1')})")],
        "812": [("– Lei nº 726/2007", f"– [Lei nº 726/2007]({L('726')})"),
                ("– Lei nº 719/2006", f"– [Lei nº 719/2006]({L('719')})"),
                ("– Lei nº 642/2005", f"– [Lei nº 642/2005]({L('642')})"),
                ("– Lei nº 494/01", f"– [Lei nº 494/01]({L('494')})"),
                ("– Lei nº 495/01", f"– [Lei nº 495/01]({L('495')})"),
                ("– Lei nº 749/2007", f"– [Lei nº 749/2007]({L('749')})")],
        "813": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "815": [("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                ("Lei nº 786/2008", f"[Lei nº 786/2008]({L('786')})"),
                ("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "820": [("Lei Complementar nº 01/91", f"[Lei Complementar nº 01/91]({TRIBUTARIO})")],
        "823": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei Municipal nº 729/2007", f"[Lei Municipal nº 729/2007]({L('729')})"),
                ("Lei Complementar nº 03/2001", f"[Lei Complementar nº 03/2001]({ESTATUTO})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "827": [("Lei nº 716/2006", f"[Lei nº 716/2006]({L('716')})")],
        "830": [("Anexo nº II, da Lei nº 812/2009", f"[Anexo nº II, da Lei nº 812/2009]({L('812', '#anexo-ii')})"),
                ("ANEXO II DA LEI Nº 812/2009", f"ANEXO II DA [LEI Nº 812/2009]({L('812', '#anexo-ii')})")],
        "831": [("Lei nº 689/2006", f"[Lei nº 689/2006]({L('689', '#art-1')})"),
                ("Lei nº 752/2008", f"[Lei nº 752/2008]({L('752')})")],
        "832": [("Lei nº 550/2002", f"[Lei nº 550/2002]({L('550')})")],
        "833": [("Lei Complementar Municipal nº 01/91", f"[Lei Complementar Municipal nº 01/91]({TRIBUTARIO})")],
        "834": [("Lei de Diretrizes Orçamentária nº 815/09", f"[Lei de Diretrizes Orçamentária nº 815/09]({L('815')})")],
    }
    EXTERNAS = [
        ("712", "topo", '!!! info "Área desafetada pela Lei nº 796/2009"\n    A área de 4.000 m² objeto da doação autorizada por '
         f'esta lei foi desafetada, passando a bem patrimonial disponível do Município, pela [Lei nº 796/2009]({L("796", "", "2006")}), '
         'de 13 de fevereiro de 2009.'),
        ("729", "topo", '!!! info "Alterada pelas Leis nº 801 e 823/2009"\n    O [Anexo I](#anexo-i) foi alterado pela '
         f'[Lei nº 801/2009]({L("801", "", "2007")}), de 27 de abril de 2009 (Tabelas 1, 2, 3, 5 e 6), e pela '
         f'[Lei nº 823/2009]({L("823", "", "2007")}), de 24 de setembro de 2009 (Tabela 1).'),
        ("792", "topo", '!!! info "Alterada pela Lei nº 802/2009"\n    O inciso V do [art. 3º](#art-3) recebeu nova redação e os '
         f'[Anexos III](#anexo-iii) e [IV](#anexo-iv) foram alterados pela [Lei nº 802/2009]({L("802", "", "2008")}), de 27 de abril de 2009.'),
        ("792", "V - Nível de Atuação Específica, voltado aos serviços de protocolo geral, ocupantes de Cargo em Comissão símbolo CC6-01;",
         '!!! info "Redação dada pela Lei nº 802/2009"\n    Nova redação deste inciso, dada pelo '
         f'[art. 1º da Lei nº 802/2009]({L("802", "#art-1", "2008")}):\n\n'
         '    V - Nível de Atuação Diversa, voltado aos serviços de estafeta, guardador, “office-boy”, segurança, e etc; ocupantes de Cargo em Comissão símbolo CC6-01;'),
        ("490", "topo", '!!! info "Alterada pela Lei nº 804/2009"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 804/2009]({L("804", "", "2001")}), de 29 de abril de 2009, que revogou a [Lei nº 751/2008]({L("751", "", "2001")}).'),
        ("490", "{ #art-3 }", redacao("804", L("804", "#art-1", "2001"), "1º")),
        ("751", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 804/2009]({L("804", "#art-2", "2008")}), de 29 de abril de 2009.'),
        ("691", "topo", '!!! info "Alterada pela Lei nº 808/2009"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 808/2009]({L("808", "", "2006")}), de 19 de maio de 2009.'),
        ("691", "{ #art-1 }", redacao("808", L("808", "#art-1", "2006"), "1º")),
        ("716", "topo", '!!! info "Alterada pela Lei nº 827/2009"\n    A '
         f'[Lei nº 827/2009]({L("827", "", "2006")}), de 27 de outubro de 2009, autorizou a permuta do imóvel doado por esta lei, '
         'mantendo as obrigações aqui previstas.'),
        ("689", "topo", '!!! info "Alterada pela Lei nº 831/2009"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 831/2009]({L("831", "", "2006")}), de 2 de dezembro de 2009, que revogou a [Lei nº 752/2008]({L("752", "", "2006")}).'),
        ("689", "{ #art-1 }", redacao("831", L("831", "#art-1", "2006"), "1º")),
        ("752", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 831/2009]({L("831", "#art-2", "2008")}), de 2 de dezembro de 2009.'),
        ("550", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 12 da Lei nº 832/2009]({L("832", "#art-12", "2002")}), de 9 de dezembro de 2009, que adotou o Diário Oficial dos '
         'Municípios do Estado do Mato Grosso do Sul como meio oficial de comunicação dos atos municipais.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2010():
    PDFS = {("845", "2010"): ("lei-845-2010.pdf", "")}
    NOTAS = {
        "864": ['!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
                f'[art. 36 da Lei nº 867/2010]({L("867", "#art-36")}), de 30 de julho de 2010, que reformulou a '
                'organização estrutural da Prefeitura.'],
    }
    LINKS = {
        "839": [("Lei nº 490/2001", f"[Lei nº 490/2001]({L('490', '#art-3')})"),
                ("Lei nº 804/2009", f"[Lei nº 804/2009]({L('804')})")],
        "848": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei Municipal nº 729/2007", f"[Lei Municipal nº 729/2007]({L('729')})"),
                ("Lei Complementar nº 03/2001", f"[Lei Complementar nº 03/2001]({ESTATUTO})"),
                ("Lei nº 792/2008", f"[Lei nº 792/2008]({L('792', '#anexo-iv')})"),
                ("Lei nº 802/2009", f"[Lei nº 802/2009]({L('802')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "850": [("O § 2º do art. 18 da Lei nº 719/2006", f"O § 2º do [art. 18 da Lei nº 719/2006]({L('719', '#art-18')})"),
                ("O Item VII do art. 22 da Lei nº 719/2006", f"O Item VII do [art. 22 da Lei nº 719/2006]({L('719', '#art-22')})")],
        "851": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "857": [("Lei nº 843/2010", f"[Lei nº 843/2010]({L('843')})")],
        "861": [("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                ("Lei nº 786/2008", f"[Lei nº 786/2008]({L('786')})"),
                ("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "864": [("Anexo IV da Lei nº 792/2008", f"[Anexo IV da Lei nº 792/2008]({L('792', '#anexo-iv')})"),
                ("Lei nº 802/2009", f"[Lei nº 802/2009]({L('802')})")],
        "867": [("Lei nº 502/2001", f"[Lei nº 502/2001]({L('502')})"),
                ("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729')})"),
                ("Lei nº 740/2007", f"[Lei nº 740/2007]({L('740')})"),
                ("Lei nº 792/2008, de 16 de dezembro de 2008, e 802/2009, de 27 de abril de 2009, e 864/2010",
                 f"[Lei nº 792/2008]({L('792')}), de 16 de dezembro de 2008, e [802/2009]({L('802')}), de 27 de abril de 2009, e [864/2010]({L('864')})")],
        "869": [("O artigo 6º da Lei nº 843/2010", f"O [artigo 6º da Lei nº 843/2010]({L('843', '#art-6')})")],
        "870": [("O artigo 6º da Lei nº 842/2010", f"O [artigo 6º da Lei nº 842/2010]({L('842', '#art-6')})")],
        "872": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "879": [("Lei nº 856/2010", f"[Lei nº 856/2010]({L('856')})")],
        "883": [("Anexo I, da Lei nº 729/2007", f"[Anexo I, da Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("de conformidade com a Lei nº 729/2007", f"de conformidade com a [Lei nº 729/2007]({L('729')})"),
                ("EM CURSO DE TRANSFORMAÇÃO**, da Lei nº 729/2007", f"EM CURSO DE TRANSFORMAÇÃO**, da [Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "884": [("O artigo 1º da Lei nº 879/2010", f"O [artigo 1º da Lei nº 879/2010]({L('879', '#art-1')})")],
        "887": [("O artigo 2º da Lei nº 709/2006", f"O [artigo 2º da Lei nº 709/2006]({L('709', '#art-2')})")],
        "889": [("Lei de Diretrizes Orçamentária nº 861/2010", f"[Lei de Diretrizes Orçamentária nº 861/2010]({L('861')})")],
    }
    EXTERNAS = [
        ("490", "topo", '!!! info "Alterada pela Lei nº 839/2010"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 839/2010]({L("839", "", "2001")}), de 23 de março de 2010, que revogou a [Lei nº 804/2009]({L("804", "", "2001")}).'),
        ("490", "{ #art-3 }", redacao("839", L("839", "#art-1", "2001"), "1º")),
        ("804", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 839/2010]({L("839", "#art-2", "2009")}), de 23 de março de 2010.'),
        ("719", "topo", '!!! info "Alterada pela Lei nº 850/2010"\n    O § 2º do [art. 18](#art-18) e o inciso VII do [art. 22](#art-22) '
         f'receberam nova redação pela [Lei nº 850/2010]({L("850", "", "2006")}), de 19 de maio de 2010.'),
        ("719", "{ #art-18 }", redacao("850", L("850", "#art-1", "2006"), "1º", 0)),
        ("719", "{ #art-22 }", redacao("850", L("850", "#art-2", "2006"), "2º", 1)),
        ("729", "topo", '!!! info "Alterada pelas Leis nº 848, 851, 872 e 883/2010"\n    O [Anexo I](#anexo-i) foi alterado pela '
         f'[Lei nº 848/2010]({L("848", "", "2007")}), de 12 de maio de 2010 (Tabelas 1, 2, 4, 5 e 6), pela '
         f'[Lei nº 851/2010]({L("851", "", "2007")}), de 19 de maio de 2010 (Tabela 1), pela '
         f'[Lei nº 872/2010]({L("872", "", "2007")}), de 17 de agosto de 2010 (Tabela 2), e pela '
         f'[Lei nº 883/2010]({L("883", "", "2007")}), de 23 de novembro de 2010 (Tabelas 1, 2 e 8).'),
        ("792", "topo", '!!! danger "Lei revogada"\n    Esta lei (após alterações no [Anexo IV](#anexo-iv) pelas Leis nº '
         f'[848/2010]({L("848", "", "2008")}), de 12 de maio de 2010, e [864/2010]({L("864", "", "2008")}), de 1º de julho de 2010) '
         f'foi revogada pelo [art. 36 da Lei nº 867/2010]({L("867", "#art-36", "2008")}), de 30 de julho de 2010, que reformulou a '
         'organização estrutural da Prefeitura.'),
        ("802", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 36 da Lei nº 867/2010]({L("867", "#art-36", "2009")}), de 30 de julho de 2010, que reformulou a '
         'organização estrutural da Prefeitura.'),
        ("842", "topo", '!!! info "Alterada pela Lei nº 870/2010"\n    O [art. 6º](#art-6) recebeu nova redação pela '
         f'[Lei nº 870/2010]({L("870")}), de 5 de agosto de 2010.'),
        ("842", "{ #art-6 }", redacao("870", L("870", "#art-1"), "1º")),
        ("843", "topo", '!!! info "Área desafetada pela Lei nº 857/2010 e alterada pela Lei nº 869/2010"\n    A área de 2.522,00 m² '
         f'doada por esta lei foi desafetada pela [Lei nº 857/2010]({L("857")}), de 15 de junho de 2010, e o [art. 6º](#art-6) '
         f'recebeu nova redação pela [Lei nº 869/2010]({L("869")}), de 5 de agosto de 2010.'),
        ("843", "{ #art-6 }", redacao("869", L("869", "#art-1"), "1º")),
        ("879", "topo", '!!! info "Alterada pela Lei nº 884/2010"\n    O [art. 1º](#art-1) foi acrescido de parágrafo único pela '
         f'[Lei nº 884/2010]({L("884")}), de 30 de novembro de 2010.'),
        ("879", "{ #art-1 }", redacao("884", L("884", "#art-1"), "1º")),
        ("709", "topo", '!!! info "Alterada pela Lei nº 887/2010"\n    O [art. 2º](#art-2) recebeu nova redação pela '
         f'[Lei nº 887/2010]({L("887", "", "2006")}), de 15 de dezembro de 2010.'),
        ("709", "{ #art-2 }", redacao("887", L("887", "#art-1", "2006"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2011():
    PDFS = {("904", "2011"): ("lei-904-2011.pdf", "")}
    NOTAS = {
        "900": ['!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
                f'[art. 5º da Lei nº 924/2011]({L("924", "#art-5")}), de 30 de agosto de 2011, que deu nova redação à matéria.'],
    }
    LINKS = {
        "897": [("artigo 4º da Lei nº 895/2011", f"[artigo 4º da Lei nº 895/2011]({L('895', '#art-4')})")],
        "901": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "904": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "905": [("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                ("Lei nº 786/2008", f"[Lei nº 786/2008]({L('786')})"),
                ("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "911": [("Lei nº 841/2010", f"[Lei nº 841/2010]({L('841')})")],
        "913": [("Lei nº 624/2004", f"[Lei nº 624/2004]({L('624')})")],
        "914": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("LEI Nº 729/2007", f"[LEI Nº 729/2007]({L('729', '#anexo-i')})")],
        "915": [("Inciso V, do art. 47 da Lei Complementar nº 018/2011",
                 "[Inciso V, do art. 47 da Lei Complementar nº 018/2011](../../plano-cargos-magisterio/lc-018-2011.md#art-47)")],
        "916": [("O art. 1º da Lei nº 817/2009", f"O [art. 1º da Lei nº 817/2009]({L('817', '#art-1')})")],
        "918": [("o artigo 2º da Lei Municipal nº 768/2008", f"o [artigo 2º da Lei Municipal nº 768/2008]({L('768', '#art-2')})")],
        "919": [("Lei Municipal N° 768/2008", f"[Lei Municipal N° 768/2008]({L('768')})")],
        "920": [("Anexo IV da Lei nº 867/2010", f"[Anexo IV da Lei nº 867/2010]({L('867', '#anexo-iv')})"),
                ("Anexo IV da Lei nº 867/2011", f"[Anexo IV da Lei nº 867/2011]({L('867', '#anexo-iv')})")],
        "924": [("Lei nº 900/2011", f"[Lei nº 900/2011]({L('900')})")],
        "925": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "926": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "929": [("Anexo I, da Lei nº 729/2007", f"[Anexo I, da Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("de conformidade com a Lei nº 729/2007", f"de conformidade com a [Lei nº 729/2007]({L('729')})"),
                ("EM CURSO DE TRANSFORMAÇÃO**, da Lei nº 729/2007", f"EM CURSO DE TRANSFORMAÇÃO**, da [Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("APOIO ADMINISTRATIVO,** da Lei nº 729/2007", f"APOIO ADMINISTRATIVO,** da [Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})")],
        "933": [("O art. 2º da Lei nº 492/2001", f"O [art. 2º da Lei nº 492/2001]({L('492', '#art-2')})")],
        "934": [("O artigo 1º da Lei nº 709/2006", f"O [artigo 1º da Lei nº 709/2006]({L('709', '#art-1')})"),
                ("O artigo 2º da Lei nº 709/2006", f"O [artigo 2º da Lei nº 709/2006]({L('709', '#art-2')})"),
                ("O Parágrafo Único do artigo 3º, da Lei nº 709/2006", f"O Parágrafo Único do [artigo 3º, da Lei nº 709/2006]({L('709', '#art-3')})"),
                ("a Lei nº 717/2006", f"a [Lei nº 717/2006]({L('717')})"),
                ("a Lei nº 887/2010", f"a [Lei nº 887/2010]({L('887')})")],
        "936": [("O artigo 4º da Lei nº 490/2001", f"O [artigo 4º da Lei nº 490/2001]({L('490', '#art-4')})")],
        "937": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})"),
                ("LEI Nº 729/2007", f"[LEI Nº 729/2007]({L('729', '#anexo-i')})")],
        "939": [("O art. 3º da Lei nº 860/2010", f"O [art. 3º da Lei nº 860/2010]({L('860', '#art-3')})")],
        "940": [("Lei de Diretrizes Orçamentária nº 905/2011", f"[Lei de Diretrizes Orçamentária nº 905/2011]({L('905')})")],
        "941": [("Item II do art. 2º da Lei Municipal nº 867/2010", f"Item II do [art. 2º da Lei Municipal nº 867/2010]({L('867', '#art-2')})")],
    }
    EXTERNAS = [
        ("895", "topo", '!!! info "Alterada pela Lei nº 897/2011"\n    O [art. 4º](#art-4) recebeu nova redação pela '
         f'[Lei nº 897/2011]({L("897")}), de 13 de abril de 2011.'),
        ("895", "{ #art-4 }", redacao("897", L("897", "#art-1"), "1º")),
        ("841", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 911/2011]({L("911", "#art-2", "2010")}), de 3 de agosto de 2011, que deu nova denominação ao loteamento.'),
        ("624", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 5º da Lei nº 913/2011]({L("913", "#art-5", "2004")}), de 9 de agosto de 2011.'),
        ("817", "topo", '!!! info "Alterada pela Lei nº 916/2011"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 916/2011]({L("916", "", "2009")}), de 17 de agosto de 2011.'),
        ("817", "{ #art-1 }", redacao("916", L("916", "#art-1", "2009"), "1º")),
        ("768", "topo", '!!! info "Alterada pela Lei nº 918/2011 e regulamentada pela Lei nº 919/2011"\n    O *caput* do [art. 2º](#art-2) '
         f'recebeu nova redação pela [Lei nº 918/2011]({L("918", "", "2008")}), de 24 de agosto de 2011 (que também instituiu as penalidades '
         f'do SIM), e as taxas do SIM foram instituídas pela [Lei nº 919/2011]({L("919", "", "2008")}), da mesma data.'),
        ("768", "{ #art-2 }", redacao("918", L("918", "#art-1", "2008"), "1º")),
        ("867", "topo", '!!! info "Alterada pela Lei nº 920/2011"\n    A '
         f'[Lei nº 920/2011]({L("920", "", "2010")}), de 24 de agosto de 2011, criou mais 3 (três) cargos em comissão de Assistente Técnico II '
         '(símbolo TCT-4-01) no [Anexo IV](#anexo-iv).'),
        ("729", "topo", '!!! info "Alterada pelas Leis nº 914, 929 e 937/2011"\n    O [Anexo I](#anexo-i) foi alterado pela '
         f'[Lei nº 914/2011]({L("914", "", "2007")}), de 9 de agosto de 2011 (Tabela 4), pela '
         f'[Lei nº 929/2011]({L("929", "", "2007")}), de 5 de outubro de 2011 (Tabelas 4 e 8), e pela '
         f'[Lei nº 937/2011]({L("937", "", "2007")}), de 1º de dezembro de 2011 (Tabela 3).'),
        ("492", "topo", '!!! info "Alterada pela Lei nº 933/2011"\n    O [art. 2º](#art-2) e suas Tabelas I e II receberam nova redação pela '
         f'[Lei nº 933/2011]({L("933", "", "2001")}), de 22 de novembro de 2011.'),
        ("492", "{ #art-2 }", '!!! info "Redação dada pela Lei nº 933/2011"\n    O *caput* deste artigo e as Tabelas I e II a seguir receberam '
         f'nova redação pelo [art. 1º da Lei nº 933/2011]({L("933", "#art-1", "2001")}), de 22 de novembro de 2011.'),
        ("709", "topo", '!!! info "Alterada pela Lei nº 934/2011"\n    Os [arts. 1º](#art-1) e [2º](#art-2) e o parágrafo único do [art. 3º](#art-3) '
         f'receberam nova redação pela [Lei nº 934/2011]({L("934", "", "2006")}), de 1º de dezembro de 2011, que revogou as Leis nº '
         f'[717/2006]({L("717", "", "2006")}) e [887/2010]({L("887", "", "2006")}).'),
        ("709", "{ #art-1 }", redacao("934", L("934", "#art-1", "2006"), "1º", 0)),
        ("709", "{ #art-2 }", redacao("934", L("934", "#art-2", "2006"), "2º", 1)),
        ("709", "Parágrafo único. Em casos de utilização estranha, definida neste artigo, o imóvel retornará ao domínio do município, sem nenhuma indenização.",
         redacao("934", L("934", "#art-3", "2006"), "3º", 2)),
        ("717", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 4º da Lei nº 934/2011]({L("934", "#art-4", "2006")}), de 1º de dezembro de 2011.'),
        ("887", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 4º da Lei nº 934/2011]({L("934", "#art-4", "2010")}), de 1º de dezembro de 2011.'),
        ("490", "topo", '!!! info "Alterada pela Lei nº 936/2011"\n    O [art. 4º](#art-4) recebeu nova redação pela '
         f'[Lei nº 936/2011]({L("936", "", "2001")}), de 1º de dezembro de 2011.'),
        ("490", "{ #art-4 }", redacao("936", L("936", "#art-1", "2001"), "1º")),
        ("860", "topo", '!!! info "Alterada pela Lei nº 939/2011"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 939/2011]({L("939", "", "2010")}), de 16 de dezembro de 2011.'),
        ("860", "{ #art-3 }", redacao("939", L("939", "#art-1", "2010"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2012():
    PDFS = {
        ("977", "2012"): ("lei-977-2012.pdf", ""),
        ("983", "2012"): ("lei-983-2012.pdf", ""),
        ("986", "2012"): ("lei-986-2012.pdf", ""),
        ("996", "2012"): ("lei-996-2012.pdf", ""),
    }
    NOTAS = {}
    LINKS = {
        "949": [("Art. 3º da Lei nº 490/2001", f"[Art. 3º da Lei nº 490/2001]({L('490', '#art-3')})"),
                ("O artigo 3º da Lei nº 490/2001", f"O [artigo 3º da Lei nº 490/2001]({L('490', '#art-3')})"),
                ("a Lei nº 839/2010", f"a [Lei nº 839/2010]({L('839')})")],
        "952": [("Art. 1º da Lei nº 689/2006", f"[Art. 1º da Lei nº 689/2006]({L('689', '#art-1')})"),
                ("O artigo 1º da Lei nº 689/2006", f"O [artigo 1º da Lei nº 689/2006]({L('689', '#art-1')})"),
                ("a Lei nº 831/2009", f"a [Lei nº 831/2009]({L('831')})")],
        "955": [("Lei nº 938/2011", f"[Lei nº 938/2011]({L('938')})")],
        "959": [("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729', '#anexo-i')})"),
                ("Lei nº 729/2009", f"[Lei nº 729/2009]({L('729')})"),
                ("LEI Nº 729/2007", f"[LEI Nº 729/2007]({L('729', '#anexo-i')})")],
        "964": [("Lei n° 772/2008", f"[Lei n° 772/2008]({L('772')})"),
                ("Lei nº 772/2008", f"[Lei nº 772/2008]({L('772')})")],
        "965": [("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                ("Lei nº 786/2008", f"[Lei nº 786/2008]({L('786')})"),
                ("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "992": [("art. 1º da Lei nº 970/2012", f"[art. 1º da Lei nº 970/2012]({L('970', '#art-3')})"),
                ("O artigo 1º da Lei nº 970/2012", f"O [artigo 1º da Lei nº 970/2012]({L('970', '#art-3')})")],
        "995": [("Lei de Diretrizes Orçamentária nº 965/2012", f"[Lei de Diretrizes Orçamentária nº 965/2012]({L('965')})")],
    }
    EXTERNAS = [
        ("490", "topo", '!!! info "Alterada pela Lei nº 949/2012"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 949/2012]({L("949", "", "2001")}), de 20 de janeiro de 2012, que revogou a [Lei nº 839/2010]({L("839", "", "2001")}).'),
        ("490", "{ #art-3 }", redacao("949", L("949", "#art-1", "2001"), "1º")),
        ("839", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 949/2012]({L("949", "#art-2", "2010")}), de 20 de janeiro de 2012.'),
        ("689", "topo", '!!! info "Alterada pela Lei nº 952/2012"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 952/2012]({L("952", "", "2006")}), de 6 de março de 2012, que revogou a [Lei nº 831/2009]({L("831", "", "2006")}).'),
        ("689", "{ #art-1 }", redacao("952", L("952", "#art-1", "2006"), "1º")),
        ("831", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 952/2012]({L("952", "#art-2", "2009")}), de 6 de março de 2012.'),
        ("938", "topo", '!!! info "Alterada pela Lei nº 955/2012"\n    Esta lei recebeu nova redação pela '
         f'[Lei nº 955/2012]({L("955", "", "2011")}), de 15 de março de 2012.'),
        ("729", "topo", '!!! info "Alterada pela Lei nº 959/2012"\n    O [Anexo I](#anexo-i) (Tabelas 1 e 2) foi alterado pela '
         f'[Lei nº 959/2012]({L("959", "", "2007")}), de 4 de abril de 2012.'),
        ("772", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 14 da Lei nº 964/2012]({L("964", "#art-14", "2008")}), de 29 de junho de 2012, que deu nova redação à matéria.'),
        ("970", "topo", '!!! info "Alterada pela Lei nº 992/2012"\n    O [art. 3º](#art-3) (referido na lei alteradora como art. 1º) '
         f'recebeu nova redação pela [Lei nº 992/2012]({L("992")}), de 28 de novembro de 2012.'),
        ("970", "{ #art-3 }", redacao("992", L("992", "#art-1"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2013():
    PDFS = {}
    NOTAS = {}
    LINKS = {
        "1000": [("Lei nº 941/2011", f"[Lei nº 941/2011]({L('941')})"),
                 ("Lei nº 847/2010", f"[Lei nº 847/2010]({L('847')})"),
                 ("LEI 847/2010", f"[LEI 847/2010]({L('847')})"),
                 ("Lei nº 502/2001", f"[Lei nº 502/2001]({L('502')})"),
                 ("Lei nº 729/2007", f"[Lei nº 729/2007]({L('729')})"),
                 ("Lei nº 648/2005", f"[Lei nº 648/2005]({L('648')})"),
                 ("Lei nº 740/2007", f"[Lei nº 740/2007]({L('740')})"),
                 ("Lei nº 867/2010", f"[Lei nº 867/2010]({L('867')})")],
        "1002": [("Art. 3º da Lei nº 490/2001", f"[Art. 3º da Lei nº 490/2001]({L('490', '#art-3')})"),
                 ("artigo 3º da Lei nº 490/2001", f"[artigo 3º da Lei nº 490/2001]({L('490', '#art-3')})"),
                 ("Lei nº 949/2012", f"[Lei nº 949/2012]({L('949')})")],
        "1003": [("Anexo I da Lei nº 502/2001", f"[Anexo I da Lei nº 502/2001]({L('502', '#anexo-i')})"),
                 ("ANEXO I DA LEI Nº 502/2001", f"[ANEXO I DA LEI Nº 502/2001]({L('502', '#anexo-i')})"),
                 ("Lei nº 782/2008", f"[Lei nº 782/2008]({L('782')})")],
        "1006": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "1007": [("Lei nº 719/2006", f"[Lei nº 719/2006]({L('719')})"),
                 ("719/2006", f"[719/2006]({L('719')})"),
                 ("850/2010", f"[850/2010]({L('850')})")],
        "1010": [("Lei Complementar n° 01/91", f"[Lei Complementar n° 01/91]({TRIBUTARIO})")],
        "1013": [("Lei nº 1000/2013", f"[Lei nº 1000/2013]({L('1000')})"),
                 ("LEI 847/2010", f"[LEI 847/2010]({L('847')})")],
        "1014": [("716/2006", f"[716/2006]({L('716')})"),
                 ("827/2009", f"[827/2009]({L('827')})")],
        "1016": [("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                 ("Lei nº 786/2008", f"[Lei nº 786/2008]({L('786')})"),
                 ("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "1017": [("Lei n° 1012/2013", f"[Lei n° 1012/2013]({L('1012')})")],
        "1018": [("Lei nº 501/2001", f"[Lei nº 501/2001]({L('501')})")],
        "1020": [("Lei Complementar nº 008/2003", f"[Lei Complementar nº 008/2003]({POSTURAS})")],
        "1021": [("Lei nº 1007/2013", f"[Lei nº 1007/2013]({L('1007', '#art-39')})")],
        "1022": [("Lei Complementar nº 003/2001", f"[Lei Complementar nº 003/2001]({ESTATUTO})")],
        "1023": [("Lei nº 1000/2013", f"[Lei nº 1000/2013]({L('1000')})")],
        "1025": [("Lei nº 993/2012", f"[Lei nº 993/2012]({L('993')})")],
        "1026": [("Lei nº 994/2012", f"[Lei nº 994/2012]({L('994')})")],
        "1030": [("Lei nº 642/2005", f"[Lei nº 642/2005]({L('642')})")],
        "1033": [("Lei nº 1028/2013", f"[Lei nº 1028/2013]({L('1028', '#art-2')})")],
        "1035": [("Lei nº 833/2009", f"[Lei nº 833/2009]({L('833')})")],
        "1039": [("Lei nº 727/2007", f"[Lei nº 727/2007]({L('727')})"),
                 ("Lei nº 719/2006", f"[Lei nº 719/2006]({L('719')})"),
                 ("Lei nº 749/2007", f"[Lei nº 749/2007]({L('749')})"),
                 ("Lei nº.1015/2013", f"[Lei nº.1015/2013]({L('1015')})"),
                 ("Lei n°-1015/2013", f"[Lei n°-1015/2013]({L('1015')})"),
                 ("Lei n°-809/2009", f"[Lei n°-809/2009]({L('809')})"),
                 ("Lei n°-1000/2013", f"[Lei n°-1000/2013]({L('1000')})"),
                 ("Lei Municipal nº 941/2011", f"[Lei Municipal nº 941/2011]({L('941')})"),
                 ("Lei Municipal n°-1000/2013", f"[Lei Municipal n°-1000/2013]({L('1000')})"),
                 ("Lei Municipal nº.490/2001", f"[Lei Municipal nº.490/2001]({L('490')})"),
                 ("Leo 908/2011", f"[Leo 908/2011]({L('908')})"),
                 ("Lei n°-791/2008", f"[Lei n°-791/2008]({L('791')})")],
        "1042": [("Lei Municipal nº 791/2008", f"[Lei Municipal nº 791/2008]({L('791')})")],
        "1044": [("Lei nº 908/2011", f"[Lei nº 908/2011]({L('908')})")],
        "1049": [("490/2001", f"[490/2001]({L('490')})"),
                 ("804/2009", f"[804/2009]({L('804')})"),
                 ("1002/2013", f"[1002/2013]({L('1002')})")],
        "1050": [("Lei de Diretrizes Orçamentária nº 1016/2013", f"[Lei de Diretrizes Orçamentária nº 1016/2013]({L('1016')})")],
    }
    EXTERNAS = [
        ("867", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 39 da Lei nº 1000/2013]({L("1000", "#art-39", "2010")}), de 16 de janeiro de 2013.'),
        ("740", "topo", '!!! info "Alterada pela Lei nº 1000/2013"\n    A Coordenadoria Especial da Mulher – CEMU passou a ser vinculada à Secretaria Municipal de Assistência Social pelo '
         f'[art. 30 da Lei nº 1000/2013]({L("1000", "#art-30", "2007")}), de 16 de janeiro de 2013.'),
        ("490", "topo", '!!! info "Alterada pela Lei nº 1002/2013"\n    O [art. 3º](#art-3) recebeu nova redação pela '
         f'[Lei nº 1002/2013]({L("1002", "", "2001")}), de 26 de fevereiro de 2013, que revogou a [Lei nº 949/2012]({L("949", "", "2001")}).'),
        ("490", "{ #art-3 }", redacao("1002", L("1002", "#art-1", "2001"), "1º")),
        ("949", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1002/2013]({L("1002", "#art-2", "2012")}), de 26 de fevereiro de 2013.'),
        ("502", "topo", '!!! info "Alterada pela Lei nº 1003/2013"\n    As Tabelas 1 e 4 do [Anexo I](#anexo-i) foram alteradas pelo '
         f'[art. 4º da Lei nº 1003/2013]({L("1003", "#art-4", "2001")}), de 6 de março de 2013.'),
        ("719", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 77 da Lei nº 1007/2013]({L("1007", "#art-77", "2006")}), de 9 de abril de 2013, que deu nova redação à matéria.'),
        ("850", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 77 da Lei nº 1007/2013]({L("1007", "#art-77", "2010")}), de 9 de abril de 2013.'),
        ("1000", "topo", '!!! info "Alterada pelas Leis nº 1013/2013 e nº 1023/2013"\n    Os Anexos I, III e IV foram alterados pela '
         f'[Lei nº 1013/2013]({L("1013")}), de 28 de maio de 2013, e foi criado cargo pela '
         f'[Lei nº 1023/2013]({L("1023")}), de 3 de setembro de 2013.'),
        ("716", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1014/2013]({L("1014", "#art-2", "2006")}), de 12 de junho de 2013.'),
        ("827", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1014/2013]({L("1014", "#art-2", "2009")}), de 12 de junho de 2013.'),
        ("1012", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 4º da Lei nº 1017/2013]({L("1017", "#art-4")}), de 11 de julho de 2013.'),
        ("501", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 12 da Lei nº 1018/2013]({L("1018", "#art-12", "2001")}), de 7 de agosto de 2013.'),
        ("1007", "topo", '!!! info "Alterada pela Lei nº 1021/2013"\n    O [art. 39](#art-39) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1021/2013]({L("1021")}), de 30 de agosto de 2013.'),
        ("1007", "{ #art-39 }", redacao("1021", L("1021", "#art-1"), "1º")),
        ("993", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 28 da Lei nº 1025/2013]({L("1025", "#art-28", "2012")}), de 11 de setembro de 2013.'),
        ("994", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 10 da Lei nº 1026/2013]({L("1026", "#art-10", "2012")}), de 11 de setembro de 2013.'),
        ("642", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 14 da Lei nº 1030/2013]({L("1030", "#art-14", "2005")}), de 25 de setembro de 2013.'),
        ("1028", "topo", '!!! info "Prazo prorrogado pela Lei nº 1033/2013"\n    O prazo do [art. 2º](#art-2) foi prorrogado para 20/12/2013 pela '
         f'[Lei nº 1033/2013]({L("1033")}), de 16 de outubro de 2013.'),
        ("833", "topo", '!!! info "Alterada pela Lei nº 1035/2013"\n    Diversos dispositivos desta lei foram alterados pela '
         f'[Lei nº 1035/2013]({L("1035", "", "2009")}), de 24 de outubro de 2013.'),
        ("490", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 5º da Lei nº 1049/2013]({L("1049", "#art-5", "2001")}), de 20 de dezembro de 2013.'),
        ("804", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 5º da Lei nº 1049/2013]({L("1049", "#art-5", "2009")}), de 20 de dezembro de 2013.'),
        ("1002", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 5º da Lei nº 1049/2013]({L("1049", "#art-5")}), de 20 de dezembro de 2013.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2014():
    PDFS = {}
    NOTAS = {
        "1061": ['!!! danger "Lei revogada"\n    Esta lei recebeu nova redação / foi revogada pela '
                 f'[Lei nº 1083/2014]({L("1083")}), de 11 de dezembro de 2014 (indicação também no nome do arquivo original da prefeitura).'],
        "1083": ['!!! info "Nova redação à Lei nº 1061/2014"\n    Esta lei dá nova redação à '
                 f'[Lei nº 1061/2014]({L("1061")}), de 8 de abril de 2014.'],
    }
    LINKS = {
        "1057": [("Lei nº 689/2006", f"[Lei nº 689/2006]({L('689')})")],
        "1068": [("Lei nº 1017/2013", f"[Lei nº 1017/2013]({L('1017')})")],
        "1069": [("Lei nº 1022/2013", f"[Lei nº 1022/2013]({L('1022')})")],
        "1070": [("Código Tributário Municipal", f"[Código Tributário Municipal]({TRIBUTARIO})")],
        "1072": [("Lei nº. 1022/2013", f"[Lei nº. 1022/2013]({L('1022')})")],
        "1079": [("Código Tributário Municipal", f"[Código Tributário Municipal]({TRIBUTARIO})")],
        "1080": [("Lei nº. 1039/2013", f"[Lei nº. 1039/2013]({L('1039')})")],
        "1082": [("Lei nº 837/2010", f"[Lei nº 837/2010]({L('837')})")],
        "1083": [("Lei nº 1061/2014", f"[Lei nº 1061/2014]({L('1061')})")],
    }
    EXTERNAS = [
        ("689", "topo", '!!! info "Alterada pela Lei nº 1057/2014"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 1057/2014]({L("1057", "", "2006")}), de 2 de abril de 2014.'),
        ("689", "{ #art-1 }", redacao("1057", L("1057", "#art-1", "2006"), "1º")),
        ("1017", "topo", '!!! info "Alterada pela Lei nº 1068/2014"\n    O [art. 1º](#art-1) recebeu nova redação pela '
         f'[Lei nº 1068/2014]({L("1068", "", "2013")}), de 1º de julho de 2014.'),
        ("1017", "{ #art-1 }", redacao("1068", L("1068", "#art-1", "2013"), "1º")),
        ("1022", "topo", '!!! info "Alterada pelas Leis nº 1069/2014 e nº 1072/2014"\n    O [art. 7º](#art-7) recebeu nova redação pela '
         f'[Lei nº 1069/2014]({L("1069", "", "2013")}), de 4 de julho de 2014, e o [art. 1º](#art-1) pela '
         f'[Lei nº 1072/2014]({L("1072", "", "2013")}), de 28 de agosto de 2014.'),
        ("1022", "{ #art-1 }", redacao("1072", L("1072", "#art-1", "2013"), "1º")),
        ("1022", "{ #art-7 }", redacao("1069", L("1069", "#art-1", "2013"), "1º")),
        ("1039", "topo", '!!! info "Alterada pela Lei nº 1080/2014"\n    O Anexo I foi alterado pela '
         f'[Lei nº 1080/2014]({L("1080", "", "2013")}), de 5 de novembro de 2014.'),
        ("837", "topo", '!!! info "Alterada pela Lei nº 1082/2014"\n    Esta lei recebeu nova redação pela '
         f'[Lei nº 1082/2014]({L("1082", "", "2010")}), de 11 de dezembro de 2014.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2015():
    PDFS = {
        ("1106", "2015"): ("lei-1106-2015.pdf", "", "cópia assinada e escaneada, com a publicação no Diário Oficial"),
    }
    NOTAS = {
        "1114": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                 '“REVOGAÇÃO TACITA LEI COMP. 40.2018”, isto é, revogação tácita pela Lei Complementar nº 40/2018, que ainda não está neste site.'],
    }
    LINKS = {
        "1089": [("Lei Municipal nº 818/2009", f"[Lei Municipal nº 818/2009]({L('818')})")],
        "1090": [("749/2007", f"[749/2007]({L('749')})"),
                 ("786/2008", f"[786/2008]({L('786')})")],
        "1091": [("Lei de nº 1017/2013", f"[Lei de nº 1017/2013]({L('1017')})"),
                 ("Lei nº 1049/2013", f"[Lei nº 1049/2013]({L('1049')})"),
                 ("Lei nº 1068/2014", f"[Lei nº 1068/2014]({L('1068')})")],
        "1092": [("Lei nº. 1083/2014", f"[Lei nº. 1083/2014]({L('1083', '#art-14')})")],
        "1093": [("Lei Municipal nº 762/2008", f"[Lei Municipal nº 762/2008]({L('762')})")],
        "1095": [("Lei nº. 1073/2014", f"[Lei nº. 1073/2014]({L('1073', '#art-3')})")],
        "1101": [("Lei nº 1039/2013", f"[Lei nº 1039/2013]({L('1039')})"),
                 ("Lei nº 1080/2014", f"[Lei nº 1080/2014]({L('1080')})")],
        "1103": [("Lei Municipal nº 1048/2013", f"[Lei Municipal nº 1048/2013]({L('1048')})")],
        "1107": [("Lei nº 882/2010", f"[Lei nº 882/2010]({L('882')})"),
                 ("Lei nº. 882/2010", f"[Lei nº. 882/2010]({L('882')})")],
        "1108": [("LEI Nº 1039/2013", f"[LEI Nº 1039/2013]({L('1039')})"),
                 ("LEI N° 1039/2013", f"[LEI N° 1039/2013]({L('1039')})")],
        "1114": [("Lei Municipal n. 1.083/2015", f"[Lei Municipal n. 1.083/2015]({L('1083')})")],
    }
    EXTERNAS = [
        ("818", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 1º da Lei nº 1089/2015]({L("1089", "#art-1", "2009")}), de 16 de março de 2015.'),
        ("749", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 10 da Lei nº 1090/2015]({L("1090", "#art-10", "2007")}), de 24 de março de 2015, que deu nova redação à matéria.'),
        ("786", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 10 da Lei nº 1090/2015]({L("1090", "#art-10", "2008")}), de 24 de março de 2015.'),
        ("1017", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 6º da Lei nº 1091/2015]({L("1091", "#art-6", "2013")}), de 7 de abril de 2015.'),
        ("1049", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 6º da Lei nº 1091/2015]({L("1091", "#art-6", "2013")}), de 7 de abril de 2015.'),
        ("1068", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 6º da Lei nº 1091/2015]({L("1091", "#art-6", "2014")}), de 7 de abril de 2015.'),
        ("1083", "topo", '!!! info "Alterada pela Lei nº 1092/2015"\n    O § 1º do [art. 14](#art-14) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1092/2015]({L("1092", "#art-1", "2014")}), de 7 de abril de 2015.'),
        ("1083", "{ #art-14 }", redacao("1092", L("1092", "#art-1", "2014"), "1º")),
        ("762", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 1º da Lei nº 1093/2015]({L("1093", "#art-1", "2008")}), de 7 de abril de 2015.'),
        ("1073", "topo", '!!! info "Alterada pela Lei nº 1095/2015"\n    O [art. 3º](#art-3) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1095/2015]({L("1095", "#art-1", "2014")}), de 5 de maio de 2015.'),
        ("1073", "{ #art-3 }", redacao("1095", L("1095", "#art-1", "2014"), "1º")),
        ("1039", "topo", '!!! info "Alterada pelas Leis nº 1101/2015 e nº 1108/2015"\n    O Anexo II foi alterado pela '
         f'[Lei nº 1101/2015]({L("1101", "", "2013")}), de 5 de agosto de 2015, e os Anexos I, II e a Relação Detalhada das Receitas e Despesas Planejadas foram alterados pela '
         f'[Lei nº 1108/2015]({L("1108", "", "2013")}), de 29 de outubro de 2015.'),
        ("1048", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 1º da Lei nº 1103/2015]({L("1103", "#art-1", "2013")}), de 20 de agosto de 2015.'),
        ("882", "topo", '!!! info "Parcialmente revogada pela Lei nº 1107/2015"\n    O [art. 2º](#art-2) e seu parágrafo único foram revogados pelo '
         f'[art. 1º da Lei nº 1107/2015]({L("1107", "#art-1", "2010")}), de 8 de outubro de 2015.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2016():
    PDFS = {}
    NOTAS = {}
    LINKS = {
        "1124": [("Lei nº 847/2010", f"[Lei nº 847/2010]({L('847')})")],
        "1130": [("Lei nº 1.039/2013", f"[Lei nº 1.039/2013]({L('1039')})"),
                 ("1.080/2014", f"[1.080/2014]({L('1080')})"),
                 ("1.101/2015", f"[1.101/2015]({L('1101')})")],
        "1131": [("Lei n. 1000/2013", f"[Lei n. 1000/2013]({L('1000', '#art-8')})"),
                 ("Lei nº 1000/2013", f"[Lei nº 1000/2013]({L('1000', '#art-8')})"),
                 ("Lei 941/2011", f"[Lei 941/2011]({L('941')})")],
        "1134": [("Lei nº 1.073/2014", f"[Lei nº 1.073/2014]({L('1073', '#art-3')})"),
                 ("Lei nº. 1073/2014", f"[Lei nº. 1073/2014]({L('1073', '#art-3')})")],
        "1137": [("Lei de Diretrizes Orçamentária nº 1126/2016", f"[Lei de Diretrizes Orçamentária nº 1126/2016]({L('1126')})")],
    }
    EXTERNAS = [
        ("847", "topo", '!!! info "Alterada pela Lei nº 1124/2016"\n    Extintos os 2 cargos de Coordenador de Assistência Social (Símbolo BY-CC PS1-03) criados por esta lei, conforme o '
         f'[art. 1º da Lei nº 1124/2016]({L("1124", "#art-1", "2010")}), de 20 de abril de 2016.'),
        ("1039", "topo", '!!! info "Alterada pela Lei nº 1130/2016"\n    O Anexo II foi alterado pela '
         f'[Lei nº 1130/2016]({L("1130", "", "2013")}), de 26 de agosto de 2016.'),
        ("1000", "topo", '!!! info "Alterada pela Lei nº 1131/2016"\n    O [art. 8º](#art-8) recebeu nova redação pelo '
         f'[art. 33 da Lei nº 1131/2016]({L("1131", "#art-33", "2013")}), de 13 de setembro de 2016.'),
        ("1000", "{ #art-8 }", redacao("1131", L("1131", "#art-33", "2013"), "33")),
        ("941", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 34 da Lei nº 1131/2016]({L("1131", "#art-34", "2011")}), de 13 de setembro de 2016.'),
        ("1073", "topo", '!!! info "Alterada pela Lei nº 1134/2016"\n    O [art. 3º](#art-3) recebeu nova redação pelo '
         f'[art. 2º da Lei nº 1134/2016]({L("1134", "#art-2", "2014")}), de 22 de novembro de 2016.'),
        ("1073", "{ #art-3 }", redacao("1134", L("1134", "#art-2", "2014"), "2º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2017():
    PDFS = {
        ("1169", "2017"): ("lei-1169-2017.pdf", "", "versão em PDF do documento, impressa do Word"),
    }
    NOTAS = {
        "1168": ['!!! info "Veto parcial"\n    O arquivo original da prefeitura traz a indicação “APROVADA COM VETO PARCIAL”.'],
    }
    LINKS = {
        "1138": [("Lei nº 1000/2013", f"[Lei nº 1000/2013]({L('1000')})"),
                 ("Lei nº 847/2010", f"[Lei nº 847/2010]({L('847')})"),
                 ("Lei nº 1.122/2016", f"[Lei nº 1.122/2016]({L('1122', '#art-6')})"),
                 ("LEI Nº 1000/2013", f"[LEI Nº 1000/2013]({L('1000')})")],
        "1147": [("Lei nº. 1.145/2017", f"[Lei nº. 1.145/2017]({L('1145', '#art-1')})")],
        "1152": [("Código Tributário Municipal", f"[Código Tributário Municipal]({TRIBUTARIO})")],
        "1161": [("Lei n. 1.061/14", f"[Lei n. 1.061/14]({L('1061', '#art-8')})")],
        "1162": [("Lei nº. 740/2007", f"[Lei nº. 740/2007]({L('740')})"),
                 ("Lei nº 770/2008", f"[Lei nº 770/2008]({L('770')})"),
                 ("Lei nº 809/2009", f"[Lei nº 809/2009]({L('809')})")],
        "1163": [("Lei nº 520/2001", f"[Lei nº 520/2001]({L('520')})"),
                 ("Lei nº 617/2003", f"[Lei nº 617/2003]({L('617')})")],
        "1164": [("Lei nº 709/2006", f"[Lei nº 709/2006]({L('709', '#art-2')})")],
        "1169": [("Lei nº 492/2001", f"[Lei nº 492/2001]({L('492')})"),
                 ("Lei nº. 933/2011", f"[Lei nº. 933/2011]({L('933')})")],
    }
    EXTERNAS = [
        ("1000", "topo", '!!! info "Alterada pela Lei nº 1.138/2017"\n    O [art. 3º](#art-3) e os Anexos I, III e IV foram alterados pela '
         f'[Lei nº 1.138/2017]({L("1138", "", "2013")}), de 13 de janeiro de 2017, que extinguiu e criou cargos em comissão.'),
        ("1000", "{ #art-3 }", redacao("1138", L("1138", "#art-4", "2013"), "4º")),
        ("847", "topo", '!!! info "Alterada pela Lei nº 1.138/2017"\n    Cargos do Departamento de Gerência de Programas Sociais foram extintos pelo '
         f'[art. 1º da Lei nº 1.138/2017]({L("1138", "#art-1", "2010")}), de 13 de janeiro de 2017.'),
        ("1122", "topo", '!!! info "Alterada pela Lei nº 1.138/2017"\n    O [art. 6º](#art-6) recebeu nova redação pelo '
         f'[art. 5º da Lei nº 1.138/2017]({L("1138", "#art-5", "2016")}), de 13 de janeiro de 2017.'),
        ("1122", "{ #art-6 }", redacao("1138", L("1138", "#art-5", "2016"), "5º")),
        ("1145", "topo", '!!! info "Alterada pela Lei nº 1.147/2017"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.147/2017]({L("1147", "#art-1", "2017")}), de 19 de abril de 2017.'),
        ("1145", "{ #art-1 }", redacao("1147", L("1147", "#art-1", "2017"), "1º")),
        ("740", "topo", '!!! info "Alterada pela Lei nº 1.162/2017"\n    Os [arts. 2º](#art-2) e [8º](#art-8) receberam nova redação pelo '
         f'[art. 13 da Lei nº 1.162/2017]({L("1162", "#art-13", "2007")}), de 24 de novembro de 2017.'),
        ("740", "{ #art-2 }", redacao("1162", L("1162", "#art-13", "2007"), "13")),
        ("740", "{ #art-8 }", redacao("1162", L("1162", "#art-13", "2007"), "13")),
        ("770", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 15 da Lei nº 1.162/2017]({L("1162", "#art-15", "2008")}), de 24 de novembro de 2017, que deu nova redação à matéria.'),
        ("809", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 15 da Lei nº 1.162/2017]({L("1162", "#art-15", "2009")}), de 24 de novembro de 2017.'),
        ("520", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 4º da Lei nº 1.163/2017]({L("1163", "#art-4", "2001")}), de 6 de dezembro de 2017, que deu nova redação à matéria.'),
        ("617", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 4º da Lei nº 1.163/2017]({L("1163", "#art-4", "2003")}), de 6 de dezembro de 2017.'),
        ("709", "topo", '!!! info "Alterada pela Lei nº 1.164/2017"\n    O [art. 2º](#art-2) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.164/2017]({L("1164", "#art-1", "2006")}), de 20 de dezembro de 2017.'),
        ("709", "{ #art-2 }", redacao("1164", L("1164", "#art-1", "2006"), "1º")),
        ("492", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 7º da Lei nº 1.169/2017]({L("1169", "#art-7", "2001")}), de 28 de dezembro de 2017.'),
        ("933", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 7º da Lei nº 1.169/2017]({L("1169", "#art-7", "2011")}), de 28 de dezembro de 2017.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2018():
    PDFS = {}
    NOTAS = {
        "1182": ['!!! info "Alterada pela Lei nº 1.190/2018"\n    Esta lei recebeu adequações pela '
                 f'[Lei nº 1.190/2018]({L("1190")}), de 20 de dezembro de 2018.'],
    }
    LINKS = {
        "1186": [("Lei n. 1.122/2016", f"[Lei n. 1.122/2016]({L('1122', '#art-18')})")],
        "1190": [("Lei nº 1.182/2018", f"[Lei nº 1.182/2018]({L('1182')})")],
        "1193": [("Lei nº 648/2005", f"[Lei nº 648/2005]({L('648')})"),
                 ("Código de Polícia Administrativa", f"[Código de Polícia Administrativa]({POSTURAS})"),
                 ("Lei nº 1.131/2016", f"[Lei nº 1.131/2016]({L('1131')})"),
                 ("Lei nº 740/2007", f"[Lei nº 740/2007]({L('740')})"),
                 ("Lei nº 1.000/2013", f"[Lei nº 1.000/2013]({L('1000')})")],
    }
    EXTERNAS = [
        ("1122", "topo", '!!! info "Parcialmente revogada pela Lei nº 1.186/2018"\n    Os [arts. 18](#art-18), [19](#art-19) e [20](#art-20) foram revogados pelo '
         f'[art. 24 da Lei nº 1.186/2018]({L("1186", "#art-24", "2016")}), de 20 de novembro de 2018.'),
        ("1000", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 36 da Lei nº 1.193/2018]({L("1193", "#art-36", "2013")}), de 28 de dezembro de 2018, que dispôs sobre a nova estrutura organizacional da Prefeitura.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2019():
    PDFS = {
        ("1208", "2019"): ("lei-1208-2019.pdf", "", "versão em PDF do documento, impressa do Word"),
        ("1216", "2019"): ("lei-1216-2019.pdf", "", "cópia assinada e escaneada"),
    }
    NOTAS = {
        "1198": ['!!! info "Alterada pela Lei nº 1.204/2019"\n    O [art. 1º](#art-1) recebeu nova redação pela '
                 f'[Lei nº 1.204/2019]({L("1204", "#art-1")}), de 19 de agosto de 2019 (que substituiu a [Lei nº 1.203/2019]({L("1203")}), cuja publicação foi anulada).'],
        "1203": ['!!! warning "Publicação anulada"\n    Na pasta original da prefeitura consta aviso de anulação tornando sem efeito a publicação desta lei '
                 f'(substituída pela [Lei nº 1.204/2019]({L("1204")})).'],
    }
    LINKS = {
        "1196": [("Lei nº. 1.180/2018", f"[Lei nº. 1.180/2018]({L('1180')})")],
        "1203": [("Lei nº 1.198/2019", f"[Lei nº 1.198/2019]({L('1198', '#art-1')})")],
        "1204": [("Lei nº 1.198/2019", f"[Lei nº 1.198/2019]({L('1198', '#art-1')})")],
        "1209": [("Lei nº. 904, de 18 de maio de 2011", f"[Lei nº. 904, de 18 de maio de 2011]({L('904')})"),
                 ("Código Tributário Municipal", f"[Código Tributário Municipal]({TRIBUTARIO})")],
        "1210": [("Lei nº. 1090/2015", f"[Lei nº. 1090/2015]({L('1090', '#art-5')})"),
                 ("Lei nº 1090/2015", f"[Lei nº 1090/2015]({L('1090', '#art-5')})")],
        "1211": [("Lei nº. 989/2012", f"[Lei nº. 989/2012]({L('989')})")],
        "1212": [("Lei Municipal nº 1.168/2017", f"[Lei Municipal nº 1.168/2017]({L('1168')})")],
        "1222": [("Lei nº. 1.007/2013", f"[Lei nº. 1.007/2013]({L('1007')})"),
                 ("Código de Posturas do Município", f"[Código de Posturas do Município]({POSTURAS})"),
                 ("Estatuto dos Servidores Municipais", f"[Estatuto dos Servidores Municipais]({ESTATUTO})")],
        "1223": [("Lei nº. 1.189/2018", f"[Lei nº. 1.189/2018]({L('1189', '#art-3')})")],
    }
    EXTERNAS = [
        ("1180", "topo", '!!! info "Alterada pela Lei nº 1.196/2019"\n    Os [arts. 2º](#art-2) e [3º](#art-3) receberam nova redação pela '
         f'[Lei nº 1.196/2019]({L("1196", "", "2018")}), de 29 de janeiro de 2019.'),
        ("1180", "{ #art-2 }", redacao("1196", L("1196", "#art-1", "2018"), "1º")),
        ("1180", "{ #art-3 }", redacao("1196", L("1196", "#art-2", "2018"), "2º")),
        ("904", "topo", '!!! info "Alterada pela Lei nº 1.209/2019"\n    Os [arts. 3º](#art-3) e [7º](#art-7) receberam nova redação pela '
         f'[Lei nº 1.209/2019]({L("1209", "", "2011")}), de 4 de setembro de 2019.'),
        ("904", "{ #art-3 }", redacao("1209", L("1209", "#art-1", "2011"), "1º")),
        ("904", "{ #art-7 }", redacao("1209", L("1209", "#art-2", "2011"), "2º")),
        ("1090", "topo", '!!! info "Alterada pela Lei nº 1.210/2019"\n    O [art. 5º](#art-5) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.210/2019]({L("1210", "#art-1", "2015")}), de 4 de setembro de 2019.'),
        ("1090", "{ #art-5 }", redacao("1210", L("1210", "#art-1", "2015"), "1º")),
        ("989", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1.211/2019]({L("1211", "#art-2", "2012")}), de 4 de setembro de 2019.'),
        ("1168", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 1º da Lei nº 1.212/2019]({L("1212", "#art-1", "2017")}), de 10 de setembro de 2019.'),
        ("1007", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 90 da Lei nº 1.222/2019]({L("1222", "#art-90", "2013")}), de 19 de dezembro de 2019, que deu nova redação à matéria.'),
        ("1189", "topo", '!!! info "Alterada pela Lei nº 1.223/2019"\n    O [art. 3º](#art-3) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.223/2019]({L("1223", "#art-1", "2018")}), de 19 de dezembro de 2019.'),
        ("1189", "{ #art-3 }", redacao("1223", L("1223", "#art-1", "2018"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2020():
    PDFS = {
        ("1232", "2020"): ("lei-1232-2020.pdf", "", "versão em PDF da prefeitura"),
        ("1241", "2020"): ("lei-1241-2020.pdf", " (arquivo da prefeitura)"),
    }
    NOTAS = {
        "1230": ['!!! info "Alterada pela Lei nº 1.242/2020"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
                 f'[art. 1º da Lei nº 1.242/2020]({L("1242", "#art-1")}), de 6 de outubro de 2020.'],
        "1234": ['!!! info "Texto extraído da publicação oficial"\n    O arquivo `.doc` desta lei na pasta da prefeitura '
                 'estava vazio; o texto foi extraído da publicação no Diário Oficial da Assomasul (Edição nº 2633, de 02/07/2020).'],
        "1247": ['!!! info "Texto extraído da publicação oficial"\n    O arquivo `.doc` desta lei na pasta da prefeitura '
                 'continha por engano uma cópia da Lei nº 1.246/2020; o texto foi extraído da publicação no Diário Oficial da Assomasul (Edição nº 2755, de 29/12/2020).'],
    }
    LINKS = {
        "1229": [("Lei nº. 1090/2015", f"[Lei nº. 1090/2015]({L('1090')})"),
                 ("Lei nº 1090/2015", f"[Lei nº 1090/2015]({L('1090', '#art-2')})")],
        "1233": [("Lei 768/2008", f"[Lei 768/2008]({L('768')})"),
                 ("Lei nº 768/2008", f"[Lei nº 768/2008]({L('768', '#art-2')})"),
                 ("na Lei nº 919/2011", f"na [Lei nº 919/2011]({L('919')})"),
                 ("art. 12 da Lei nº 919/2011", f"[art. 12 da Lei nº 919/2011]({L('919', '#art-12')})"),
                 ("da Lei nº 919/2011 de 24 de agosto de 2011, que passam", f"da [Lei nº 919/2011]({L('919')}) de 24 de agosto de 2011, que passam"),
                 ("ANEXO I DA LEI Nº 919/2011", f"ANEXO I DA [LEI Nº 919/2011]({L('919')})")],
        "1238": [("Lei nº. 935/2011", f"[Lei nº. 935/2011]({L('935')})"),
                 ("Lei nº. 935/2011", f"[Lei nº. 935/2011]({L('935', '#art-1')})")],
        "1240": [("Lei nº 1082/2014", f"[Lei nº 1082/2014]({L('1082')})")],
        "1242": [("Lei nº. 1.230, de 13 de abril de 2020", f"[Lei nº. 1.230, de 13 de abril de 2020]({L('1230', '#art-1')})")],
        "1246": [("Lei nº. 1.155/2017", f"[Lei nº. 1.155/2017]({L('1155')})")],
    }
    EXTERNAS = [
        ("1090", "topo", '!!! info "Alterada pela Lei nº 1.229/2020"\n    O [art. 2º](#art-2) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.229/2020]({L("1229", "#art-1", "2015")}), de 24 de março de 2020.'),
        ("1090", "{ #art-2 }", redacao("1229", L("1229", "#art-1", "2015"), "1º")),
        ("768", "topo", '!!! info "Alterada pela Lei nº 1.233/2020"\n    Foi acrescido o art. 2º-A após o [art. 2º](#art-2) pelo '
         f'[art. 1º da Lei nº 1.233/2020]({L("1233", "#art-1", "2008")}), de 2 de junho de 2020.'),
        ("768", "{ #art-2 }", '!!! info "Dispositivo acrescido pela Lei nº 1.233/2020"\n    Artigo acrescido pelo '
         f'[art. 1º da Lei nº 1.233/2020]({L("1233", "#art-1", "2008")}) — ver texto do art. 2º-A na lei alteradora.'),
        ("919", "topo", '!!! info "Alterada pela Lei nº 1.233/2020"\n    O [art. 12](#art-12) e os Anexos I e II foram alterados pelos '
         f'[arts. 2º e 3º da Lei nº 1.233/2020]({L("1233", "#art-2", "2011")}), de 2 de junho de 2020.'),
        ("919", "{ #art-12 }", redacao("1233", L("1233", "#art-2", "2011"), "2º", idx=1)),
        ("935", "topo", '!!! info "Alterada pela Lei nº 1.238/2020"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.238/2020]({L("1238", "#art-1", "2011")}), de 26 de agosto de 2020.'),
        ("935", "{ #art-1 }", redacao("1238", L("1238", "#art-1", "2011"), "1º")),
        ("1082", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 69 da Lei nº 1.240/2020]({L("1240", "#art-69", "2014")}), de 9 de setembro de 2020.'),
        ("1230", "{ #art-1 }", redacao("1242", L("1242", "#art-1"), "1º")),
        ("1155", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 9º da Lei nº 1.246/2020]({L("1246", "#art-9", "2017")}), de 4 de dezembro de 2020.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2021():
    PDFS = {
        ("1254", "2021"): ("lei-1254-2021.pdf", "", "versão em PDF da prefeitura"),
        ("1258", "2021"): ("lei-1258-2021.pdf", "", "versão em PDF da prefeitura"),
        ("1259", "2021"): ("lei-1259-2021.pdf", "", "versão em PDF da prefeitura"),
        ("1262", "2021"): ("lei-1262-2021.pdf", "", "versão em PDF da prefeitura"),
        ("1267", "2021"): ("lei-1267-2021.pdf", "", "versão em PDF da prefeitura"),
    }
    NOTAS = {
        "1249": ['!!! info "Retificação de publicação"\n    Retificação publicada no Diário Oficial da Assomasul '
                 '(Edição nº 2776, de 29/01/2021): no art. 1º, onde se lê `2.107 – ENFRENTAMENTO AO COVID-19`, '
                 'leia-se `2.207 – ENFRENTAMENTO AO COVID-19`.'],
        "1258": ['!!! info "Alterada pela Lei nº 1.259/2021"\n    Foi acrescido o art. 54-A após o [art. 54](#art-54) pelo '
                 f'[art. 1º da Lei nº 1.259/2021]({L("1259", "#art-1")}), de 21 de setembro de 2021.'],
    }
    LINKS = {
        "1251": [("Lei Municipal nº 725, de 14 de março de 2007", f"[Lei Municipal nº 725, de 14 de março de 2007]({L('725')})"),
                 ("Lei Municipal 725/2007", f"[Lei Municipal 725/2007]({L('725')})"),
                 ("Lei 739/2007", f"[Lei 739/2007]({L('739')})")],
        "1254": [("Estatuto dos Servidores Públicos", f"[Estatuto dos Servidores Públicos]({ESTATUTO})"),
                 ("código tributário municipal", f"[código tributário municipal]({TRIBUTARIO})")],
        "1258": [("Lei nº. 1.213/2019", f"[Lei nº. 1.213/2019]({L('1213')})")],
        "1259": [("Lei nº. 1.258, de 14 de setembro de 2021", f"[Lei nº. 1.258, de 14 de setembro de 2021]({L('1258')})"),
                 ("Lei nº 1.258, de 14 de setembro de 2021", f"[Lei nº 1.258, de 14 de setembro de 2021]({L('1258')})")],
        "1260": [("Lei Orçamentária do Exercício de 2021", f"[Lei Orçamentária do Exercício de 2021]({L('1247')})"),
                 ("art. 5º da Lei Municipal nº 1.247, de 21 de dezembro de 2020", f"[art. 5º da Lei Municipal nº 1.247, de 21 de dezembro de 2020]({L('1247', '#art-5')})")],
        "1263": [("Lei nº 838/2010", f"[Lei nº 838/2010]({L('838')})"),
                 ("Código Tributário Municipal", f"[Código Tributário Municipal]({TRIBUTARIO})")],
        "1264": [("Estatuto dos Servidores Públicos Municipais", f"[Estatuto dos Servidores Públicos Municipais]({ESTATUTO})"),
                 ("Lei nº 595/2003", f"[Lei nº 595/2003]({L('595')})")],
    }
    EXTERNAS = [
        ("725", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 18 da Lei nº 1.251/2021]({L("1251", "#art-18", "2007")}), de 24 de março de 2021.'),
        ("1213", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 54 da Lei nº 1.258/2021]({L("1258", "#art-54", "2019")}), de 14 de setembro de 2021.'),
        ("1258", "{ #art-54 }", '!!! info "Dispositivo acrescido pela Lei nº 1.259/2021"\n    Artigo acrescido pelo '
         f'[art. 1º da Lei nº 1.259/2021]({L("1259", "#art-1")}): ver texto do art. 54-A na lei alteradora.'),
        ("1247", "topo", '!!! info "Alterada pela Lei nº 1.260/2021"\n    A alínea “c” do [art. 5º](#art-5) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.260/2021]({L("1260", "#art-1", "2020")}), de 6 de outubro de 2021.'),
        ("1247", "{ #art-5 }", redacao("1260", L("1260", "#art-1", "2020"), "1º")),
        ("838", "topo", '!!! info "Convalidada pela Lei nº 1.263/2021"\n    Esta lei foi convalidada pelo '
         f'[art. 1º da Lei nº 1.263/2021]({L("1263", "#art-1", "2010")}), de 29 de novembro de 2021.'),
        ("595", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 22 da Lei nº 1.264/2021]({L("1264", "#art-22", "2003")}), de 29 de novembro de 2021.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2022():
    PDFS = {
        ("1276", "2022"): ("lei-1276-2022.pdf", " (arquivo da prefeitura)"),
        ("1277", "2022"): ("lei-1277-2022.pdf", "", "versão em PDF da prefeitura"),
        ("1278", "2022"): ("lei-1278-2022.pdf", "", "versão em PDF da prefeitura"),
        ("1279", "2022"): ("lei-1279-2022.pdf", " (arquivo da prefeitura)"),
        ("1285", "2022"): ("lei-1285-2022.pdf", " (arquivo da prefeitura)"),
        ("1287", "2022"): ("lei-1287-2022.pdf", " (arquivo da prefeitura)"),
        ("1288", "2022"): ("lei-1288-2022.pdf", " (arquivo da prefeitura)"),
        ("1289", "2022"): ("lei-1289-2022.pdf", " (arquivo da prefeitura)"),
        ("1290", "2022"): ("lei-1290-2022.pdf", " (arquivo da prefeitura)"),
        ("1294", "2022"): ("lei-1294-2022.pdf", " (arquivo da prefeitura)"),
        ("1296", "2022"): ("lei-1296-2022.pdf", " (arquivo da prefeitura)"),
        ("1298", "2022"): ("lei-1298-2022.pdf", " (arquivo da prefeitura)"),
        ("1299", "2022"): ("lei-1299-2022.pdf", " (arquivo da prefeitura)"),
        ("1300", "2022"): ("lei-1300-2022.pdf", " (arquivo da prefeitura)"),
    }
    NOTAS = {
        "1270": ['!!! info "Retificação de publicação"\n    Retificação da republicação publicada no Diário Oficial da Assomasul '
                 '(Edição nº 3017, de 24/01/2022): na Tabela II – Cargos de Provimento em Comissão, para o símbolo `DAS 2`, '
                 'onde se lê `4.094,68`, leia-se `6.378,71`.'],
        "1284": ['!!! info "Alterada pela Lei nº 1.306/2022"\n    Foram acrescidos os incisos XI, XII e XIII ao § 2º do [art. 4º](#art-4) pelo '
                 f'[art. 1º da Lei nº 1.306/2022]({L("1306", "#art-1")}), de 2 de dezembro de 2022.'],
        "1285": ['!!! info "Alterada pela Lei nº 1.305/2022"\n    Os [arts. 1º](#art-1) e [2º](#art-2) foram alterados e foi acrescido o art. 8º-A pela '
                 f'[Lei nº 1.305/2022]({L("1305")}), de 23 de novembro de 2022.'],
        "1298": ['!!! info "Alterada pela Lei nº 1.309/2022"\n    O [art. 1º](#art-1) e o Anexo Único foram alterados pela '
                 f'[Lei nº 1.309/2022]({L("1309")}), de 16 de dezembro de 2022.'],
        "1306": ['!!! info "Revogação indicada no arquivo"\n    O arquivo desta lei na pasta da prefeitura tem no nome '
                 '“REVOGADA PELA LEI 1.321.2023”, isto é, revogada pela Lei nº 1.321/2023, que ainda não está neste site.'],
    }
    LINKS = {
        "1269": [("Lei nº 1.236/2020", f"[Lei nº 1.236/2020]({L('1236')})")],
        "1272": [("Lei Municipal nº 1.193/2018", f"[Lei Municipal nº 1.193/2018]({L('1193')})")],
        "1273": [("Lei nº 1.151/2017", f"[Lei nº 1.151/2017]({L('1151')})")],
        "1274": [("Lei nº 1.142/2017", f"[Lei nº 1.142/2017]({L('1142')})")],
        "1275": [("Lei nº 1.144/2017", f"[Lei nº 1.144/2017]({L('1144')})")],
        "1276": [("Lei nº 1.252, de 22 de abril de 2021", f"[Lei nº 1.252, de 22 de abril de 2021]({L('1252')})")],
        "1277": [("Lei nº. 1.169/2017", f"[Lei nº. 1.169/2017]({L('1169')})")],
        "1280": [("Lei nº. 1.180, de 28 de junho de 2018", f"[Lei nº. 1.180, de 28 de junho de 2018]({L('1180')})")],
        "1290": [("Código Tributário", f"[Código Tributário]({TRIBUTARIO})")],
        "1291": [("Lei nº. 1.268, de 29 de dezembro de 2021", f"[Lei nº. 1.268, de 29 de dezembro de 2021]({L('1268')})")],
        "1293": [("Lei nº. 1.018/2013", f"[Lei nº. 1.018/2013]({L('1018')})")],
        "1294": [("768/2008", f"[768/2008]({L('768')})"),
                 ("918/2011", f"[918/2011]({L('918')})"),
                 ("919/2011", f"[919/2011]({L('919')})"),
                 ("Lei nº 1.233/2020", f"[Lei nº 1.233/2020]({L('1233')})")],
        "1303": [("Lei nº. 1.222/2019", f"[Lei nº. 1.222/2019]({L('1222')})"),
                 ("Lei nº. 1.222, de 19 de dezembro de 2019", f"[Lei nº. 1.222, de 19 de dezembro de 2019]({L('1222')})")],
        "1305": [("Lei nº. 1.285, de 3 de junho de 2022", f"[Lei nº. 1.285, de 3 de junho de 2022]({L('1285')})")],
        "1306": [("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})"),
                 ("Lei n° 1036/2013", f"[Lei n° 1036/2013]({L('1036')})")],
        "1307": [("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})")],
        "1309": [("Lei nº 1298, de 14 de outubro de 2022", f"[Lei nº 1298, de 14 de outubro de 2022]({L('1298')})"),
                 ("Lei 1298, de 14 de outubro de 2022", f"[Lei 1298, de 14 de outubro de 2022]({L('1298')})"),
                 ("Lei nº 1.298, de 14 de outubro de 2022", f"[Lei nº 1.298, de 14 de outubro de 2022]({L('1298')})")],
    }
    EXTERNAS = [
        ("1151", "topo", '!!! info "Alterada pela Lei nº 1.273/2022"\n    Os [arts. 2º](#art-2) e [3º](#art-3) foram alterados pela '
         f'[Lei nº 1.273/2022]({L("1273", "", "2017")}), de 10 de março de 2022.'),
        ("1151", "{ #art-2 }", redacao("1273", L("1273", "#art-1", "2017"), "1º", idx=0)),
        ("1151", "{ #art-3 }", redacao("1273", L("1273", "#art-2", "2017"), "2º", idx=1)),
        ("1142", "topo", '!!! info "Alterada pela Lei nº 1.274/2022"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.274/2022]({L("1274", "#art-1", "2017")}), de 17 de março de 2022.'),
        ("1142", "{ #art-1 }", redacao("1274", L("1274", "#art-1", "2017"), "1º")),
        ("1144", "topo", '!!! info "Alterada pela Lei nº 1.275/2022"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.275/2022]({L("1275", "#art-1", "2017")}), de 17 de março de 2022.'),
        ("1144", "{ #art-1 }", redacao("1275", L("1275", "#art-1", "2017"), "1º")),
        ("1252", "topo", '!!! info "Alterada pela Lei nº 1.276/2022"\n    Foi acrescido o art. 6º-A após o [art. 6º](#art-6) pelo '
         f'[art. 9º da Lei nº 1.276/2022]({L("1276", "#art-9", "2021")}), de 22 de março de 2022.'),
        ("1252", "{ #art-6 }", '!!! info "Dispositivo acrescido pela Lei nº 1.276/2022"\n    Artigo acrescido pelo '
         f'[art. 9º da Lei nº 1.276/2022]({L("1276", "#art-9", "2021")}) — ver texto do art. 6º-A na lei alteradora.'),
        ("1169", "topo", '!!! info "Alterada pela Lei nº 1.277/2022"\n    O [art. 2º](#art-2) e o § 3º do [art. 3º](#art-3) foram alterados pela '
         f'[Lei nº 1.277/2022]({L("1277", "", "2017")}), de 5 de abril de 2022.'),
        ("1169", "{ #art-2 }", redacao("1277", L("1277", "#art-1", "2017"), "1º", idx=0)),
        ("1169", "{ #art-3 }", redacao("1277", L("1277", "#art-2", "2017"), "2º", idx=1)),
        ("1180", "topo", '!!! info "Alterada pela Lei nº 1.280/2022"\n    O [art. 3º](#art-3) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.280/2022]({L("1280", "#art-1", "2018")}), de 12 de abril de 2022.'),
        ("1180", "{ #art-3 }", redacao("1280", L("1280", "#art-1", "2018"), "1º")),
        ("1018", "topo", '!!! info "Alterada pela Lei nº 1.293/2022"\n    O [art. 5º](#art-5) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.293/2022]({L("1293", "#art-1", "2013")}), de 16 de agosto de 2022.'),
        ("1018", "{ #art-5 }", redacao("1293", L("1293", "#art-1", "2013"), "1º")),
        ("768", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 33 da Lei nº 1.294/2022]({L("1294", "#art-33", "2008")}), de 9 de setembro de 2022.'),
        ("918", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 33 da Lei nº 1.294/2022]({L("1294", "#art-33", "2011")}), de 9 de setembro de 2022.'),
        ("919", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 33 da Lei nº 1.294/2022]({L("1294", "#art-33", "2011")}), de 9 de setembro de 2022.'),
        ("1233", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 33 da Lei nº 1.294/2022]({L("1294", "#art-33", "2020")}), de 9 de setembro de 2022.'),
        ("1222", "topo", '!!! info "Alterada pela Lei nº 1.303/2022"\n    Os [arts. 22](#art-22), [24](#art-24) e [29](#art-29) foram alterados e foi acrescido o art. 88-A após o [art. 88](#art-88) pela '
         f'[Lei nº 1.303/2022]({L("1303", "", "2019")}), de 11 de novembro de 2022.'),
        ("1222", "{ #art-22 }", redacao("1303", L("1303", "#art-1", "2019"), "1º", idx=0)),
        ("1222", "{ #art-24 }", redacao("1303", L("1303", "#art-2", "2019"), "2º", idx=1)),
        ("1222", "{ #art-29 }", redacao("1303", L("1303", "#art-3", "2019"), "3º", idx=2)),
        ("1285", "{ #art-1 }", redacao("1305", L("1305", "#art-1"), "1º", idx=0)),
        ("1285", "{ #art-2 }", redacao("1305", L("1305", "#art-2"), "2º", idx=1)),
        ("1298", "{ #art-1 }", redacao("1309", L("1309", "#art-2"), "2º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2023():
    PDFS = {
        ("1320", "2023"): ("lei-1320-2023.pdf", " (arquivo da prefeitura)"),
        ("1321", "2023"): ("lei-1321-2023.pdf", " (arquivo da prefeitura)"),
        ("1325", "2023"): ("lei-1325-2023.pdf", " (arquivo da prefeitura)"),
        ("1326", "2023"): ("lei-1326-2023.pdf", " (arquivo da prefeitura)"),
        ("1327", "2023"): ("lei-1327-2023.pdf", " (arquivo da prefeitura)"),
        ("1328", "2023"): ("lei-1328-2023.pdf", " (arquivo da prefeitura)"),
        ("1329", "2023"): ("lei-1329-2023.pdf", " (arquivo da prefeitura)"),
        ("1330", "2023"): ("lei-1330-2023.pdf", " (arquivo da prefeitura)"),
        ("1348", "2023"): ("lei-1348-2023.pdf", " (arquivo da prefeitura)"),
    }
    NOTAS = {
        "1313": ['!!! warning "Anulação de publicação"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* referente à publicação da Lei nº 1.313/2023 na Edição nº 3297, de 13 de março de 2023.'],
        "1331": ['!!! info "Retificação de publicação"\n    Consta no arquivo oficial *Retificação de Publicação* referente à publicação da Lei nº 1.331/2023 na Edição nº 3420, às páginas 82 e 83: onde se lê *Exercício de 2022*, leia-se *Exercício de 2023*.'],
    }
    LINKS = {
        "1314": [("Lei nº. 1083/2014", f"[Lei nº. 1083/2014]({L('1083')})")],
        "1321": [
            ("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})"),
            ("Lei nº. 1.306, de 2 de dezembro de 2022", f"[Lei nº. 1.306, de 2 de dezembro de 2022]({L('1306')})"),
            ("Lei n° 1036/2013", f"[Lei n° 1036/2013]({L('1036')})"),
        ],
        "1331": [
            ("Lei nº. 1.310, de 22 de dezembro de 2022", f"[Lei nº. 1.310, de 22 de dezembro de 2022]({L('1310')})"),
        ],
        "1333": [
            ("Lei nº. 1.169/2017", f"[Lei nº. 1.169/2017]({L('1169')})"),
        ],
        "1340": [("Lei nº. 924/2011", f"[Lei nº. 924/2011]({L('924')})")],
        "1343": [("Lei nº. 1.310, de 22 de dezembro de 2022", f"[Lei nº. 1.310, de 22 de dezembro de 2022]({L('1310')})")],
        "1346": [
            ("Lei nº. 1.310, de 22 de dezembro de 2022", f"[Lei nº. 1.310, de 22 de dezembro de 2022]({L('1310')})"),
        ],
    }
    EXTERNAS = [
        ("1083", "topo", '!!! info "Alterada pela Lei nº 1.314/2023"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.314/2023]({L("1314", "", "2014")}), de 10 de março de 2023.'),
        ("1284", "topo", '!!! info "Alterada pela Lei nº 1.321/2023"\n    Os [arts. 2º](#art-2), [4º](#art-4) e [5º](#art-5) foram alterados pelo '
         f'[art. 1º da Lei nº 1.321/2023]({L("1321", "#art-1", "2022")}).'),
        ("1284", "{ #art-2 }", redacao("1321", L("1321", "#art-1", "2022"), "1º", idx=0)),
        ("1284", "{ #art-4 }", redacao("1321", L("1321", "#art-1", "2022"), "1º", idx=1)),
        ("1284", "{ #art-5 }", redacao("1321", L("1321", "#art-1", "2022"), "1º", idx=2)),
        ("1306", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1.321/2023]({L("1321", "#art-2", "2022")}).'),
        ("1169", "topo", '!!! info "Alterada pela Lei nº 1.333/2023"\n    Foi incluído o inciso III no [art. 2º](#art-2) pelo '
         f'[art. 1º da Lei nº 1.333/2023]({L("1333", "#art-1", "2017")}).'),
        ("1169", "{ #art-2 }", redacao("1333", L("1333", "#art-1", "2017"), "1º")),
        ("924", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1.340/2023]({L("1340", "#art-2", "2011")}).'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2024():
    PDFS = {
        ("1350", "2024"): ("lei-1350-2024.pdf", " (arquivo da prefeitura)"),
        ("1360", "2024"): ("lei-1360-2024.pdf", " (arquivo da prefeitura)"),
        ("1361", "2024"): ("lei-1361-2024.pdf", " (arquivo da prefeitura)"),
        ("1367", "2024"): ("lei-1367-2024.pdf", " (arquivo da prefeitura)"),
        ("1369", "2024"): ("lei-1369-2024.pdf", " (arquivo da prefeitura)"),
    }
    NOTAS = {
        "1359": ['!!! danger "Lei revogada"\n    Esta lei foi revogada pelo art. 4º da '
                 '[Lei Complementar nº 065/2024](../../leis-complementares/lc-065-2024.md), de 30 de outubro de 2024.'],
        "1353": ['!!! warning "Anulação de publicação"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* tornando sem efeito a publicação da Lei nº 1.353/2024 na Edição nº 3552, de 21 de março de 2024, às páginas 95 a 97.'],
        "1356": ['!!! info "Retificação de publicação"\n    Consta no arquivo oficial *Retificação de Publicação* referente à Edição nº 3553, de 22 de março de 2024 (páginas 135 a 140), na tabela da SODETA do Anexo Único, para o símbolo `CC1-04` (Assessor Especial III): onde se lê `2.566,89`, leia-se `2.866,89`.'],
        "1363": ['!!! warning "Anulação de publicação"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* tornando sem efeito a publicação da Lei nº 1.363/2024 na Edição nº 3678, de 18 de setembro de 2024, à página 37.'],
    }
    LINKS = {
        "1350": [("Estatuto do Servidor Público", f"[Estatuto do Servidor Público]({ESTATUTO})")],
        "1353": [
            ("Lei nº 1.350, de 1º de março de 2024", f"[Lei nº 1.350, de 1º de março de 2024]({L('1350')})"),
            ("Lei nº 1.350, de 01 de março de 2024", f"[Lei nº 1.350, de 01 de março de 2024]({L('1350')})"),
        ],
        "1355": [("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})")],
        "1356": [("Lei nº 1.193/2018", f"[Lei nº 1.193/2018]({L('1193')})")],
        "1358": [("Lei Complementar nº 018/2011", "[Lei Complementar nº 018/2011](../../plano-cargos-magisterio/lc-018-2011.md)")],
        "1359": [("Lei nº. 1.169/2017", f"[Lei nº. 1.169/2017]({L('1169')})")],
        "1363": [("1.348, de 21 de dezembro de 2023", f"[1.348, de 21 de dezembro de 2023]({L('1348')})")],
        "1365": [("Lei nº. 1.264, de 29 de novembro de 2021", f"[Lei nº. 1.264, de 29 de novembro de 2021]({L('1264')})")],
        "1366": [("Lei nº. 1.240, de 9 de setembro de 2020", f"[Lei nº. 1.240, de 9 de setembro de 2020]({L('1240')})")],
        "1368": [("Lei nº 1.348, de 21 de dezembro de 2023", f"[Lei nº 1.348, de 21 de dezembro de 2023]({L('1348')})")],
        "1370": [("Lei nº 1.129/2016", f"[Lei nº 1.129/2016]({L('1129')})")],
    }
    EXTERNAS = [
        ("1350", "topo", '!!! info "Alterada pela Lei nº 1.353/2024"\n    Os [arts. 1º](#art-1), [5º](#art-5), [6º](#art-6) e [14](#art-14) e os anexos foram alterados pela '
         f'[Lei nº 1.353/2024]({L("1353")}), de 18 de março de 2024.'),
        ("1350", "{ #art-5 }", redacao("1353", L("1353", "#art-2"), "2º", idx=0)),
        ("1350", "{ #art-6 }", redacao("1353", L("1353", "#art-3"), "3º", idx=1)),
        ("1350", "{ #art-14 }", redacao("1353", L("1353", "#art-4"), "4º", idx=2)),
        ("1284", "topo", '!!! info "Alterada pela Lei nº 1.355/2024"\n    O [art. 2º](#art-2) foi alterado pelo '
         f'[art. 1º da Lei nº 1.355/2024]({L("1355", "#art-1", "2022")}), de 21 de março de 2024.'),
        ("1284", "{ #art-2 }", redacao("1355", L("1355", "#art-1", "2022"), "1º")),
        ("1193", "topo", '!!! info "Alterada pela Lei nº 1.356/2024"\n    O [art. 3º](#art-3) e os Anexos I, III e IV foram alterados pela '
         f'[Lei nº 1.356/2024]({L("1356", "", "2018")}), de 21 de março de 2024.'),
        ("1264", "topo", '!!! info "Alterada pela Lei nº 1.365/2024"\n    O [art. 3º](#art-3) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.365/2024]({L("1365", "#art-1", "2021")}), de 28 de novembro de 2024.'),
        ("1264", "{ #art-3 }", redacao("1365", L("1365", "#art-1", "2021"), "1º")),
        ("1240", "topo", '!!! info "Alterada pela Lei nº 1.366/2024"\n    O [art. 20](#art-20) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.366/2024]({L("1366", "#art-1", "2020")}), de 28 de novembro de 2024.'),
        ("1240", "{ #art-20 }", redacao("1366", L("1366", "#art-1", "2020"), "1º")),
        ("1129", "topo", '!!! info "Alterada pela Lei nº 1.370/2024"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.370/2024]({L("1370", "#art-1", "2016")}), de 30 de dezembro de 2024.'),
        ("1129", "{ #art-1 }", redacao("1370", L("1370", "#art-1", "2016"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2025():
    PDFS = {
        (n, "2025"): (f"lei-{n}-2025.pdf", " (arquivo da prefeitura)")
        for n in [
            "1372", "1373", "1378", "1379", "1380", "1387", "1389", "1390",
            "1391", "1392", "1395", "1396", "1397", "1398", "1399", "1400",
            "1404", "1409", "1410", "1411", "1412", "1413", "1414",
        ]
    }
    NOTAS = {
        "1374": ['!!! warning "Anulação de publicação"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* tornando sem efeito a publicação da Lei nº 1.374/2025 na Edição nº 3790, de 28 de fevereiro de 2025, à página 166.'],
        "1405": ['!!! warning "Anulação de publicação"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* tornando sem efeito a publicação da Lei nº 1.405/2025 na Edição nº 3951, de 20 de outubro de 2025, à página 63.'],
        "1411": ['!!! info "Anulação de publicação com numeração incorreta"\n    Consta no arquivo oficial o *Aviso de Anulação de Publicação* tornando sem efeito a publicação da Lei sobre descarte irregular de lixo intitulada erroneamente como nº 1.411 (Edição nº 3974, de 21 de novembro de 2025, página 49), cuja numeração correta é [Lei nº 1.415/2025](lei-1415-2025.md).'],
        "1415": ['!!! info "Numeração corrigida"\n    Publicada inicialmente com numeração incorreta (nº 1.411) na Edição nº 3974, de 21 de novembro de 2025, página 49, objeto de *Aviso de Anulação de Publicação*.'],
    }
    LINKS = {
        "1376": [
            ("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})"),
            ("Lei nº. 1.321, de 11 de maio de 2023", f"[Lei nº. 1.321, de 11 de maio de 2023]({L('1321')})"),
        ],
        "1377": [("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})")],
        "1381": [("Lei nº 1.100/2015", f"[Lei nº 1.100/2015]({L('1100')})")],
        "1384": [("Lei nº 1316", f"[Lei nº 1316]({L('1316')})")],
        "1386": [("Lei nº 1.369, de 20 dezembro de 2024", f"[Lei nº 1.369, de 20 dezembro de 2024]({L('1369')})")],
        "1388": [("Lei nº. 1.336, de 23 de outubro de 2023", f"[Lei nº. 1.336, de 23 de outubro de 2023]({L('1336')})")],
        "1390": [
            ("Lei nº 1.208/2019", f"[Lei nº 1.208/2019]({L('1208')})"),
            ("Lei nº. 1.208/2019", f"[Lei nº. 1.208/2019]({L('1208')})"),
        ],
        "1391": [("Lei nº. 942/2011", f"[Lei nº. 942/2011]({L('942')})")],
        "1393": [("Lei nº 1.043, de 4 de dezembro de 2013", f"[Lei nº 1.043, de 4 de dezembro de 2013]({L('1043')})")],
        "1394": [("Lei nº 1.285, de 3 de junho de 2022", f"[Lei nº 1.285, de 3 de junho de 2022]({L('1285')})")],
        "1402": [
            ("Lei nº. 1090/2015", f"[Lei nº. 1090/2015]({L('1090')})"),
            ("Lei nº 1090/2015", f"[Lei nº 1090/2015]({L('1090')})"),
            ("1.210/2019", f"[1.210/2019]({L('1210')})"),
            ("Lei nº. 1.229, de 24 de março", f"[Lei nº. 1.229, de 24 de março]({L('1229')})"),
        ],
        "1403": [
            ("Lei nº 1.350, de 1º de março de 2024", f"[Lei nº 1.350, de 1º de março de 2024]({L('1350')})"),
            ("Lei nº 1.350 de 1º de março de 2024", f"[Lei nº 1.350 de 1º de março de 2024]({L('1350')})"),
            ("Lei nº 1.350, de 2024", f"[Lei nº 1.350, de 2024]({L('1350')})"),
        ],
        "1405": [("Lei nº 1.336, de 23 de outubro de 2023", f"[Lei nº 1.336, de 23 de outubro de 2023]({L('1336')})")],
        "1407": [("Lei 1.148/2017", f"[Lei 1.148/2017]({L('1148')})")],
        "1411": [("Lei nº. 1.369, de 20 de dezembro de 2024", f"[Lei nº. 1.369, de 20 de dezembro de 2024]({L('1369')})")],
        "1412": [("Lei nº 1.369, de 20 de dezembro de 2024", f"[Lei nº 1.369, de 20 de dezembro de 2024]({L('1369')})")],
        "1413": [
            ("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})"),
            ("Lei nº. 1.321, de 11 de maio de 2023", f"[Lei nº. 1.321, de 11 de maio de 2023]({L('1321')})"),
        ],
        "1414": [("Lei nº. 1.404, de 9 de outubro de 2025", f"[Lei nº. 1.404, de 9 de outubro de 2025]({L('1404')})")],
    }
    EXTERNAS = [
        ("1284", "topo", '!!! info "Alterada pela Lei nº 1.377/2025"\n    O [art. 2º](#art-2) foi alterado pelo '
         f'[art. 1º da Lei nº 1.377/2025]({L("1377", "#art-1", "2022")}), de 27 de fevereiro de 2025.'),
        ("1100", "topo", '!!! info "Prazo prorrogado pela Lei nº 1.381/2025"\n    O prazo de vigência do Plano Municipal de Educação foi prorrogado até 31 de dezembro de 2025 pela '
         f'[Lei nº 1.381/2025]({L("1381", "", "2015")}), de 3 de abril de 2025.'),
        ("1316", "topo", '!!! info "Alterada pela Lei nº 1.384/2025"\n    O [art. 2º](#art-2) foi alterado pelo '
         f'[art. 1º da Lei nº 1.384/2025]({L("1384", "#art-1", "2023")}), de 16 de abril de 2025.'),
        ("1336", "topo", '!!! info "Alterada pelas Leis nº 1.388/2025 e 1.405/2025"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.388/2025]({L("1388", "", "2023")}) e pela [Lei nº 1.405/2025]({L("1405", "", "2023")}).'),
        ("1208", "topo", '!!! info "Alterada pela Lei nº 1.390/2025"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.390/2025]({L("1390", "", "2019")}), de 16 de maio de 2025.'),
        ("1043", "topo", '!!! info "Alterada pela Lei nº 1.393/2025"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.393/2025]({L("1393", "", "2013")}), de 7 de julho de 2025.'),
        ("1285", "topo", '!!! info "Alterada pela Lei nº 1.394/2025"\n    O [art. 2º](#art-2) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.394/2025]({L("1394", "#art-1", "2022")}), de 15 de julho de 2025.'),
        ("1285", "{ #art-2 }", redacao("1394", L("1394", "#art-1", "2022"), "1º")),
        ("1090", "topo", '!!! info "Alterada pela Lei nº 1.402/2025"\n    Os [arts. 2º](#art-2) e [5º](#art-5) receberam nova redação pelo '
         f'[art. 1º da Lei nº 1.402/2025]({L("1402", "#art-1", "2015")}), de 10 de setembro de 2025.'),
        ("1090", "{ #art-2 }", redacao("1402", L("1402", "#art-1", "2015"), "1º", idx=0)),
        ("1090", "{ #art-5 }", redacao("1402", L("1402", "#art-1", "2015"), "1º", idx=1)),
        ("1210", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1.402/2025]({L("1402", "#art-2", "2019")}), de 10 de setembro de 2025.'),
        ("1229", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pelo '
         f'[art. 2º da Lei nº 1.402/2025]({L("1402", "#art-2", "2020")}), de 10 de setembro de 2025.'),
        ("1350", "topo", '!!! info "Alterada pela Lei nº 1.403/2025"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.403/2025]({L("1403", "", "2024")}), de 2 de outubro de 2025.'),
        ("1148", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pela '
         f'[Lei nº 1.407/2025]({L("1407", "", "2017")}), de 28 de outubro de 2025.'),
        ("1404", "topo", '!!! info "Alterada pela Lei nº 1.414/2025"\n    O [art. 1º](#art-1) recebeu nova redação pelo '
         f'[art. 1º da Lei nº 1.414/2025]({L("1414", "#art-1")}), de 19 de novembro de 2025.'),
        ("1404", "{ #art-1 }", redacao("1414", L("1414", "#art-1"), "1º")),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


def config_2026():
    PDFS = {
        (n, "2026"): (f"lei-{n}-2026.pdf", " (arquivo da prefeitura)")
        for n in [
            "1421", "1422", "1424", "1425", "1426", "1427", "1428",
            "1429", "1430", "1431", "1446", "1449", "1450", "1456",
        ]
    }
    NOTAS = {
        "1432": ['!!! info "Retificação de publicação"\n    Publicada inicialmente com numeração incorreta (Lei nº 1.428) na Edição nº 4083 (Suplemento), de 30 de abril de 2026, página 2, retificada para Lei nº 1.432/2026 em 5 de maio de 2026.'],
    }
    LINKS = {
        "1422": [("Lei nº 1.419, de 19 dezembro de 2025", f"[Lei nº 1.419, de 19 dezembro de 2025]({L('1419')})")],
        "1426": [
            ("Lei nº 1.316, de 17 de abril de 2023", f"[Lei nº 1.316, de 17 de abril de 2023]({L('1316')})"),
            ("Lei nº 1.316 de 17 de abril de 2023", f"[Lei nº 1.316 de 17 de abril de 2023]({L('1316')})"),
        ],
        "1430": [("Lei nº. 1.284, de 12 de maio de 2022", f"[Lei nº. 1.284, de 12 de maio de 2022]({L('1284')})")],
        "1431": [
            ("Lei nº. 1.222/2019", f"[Lei nº. 1.222/2019]({L('1222')})"),
            ("Lei nº. 1.222, de 19 de dezembro de 2019", f"[Lei nº. 1.222, de 19 de dezembro de 2019]({L('1222')})"),
        ],
        "1432": [("Lei Municipal 1.383 de 16 de abril de 2025", f"[Lei Municipal 1.383 de 16 de abril de 2025]({L('1383')})")],
        "1433": [("Lei nº 1.419, de 19 de dezembro de 2025", f"[Lei nº 1.419, de 19 de dezembro de 2025]({L('1419')})")],
        "1435": [("Lei nº 1.100/2015", f"[Lei nº 1.100/2015]({L('1100')})")],
        "1440": [("Lei nº 1.419, de 19 de dezembro de 2025", f"[Lei nº 1.419, de 19 de dezembro de 2025]({L('1419')})")],
        "1443": [
            ("Lei nº 1.090/2015", f"[Lei nº 1.090/2015]({L('1090')})"),
            ("Lei nº 1.402/2025", f"[Lei nº 1.402/2025]({L('1402')})"),
        ],
        "1449": [("Lei nº 1.419, de 19 de dezembro 2025", f"[Lei nº 1.419, de 19 de dezembro 2025]({L('1419')})")],
        "1450": [("Lei Complementar nº 24, de 23 de agosto de 2013", "[Lei Complementar nº 24, de 23 de agosto de 2013](../../plano-diretor/lc-024-2013.md)")],
        "1451": [("Lei Municipal nº 1.240, de 9 de setembro de 2020", f"[Lei Municipal nº 1.240, de 9 de setembro de 2020]({L('1240')})")],
        "1454": [
            ("Lei Municipal n.º 1.449, de 1º de outubro de 2026", f"[Lei Municipal n.º 1.449, de 1º de outubro de 2026]({L('1449')})"),
            ("Lei n.º 1.449, de 1º de outubro", f"[Lei n.º 1.449, de 1º de outubro]({L('1449')})"),
        ],
    }
    EXTERNAS = [
        ("1316", "topo", '!!! info "Alterada pela Lei nº 1.426/2026"\n    Os [arts. 2º](#art-2) e [4º](#art-4) foram alterados pela '
         f'[Lei nº 1.426/2026]({L("1426", "", "2023")}), de 24 de março de 2026.'),
        ("1284", "topo", '!!! info "Alterada pela Lei nº 1.430/2026"\n    O [art. 2º](#art-2) foi alterado pelo '
         f'[art. 1º da Lei nº 1.430/2026]({L("1430", "#art-1", "2022")}), de 9 de abril de 2026.'),
        ("1222", "topo", '!!! info "Alterada pela Lei nº 1.431/2026"\n    O [art. 63](#art-63) foi alterado pela '
         f'[Lei nº 1.431/2026]({L("1431", "", "2019")}), de 9 de abril de 2026.'),
        ("1383", "topo", '!!! info "Alterada pela Lei nº 1.432/2026"\n    Esta lei foi alterada pela '
         f'[Lei nº 1.432/2026]({L("1432", "", "2025")}), de 29 de abril de 2026.'),
        ("1100", "topo", '!!! info "Prazo prorrogado pela Lei nº 1.435/2026"\n    O prazo de vigência do Plano Municipal de Educação foi prorrogado até 31 de dezembro de 2026 pela '
         f'[Lei nº 1.435/2026]({L("1435", "", "2015")}), de 14 de maio de 2026.'),
        ("1090", "topo", '!!! danger "Lei revogada"\n    Esta lei recebeu nova redação / foi revogada pela '
         f'[Lei nº 1.443/2026]({L("1443", "", "2015")}), de 6 de julho de 2026.'),
        ("1402", "topo", '!!! danger "Lei revogada"\n    Esta lei foi revogada pela '
         f'[Lei nº 1.443/2026]({L("1443", "", "2025")}), de 6 de julho de 2026.'),
        ("1240", "topo", '!!! info "Alterada pela Lei nº 1.451/2026"\n    Dispositivos desta lei foram alterados pela '
         f'[Lei nº 1.451/2026]({L("1451", "", "2020")}), de 2 de outubro de 2026.'),
        ("1449", "topo", '!!! info "Alterada pela Lei nº 1.454/2026"\n    O inciso V do [art. 6º](#art-6) foi alterado pela '
         f'[Lei nº 1.454/2026]({L("1454")}), de 27 de outubro de 2026.'),
    ]
    return PDFS, NOTAS, LINKS, EXTERNAS


PDFS, NOTAS, LINKS, EXTERNAS = {"2005": config_2005, "2006": config_2006, "2007": config_2007, "2008": config_2008, "2009": config_2009, "2010": config_2010, "2011": config_2011, "2012": config_2012, "2013": config_2013, "2014": config_2014, "2015": config_2015, "2016": config_2016, "2017": config_2017, "2018": config_2018, "2019": config_2019, "2020": config_2020, "2021": config_2021, "2022": config_2022, "2023": config_2023, "2024": config_2024, "2025": config_2025, "2026": config_2026}[ANO]()


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


DIARIO = "publicação no Diário Oficial dos Municípios (Assomasul)"

# leis cujo arquivo na pasta da prefeitura está vazio (só o cabeçalho com o brasão) e que ainda não foram transcritas
# de outra fonte: ganham uma página que só registra a lei. (ano, número) -> (assunto, data ou None, arquivo)
SEM_TEXTO = {
    ("2017", "1165"): ("Lei de Diretrizes Orçamentárias (LDO) para 2018.", None, "LEI Nº 1165.2017-LDO 2018.doc"),
    ("2017", "1166"): ("Plano Plurianual (PPA) 2018–2021.", None, "LEI Nº 1166.2017-PPA 2018-2021-PLANO PLURIANUAL.doc"),
    ("2017", "1167"): ("Lei Orçamentária Anual (LOA) para 2018.", None, "LEI Nº 1167.2017-LOA 2017-ORÇAMENTO 2018.doc"),
    ("2019", "1220"): ("Lei Orçamentária Anual (LOA) para 2020.", "2019-12-17",
                       "LEI Nº 1.220.2019-LOA 2020 - ROCHA QUE SANCIONOU 17.12.19.doc"),
}


def pagina_sem_texto(num, assunto, data, arq):
    titulo, slug = f"Lei nº {num}/{ANO}", f"lei-{num}-{ANO}"
    obs_data = (" A data vem do nome do arquivo (“sancionou 17.12.19”)." if data else
                " A data da lei não aparece no nome do arquivo e fica em branco até a transcrição.")
    cab = ["---", f'title: "{titulo}"'] + ([f"data: {data}"] if data else []) + [
        f"ementa: {converter.yaml_str(assunto)}", 'extracao: "sem texto"',
        f"fonte_doc: {converter.yaml_str(arq + ' (arquivo da prefeitura, vazio)')}", "revisao: pendente",
        "hide:", "  - toc", "---", "", f"# {titulo}", "", f"> {assunto}", "",
        '!!! warning "Texto não disponível"',
        f"    O arquivo desta lei na pasta da prefeitura (“{arq}”) está vazio: tem só o cabeçalho com o brasão. "
        "O assunto acima vem do nome do arquivo." + obs_data + " O texto ainda não foi transcrito; ele pode ser obtido "
        "na publicação do Diário Oficial dos Municípios (Assomasul) ou na Câmara Municipal.", ""]
    (DOCS / PASTA / f"{slug}.md").write_text("\n".join(cab))
    return {"origem": "doc", "titulo": titulo, "titulo_detectado": titulo, "url": None, "pdf_local": None,
            "fonte_doc": arq + " (arquivo da prefeitura, vazio)", "categoria": PASTA, "categoria_nome": NOME,
            "pagina_origem": None, "arquivo": f"{PASTA}/{slug}.md", "ementa": assunto, "data": data,
            "extracao": "sem texto"}


def fonte_doc(num):
    """Arquivo de onde veio o texto: o .doc da lei; sem ele, o PDF da pasta da prefeitura; sem os dois, o Diário Oficial."""
    nomes = sorted(nfc(f.name) for f in (SCR / "orig").iterdir())
    alts = [num] + ([f"{num[0]}.{num[1:]}"] if len(num) == 4 else [])
    for a in alts:
        if f"LEI Nº {a}.{ANO}.doc" in nomes:
            return f"LEI Nº {a}.{ANO}.doc"
    # arquivos com sufixo no nome (ex.: "LEI Nº 680.2005-PPA.doc"), sem contar as cópias -A4 e os extratos do DO
    return next((n for n in nomes if any(n.upper().startswith(f"LEI Nº {a}.{ANO}-") or n.upper().startswith(f"LEI Nº {a}.") for a in alts)
                 and not any(x in n.upper() for x in ("-A4", "-EXTRATO", "-ANEXO")) and n.endswith(".doc")),
                next((n for n in nomes if n.lower().endswith(".pdf") and any(f" {x}." in n or f" {x}-" in n for x in alts)),
                     DIARIO))


def copiar_imagens(num, slug, texto):
    """Imagens citadas na lei (media/imageN.png, nomes do pandoc) saem de dentro dos .docx da lei e dos anexos
    (docx/LEI Nº num.ANO*.docx) para docs/assets/<slug>/."""
    docxs = [f for f in sorted((SCR / "docx").iterdir()) if nfc(f.name).startswith(f"LEI Nº {num}.{ANO}")]
    destino = DOCS / "assets" / slug
    destino.mkdir(parents=True, exist_ok=True)
    for nome in sorted(set(re.findall(r"\]\(media/([^)\s]+)\)", texto))):
        achados = set()
        for d in docxs:
            with zipfile.ZipFile(d) as z:
                if f"word/media/{nome}" in z.namelist():
                    achados.add(z.read(f"word/media/{nome}"))
        assert len(achados) == 1, (num, nome, len(achados))  # nenhuma, ou nomes iguais com conteúdo diferente
        (destino / nome).write_bytes(achados.pop())
        if nome.lower().endswith((".emf", ".wmf")):
            import subprocess
            subprocess.run(["/Applications/LibreOffice.app/Contents/MacOS/soffice", "--headless",
                            "--convert-to", "png", "--outdir", str(destino), str(destino / nome)],
                           check=True, env={**__import__("os").environ, "HOME": "/tmp"})
            (destino / nome).unlink()


def main():
    nums = sorted(m.group(1) for f in (SCR / "out").iterdir() if (m := re.match(rf"lei-(\d+)-{ANO}\.md", f.name)))
    nums = [n for n in nums if n not in OUTRA_SECAO]
    (DOCS / PASTA).mkdir(parents=True, exist_ok=True)
    fontes_novas = []
    for num in nums:
        r = conv.converter(num)
        texto = r["texto"]
        for a, b in LINKS.get(num, []):
            assert a in texto, (num, a)
            texto = texto.replace(a, b)
        titulo, slug, doc = f"Lei nº {num}/{ANO}", f"lei-{num}-{ANO}", fonte_doc(num)
        if "](media/" in texto:
            copiar_imagens(num, slug, texto)
            texto = re.sub(r"\]\(media/([^)\s]+)\.(?:emf|wmf)\)", rf"](../../assets/{slug}/\1.png)", texto, flags=re.I)
            texto = texto.replace("](media/", f"](../../assets/{slug}/")
        if doc == DIARIO:
            extracao = "publicação no Diário Oficial"
            aviso = ('Transcrito da publicação no Diário Oficial dos Municípios (Assomasul), porque não há arquivo da lei '
                     f'na pasta da prefeitura, e **ainda em revisão**. Esta lei não está publicada na [página de legislação da prefeitura]({LEGIS}).')
        elif (num, ANO) in PDFS and not doc.endswith(".doc"):
            arq, obs, *rot = PDFS[(num, ANO)]
            rot = rot[0] if rot else "cópia assinada e escaneada"
            extracao = "cópia assinada da prefeitura" if "assinada" in rot else "PDF da prefeitura"
            aviso = (f'Transcrito da [{rot}](../../assets/{slug}/{arq}){obs}, porque não há arquivo .doc desta lei na pasta '
                     f'da prefeitura, e **ainda em revisão**. Esta lei não está publicada na [página de legislação da prefeitura]({LEGIS}).')
        elif (num, ANO) in PDFS:
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
               f'extracao: "{extracao}"', f"fonte_doc: {converter.yaml_str(doc if doc == DIARIO else doc + ' (arquivo da prefeitura)')}",
               "revisao: pendente", "hide:", "  - toc", "---", "", f"# {titulo}", "", f"> {r['ementa']}", "",
               f'!!! warning "Texto em revisão"\n    {aviso}', ""]
        for n in NOTAS.get(num, []):
            cab += [n, ""]
        cab += [converter.botoes_download(f"{PASTA}/{slug}.md"), ""]
        (DOCS / PASTA / f"{slug}.md").write_text("\n".join(cab) + "\n" + texto.rstrip() + "\n")
        fontes_novas.append({
            "origem": "doc", "titulo": titulo, "titulo_detectado": titulo, "url": None, "pdf_local": None,
            "fonte_doc": doc if doc == DIARIO else doc + " (arquivo da prefeitura)", "categoria": PASTA, "categoria_nome": NOME,
            "pagina_origem": None, "arquivo": f"{PASTA}/{slug}.md", "ementa": r["ementa"], "data": r["data"],
            "extracao": "doc" if doc.endswith(".doc") else "Diário Oficial" if doc == DIARIO else "PDF"})
    for (ano, num), (assunto, data, arq) in SEM_TEXTO.items():
        if ano == ANO:
            fontes_novas.append(pagina_sem_texto(num, assunto, data, arq))
    for (num, ano), (arq, *_) in PDFS.items():
        if ano == ANO:
            destino = DOCS / "assets" / f"lei-{num}-{ano}"
            destino.mkdir(parents=True, exist_ok=True)
            alts = [num] + ([f"{num[0]}.{num[1:]}"] if len(num) == 4 else [])
            pdf = next(f for f in (SCR / "orig").iterdir() if f.suffix.lower() == ".pdf" and any(f" {a}." in nfc(f.name) for a in alts))
            shutil.copy(pdf, destino / arq)
    for num, onde, nota in EXTERNAS:
        inserir_externa(num, onde, nota)
    arq = RAIZ / "data" / "fontes.json"
    fontes = [f for f in json.loads(arq.read_text()) if f["categoria"] != PASTA] + fontes_novas
    arq.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n")
    outras = [f for f in fontes if f["arquivo"] in {OUTRA_SECAO[n] for n in OUTRA_SECAO if ano_da(n) == ANO}]
    converter.gerar_indice(PASTA, NOME, fontes_novas + outras)
    converter.gerar_indice_grupo("leis-ordinarias", fontes)
    converter.gerar_nav(fontes)
    print(ANO, len(fontes_novas), "leis")


if __name__ == "__main__":
    main()
