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
ULTIMA = {"2001": 541, "2002": 577, "2003": 621, "2004": 639, "2005": 683, "2006": 721, "2007": 750, "2008": 794, "2009": 834, "2010": 890}


def ano_da(num):
    return next(a for a, u in sorted(ULTIMA.items()) if int(num) <= u)


def L(num, alvo="", de=None):
    """Link relativo para outra lei ordinária, a partir de uma página do ano `de` (padrão: o ano montado)."""
    ano, de = ano_da(num), de or ANO
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
    texto = conv.converter(num)["texto"]
    cit = [b for b in texto.split("\n\n") if b.startswith("> “")][idx]
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


PDFS, NOTAS, LINKS, EXTERNAS = {"2005": config_2005, "2006": config_2006, "2007": config_2007, "2008": config_2008, "2009": config_2009, "2010": config_2010}[ANO]()


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
    # arquivos com sufixo no nome (ex.: "LEI Nº 680.2005-PPA.doc"), sem contar as cópias -A4 e os extratos do DO
    return next(n for n in nomes if (n.upper().startswith(f"LEI Nº {num}.{ANO}-") or n.upper().startswith(f"LEI Nº {num}."))
                and not any(x in n.upper() for x in ("-A4", "-EXTRATO", "-ANEXO")) and n.endswith(".doc"))


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
