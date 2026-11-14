"""Leis ordinárias a partir dos .doc da prefeitura: saída do pandoc (.doc -> .docx -> markdown) -> texto no formato do site.

Pasta de trabalho do ano (LDIR), preparada antes:
  orig/  os .doc copiados da pasta da rede
  txt/   os .doc em texto (LibreOffice), usados só na conferência (check.py)
  md2/   os .doc em markdown: soffice --convert-to docx; pandoc -f docx -t markdown-smart-simple_tables-
         multiline_tables-grid_tables-fancy_lists+fancy_lists-header_attributes-bracketed_spans-native_spans-
         link_attributes-line_blocks --wrap=none
Uso: ANO=2005 LDIR=<pasta> python conv.py [número ...]   -> grava LDIR/out/lei-NNN-ANO.md
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

ANO = os.environ.get("ANO", "2005")
SCR = Path(os.environ.get("LDIR", "."))
MESES = {m: i + 1 for i, m in enumerate("janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}

ROT = re.compile(r"^(T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+([IVXL]+|[ÚU]NIC[OA])\b\s*[-–—.:]?\s*(.*)$", re.I)
ANEXO = re.compile(r"^ANEXO\s+([IVXL]+|\d+|[ÚU]NICO)\b\s*[-–—.:]?\s*(.*)$", re.I)
ART = re.compile(r"^Art(?:igo)?\.?\s*(\d+)\s*(?:[º°ºo]|\.º)?\s*(-[A-Z]\b)?\s*[.\-–—:]*\s*", re.I)
PAR = re.compile(r"^§\s*(\d+)\s*[º°o]?\s*[.\-–—:]*\s*")
UNICO = re.compile(r"^Par[áa]grafo\s+[úu]nico\s*[.\-–—:]*\s*", re.I)
INC = re.compile(r"^([IVXL]+)\s*[-–—]+\s*(?=\S)")
ALI = re.compile(r"^([a-z])\s*(?:\)\s*[-–—]?|[-–]\s)\s*")
NIVEL = {"TÍTULO": "##", "CAPÍTULO": "###", "SEÇÃO": "####", "SUBSEÇÃO": "#####"}
LISTA = re.compile(r"^\s*([IVXL]+|[a-z])([.)])\s+(?=\S)")
CARGO = re.compile(r"^(\d+)\s+(CC\s*\d+\s*-.*?)\s+R\\\$\s*([\d.,]+)$")
TOTAL = re.compile(r"^\*\*TOTAL\s*-\s*R\\\$\s*([\d.,]+)\*\*$")

# leis do orçamento em que o Word pôs cada coluna das tabelas numa célula só
ORCAMENTOS = {("681", "2005"), ("718", "2006"), ("750", "2007"), ("794", "2008"), ("834", "2009"), ("889", "2010")}
# anexos desenhados no Word que viram imagem: (ano, lei) -> (começo do trecho a cortar, markdown no lugar)
MAPAS = {}
# arquivos extras (anexos em .doc separados) a juntar no fim da lei: (ano, lei) -> [nomes em md2/ ou "md:texto"]
EXTRAS = {}
# acertos pontuais no texto final: (ano, lei) -> [(trecho, novo)]
CORRECOES = {
    ("2010", "836"): [
        (
            "#### SEÇÃO I { .centro }\n\n**Da Finalidade do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital**",
            "#### SEÇÃO I — Da Finalidade do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital { .centro }",
        ),
        (
            "#### SEÇÃO II { .centro }\n\n**Das Obrigações do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital**",
            "#### SEÇÃO II — Das Obrigações do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital { .centro }",
        ),
        (
            "#### SEÇÃO III { .centro }\n\n**Dos Princípios e Diretrizes do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital**",
            "#### SEÇÃO III — Dos Princípios e Diretrizes do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital { .centro }",
        ),
        (
            "#### SEÇÃO I { .centro }\n\n**Da Criação do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital**",
            "#### SEÇÃO I — Da Criação do Conselho Gestor do TELECENTRO COMUNITÁRIO Projeto de Inclusão Digital { .centro }",
        ),
        (
            "#### SEÇÃO II { .centro }\n\n**Da Composição do Conselho Gestor**",
            "#### SEÇÃO II — Da Composição do Conselho Gestor { .centro }",
        ),
        (
            "#### SEÇÃO III { .centro }\n\n**Da Estrutura e do Funcionamento do Conselho Gestor**",
            "#### SEÇÃO III — Da Estrutura e do Funcionamento do Conselho Gestor { .centro }",
        ),
        ("VIII\\. ", "VIII - "),
        ("VII\\. ", "VII - "),
        ("III\\. ", "III - "),
        ("II\\. ", "II - "),
        ("IV\\. ", "IV - "),
        ("VI\\. ", "VI - "),
        ("IX\\. ", "IX - "),
        ("XI\\. ", "XI - "),
        ("**Art. 11.** mandato", "**Art. 11.** O mandato"),
    ],
    ("2010", "837"): [
        (
            "### CAPÍTULO L — DA NATUREZA E FINALIDADE { .centro }",
            "### CAPÍTULO I — DA NATUREZA E FINALIDADE { .centro }",
        ),
        ("### CAPÍTULO LL { .centro }", "### CAPÍTULO II { .centro }"),
        ("l) elaborar", "I - elaborar"),
        ("l) sejam assíduos", "I - sejam assíduos"),
        ("**Art. 10.** CMAS", "**Art. 10.** O CMAS"),
        ("**Art. 14.** Órgão Público", "**Art. 14.** O Órgão Público"),
        ("em outros espaços;\\]", "em outros espaços;"),
    ],
    ("2010", "842"): [("**JOSÉ CALDETO TOMAELLO*,***", "**JOSÉ CALDETO TOMAELLO**,")],
    ("2010", "847"): [
        (
            "## ANEXO ÚNICO — QUADRO I { #anexo-unico .centro }\n\nCARGOS EFETIVOS",
            "## ANEXO ÚNICO { #anexo-unico .centro }\n\n**QUADRO I — CARGOS EFETIVOS**\n{ .centro }",
        ),
        ("QUADRO II\n\nCARGOS COMISSIONADOS", "**QUADRO II — CARGOS COMISSIONADOS**\n{ .centro }"),
    ],
    ("2010", "849"): [("“**SANTO BENEDITO DE SÁ”**,", "**“SANTO BENEDITO DE SÁ”**,")],
    ("2010", "850"): [
        (
            "> § 1º\n>\n> ...............................................................................................................................................",
            "> § 1º ........................................................................................................................................",
        ),
        (
            "> I -\n>\n> II -\n>\n> III -\n>\n> IV -\n>\n> V -\n>\n> VI -\n>\n> VII - Carteira Nacional de Habilitação, na Categoria B, quando não habilitado, tem o prazo de 06 (seis) meses após a posse, para apresentá-la.\n>\n> VIII -\n>\n> IX -\n>\n> X -\n>\n> XI -\n>\n> XII - ”",
            "> I - .......................................................................................................................\n>\n> II - ................................\n>\n> III - ............................\n>\n> IV - ..........................\n>\n> V - .............................\n>\n> VI - ...........................\n>\n> VII - Carteira Nacional de Habilitação, na Categoria B, quando não habilitado, tem o prazo de 06 (seis) meses após a posse, para apresentá-la.\n>\n> VIII - ........................\n>\n> IX - ............................\n>\n> X - ..............................\n>\n> XI - .............................\n>\n> XII - ............................”",
        ),
    ],
    ("2010", "854"): [("**VALDINEI DE SOUZA*,***", "**VALDINEI DE SOUZA**,")],
    ("2010", "856"): [
        (
            "*é destina à **ÁREA DE INTERESSE PÚBLICO.***",
            "é destina à **ÁREA DE INTERESSE PÚBLICO.**",
        ),
    ],
    ("2010", "859"): [
        ("\n\nI-\n\n", "\n\nI -\n\n"),
        ("\n\nII-\n\n", "\n\nII -\n\n"),
        ("\n\nIII-\n\n", "\n\nIII -\n\n"),
        ("\n\nIV-\n\n", "\n\nIV -\n\n"),
    ],
    ("2010", "861"): [
        ("DAS DISPOSIÇÕES PRELIMINARES", "**DAS DISPOSIÇÕES PRELIMINARES**\n{ .centro }"),
        (
            "### CAPÍTULO I — DAS PRIORIDADES E METAS DA { .centro }\n\n**ADMINISTRAÇÃO PÚBLICA MUNICIPAL**",
            "### CAPÍTULO I — DAS PRIORIDADES E METAS DA ADMINISTRAÇÃO PÚBLICA MUNICIPAL { .centro }",
        ),
        (
            "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO { .centro }\n\n**DOS ORÇAMENTOS**",
            "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO DOS ORÇAMENTOS { .centro }",
        ),
        (
            "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS { .centro }\n\n**PARA O PODER LEGISLATIVO**",
            "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS PARA O PODER LEGISLATIVO { .centro }",
        ),
        (
            "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO { .centro }\n\n**DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES**",
            "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES { .centro }",
        ),
        (
            "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS { .centro }\n\n**FISCAL E DA SEGURIDADE SOCIAL**",
            "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS FISCAL E DA SEGURIDADE SOCIAL { .centro }",
        ),
        (
            "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS { .centro }\n\n**DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO**",
            "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO { .centro }",
        ),
        (
            "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS { .centro }\n\n**COM PESSOAL E ENCARGOS SOCIAIS**",
            "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS COM PESSOAL E ENCARGOS SOCIAIS { .centro }",
        ),
        (
            "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS { .centro }\n\n**E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS**",
            "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS { .centro }",
        ),
        ("§ 2º º", "§ 2º"),
        ("§ 3º º", "§ 3º"),
        ("§ 4º º", "§ 4º"),
    ],
    ("2010", "863"): [("II\\_ cometam", "II - cometam")],
    ("2010", "865"): [("**X.** Lanchonetes.", "X - Lanchonetes.")],
    ("2010", "867"): [
        (
            "I - *Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;*",
            "I - Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;",
        ),
        (
            "a) Os Secretários Municipais, como agente políticos, serão escolhidos dentre brasileiros maiores de 21 anos, no exercício dos direitos políticos;*",
            "a) Os Secretários Municipais, como agente políticos, serão escolhidos dentre brasileiros maiores de 21 anos, no exercício dos direitos políticos;",
        ),
        (
            "b) Compete ainda aos Secretários Municipais além das atribuições estabelecidas na Lei Orgânica e na Lei; exercer a orientação, coordenação e supervisão dos órgãos e entidades da administração municipal, na área de sua competência e referendar os atos e decretos assinados pelo Prefeito Municipal;*",
            "b) Compete ainda aos Secretários Municipais além das atribuições estabelecidas na Lei Orgânica e na Lei; exercer a orientação, coordenação e supervisão dos órgãos e entidades da administração municipal, na área de sua competência e referendar os atos e decretos assinados pelo Prefeito Municipal;",
        ),
    ],
    ("2010", "868"): [
        ("\n\nI-\n\n", "\n\nI -\n\n"),
        ("\n\nII-\n\n", "\n\nII -\n\n"),
        ("\n\nIII-\n\n", "\n\nIII -\n\n"),
        ("\n\nIV-\n\n", "\n\nIV -\n\n"),
        ("\n\nV-\n\n", "\n\nV -\n\n"),
    ],
    ("2010", "869"): [
        (
            "> ***“Art.6º.** A competente Escritura de doação do imóvel será feita em nome do beneficiário ou de pessoa jurídica de sua propriedade.*",
            "> “Art.6º. A competente Escritura de doação do imóvel será feita em nome do beneficiário ou de pessoa jurídica de sua propriedade.",
        ),
    ],
    ("2010", "870"): [
        (
            "> ***“Art.6º.** A competente Escritura de doação do imóvel será feita em nome do beneficiário ou de pessoa jurídica de sua propriedade.*",
            "> “Art.6º. A competente Escritura de doação do imóvel será feita em nome do beneficiário ou de pessoa jurídica de sua propriedade.",
        ),
    ],
    ("2010", "886"): [("\n\n.\n\n", "\n\n")],
    ("2010", "889"): [
        ("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**\n\n2.  ", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**"),
    ],
    ("2009", "802"): [
        (
            "> “Art. 3º - .........\n>\n> I -\n>\n> a)\n>\n> b)\n>\n> II -\n>\n> III -\n>\n> IV -\n>\n> V - Nível de Atuação Diversa, voltado aos serviços de estafeta, guardador, “office-boy”, segurança, e etc; ocupantes de Cargo em Comissão símbolo CC6-01;\n>\n> VI -\n>\n> VII -\n>\n> VIII -\n>\n> IX - ”",
            "> “Art. 3º - .........\n>\n> I - ......................\n>\n> a) ................\n>\n> b) ...................\n>\n> II - ....................\n>\n> III - .....................\n>\n> IV - ...................\n>\n> V - Nível de Atuação Diversa, voltado aos serviços de estafeta, guardador, “office-boy”, segurança, e etc; ocupantes de Cargo em Comissão símbolo CC6-01;\n>\n> VI - .....................\n>\n> VII - ..........................\n>\n> VIII - ..........................\n>\n> IX - .....................”",
        ),
    ],
    ("2009", "803"): [("Parágrafo único. A** presente", "Parágrafo único. A presente")],
    ("2009", "808"): [("> § 1º\n>\n> § 2º ”", "> § 1º ........\n>\n> § 2º .......”")],
    ("2009", "812"): [
        (
            "| Fundo Municipal de Turismo – Lei nº 495/01 |  |  |  |  |\n\n| Fundo De Desenvolvimento Municipal – Lei nº 311/95 |  |  |  |  |\n|:--------------------|------------|------------|------------|-------------|",
            "| Fundo Municipal de Turismo – Lei nº 495/01 |  |  |  |  |\n| Fundo De Desenvolvimento Municipal – Lei nº 311/95 |  |  |  |  |",
        ),
        (
            "***Edson Peres Ibrahim***\n\n***Prefeito Municipal***",
            "**Edson Peres Ibrahim**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }",
        ),
    ],
    ("2009", "815"): [
        ("DAS DISPOSIÇÕES PRELIMINARES", "**DAS DISPOSIÇÕES PRELIMINARES**\n{ .centro }"),
        (
            "### CAPÍTULO I — DAS PRIORIDADES E METAS DA { .centro }\n\n**ADMINISTRAÇÃO PÚBLICA MUNICIPAL**",
            "### CAPÍTULO I — DAS PRIORIDADES E METAS DA ADMINISTRAÇÃO PÚBLICA MUNICIPAL { .centro }",
        ),
        (
            "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO { .centro }\n\n**DOS ORÇAMENTOS**",
            "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO DOS ORÇAMENTOS { .centro }",
        ),
        (
            "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS { .centro }\n\n**PARA O PODER LEGISLATIVO**",
            "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS PARA O PODER LEGISLATIVO { .centro }",
        ),
        (
            "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO { .centro }\n\n**DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES**",
            "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES { .centro }",
        ),
        (
            "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS { .centro }\n\n**FISCAL E DA SEGURIDADE SOCIAL**",
            "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS FISCAL E DA SEGURIDADE SOCIAL { .centro }",
        ),
        (
            "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS { .centro }\n\n**DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO**",
            "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO { .centro }",
        ),
        (
            "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS { .centro }\n\n**COM PESSOAL E ENCARGOS SOCIAIS**",
            "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS COM PESSOAL E ENCARGOS SOCIAIS { .centro }",
        ),
        (
            "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS { .centro }\n\n**E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS**",
            "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS { .centro }",
        ),
    ],
    ("2009", "820"): [("\\^", "°")],
    ("2009", "826"): [("**Parágrafo Primeiro-**", "§ 1º"), ("**Parágrafo Segundo-**", "§ 2º")],
    ("2009", "827"): [("**JOSÉ APARECIDO ZACCHI – ME*,***", "**JOSÉ APARECIDO ZACCHI – ME**,")],
    ("2009", "830"): [
        (
            ">I- Adequação das instalações gerais para o ensino e para aquisição de mobiliários e equipamentos a partir de padrões mínimos de funcionamento das escolas e da acessibilidade;</p>\n<p id=\"adequação-eou-construção-de-quadras-de-esportes-nas-escolas-da-rede-municipal-de-ensino-adotando-os-padrões-mínimos-e-considerando-a-acessibilidade\" class=\"heading\">Adequação e/ou construção de quadras de esportes nas escolas da rede municipal de Ensino adotando os padrões mínimos, e considerando a acessibilidade;</p>\n<p id=\"adequação-eou-construção-de-bibliotecas-escolares-e-equipa-las-adotando-os-padrões-mínimos-de-funcionamento-das-escolas-e-considerando-a-acessibilidade\" class=\"heading\">Adequação e/ou construção de bibliotecas escolares e equipa-las adotando os padrões mínimos de funcionamento das escolas e considerando a acessibilidade;</p>\n<p id=\"adequação-dos-espaços-escolares-às-pessoas-com-deficiência-eou-mobilidade-reduzida-e-para-aquisição-de-mobiliário-e-equipamentos\" class=\"heading\">Adequação dos espaços escolares às pessoas com deficiência e/ou mobilidade reduzida e para aquisição de mobiliário e equipamentos;</p>\n<p id=\"outros-equipamentos-eou-mobiliários-que-poderão-ser-criados-para-a-melhoria-na-utilização-dos-programas-de-acessibilidade.\" class=\"heading\">.Outros equipamentos e/ou mobiliários que poderão ser criados, para a melhoria na utilização dos Programas de Acessibilidade.</p>",
            ">I - Adequação das instalações gerais para o ensino e para aquisição de mobiliários e equipamentos a partir de padrões mínimos de funcionamento das escolas e da acessibilidade;</p>\n<p id=\"adequação-eou-construção-de-quadras-de-esportes-nas-escolas-da-rede-municipal-de-ensino-adotando-os-padrões-mínimos-e-considerando-a-acessibilidade\" class=\"heading\">II - Adequação e/ou construção de quadras de esportes nas escolas da rede municipal de Ensino adotando os padrões mínimos, e considerando a acessibilidade;</p>\n<p id=\"adequação-eou-construção-de-bibliotecas-escolares-e-equipa-las-adotando-os-padrões-mínimos-de-funcionamento-das-escolas-e-considerando-a-acessibilidade\" class=\"heading\">III - Adequação e/ou construção de bibliotecas escolares e equipa-las adotando os padrões mínimos de funcionamento das escolas e considerando a acessibilidade;</p>\n<p id=\"adequação-dos-espaços-escolares-às-pessoas-com-deficiência-eou-mobilidade-reduzida-e-para-aquisição-de-mobiliário-e-equipamentos\" class=\"heading\">IV - Adequação dos espaços escolares às pessoas com deficiência e/ou mobilidade reduzida e para aquisição de mobiliário e equipamentos;</p>\n<p id=\"outros-equipamentos-eou-mobiliários-que-poderão-ser-criados-para-a-melhoria-na-utilização-dos-programas-de-acessibilidade.\" class=\"heading\">V - Outros equipamentos e/ou mobiliários que poderão ser criados, para a melhoria na utilização dos Programas de Acessibilidade.</p>",
        ),
        (
            "***Edson Peres Ibrahim***\n\n***Prefeito Municipal***",
            "**Edson Peres Ibrahim**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }",
        ),
    ],
    ("2009", "832"): [('<span class="mark"></span>\n\n', "")],
    ("2009", "833"): [
        (
            "### CAPÍTULO I { .centro }\n\n**Disposições Preliminares**",
            "### CAPÍTULO I — Disposições Preliminares { .centro }",
        ),
        (
            "### CAPÍTULO II { .centro }\n\n**Definição de Pequeno Empresário, Microempresa e Empresa de Pequeno Porte**",
            "### CAPÍTULO II — Definição de Pequeno Empresário, Microempresa e Empresa de Pequeno Porte { .centro }",
        ),
        (
            "#### SEÇÃO I { .centro }\n\n**Do Pequeno Empresário**",
            "#### SEÇÃO I — Do Pequeno Empresário { .centro }",
        ),
        (
            "#### SEÇÃO II { .centro }\n\n**Da Microempresa e da Empresa de Pequeno Portes**",
            "#### SEÇÃO II — Da Microempresa e da Empresa de Pequeno Portes { .centro }",
        ),
        (
            "### CAPÍTULO II { .centro }\n\n**Da Inscrição e Baixa**",
            "### CAPÍTULO II — Da Inscrição e Baixa { .centro }",
        ),
        (
            "### CAPÍTULO IV { .centro }\n\n**Dos Tributos e Contribuições**",
            "### CAPÍTULO IV — Dos Tributos e Contribuições { .centro }",
        ),
        (
            "### CAPÍTULO V { .centro }\n\n**Do Acesso aos Mercados**",
            "### CAPÍTULO V — Do Acesso aos Mercados { .centro }",
        ),
        (
            "#### SEÇÃO I { .centro }\n\n**Acesso às Compras Públicas**",
            "#### SEÇÃO I — Acesso às Compras Públicas { .centro }",
        ),
        (
            "#### SEÇÃO II { .centro }\n\n**Estímulo ao Mercado Local**",
            "#### SEÇÃO II — Estímulo ao Mercado Local { .centro }",
        ),
        (
            "### CAPÍTULO VI { .centro }\n\n**Das Relações do Trabalho**",
            "### CAPÍTULO VI — Das Relações do Trabalho { .centro }",
        ),
        (
            "#### SEÇÃO I { .centro }\n\n**Da Segurança e da Medicina do Trabalho**",
            "#### SEÇÃO I — Da Segurança e da Medicina do Trabalho { .centro }",
        ),
        (
            "### CAPÍTULO VII { .centro }\n\n**Da Fiscalização Orientadora**",
            "### CAPÍTULO VII — Da Fiscalização Orientadora { .centro }",
        ),
        (
            "### CAPÍTULO VIII { .centro }\n\n**Do Associativismo**",
            "### CAPÍTULO VIII — Do Associativismo { .centro }",
        ),
        (
            "### CAPÍTULO IX { .centro }\n\n**Do Estímulo ao Crédito e Capitalização**",
            "### CAPÍTULO IX — Do Estímulo ao Crédito e Capitalização { .centro }",
        ),
        (
            "### CAPÍTULO X { .centro }\n\n**Do Estímulo à Inovação**",
            "### CAPÍTULO X — Do Estímulo à Inovação { .centro }",
        ),
        (
            "#### SEÇÃO I { .centro }\n\n**Disposições Gerais**",
            "#### SEÇÃO I — Disposições Gerais { .centro }",
        ),
        (
            "#### SEÇÃO II { .centro }\n\n**Do Apoio à Inovação**",
            "#### SEÇÃO II — Do Apoio à Inovação { .centro }",
        ),
        (
            "##### SUBSEÇÃO I { .centro }\n\n**Da Gestão da Inovação**",
            "##### SUBSEÇÃO I — Da Gestão da Inovação { .centro }",
        ),
        (
            "##### SUBSEÇÃO II { .centro }\n\n**Do Fundo Municipal de Inovação Tecnológica**",
            "##### SUBSEÇÃO II — Do Fundo Municipal de Inovação Tecnológica { .centro }",
        ),
        (
            "##### SUBSEÇÃO III { .centro }\n\n**Da Suplementação pelo Município de Projetos de Fomento à Inovação**",
            "##### SUBSEÇÃO III — Da Suplementação pelo Município de Projetos de Fomento à Inovação { .centro }",
        ),
        (
            "##### SUBSEÇÃO IV { .centro }\n\n**Dos Incentivos Fiscais e à Inovação**",
            "##### SUBSEÇÃO IV — Dos Incentivos Fiscais e à Inovação { .centro }",
        ),
        (
            "##### SUBSEÇÃO V { .centro }\n\n**Do Ambiente de Apoio à Inovação**",
            "##### SUBSEÇÃO V — Do Ambiente de Apoio à Inovação { .centro }",
        ),
        (
            "### CAPÍTULO XI { .centro }\n\n**Do Acesso à Justiça**",
            "### CAPÍTULO XI — Do Acesso à Justiça { .centro }",
        ),
        (
            "### CAPÍTULO XII { .centro }\n\n**Da Agropecuária e dos Pequenos Produtores Rurais**",
            "### CAPÍTULO XII — Da Agropecuária e dos Pequenos Produtores Rurais { .centro }",
        ),
        (
            "### CAPÍTULO XIII { .centro }\n\n**Da Educação Empreendedora e do Acesso à Informação**",
            "### CAPÍTULO XIII — Da Educação Empreendedora e do Acesso à Informação { .centro }",
        ),
        (
            "### CAPÍTULO XIV { .centro }\n\n**Da Responsabilidade Social, Comércio Justo e Solidário e Meio Ambiente**",
            "### CAPÍTULO XIV — Da Responsabilidade Social, Comércio Justo e Solidário e Meio Ambiente { .centro }",
        ),
        ("I - inovação:**", "I - **inovação:**"),
        ("II - agência de fomento:**", "II - **agência de fomento:**"),
        (
            "III - instituição científica e tecnológica – ICT:**",
            "III - **instituição científica e tecnológica – ICT:**",
        ),
        (
            "IV - núcleo de inovação tecnológica:**",
            "IV - **núcleo de inovação tecnológica:**",
        ),
        ("V - instituição de apoio:**", "V - **instituição de apoio:**"),
        ("VI - incubadora de empresas:**", "VI - **incubadora de empresas:**"),
        ("VII - parque tecnológico:**", "VII - **parque tecnológico:**"),
        ("VIII - condomínios empresariais:**", "VIII - **condomínios empresariais:**"),
        ("para 2% (dois por cento);**", "para 2% (dois por cento);"),
    ],
    ("2009", "834"): [
        ("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**\n\n2.  ", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**"),
    ],
    ("2008", "755"): [("**MARIO DA SILVA PAIÃO - ME*,***", "**MARIO DA SILVA PAIÃO - ME**,")],
    ("2008", "756"): [("***Prefeito Municipal***", "Prefeito Municipal\n{ .centro }")],
    ("2008", "760"): [("***Prefeito Municipal***", "Prefeito Municipal\n{ .centro }")],
    ("2008", "764"): [("**CONFECÇÔES D´LAFORET LTDA – ME*,***", "**CONFECÇÔES D´LAFORET LTDA – ME**,")],
    ("2008", "769"): [("**Art. 4º-O.** Conselho", "**Art. 4º** O Conselho"),
                      ("{ #art-4-o }", "{ #art-4 }"),
                      ("**Art. 5º-O.** Conselho", "**Art. 5º** O Conselho"),
                      ("{ #art-5-o }", "{ #art-5 }")],
    ("2008", "772"): [("**Art. 4º-O.** mandato", "**Art. 4º** O mandato"),
                      ("{ #art-4-o }", "{ #art-4 }"),
                      ("§-2º- As deliberações", "§ 2º As deliberações"),
                      ("**Art. 11-A.** organização", "**Art. 11.** A organização"),
                      ("{ #art-11-a }", "{ #art-11 }")],
    ("2008", "779"): [("DAS DISPOSIÇÕES PRELIMINARES", "**DAS DISPOSIÇÕES PRELIMINARES**\n{ .centro }"),
                      ("### CAPÍTULO I — DAS PRIORIDADES E METAS DA { .centro }\n\n**ADMINISTRAÇÃO PÚBLICA MUNICIPAL**",
                       "### CAPÍTULO I — DAS PRIORIDADES E METAS DA ADMINISTRAÇÃO PÚBLICA MUNICIPAL { .centro }"),
                      ("### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO { .centro }\n\n**DOS ORÇAMENTOS**",
                       "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO DOS ORÇAMENTOS { .centro }"),
                      ("### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS { .centro }\n\n**PARA O PODER LEGISLATIVO**",
                       "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS PARA O PODER LEGISLATIVO { .centro }"),
                      ("### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO { .centro }\n\n**DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES**",
                       "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES { .centro }"),
                      ("### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS { .centro }\n\n**FISCAL E DA SEGURIDADE SOCIAL**",
                       "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS FISCAL E DA SEGURIDADE SOCIAL { .centro }"),
                      ("### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS { .centro }\n\n**DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO**",
                       "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO { .centro }"),
                      ("### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS { .centro }\n\n**COM PESSOAL E ENCARGOS SOCIAIS**",
                       "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS COM PESSOAL E ENCARGOS SOCIAIS { .centro }"),
                      ("### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS { .centro }\n\n**E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS**",
                       "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS { .centro }"),
                      ("***Prefeito Municipal***", "Prefeito Municipal\n{ .centro }")],
    ("2008", "781"): [("**Arrecadação do primeiro período/2007**\n{ .centro }", "Arrecadação do primeiro período/2007"),
                      ("1.  Arrecadação", "1\\. Arrecadação"), ("2.  Arrecadação", "2\\. Arrecadação"),
                      ("3.  Receita", "3\\. Receita")],
    ("2008", "783"): [("**MARIA ERCILIA HENNES DA SILVA - ME*,***", "**MARIA ERCILIA HENNES DA SILVA - ME**,")],
    ("2008", "788"): [("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2008", "789"): [("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2008", "791"): [("III - estabelecer padrões e normas para a adequada prestação dos serviços e para a satisfação dos usuários;**",
                       "III - estabelecer padrões e normas para a adequada prestação dos serviços e para a satisfação dos usuários;"),
                      ("**Art. 9º** Fica o Município autorizado realizar a cessão onerosa da rede de esgoto já existente, mediante avaliação, utilizando o valor correspondente para a compensação de débitos vencidos e vincendos com a Sanesul.**",
                       "**Art. 9º** Fica o Município autorizado realizar a cessão onerosa da rede de esgoto já existente, mediante avaliação, utilizando o valor correspondente para a compensação de débitos vencidos e vincendos com a Sanesul."),
                      ("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2008", "792"): [("I - *Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;*",
                       "I - Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;"),
                      ("a) Os Secretários Municipais, como agente políticos, serão escolhidos dentre brasileiros maiores de 21 anos, no exercício dos direitos políticos;*",
                       "a) Os Secretários Municipais, como agente políticos, serão escolhidos dentre brasileiros maiores de 21 anos, no exercício dos direitos políticos;"),
                      ("b) Compete ainda aos Secretários Municipais além das atribuições estabelecidas na Lei Orgânica e na Lei; exercer a orientação, coordenação e supervisão dos órgãos e entidades da administração municipal, na área de sua competência e referendar os atos e decretos assinados pelo Prefeito Municipal;*",
                       "b) Compete ainda aos Secretários Municipais além das atribuições estabelecidas na Lei Orgânica e na Lei; exercer a orientação, coordenação e supervisão dos órgãos e entidades da administração municipal, na área de sua competência e referendar os atos e decretos assinados pelo Prefeito Municipal;")],
    ("2008", "793"): [("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2008", "794"): [("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**")],
    ("2007", "725"): [("### CAPÍTULO I { .centro }\n\n**Das Disposições Preliminares**",
                       "### CAPÍTULO I — Das Disposições Preliminares { .centro }"),
                      ("### CAPÍTULO II { .centro }\n\nDa composição",
                       "### CAPÍTULO II — Da composição { .centro }"),
                      ("### CAPÍTULO III { .centro }\n\n**Das Competências do Conselho do FUNDEB**",
                       "### CAPÍTULO III — Das Competências do Conselho do FUNDEB { .centro }"),
                      ("### CAPÍTULO IV { .centro }\n\nDas Disposições Finais",
                       "### CAPÍTULO IV — Das Disposições Finais { .centro }"),
                      ("§ 5º São impedidos de integrar o Conselho do FUNDEB:**",
                       "§ 5º São impedidos de integrar o Conselho do FUNDEB:"),
                      ("***Dr. Jercé Eusébio de Souza***\n\n**Prefeito Municipal**\n{ .centro }",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }"),
                      ("**José Antonio Frutuoso**\n{ .centro }\n\nSecretário",
                       "**José Antonio Frutuoso**\n{ .centro }\n\nSecretário\n{ .centro }")],
    ("2007", "726"): [("I - Remuneração**:\u00a0o total", "I - **Remuneração**: o total"),
                      ("***Dr. Jercé Eusébio de Souza***\n\n**Prefeito Municipal**\n{ .centro }",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2007", "727"): [("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2007", "728"): [("***Dr. Jercé Eusébio de Souza***\n\n**Prefeito Municipal**\n{ .centro }",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2007", "729"): [("***Prefeito Municipal***", "Prefeito Municipal\n{ .centro }")],
    ("2007", "731"): [("***Dr. Jercé Eusébio de Souza***\n\n***Prefeito Municipal***",
                       "**Dr. Jercé Eusébio de Souza**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }")],
    ("2007", "734"): [("DAS DISPOSIÇÕES PRELIMINARES", "**DAS DISPOSIÇÕES PRELIMINARES**\n{ .centro }"),
                      ("### CAPÍTULO I — DAS PRIORIDADES E METAS DA { .centro }\n\n**ADMINISTRAÇÃO PÚBLICA MUNICIPAL**",
                       "### CAPÍTULO I — DAS PRIORIDADES E METAS DA ADMINISTRAÇÃO PÚBLICA MUNICIPAL { .centro }"),
                      ("### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO { .centro }\n\n**DOS ORÇAMENTOS**",
                       "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO DOS ORÇAMENTOS { .centro }"),
                      ("### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS { .centro }\n\n**PARA O PODER LEGISLATIVO**",
                       "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS PARA O PODER LEGISLATIVO { .centro }"),
                      ("### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO { .centro }\n\n**DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES**",
                       "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES { .centro }"),
                      ("### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS { .centro }\n\n**FISCAL E DA SEGURIDADE SOCIAL**",
                       "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS FISCAL E DA SEGURIDADE SOCIAL { .centro }"),
                      ("### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS { .centro }\n\n**DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO**",
                       "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO { .centro }"),
                      ("### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS { .centro }\n\n**COM PESSOAL E ENCARGOS SOCIAIS**",
                       "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS COM PESSOAL E ENCARGOS SOCIAIS { .centro }"),
                      ("### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS { .centro }\n\n**E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS**",
                       "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS { .centro }"),
                      ("***Prefeito Municipal***", "Prefeito Municipal\n{ .centro }")],
    ("2007", "741"): [("**Arrecadação do primeiro período/2006**\n{ .centro }", "Arrecadação do primeiro período/2006"),
                      ("1.  Arrecadação", "1\\. Arrecadação"), ("2.  Arrecadação", "2\\. Arrecadação"),
                      ("3.  Receita", "3\\. Receita")],
    ("2007", "746"): [("\\]Prefeitura", "Prefeitura")],
    ("2007", "748"): [("**MARIA ERCILIA HENNES DA SILVA - ME*,***", "**MARIA ERCILIA HENNES DA SILVA - ME**,")],
    ("2007", "750"): [("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**")],
    ("2006", "718"): [("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**")],
    ("2006", "719"): [("**DO CONSELHO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO**\n\n**ADOLESCENTE**",
                       "**DO CONSELHO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO ADOLESCENTE**"),
                      ("**DO FUNDO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO**\n\n**ADOLESCENTE**\n",
                       "**DO FUNDO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO ADOLESCENTE**\n{ .centro }\n"),
                      ("**DA ESTRUTURA**\n", "**DA ESTRUTURA**\n{ .centro }\n"),
                      ("**DO CONTROLE DO CONSELHO TUTELAR**\n", "**DO CONTROLE DO CONSELHO TUTELAR**\n{ .centro }\n"),
                      ("**DO PROCESSO DISCIPLINAR**\n", "**DO PROCESSO DISCIPLINAR**\n{ .centro }\n"),
                      ("**DAS DISPOSIÇÕES FINAIS**\n", "**DAS DISPOSIÇÕES FINAIS**\n{ .centro }\n")],
    ("2006", "708"): [("**Arrecadação do primeiro período/2005**\n{ .centro }", "Arrecadação do primeiro período/2005"),
                      ("1.  Arrecadação", "1\\. Arrecadação"), ("2.  Arrecadação", "2\\. Arrecadação"),
                      ("3.  Receita", "3\\. Receita")],
    ("2005", "681"): [("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**")],
    ("2005", "656"): [("1.  Identificação do Projeto:", "1\\. Identificação do Projeto:"),
                      ("1.  \\- Título", "1.1 - Título"), ("2.  \\- Área", "1.2 - Área"), ("3.  \\- Público", "1.3 - Público"),
                      ("4.  \\- 100 pessoas", "1.4 - 100 pessoas"), ("5.  \\- Duração", "1.5 - Duração")],
    ("2005", "668"): [("> *“**Art 4º-** O Conselho Municipal do Meio Ambiente C.M.M.A será composto por representantes a saber:*\n\n"
                       "a) 08 (oito) do Poder Público;*\n\nb) 08 (oito) da Sociedade Civil.”*\n\n§ 1º ",
                       "> “Art 4º- O Conselho Municipal do Meio Ambiente C.M.M.A será composto por representantes a saber:\n>\n"
                       "> a) 08 (oito) do Poder Público;\n>\n> b) 08 (oito) da Sociedade Civil.”\n>\n> § 1º "),
                      ("\n\n§ 2º O exercício das funções", "\n>\n> § 2º O exercício das funções"),
                      ("Política Municipal do Meio Ambiente.*", "Política Municipal do Meio Ambiente."),
                      ("relevante interesse público.”*", "relevante interesse público.”")],
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def plano(s):
    """Texto sem a marcação do markdown, para reconhecer o que é cada parágrafo."""
    s = re.sub(r"^(>\s*)+", "", s.strip())
    s = re.sub(r"^#+\s*", "", s)
    s = s.replace("**", "").replace("\\", "")
    s = re.sub(r"(?<!\w)\*|\*(?!\w)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def tira_rotulo(md, n):
    """Tira do começo do parágrafo em markdown os primeiros n caracteres do texto plano (o rótulo)."""
    vistos, i = 0, 0
    while i < len(md) and vistos < n:
        c = md[i]
        if md.startswith("**", i):
            i += 2
            continue
        if c in "*\\" or (c == ">" and vistos == 0) or (c == " " and vistos == 0):
            i += 1
            continue
        vistos += 1
        i += 1
    resto = md[i:]
    resto = re.sub(r"^\s*\*\*\s*", "", resto) if md[:i].count("**") % 2 else resto
    resto = re.sub(r"^(\s|\*\*\s*\*\*|[-–—.:])+", "", resto)
    if resto.startswith("**") and resto.count("**") % 2:
        resto = resto[2:]
    return resto.strip()


def preparar(md):
    """Ajustes na saída do pandoc antes de separar os parágrafos."""
    md = md.replace("<!-- -->", "")
    # sobrescritos do Word (1^o^, 3^a^) viram os ordinais
    md = re.sub(r"\^(?:o|º)\.?\\?\s*\^", "º", md)
    md = re.sub(r"\^a\^", "ª", md)
    md = re.sub(r"\^([^\^\s]+)\^", r"\1", md)
    saida = []
    for b in re.split(r"\n\s*\n", md):
        b = re.sub(r"^#{7,}\s*", "", b)
        b = re.sub(r"^#{1,6}\s+(?=\**Art)", "", b)  # artigo formatado como título no Word
        if (m6 := re.match(r"^#{6}\s+(.+)$", b)) and maiusculo(m6.group(1)):
            b = f"**{m6.group(1).strip()}**"
        m = LISTA.match(b)
        if m and not b.lstrip().startswith("|"):
            # itens de lista numerados pelo Word viram incisos (I -) e alíneas (a)
            rot = f"{m.group(1)} -" if re.fullmatch(r"[IVXL]+", m.group(1)) else f"{m.group(1)})"
            b = rot + " " + "\n".join(l.strip() for l in b[m.end():].split("\n"))
        elif re.match(r"^ {2,}\S", b) and not b.lstrip().startswith(("|", "<")):
            b = "\n".join(l.strip() for l in b.split("\n"))
        saida.append(b)
    return "\n\n".join(saida)


def blocos(md):
    """Parágrafos do pandoc; citações (>) com vários parágrafos viram parágrafos separados."""
    saida = []
    for b in re.split(r"\n\s*\n", preparar(md).strip()):
        linhas = b.split("\n")
        if all(l.startswith(">") for l in linhas) and not any(re.match(r"^>\s*\|", l) for l in linhas):
            atual = []
            for l in linhas:
                l = re.sub(r"^(>\s?)+", "", l)
                if not l.strip():
                    if atual:
                        saida.append("\n".join(atual))
                    atual = []
                else:
                    atual.append(l)
            if atual:
                saida.append("\n".join(atual))
        else:
            saida.append(b)
    return [b.strip("\n") for b in saida if b.strip() and plano(b)]


def maiusculo(s):
    letras = [c for c in s if c.isalpha()]
    return len(letras) > 2 and all(c.isupper() for c in letras)


def data_lei(t):
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")\s+(?:de\s+)?(\d{4})", t, re.I)
    return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def tabela_de_colunas(html):
    """Tabelas do orçamento em que o Word pôs cada coluna numa célula só (itens com pontilhado | R$ | valores):
    vira uma tabela com uma linha por item. Itens sem pontilhado e sem valor (ex.: Poder Executivo) viram subtítulos."""
    cel = [[re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"<(?:p|h\d)[^>]*>(.*?)</(?:p|h\d)>", c, re.S)]
           for c in re.findall(r"<td[^>]*>(.*?)</td>", html, re.S)]
    rotulos, valores = cel[0], cel[-1]
    sobra = len(rotulos) - len(valores)
    linhas = ["| Especificação | Valor (R$) |", "|---|---:|"]
    v = iter(valores)
    for r in rotulos:
        nome = re.sub(r"\s*\.{2,}\s*$", "", r).strip()
        if sobra > 0 and "..." not in r:
            linhas.append(f"| **{nome}** | |")
            sobra -= 1
            continue
        val = next(v)
        if re.match(r"(?i)^total", nome) or re.match(r"^1\.[12]\s", nome):
            linhas.append(f"| **{nome}** | **{val}** |")
        else:
            linhas.append(f"| {nome} | {val} |")
    assert next(v, None) is None
    return "\n".join(linhas)


def tabelar_cargos(texto):
    """Listas de cargos comissionados (1 CC1- Secretário R$ 1.565,00) viram tabelas."""
    bs = texto.split("\n\n")
    out, i = [], 0
    while i < len(bs):
        if CARGO.match(bs[i]):
            linhas = ["| Qtde | Cargo | Vencimento |", "|---:|---|---:|"]
            while i < len(bs) and (CARGO.match(bs[i]) or re.fullmatch(r"(\\_)+", bs[i])):
                if m := CARGO.match(bs[i]):
                    linhas.append(f"| {m.group(1)} | {m.group(2)} | R\\$ {m.group(3)} |")
                i += 1
            if i < len(bs) and (m := TOTAL.match(bs[i])):
                linhas.append(f"| | **Total** | **R\\$ {m.group(1)}** |")
                i += 1
            out.append("\n".join(linhas))
            continue
        out.append(bs[i])
        i += 1
    return "\n\n".join(out)


def celulas(linha):
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def html_simples(html):
    """Tabela HTML do pandoc sem células mescladas e com um parágrafo por célula -> tabela Markdown
    (com a linha de título vazia; acertar_tabelas decide o título). Se não der, devolve o HTML."""
    if re.search(r"rowspan|colspan", html):
        return html
    linhas = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cels = []
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
            if len(re.findall(r"<(?:p|h\d)[^>]*>", c)) > 1 or re.search(r"<(?:ul|ol|table)", c):
                return html
            c = re.sub(r"</?(?:p|h\d)[^>]*>", "", c)
            c = re.sub(r"</?strong>", "**", c)
            c = re.sub(r"</?em>", "*", c)
            c = re.sub(r"<br\s*/?>", " ", c)
            if "<" in c:
                return html
            c = re.sub(r"\s+", " ", c).strip().replace("|", "\\|")
            c = re.sub(r"^\*\*\*\*$", "", c)
            cels.append(c)
        linhas.append(cels)
    if not linhas or len({len(l) for l in linhas}) != 1:
        return html
    n = len(linhas[0])
    out = ["| " + " | ".join([""] * n) + " |", "|" + "---|" * n]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def acertar_tabelas(texto):
    """Tabelas do Word sem linha de título: a primeira linha vira o título; uma tabela só com os títulos
    seguida de outra com as mesmas colunas vira uma tabela só."""
    def tabela(b):
        ls = b.split("\n")
        return b.startswith("|") and len(ls) >= 3 and re.match(r"^\|[\s:|-]+\|$", ls[1])

    bs = texto.split("\n\n")
    out = []
    i = 0
    while i < len(bs):
        b = bs[i]
        i += 1
        ls = b.split("\n")
        if not tabela(b) and not (b.startswith("|") and len(ls) == 2 and re.match(r"^\|[\s:|-]+\|$", ls[1])):
            out.append(b)
            continue
        prox = bs[i].split("\n") if i < len(bs) and tabela(bs[i]) else []
        if len(ls) == 2 and any(celulas(ls[0])) and prox and not any(celulas(prox[0])) \
                and len(celulas(prox[0])) == len(celulas(ls[0])):
            out.append("\n".join([ls[0], prox[1]] + prox[2:]))
            i += 1
            continue
        if not any(celulas(ls[0])):
            corpo = ls[2:]
            if len(corpo) == 1 and prox and not any(celulas(prox[0])) and len(celulas(prox[0])) == len(celulas(ls[0])):
                out.append("\n".join([corpo[0], prox[1]] + prox[2:]))
                i += 1
                continue
            if corpo:
                out.append("\n".join([corpo[0], ls[1]] + corpo[1:]))
                continue
        out.append(b)
    return "\n\n".join(out)


def limpar_tabelas(texto):
    """Acertos finais nas tabelas (pode rodar de novo sobre uma página pronta sem mudar nada):
    - linhas de tabela HTML com todas as células vazias (espaçadores do Word) saem;
    - parágrafo "heading" que o pandoc às vezes põe dentro de uma célula vira texto simples;
    - tabela Markdown só com a linha de título (as "caixas" de organogramas do Word) vira uma tabela HTML
      de uma linha sem título, porque o site desenharia embaixo uma linha vazia."""
    def vazia(tr):
        cs = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr.group(0), re.S)
        return "" if cs and not any(re.sub(r"<[^>]+>|&nbsp;|\s", "", c) for c in cs) else tr.group(0)

    texto = re.sub(r"<tr[^>]*>.*?</tr>\n?", vazia, texto, flags=re.S)
    texto = re.sub(r'(<t[dh][^>]*>)<p id="[^"]*" class="heading">(.*?)</p>(</t[dh]>)', r"\1\2\3", texto)
    texto = re.sub(r'(<t[dh][^>]*>)<p id="[^"]*" class="heading">', r"\1<p>", texto)  # célula com mais parágrafos

    def caixa(m):
        cels = celulas(m.group(1))
        alin = [("center" if a.startswith(":") and a.endswith(":") else "right" if a.endswith(":") else "left")
                for a in celulas(m.group(2))]
        tds = []
        for c, a in zip(cels, alin):
            c = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", c.replace("\\|", "|"))
            tds.append(f'<td style="text-align: {a};">{c}</td>')
        return "<table>\n<tbody>\n<tr>\n" + "\n".join(tds) + "\n</tr>\n</tbody>\n</table>"

    return re.sub(r"(?:\A|(?<=\n\n))(\|[^\n]*\|)\n(\|(?:\s*:?-+:?\s*\|)+)(?=\n\n|\n?\Z)", caixa, texto)


def citacoes(texto):
    """Nova redação citada (“Art ...”): o pandoc só põe o primeiro parágrafo na citação e deixa o itálico
    do Word solto; junta os parágrafos até o fecha-aspas numa citação só, sem o itálico."""
    bs, out, k = texto.split("\n\n"), [], 0
    limpa = lambda b: re.sub(r"^(>\s*)+", "", b).replace("*", "").strip()
    fecha = lambda b: re.search(r"”\.?$", limpa(b))
    while k < len(bs):
        b = bs[k]
        if b.startswith("> ") and "\n>" not in b and re.match(r"^[“\"]Art", limpa(b)):
            fim = next((j for j in range(k, min(k + 40, len(bs))) if fecha(bs[j])), None)
            if fim is not None:
                out.append("\n>\n".join("> " + limpa(x) for x in bs[k:fim + 1]))
                k = fim + 1
                continue
        out.append(b)
        k += 1
    return "\n\n".join(out)


def ler_md2(nome):
    return next(f for f in (SCR / "md2").iterdir() if nfc(f.name) == nome).read_text()


def converter(num, extras=None):
    extras = EXTRAS.get((ANO, num), []) if extras is None else extras
    bs = blocos(ler_md2(f"LEI Nº {num}.{ANO}.md"))
    for e in extras:
        bs += blocos(e[3:] if e.startswith("md:") else ler_md2(e))
    # cabeçalho: título e ementa
    i = next(k for k, b in enumerate(bs) if re.match(rf"(?i)^lei\s+n[º°o]?\.?\s*{num}", plano(b)))
    titulo_doc = plano(bs[i])
    data = data_lei(titulo_doc)
    ementa = plano(bs[i + 1]).strip("“”\"' ")
    ementa = re.sub(r"[”\"]\.?$", "", ementa).strip()
    if not ementa.endswith("."):
        ementa += "."
    corpo = bs[i + 2:]

    out = [f"**{titulo_doc.rstrip('.')}.**\n{{ .centro }}", f"“{ementa[:-1]}”."]
    k = 0
    assinatura = []
    ultimo_art = 0
    anexos = []
    ancoras = set()

    def fecha_assinatura():
        if assinatura:
            out.append("\n".join(f"**{l}**" if j == 0 else l for j, l in enumerate(assinatura)) + "\n{ .centro }"
                       if len(assinatura) > 1 else f"**{assinatura[0]}**\n{{ .centro }}")
            assinatura.clear()

    while k < len(corpo):
        b = corpo[k]
        p = plano(b)
        tabela = b.lstrip().startswith(("|", "<"))
        # assinaturas: o pandoc transforma o nome e o cargo em títulos (## e #####)
        if re.match(r"^#{1,6}\s", b) and not ROT.match(p) and not ANEXO.match(p):
            if b.startswith("##### ") or b.startswith("###### ") and assinatura:
                assinatura.append(p)
            else:
                fecha_assinatura()
                assinatura.append(p)
            k += 1
            continue
        fecha_assinatura()
        if tabela:
            out.append(b)
        elif (m := ROT.match(p)) and len(p) < 120:
            tipo = m.group(1).upper()
            tipo = ("SUBSEÇÃO" if tipo.startswith("SUB") else "SEÇÃO" if tipo.startswith("SE")
                    else "TÍTULO" if tipo.startswith("T") else "CAPÍTULO")
            numero = m.group(2).upper().replace("UNICA", "ÚNICA").replace("UNICO", "ÚNICO")
            assunto = m.group(3)
            if not assunto and k + 1 < len(corpo) and maiusculo(plano(corpo[k + 1])) and not ROT.match(plano(corpo[k + 1])) \
                    and not ART.match(plano(corpo[k + 1])):
                assunto = plano(corpo[k + 1])
                k += 1
            out.append(f"{NIVEL[tipo]} {tipo} {numero}" + (f" — {assunto}" if assunto else "") + " { .centro }")
        elif (m := ANEXO.match(p)) and len(p) < 200 and ultimo_art:
            n = m.group(1).upper()
            assunto = m.group(2)
            if out and out[-1].startswith("## ANEXO"):
                # anexo de outra lei reproduzido dentro deste anexo (ex.: ANEXO I / ANEXO III DA LEI Nº 487/2001)
                out.append(f"**{p}**\n{{ .centro }}")
                k += 1
                continue
            if re.match(r"(?i)^DA LEI\b", assunto):
                assunto = ""
            if n.isdigit():
                n = "I II III IV V VI VII VIII IX X".split()[int(n) - 1]
            if not assunto and k + 1 < len(corpo) and maiusculo(plano(corpo[k + 1])) and len(plano(corpo[k + 1])) < 200 \
                    and not ANEXO.match(plano(corpo[k + 1])):
                assunto = plano(corpo[k + 1])
                k += 1
            ident = "anexo-" + n.lower().replace("ú", "u")
            if ident in anexos:
                ident += "-b"
            anexos.append(ident)
            out.append(f"## ANEXO {n}" + (f" — {assunto}" if assunto else "") + f" {{ #{ident} .centro }}")
        elif m := ART.match(p):
            n = int(m.group(1))
            suf = (m.group(2) or "").upper()
            rot = (f"Art. {n}º" if n < 10 else f"Art. {n}.") if not suf else f"Art. {n}{'º' if n < 10 else ''}{suf}."
            resto = tira_rotulo(b, m.end())
            ancora = f"art-{n}" + (suf.lower() if suf else "")
            while ancora in ancoras:
                ancora += "-b"
            ancoras.add(ancora)
            out.append(f"**{rot}** {resto}\n{{ #{ancora} }}")
            ultimo_art = n
        elif m := PAR.match(p):
            out.append(f"§ {m.group(1)}º {tira_rotulo(b, m.end())}")
        elif m := UNICO.match(p):
            out.append(f"Parágrafo único. {tira_rotulo(b, m.end())}")
        elif (m := INC.match(p)) and ultimo_art:
            out.append(f"{m.group(1)} - {tira_rotulo(b, m.end())}")
        elif (m := ALI.match(p)) and ultimo_art:
            out.append(f"{m.group(1)}) {tira_rotulo(b, m.end())}")
        elif re.match(r"^[“\"]Art", p):
            out.append("> " + re.sub(r"^(>\s*)+", "", b))
        else:
            out.append(re.sub(r"^(>\s*)+", "", b))
        k += 1
    fecha_assinatura()
    texto = "\n\n".join(out)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = tabelar_cargos(texto)
    if (num, ANO) in ORCAMENTOS:
        texto = re.sub(r"<table.*?</table>", lambda m: tabela_de_colunas(m.group(0)), texto, flags=re.S)
    else:
        texto = re.sub(r"<table.*?</table>", lambda m: html_simples(m.group(0)), texto, flags=re.S)
    texto = acertar_tabelas(texto)
    texto = limpar_tabelas(texto)
    texto = re.sub(r"(\{ \.centro \}\n)+", "{ .centro }\n", texto)
    if ANO >= "2006":
        texto = citacoes(texto)
    for a, b in CORRECOES.get((ANO, num), []):
        assert a in texto, (num, a)
        texto = texto.replace(a, b)
    texto = texto.replace("\\$", "$")  # o pandoc escapa o cifrão, mas o Markdown do site mostraria a barra
    # CPF e RG de pessoas citadas nas leis (doações, cessões) não vão para o site
    texto = re.sub(r"\b\d{3}\s?\.\s?\d{3}\s?\.\s?\d{3}\s?[-–]\s?\d{2}\b", "[omitido]", texto)
    texto = re.sub(r"\b[\dX.\-]*\d[\dX.\-]*\s?(?:/\s?)?SSP\s?[/-]?\s?[A-Z]{2}\b", "[omitido]", texto)  # RG: número/SSP/UF
    texto = texto.replace("RG [omitido] nº e", "RG [omitido] e").replace("[omitido] e [omitido]", "[omitidos]")
    # nome e cargo de quem assina em parágrafos separados viram um bloco só, centralizado
    texto = re.sub(r"\*\*([^*\n]+)\*\*(?:\n\{ \.centro \})?\n\n\*\*(Prefeito Municipal|Secretário|Secretária|Vice-Prefeito)\*\*(?:\n\{ \.centro \})?",
                   r"**\1**\n\2\n{ .centro }", texto)
    if ANO >= "2006":
        # nome e cargo em linhas separadas, cada um centralizado (no Markdown, uma quebra simples junta as linhas)
        texto = re.sub(r"^(\*\*[^*\n]+\*\*)\n(?![{|>])([^\n]+)\n\{ \.centro \}", r"\1\n{ .centro }\n\n\2\n{ .centro }",
                       texto, flags=re.M)
        texto = re.sub(r"(\{ \.centro \}\n\n)\*(Secretário|Secretária|Prefeito Municipal)\*$", r"\1\2\n{ .centro }",
                       texto, flags=re.M)
    if (ANO, num) in MAPAS:
        corte, novo = MAPAS[(ANO, num)]
        assert corte in texto, (num, corte)
        texto = texto[:texto.index(corte)] + novo
    return dict(num=num, data=data, ementa=ementa, titulo_doc=titulo_doc, texto=texto)


def numeros():
    return sorted({m.group(1) for f in (SCR / "md2").iterdir()
                   if (m := re.match(rf"LEI Nº (\d+)\.{ANO}\.md$", nfc(f.name)))})


if __name__ == "__main__":
    (SCR / "out").mkdir(exist_ok=True)
    for n in sys.argv[1:] or numeros():
        r = converter(n)
        (SCR / "out" / f"lei-{n}-{ANO}.md").write_text(r["texto"] + "\n")
        print(n, r["data"], r["ementa"][:80])
