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
ORCAMENTOS = {
    ("681", "2005"),
    ("718", "2006"),
    ("750", "2007"),
    ("794", "2008"),
    ("834", "2009"),
    ("889", "2010"),
    ("940", "2011"),
    ("995", "2012"),
    ("1050", "2013"),
    ("1085", "2014"),
    ("1111", "2015"),
    ("1137", "2016"),
}
# anexos desenhados no Word que viram imagem: (ano, lei) -> (começo do trecho a cortar, markdown no lugar)
MAPAS = {}
# arquivos extras (anexos em .doc separados) a juntar no fim da lei: (ano, lei) -> [nomes em md2/ ou "md:texto"]
EXTRAS = {
    ("2015", "1100"): ["LEI Nº 1100.2015-APROVA PLANO MUNICIPAL DE EDUCAÇÃO-ANEXO I.md"],
    ("2019", "1216"): ["""md:“Dispõe sobre a divulgação da lista de espera para vagas nas Escolas Municipais de Educação Infantil - EMEIs, e dá outras providências”.

O Exmo. Sr. Presidente da Câmara Municipal de Batayporã, Estado de Mato Grosso do Sul, Sr. Cícero Humberto Leite, no uso e gozo de suas atribuições legais, que lhe conferem a Lei Orgânica Municipal:

Faz saber que a **CÂMARA MUNICIPAL** aprovou o Projeto de Lei de autoria e iniciativa do Vereador Germino da Roz Silva e ele sanciona e promulga a seguinte Lei.

**Art. 1º** - Fica assegurada a divulgação da lista contendo a ordem de espera para vagas nas Escolas Municipais de Educação Infantil – EMEIs, popularmente conhecidas como Creches.

§ 1º - As informações a serem divulgadas devem conter, no mínimo, o nome do requerente, número de protocolo, data e hora da inscrição e unidade pretendida.

§ 2º - A lista de que trata a presente Lei deverá ser afixada em bem visível em todas as EMEIs públicas do Município, além de ser disponibilizada no site oficial da Prefeitura Municipal de Batayporã.

**Art. 2º** - As informações serão de inteira responsabilidade do Poder Executivo Municipal, devendo atualizar a lista de espera por vaga, imediatamente, sempre que houver alteração na disponibilidade das vagas.

Parágrafo único - Em caso de desistência da vaga pretendida, deve o solicitante comunicar isto imediatamente à secretaria da respectiva EMEI.

**Art. 3º** - Deverá ser feito um estudo socioeconômico minucioso de todo requerente à ocupação de vaga em EMEI e, para a ocupação definitiva de vaga, será observada rigorosamente a classificação a contar do que está em piores condições socioeconômicas.

**Art. 4º** - Esta Lei entra em vigor na data de sua publicação, revogadas as disposições em contrário.

Plenário das Deliberações “Erberto Flauzino de Oliveira”, em 22 de outubro de 2019.

**Cícero Humberto Leite**
Vereador Presidente"""],
}
# acertos pontuais no texto final: (ano, lei) -> [(trecho, novo)]
CORRECOES = {
    # no .doc o 7º artigo está numerado "Art. 1º" (a cópia em PDF da prefeitura traz "Art. 7º")
    ("2007", "740"): [("**Art. 1º** A atuação da equipe de trabalho obedecerá os seguintes eixos temáticos:\n{ #art-1-b }",
                       "**Art. 7º** A atuação da equipe de trabalho obedecerá os seguintes eixos temáticos:\n{ #art-7 }")],
    ("2025", "LC73"): [("serviço público*.*", "serviço público.")],  # lei complementar 073/2025: ponto em itálico
    ("2026", "1451"): [
        (
            "***“CAPÍTULO IV***\n\n***DOS BENEFÍCIOS EVENTUAIS***",
            "> **“CAPÍTULO IV**\n>\n> **DOS BENEFÍCIOS EVENTUAIS**",
        )
    ],
    ("2026", "1454"): [("Art. Art. 1º", "**Art. 1º**")],
    ("2025", "1386"): [("SEPLAN****", "SEPLAN**")],
    ("2025", "1396"): [("**.**", ".")],
    ("2025", "1401"): [("financeiro*.*", "financeiro.")],
    ("2025", "1402"): [
        (
            "> *“Art. 2º ...*\n\nParágrafo único. *O* *Fundo de Habitação de Interesse Social – FHIS fica vinculado à Secretaria Municipal de Infraestrutura Pública - SEINFRA.” **(NR)***",
            "> “Art. 2º ...\n>\n> Parágrafo único. O Fundo de Habitação de Interesse Social – FHIS fica vinculado à Secretaria Municipal de Infraestrutura Pública - SEINFRA.” (NR)",
        ),
        (
            "> *“Art. 5º ...*\n\n§ 1º *\n\n§ 2º A Presidência do Conselho Gestor de FHIS será exercida pelo Secretário Municipal de Infraestrutura Pública; **(NR)***\n\n§ 3º *\n\n§ 4º Compete à Secretaria Municipal de Infraestrutura Pública – SEINFRA proporcionar os meios necessários para o exercício das competências do Conselho Gestor do FHIS.” **(NR)***",
            "> “Art. 5º ...\n>\n> § 1º\n>\n> § 2º A Presidência do Conselho Gestor de FHIS será exercida pelo Secretário Municipal de Infraestrutura Pública; (NR)\n>\n> § 3º\n>\n> § 4º Compete à Secretaria Municipal de Infraestrutura Pública – SEINFRA proporcionar os meios necessários para o exercício das competências do Conselho Gestor do FHIS.” (NR)",
        ),
    ],
    ("2025", "1407"): [("**.**", ".")],
    ("2025", "1408"): [("**.**", ".")],
    ("2025", "1414"): [
        ("> *“****Art. 1º.**", "> “**Art. 1º.**"),
        ("finalidade de fortalecer o comércio local.” **(NR)***", "finalidade de fortalecer o comércio local.” (NR)"),
    ],
    ("2025", "1419"): [("<strong>R$</strong>", "<strong>R&#36;</strong>")],
    ("2024", "1350"): [("além das referidas no caput desse artigo**.**", "além das referidas no caput desse artigo.")],
    ("2024", "1369"): [("<strong>R$</strong>", "<strong>R&#36;</strong>")],
    ("2023", "1314"): [
        (
            "***“ Art.-20**..........*\n\n§ 1º *\n\n§ 2º *\n\n§ 3º ",
            "> “**Art. 20-** ..........\n>\n> § 1º\n>\n> § 2º\n>\n> § 3º ",
        ),
        ("<u>ou a reversão dos recursos investidos</u>.”*", "<u>ou a reversão dos recursos investidos</u>.”"),
    ],
    ("2023", "1348"): [("<strong>R$</strong>", "<strong>R&#36;</strong>")],
    ("2022", "1289"): [('<img src="media/image1.png" />', "")],
    ("2021", "1250"): [('<img src="media/image1.png" />', "")],  # pixel 1x1 transparente do Word
    ("2018", "1188"): [('<img src="media/image2.png" style="width:2.54583in;height:1.31944in" />', "")],  # carimbo no fim, fora do .docx
    ("2022", "1292"): [
        ("SILVA**,**", "SILVA,"),
        ('<img src="media/image1.png" />', ""),
    ],
    ("2022", "1310"): [("<strong>R$</strong>", "<strong>R&#36;</strong>")],
    ("2021", "1258"): [("*nu****,*", "*nu***,")],
    ("2019", "1202"): [(" ~~º~~**", "")],
    ("2019", "1205"): [(" ~~º~~**", "")],
    ("2019", "1207"): [(" ~~º~~**", "")],
    ("2019", "1209"): [
        ("***“** Art. 3º -", "> “Art. 3º -"),
        ("Código Tributário Municipal.**”***", "Código Tributário Municipal.”"),
    ],
    ("2018", "1193"): [
        ("CONSELHEIROS TUTELARES (SUPLENTES)**", "CONSELHEIROS TUTELARES (SUPLENTES)"),
    ],
    ("2017", "1143"): [
        ("§ 2º As categorias que possuem piso salarial fixado pelo Governo Federal, em havendo aumento, será compensado pelo valor ora reajustado.**",
         "§ 2º As categorias que possuem piso salarial fixado pelo Governo Federal, em havendo aumento, será compensado pelo valor ora reajustado."),
    ],
    ("2016", "1120"): [
        ("§ 2º As categorias que possuem piso salarial fixado pelo Governo Federal, em havendo aumento, será compensado pelo valor ora reajustado.**",
         "§ 2º As categorias que possuem piso salarial fixado pelo Governo Federal, em havendo aumento, será compensado pelo valor ora reajustado."),
    ],
    ("2016", "1126"): [
        ("e) concluir a construção do Centro de Educação Infantil iniciada em 2009, destinando recursos mensais**",
         "e) concluir a construção do Centro de Educação Infantil iniciada em 2009, destinando recursos mensais"),
    ],
    ("2016", "1137"): [
        ("em seus respectivos orçamentos.**", "em seus respectivos orçamentos."),
    ],
    ("2015", "1100"): [
        # no Word: "Anexo I da" numa linha e "Lei Municipal n.º 1100/2015..." na seguinte
        ("## ANEXO I — da { #anexo-i .centro }\n\n**Lei Municipal n.º 1100/2015",
         "## ANEXO I { #anexo-i .centro }\n\n**da Lei Municipal n.º 1100/2015"),
    ],
    ("2015", "1098"): [
        ("e) concluir a construção da creche iniciada em 2009, podendo destinar recursos mensal**", "e) concluir a construção da creche iniciada em 2009, podendo destinar recursos mensal"),
    ],
    ("2014", "1054"): [
        ("Parágrafo único. **Parágrafo Único**- ", "**Parágrafo único.** "),
    ],
    ("2014", "1070"): [
        ("e) concluir a construção da creche iniciada em 2009, podendo destinar recursos mensal**", "e) concluir a construção da creche iniciada em 2009, podendo destinar recursos mensal"),
    ],
    ("2014", "1073"): [
        ("I - QUADRA Nº Q6-01**", "**I - QUADRA Nº Q6-01**"),
        ("II - QUADRA Nº Q6-C**", "**II - QUADRA Nº Q6-C**"),
        ("III - QUADRA Nº 39**", "**III - QUADRA Nº 39**"),
        ("IV - QUADRA Nº 40- localizado perímetro urbano central da cidade**", "**IV - QUADRA Nº 40- localizado perímetro urbano central da cidade**"),
    ],
    ("2014", "1082"): [
        ("I - De atendimento**:", "**I - De atendimento**:"),
        ("II - De assessoramento**:", "**II - De assessoramento**:"),
        ("III - De defesa e garantia de direitos**:", "**III - De defesa e garantia de direitos**:"),
    ],
    ("2014", "1083"): [
        ("§ 3º Não se aplica as disposições do inciso III, deste artigo, quando:**", "§ 3º Não se aplica as disposições do inciso III, deste artigo, quando:"),
    ],
    ("2013", "1000"): [
        ("I - *Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;*",
         "I - Agentes Políticos ocupantes de cargos de Secretário, responsáveis pela gestão pública no âmbito de suas respectivas secretarias, remunerados por subsídio fixado pela Câmara Municipal;"),
        ("direitos políticos;*", "direitos políticos;"),
        ("Prefeito Municipal;*", "Prefeito Municipal;"),
        ("\n\n**SECRETARIA DE GOVERNO**\n\n", "\n\n**SECRETARIA DE GOVERNO**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE ADMINISTAÇÃO FINANÇAS E PLANEJAMENTO**\n\n", "\n\n**SECRETARIA MUNICIPAL DE ADMINISTAÇÃO FINANÇAS E PLANEJAMENTO**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE OBRAS, INFRA ESTRFUTURA E SERVIÇOS URBANOS**\n\n", "\n\n**SECRETARIA MUNICIPAL DE OBRAS, INFRA ESTRFUTURA E SERVIÇOS URBANOS**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE EDUCAÇÃO E CULTURA**\n\n", "\n\n**SECRETARIA MUNICIPAL DE EDUCAÇÃO E CULTURA**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE SAÚDE**\n\n", "\n\n**SECRETARIA MUNICIPAL DE SAÚDE**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL**\n\n", "\n\n**SECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE AGRICULTURA E DESENVOLVIMENTO SUSTENTÁVEL**\n\n", "\n\n**SECRETARIA MUNICIPAL DE AGRICULTURA E DESENVOLVIMENTO SUSTENTÁVEL**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE TURISMO E MEIO AMBIENTE**\n\n", "\n\n**SECRETARIA MUNICIPAL DE TURISMO E MEIO AMBIENTE**\n{ .centro }\n\n"),
        ("\n\n**SECRETARIA MUNICIPAL DE ESPORTES E LAZER**\n\n", "\n\n**SECRETARIA MUNICIPAL DE ESPORTES E LAZER**\n{ .centro }\n\n"),
    ],
    ("2013", "1001"): [
        ('<h5 id="cargo">CARGO</h5>', "CARGO"),
        ('<h5 id="diretor-financeiro">Diretor Financeiro</h5>', "Diretor Financeiro"),
        ('<h5 id="diretor-executivo">Diretor Executivo</h5>', "Diretor Executivo"),
        ('<h5 id="assessor-jurídico">Assessor Jurídico </h5>', "Assessor Jurídico"),
        ('<h5 id="assessor-legislativo">Assessor Legislativo</h5>\n<h5 id="section-4"></h5>', "Assessor Legislativo"),
        ('<h5 id="cargo-1">CARGO</h5>', "CARGO"),
        ('<h5 id="coordenadora-de-cerimonial">Coordenador(a) de Cerimonial</h5>', "Coordenador(a) de Cerimonial"),
        ('<h5 id="assessor-legislativo-1">Assessor Legislativo</h5>', "Assessor Legislativo"),
        ('<h5 id="serviços-gerais">Serviços Gerais</h5>', "Serviços Gerais"),
        ('<h5 id="assessor-de-imprensa">Assessor de Imprensa</h5>', "Assessor de Imprensa"),
        ("\n\nTABELA I – CARGOS DE PROVIMENTO EFETIVO\n\n", "\n\n**TABELA I – CARGOS DE PROVIMENTO EFETIVO**\n{ .centro }\n\n"),
        ("\n\n**TABELA III – FUNÇÕES GRATIFICADAS**\n\n", "\n\n**TABELA III – FUNÇÕES GRATIFICADAS**\n{ .centro }\n\n"),
    ],
    ("2013", "1003"): [
        ("\n\n**(ANEXO I DA LEI Nº 502/2001 COM ALTERAÇÕES INTRODUZIDAS)**\n\n",
         "\n\n**(ANEXO I DA LEI Nº 502/2001 COM ALTERAÇÕES INTRODUZIDAS)**\n{ .centro }\n\n"),
        ("\n\n**CLASSIFICAÇÃO DE CARGOS DE PROVIMENTO EFETIVO**\n\n",
         "\n\n**CLASSIFICAÇÃO DE CARGOS DE PROVIMENTO EFETIVO**\n{ .centro }\n\n"),
        ("\n\n**TABELA 1 – PROFISSIONAIS DE SAÚDE**\n\n",
         "\n\n**TABELA 1 – PROFISSIONAIS DE SAÚDE**\n{ .centro }\n\n"),
        ("\n\n**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO**\n\n",
         "\n\n**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO**\n{ .centro }\n\n"),
    ],
    ("2013", "1004"): [("Batayporã**,**", "Batayporã,")],
    ("2013", "1007"): [
        ("\n\n**DA ESTRUTURA**\n\n", "\n\n**DA ESTRUTURA**\n{ .centro }\n\n"),
        ("**DO CONSELHO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO**\n\n**ADOLESCENTE**",
         "**DO CONSELHO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO ADOLESCENTE**"),
        ("2012.**", "2012."),
        ("\n\n**DOS REQUISITOS**\n\n", "\n\n**DOS REQUISITOS**\n{ .centro }\n\n"),
        ("\n\n**DOS CONSELHEIROS TUTELARES**\n\n", "\n\n**DOS CONSELHEIROS TUTELARES**\n{ .centro }\n\n"),
        ("\n\n**DO CONTROLE DO CONSELHO TUTELAR**\n\n", "\n\n**DO CONTROLE DO CONSELHO TUTELAR**\n{ .centro }\n\n"),
        ("\n\n**DO PROCESSO DISCIPLINAR**\n\n", "\n\n**DO PROCESSO DISCIPLINAR**\n{ .centro }\n\n"),
        ("\n\n**DA PERDA DO MANDATO E DA VACÂNCIA**\n\n", "\n\n**DA PERDA DO MANDATO E DA VACÂNCIA**\n{ .centro }\n\n"),
        ("**Art. 6º** 4**- O Conselho atenderá as partes, mantendo registro das providências adotadas em cada caso e fazendo consignar em relatório.\n{ #art-6-b }",
         "**Art. 64.** O Conselho atenderá as partes, mantendo registro das providências adotadas em cada caso e fazendo consignar em relatório.\n{ #art-64 }"),
        ("\n\n**DA COMPETÊNCIA**\n\n", "\n\n**DA COMPETÊNCIA**\n{ .centro }\n\n"),
        ("**DO FUNDO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO**\n\n**ADOLESCENTE**",
         "**DO FUNDO MUNICIPAL DOS DIREITOS DA CRIANÇA E DO ADOLESCENTE**\n{ .centro }"),
        ("\n\n**DAS DISPOSIÇÕES FINAIS**\n\n", "\n\n**DAS DISPOSIÇÕES FINAIS**\n{ .centro }\n\n"),
        ("sessão**.**", "sessão."),
    ],
    ("2013", "1010"): [("\n\n.\n\n", "\n\n")],
    ("2013", "1013"): [("\n\n**ORGANOGRAMA DA PREFEITURA MUNICIPAL DE BATAYPORÃ-MS**\n\n",
                      "\n\n**ORGANOGRAMA DA PREFEITURA MUNICIPAL DE BATAYPORÃ-MS**\n{ .centro }\n\n")],
    ("2013", "1014"): [("**JOSÉ APARECIDO ZACCHI – ME*,***", "**JOSÉ APARECIDO ZACCHI – ME**,")],
    ("2013", "1016"): [
        ("\n\nDAS DISPOSIÇÕES PRELIMINARES\n\n", "\n\n**DAS DISPOSIÇÕES PRELIMINARES**\n{ .centro }\n\n"),
        ("### CAPÍTULO I — DAS PRIORIDADES E METAS DA { .centro }\n\n**ADMINISTRAÇÃO PÚBLICA MUNICIPAL**",
         "### CAPÍTULO I — DAS PRIORIDADES E METAS DA ADMINISTRAÇÃO PÚBLICA MUNICIPAL { .centro }"),
        ("### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO { .centro }\n\n**DOS ORÇAMENTOS**",
         "### CAPÍTULO II — DA ESTRUTURA E ORGANIZAÇÃO DOS ORÇAMENTOS { .centro }"),
        ("### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS { .centro }\n\n**PARA O PODER LEGISLATIVO**",
         "### CAPÍTULO III — DAS DIRETRIZES ESPECÍFICAS PARA O PODER LEGISLATIVO { .centro }"),
        ("### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO { .centro }\n\n**DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES**",
         "### CAPÍTULO IV — DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES { .centro }"),
        ("2009,** para melhorar", "2009, para melhorar"),
        ("### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS { .centro }\n\n**FISCAL E DA SEGURIDADE SOCIAL**",
         "### CAPÍTULO V — DAS DIRETRIZES DOS ORÇAMENTOS FISCAL E DA SEGURIDADE SOCIAL { .centro }"),
        ("### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS { .centro }\n\n**DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO**",
         "### CAPÍTULO VI — LIMITES E CONDIÇÕES PARA EXPANSÃO DAS DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO { .centro }"),
        ("### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS { .centro }\n\n**COM PESSOAL E ENCARGOS SOCIAIS**",
         "### CAPÍTULO VII — DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS COM PESSOAL E ENCARGOS SOCIAIS { .centro }"),
        ("### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS { .centro }\n\n**E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS**",
         "### CAPÍTULO XIII — DAS NORMAS DE CONTROLE DE CUSTOS E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS { .centro }"),
    ],
    ("2013", "1023"): [
        ("III - CONDIÇÕES DE TRABALHO:**", "III - **CONDIÇÕES DE TRABALHO:**"),
        ("IV - REQUISITOS PARA PROVIMENTO:**", "IV - **REQUISITOS PARA PROVIMENTO:**"),
    ],
    ("2013", "1031"): [("Programas**.**", "Programas.")],
    ("2013", "1035"): [
        ("acréscimos:**", "acréscimos:"),
        ('> *“Art. 1º Esta lei regulamenta o tratamento jurídico diferenciado, simplificado e favorecido assegurado ao microempreendedor individual (MEI), às microempresas (ME) e empresas de pequeno porte (EPP), doravante simplesmente denominados, respectivamente, MEI, ME e EPP, em conformidade com o que dispõe os artigos 146, III, “d”, 170, IX, e 179 da Constituição Federal e a Lei Complementar Federal nº. 123, de 14 de dezembro de 2006, e suas alterações, criando a Lei Geral Municipal da Microempresa e da Empresa de Pequeno Porte de Batayporã, Estado de Mato Grosso do Sul.” (NR)*\n\nParágrafo único. Para efeito desta lei, ficam adotados na íntegra os parâmetros de definição de microempresa (ME), de empresa de pequeno porte (MPE) e de Microempreendedor Individual (MEI) constantes no Capítulo II e no parágrafo primeiro do artigo 18-A da Lei Complementar nº 123, de 14 de dezembro de 2006, observadas suas alterações, tendo de ser aplicado ao MEI todos os benefícios e todas as prerrogativas previstas nesta Lei paras as ME e EPP, ressalvadas as vedações, as restrições e as condicionantes específicas constantes na Lei Complementar nº 123/06 vigente, e suas alterações.” (NR)*',
         '> “Art. 1º Esta lei regulamenta o tratamento jurídico diferenciado, simplificado e favorecido assegurado ao microempreendedor individual (MEI), às microempresas (ME) e empresas de pequeno porte (EPP), doravante simplesmente denominados, respectivamente, MEI, ME e EPP, em conformidade com o que dispõe os artigos 146, III, “d”, 170, IX, e 179 da Constituição Federal e a Lei Complementar Federal nº. 123, de 14 de dezembro de 2006, e suas alterações, criando a Lei Geral Municipal da Microempresa e da Empresa de Pequeno Porte de Batayporã, Estado de Mato Grosso do Sul.\n>\n> Parágrafo único. Para efeito desta lei, ficam adotados na íntegra os parâmetros de definição de microempresa (ME), de empresa de pequeno porte (MPE) e de Microempreendedor Individual (MEI) constantes no Capítulo II e no parágrafo primeiro do artigo 18-A da Lei Complementar nº 123, de 14 de dezembro de 2006, observadas suas alterações, tendo de ser aplicado ao MEI todos os benefícios e todas as prerrogativas previstas nesta Lei paras as ME e EPP, ressalvadas as vedações, as restrições e as condicionantes específicas constantes na Lei Complementar nº 123/06 vigente, e suas alterações.” (NR)'),
        ("> Art. 61. \n{ #art-61 }", "> “Art. 61. ..........................."),
        ("> Art. 2º O artigo 10, seus parágrafos e incisos, da Lei nº 833/2009, de 09 de dezembro de 2009, passa a inserir o Capítulo IV, da Sala do Empreendedor, vindo o próximo Capítulo ter a numeração romana V, e assim consecutivamente em observância à ordem.\n{ #art-2 }\n>\n> Art. 3º O artigo 11, 12, 13, 14, 15, 16, 17, seus parágrafos e incisos da Lei nº 833/2009, de 09 de dezembro de 2009, passa a inserir o Capítulo V, do Alvará, vindo o próximo Capítulo ter a numeração romana VI, e assim consecutivamente em observância à ordem.\n{ #art-3 }\n>\n> Art. 4º A Lei nº 833/2009, de 09 de dezembro de 2009, passa a vigorar acrescida do § 1º e do parágrafo único ao artigo 7º, do § 4º, do § 5º, do § 6º e do § 7º e incisos ao artigo 11, do inciso V e VI ao artigo 15:\n{ #art-4 }",
         "**Art. 2º** O artigo 10, seus parágrafos e incisos, da Lei nº 833/2009, de 09 de dezembro de 2009, passa a inserir o Capítulo IV, da Sala do Empreendedor, vindo o próximo Capítulo ter a numeração romana V, e assim consecutivamente em observância à ordem.\n{ #art-2 }\n\n**Art. 3º** O artigo 11, 12, 13, 14, 15, 16, 17, seus parágrafos e incisos da Lei nº 833/2009, de 09 de dezembro de 2009, passa a inserir o Capítulo V, do Alvará, vindo o próximo Capítulo ter a numeração romana VI, e assim consecutivamente em observância à ordem.\n{ #art-3 }\n\n**Art. 4º** A Lei nº 833/2009, de 09 de dezembro de 2009, passa a vigorar acrescida do § 1º e do parágrafo único ao artigo 7º, do § 4º, do § 5º, do § 6º e do § 7º e incisos ao artigo 11, do inciso V e VI ao artigo 15:\n{ #art-4 }"),
        ("artigo 24:**", "artigo 24:"),
        ("*2 – O ISSQN devido por microempresa que aufira receita bruta, no ano-calendário anterior, de até R\\$ 120.000,00 (cento e vinte mil reais), poderá ser cobrado por valores fixos mensais, conforme dispuser o Executivo municipal, em conformidade com as normas expedidas pelo Comitê Gestor do Simples Nacional.*\n\n*3 – Os valores fixos mensais estabelecidos para recolhimento do ISS, independentemente da receita bruta recebida no mês pelo contribuinte, não poderão exceder a 50% (cinquenta por cento) do maior recolhimento possível do tributo para a faixa de enquadramento prevista nas tabelas dos Anexos da Lei Complementar Federal nº 123/06.”*",
         "> 2 – O ISSQN devido por microempresa que aufira receita bruta, no ano-calendário anterior, de até R\\$ 120.000,00 (cento e vinte mil reais), poderá ser cobrado por valores fixos mensais, conforme dispuser o Executivo municipal, em conformidade com as normas expedidas pelo Comitê Gestor do Simples Nacional.\n>\n> 3 – Os valores fixos mensais estabelecidos para recolhimento do ISS, independentemente da receita bruta recebida no mês pelo contribuinte, não poderão exceder a 50% (cinquenta por cento) do maior recolhimento possível do tributo para a faixa de enquadramento prevista nas tabelas dos Anexos da Lei Complementar Federal nº 123/06.”"),
        ('<span class="mark">sem notificação prévia</span>', "sem notificação prévia"),
        ("artigo 32:**", "artigo 32:"),
        ("artigo 40-A:**", "artigo 40-A:"),
        ("artigo 51-A:**", "artigo 51-A:"),
        ("modificações:**", "modificações:"),
        ("### CAPÍTULO XV — DO AGENTE DE DESENVOLVIMENTO { .centro }\n\n"
         "**Art. 89.** Caberá ao Chefe do Executivo Municipal a designação de servidor e área responsável em sua estrutura funcional para a efetivação dos dispositivos previstos na presente Lei, observadas as especificidades locais.*\n{ #art-89 }\n\n"
         "§ 1º A função de Agente de desenvolvimento caracteriza-se pelo exercício de articulação das ações públicas para a promoção do desenvolvimento local e territorial, mediante ações locais ou comunitárias, individuais ou coletivas, que busquem o cumprimento das disposições e diretrizes contidas nesta Lei, sob supervisão do órgão gestor local responsável pelas políticas de desenvolvimento.*\n\n"
         "§ 2º O agente de desenvolvimento deverá preencher os seguintes requisitos:*\n\n"
         "I - residir na área da comunidade em que atuar;*\n\n"
         "II - ter concluído, com aproveitamento, curso de qualificação básica para a formação de agente de desenvolvimento;*\n\n"
         "III - ter concluído o ensino fundamental.*\n\n"
         "§ 3º Caberá ao agente de desenvolvimento buscar junto ao Ministério do Desenvolvimento, Indústria e Comércio Exterior, juntamente com as demais entidades municipalistas e de apoio e representação empresarial, o suporte para ações de capacitação, estudos, pesquisas, publicações, promoção de intercâmbio de informações e experiências.*\n\n"
         "Parágrafo único. Após a indicação do Agente de Desenvolvimento caberá ao Chefe do Executivo nomeá-lo mediante portaria, oportunidade em que traçará as diretrizes a serem cumpridas.*\n\n"
         "### CAPÍTULO XVI — DO APOIO E DA REPRESENTAÇÃO { .centro }\n\n"
         "**Art. 90.** Para o cumprimento do disposto nesta lei, bem como para desenvolver e acompanhar políticas públicas voltadas às MEs, EPPs e MEIs, a Administração Pública Municipal poderá incentivar e apoiar a criação de um Fórum Municipal, com a participação dos representantes dos órgãos públicos e das entidades vinculadas ao setor empresarial urbano e rural, além de estimular a participa­ção dos mesmos em fóruns regionais e estaduais.*\n{ #art-90 }\n\n"
         "### CAPÍTULO XVII — DO ESTÍMULO À FORMALIZAÇÃO DE EMPREENDIMENTOS { .centro }\n\n"
         "**Art. 91.** Com o objetivo de incentivar a regularização das atividades empresariais no Município, fica o Poder Executivo Municipal autorizado a conceder às pessoas físicas ou jurídicas que desempenham atividades econômicas e, espontaneamente, no prazo de 30 (trinta) dias após a promulgação desta lei, providenciem sua regularização, os seguintes benefícios:*\n{ #art-91 }\n\n"
         "I - ficarão eximidas de quaisquer penalidades referentes ao período de informalidade,*\n\n"
         "II - receberão orientação quanto à atividade ou situação em que se encontra o empreendimento em relação a aspectos trabalhistas, metrológicos, sanitários, ambientais e de segurança.*\n\n"
         "III - usufruirão de todos os serviços ofertados pela Sala do Empreendedor, descritos no artigo 10 desta lei.*\n\n"
         "Parágrafo único. Para os fins deste artigo, consideram-se informais as atividades econômicas em funcionamento que não estejam inscritas no Cadastro Nacional da Pessoa Jurídica (CNPJ) e no Cadastro de Contribuintes do município.*\n\n"
         "### CAPÍTULO XVIII — DO TURISMO E SUAS MODALIDADES { .centro }\n\n"
         "**Art. 92.** O Poder Público Municipal poderá promover parcerias com órgãos governamentais e não governamentais, entidades de apoio ao desenvolvimento do turismo sustentável, Circuitos Turísticos e outras instâncias de governança, que visem à melhoria da produtividade e da qualidade de produtos turísticos do Município.*\n{ #art-92 }\n\n"
         "§ 1º Das parcerias referidas neste artigo poderão fazer parte Associações e Sindicatos de classe, cooperativas e entidades da iniciativa privada que tenham condições de contribuir para a implementação de projetos, mediante geração e disseminação de conhecimento, fornecimento de insumos às ME, EPP e empreendedores rurais especificamente do setor.*\n\n"
         "§ 2º Poderão receber os benefícios das ações referidas no caput deste artigo os pequenos empreendimentos do setor turístico, legalmente constituídos, e que tenham realizado seu cadastro junto ao Ministério do Turismo, através do CADASTUR ou outro mecanismo de cadastramento que venha substituí-lo.*\n\n"
         "§ 3º Competirá à Secretaria Municipal de Administração Finanças e Planejamento, juntamente com o COMTUR – Conselho Municipal de Turismo –, disciplinar e coordenar as ações necessárias à consecução dos objetivos das parcerias referidas neste artigo, atendidos os dispositivos legais pertinentes.*\n\n"
         "§ 4º O Município concentrará seus esforços no sentido de promover o desenvolvimento do turismo nas modalidades características da região.*\n\n"
         "### CAPÍTULO XIX — DAS DISPOSIÇÕES FINAIS E TRANSITÓRIAS { .centro }\n\n"
         "**Art. 93.** Fica instituído o Dia Municipal da Micro e Pequena Empresa e do Desenvolvimento, que será comemorado em 5 de outubro de cada ano.*\n{ #art-93 }\n\n"
         "Parágrafo único. Nesse dia, será realizada audiência pública na Câmara dos Vereadores, amplamente divulgada, em que serão ouvidas lideranças empresariais e debatidas propostas de fomento aos pequenos negócios e melhorias da legislação específica.*\n\n"
         "**Art. 94.** A Secretaria Municipal de Administração Finanças e Planejamento elaborará cartilha para ampla divulgação dos benefícios e das vantagens instituídos por esta Lei, especialmente buscando a formalização dos empreendimentos informais.*\n{ #art-94 }\n\n"
         "**Art. 95.** A Administração Pública Municipal, como forma de estimular a criação de novas micro e pequenas empresas no município e promover o seu desenvolvimento, incentivará a criação de programas específicos de atração de novas empresas de forma direta ou em parceria com outras entidades públicas ou privadas.*\n{ #art-95 }\n\n"
         "**Art. 96.** Toda a concessão ou ampliação de incentivo ou benefício de natureza tributária da qual decorra renúncia de receita deverá atender ao disposto no art. 14 da Lei Complementar 101/2000.*\n{ #art-96 }\n\n"
         "**Art. 97.** As despesas decorrentes da presente Lei correrão por conta das dotações constantes do orçamento municipal.*\n{ #art-97 }\n\n"
         "**Art. 98.** Fica o Poder Executivo municipal autorizado a celebrar convênios e demais instrumentos públicos, na forma da Lei, visando a participação e a cooperação de instituições públicas e privadas que possam contribuir para o alcance dos resultados almejados pelas políticas públicas estabelecidas nesta Lei.*\n{ #art-98 }",
         "> **CAPÍTULO XV — DO AGENTE DE DESENVOLVIMENTO**\n>\n"
         "> “Art. 89. Caberá ao Chefe do Executivo Municipal a designação de servidor e área responsável em sua estrutura funcional para a efetivação dos dispositivos previstos na presente Lei, observadas as especificidades locais.\n>\n"
         "> § 1º A função de Agente de desenvolvimento caracteriza-se pelo exercício de articulação das ações públicas para a promoção do desenvolvimento local e territorial, mediante ações locais ou comunitárias, individuais ou coletivas, que busquem o cumprimento das disposições e diretrizes contidas nesta Lei, sob supervisão do órgão gestor local responsável pelas políticas de desenvolvimento.\n>\n"
         "> § 2º O agente de desenvolvimento deverá preencher os seguintes requisitos:\n>\n"
         "> I - residir na área da comunidade em que atuar;\n>\n"
         "> II - ter concluído, com aproveitamento, curso de qualificação básica para a formação de agente de desenvolvimento;\n>\n"
         "> III - ter concluído o ensino fundamental.\n>\n"
         "> § 3º Caberá ao agente de desenvolvimento buscar junto ao Ministério do Desenvolvimento, Indústria e Comércio Exterior, juntamente com as demais entidades municipalistas e de apoio e representação empresarial, o suporte para ações de capacitação, estudos, pesquisas, publicações, promoção de intercâmbio de informações e experiências.\n>\n"
         "> Parágrafo único. Após a indicação do Agente de Desenvolvimento caberá ao Chefe do Executivo nomeá-lo mediante portaria, oportunidade em que traçará as diretrizes a serem cumpridas.\n>\n"
         "> **CAPÍTULO XVI — DO APOIO E DA REPRESENTAÇÃO**\n>\n"
         "> Art. 90. Para o cumprimento do disposto nesta lei, bem como para desenvolver e acompanhar políticas públicas voltadas às MEs, EPPs e MEIs, a Administração Pública Municipal poderá incentivar e apoiar a criação de um Fórum Municipal, com a participação dos representantes dos órgãos públicos e das entidades vinculadas ao setor empresarial urbano e rural, além de estimular a participa­ção dos mesmos em fóruns regionais e estaduais.\n>\n"
         "> **CAPÍTULO XVII — DO ESTÍMULO À FORMALIZAÇÃO DE EMPREENDIMENTOS**\n>\n"
         "> Art. 91. Com o objetivo de incentivar a regularização das atividades empresariais no Município, fica o Poder Executivo Municipal autorizado a conceder às pessoas físicas ou jurídicas que desempenham atividades econômicas e, espontaneamente, no prazo de 30 (trinta) dias após a promulgação desta lei, providenciem sua regularização, os seguintes benefícios:\n>\n"
         "> I - ficarão eximidas de quaisquer penalidades referentes ao período de informalidade,\n>\n"
         "> II - receberão orientação quanto à atividade ou situação em que se encontra o empreendimento em relação a aspectos trabalhistas, metrológicos, sanitários, ambientais e de segurança.\n>\n"
         "> III - usufruirão de todos os serviços ofertados pela Sala do Empreendedor, descritos no artigo 10 desta lei.\n>\n"
         "> Parágrafo único. Para os fins deste artigo, consideram-se informais as atividades econômicas em funcionamento que não estejam inscritas no Cadastro Nacional da Pessoa Jurídica (CNPJ) e no Cadastro de Contribuintes do município.\n>\n"
         "> **CAPÍTULO XVIII — DO TURISMO E SUAS MODALIDADES**\n>\n"
         "> Art. 92. O Poder Público Municipal poderá promover parcerias com órgãos governamentais e não governamentais, entidades de apoio ao desenvolvimento do turismo sustentável, Circuitos Turísticos e outras instâncias de governança, que visem à melhoria da produtividade e da qualidade de produtos turísticos do Município.\n>\n"
         "> § 1º Das parcerias referidas neste artigo poderão fazer parte Associações e Sindicatos de classe, cooperativas e entidades da iniciativa privada que tenham condições de contribuir para a implementação de projetos, mediante geração e disseminação de conhecimento, fornecimento de insumos às ME, EPP e empreendedores rurais especificamente do setor.\n>\n"
         "> § 2º Poderão receber os benefícios das ações referidas no caput deste artigo os pequenos empreendimentos do setor turístico, legalmente constituídos, e que tenham realizado seu cadastro junto ao Ministério do Turismo, através do CADASTUR ou outro mecanismo de cadastramento que venha substituí-lo.\n>\n"
         "> § 3º Competirá à Secretaria Municipal de Administração Finanças e Planejamento, juntamente com o COMTUR – Conselho Municipal de Turismo –, disciplinar e coordenar as ações necessárias à consecução dos objetivos das parcerias referidas neste artigo, atendidos os dispositivos legais pertinentes.\n>\n"
         "> § 4º O Município concentrará seus esforços no sentido de promover o desenvolvimento do turismo nas modalidades características da região.\n>\n"
         "> **CAPÍTULO XIX — DAS DISPOSIÇÕES FINAIS E TRANSITÓRIAS**\n>\n"
         "> Art. 93. Fica instituído o Dia Municipal da Micro e Pequena Empresa e do Desenvolvimento, que será comemorado em 5 de outubro de cada ano.\n>\n"
         "> Parágrafo único. Nesse dia, será realizada audiência pública na Câmara dos Vereadores, amplamente divulgada, em que serão ouvidas lideranças empresariais e debatidas propostas de fomento aos pequenos negócios e melhorias da legislação específica.\n>\n"
         "> Art. 94. A Secretaria Municipal de Administração Finanças e Planejamento elaborará cartilha para ampla divulgação dos benefícios e das vantagens instituídos por esta Lei, especialmente buscando a formalização dos empreendimentos informais.\n>\n"
         "> Art. 95. A Administração Pública Municipal, como forma de estimular a criação de novas micro e pequenas empresas no município e promover o seu desenvolvimento, incentivará a criação de programas específicos de atração de novas empresas de forma direta ou em parceria com outras entidades públicas ou privadas.\n>\n"
         "> Art. 96. Toda a concessão ou ampliação de incentivo ou benefício de natureza tributária da qual decorra renúncia de receita deverá atender ao disposto no art. 14 da Lei Complementar 101/2000.\n>\n"
         "> Art. 97. As despesas decorrentes da presente Lei correrão por conta das dotações constantes do orçamento municipal.\n>\n"
         "> Art. 98. Fica o Poder Executivo municipal autorizado a celebrar convênios e demais instrumentos públicos, na forma da Lei, visando a participação e a cooperação de instituições públicas e privadas que possam contribuir para o alcance dos resultados almejados pelas políticas públicas estabelecidas nesta Lei.”"),
        ("833/2009, de 09 de dezembro de 2009.**", "833/2009, de 09 de dezembro de 2009."),
    ],
    ("2013", "1039"): [
        ('<h3 id="legislativa">Legislativa</h3>', "Legislativa"),
        ('<h3 id="controle-externo">Controle Externo</h3>', "Controle Externo"),
        ('<h3 id="valorizar-melhor-as-aplicações-dos-recursos-públicos-em-todos-os-órgãos-da-administração-do-município-evitando-o-desperdício-tendo-um-melhor-aproveitamento-na-melhoria-de-atendimento-da-população.-desenvolver-projetos-para-agilizar-a-fiscalização-dos-orçamentos-com-acompanhamento-dos-projetos-e-atividades-de-responsabilidade-do-poder-legislativo.">', "<p>"),
        ('<h3 id="fundo-municipal-de-defesa-civil-fmdc-criado-pela-lei-nº.10152013-de-18-de-junho-de-2013.-vinculado-à-secretaria-municipal-de-obras-infra-estrutura-e-serviços-urbanos-configurado-como-órgão-captador-e-aplicador-dos-recursos-financeiros-que-tenham-finalidade-de-prover-execuções-de-medidas-de-defesa-civil-tudo-em-conformidade-com-aquelas-exaradas-nos-parágrafos-1º-2º-3º-e-4º-do-art.-1º-da-lei-estadual-nº-3.278-de-23-de-outubro-de-2006.-que-será-supervisionado-e-fiscalizado-pelo-conselho-municipal-de-defesa-civil-aquisição-de-um-veiculo-para-atender-as-necessidade-dos-conselhos-municipais-de-defesa-civil-e-conselho-municipal-das-cidades.">', "<p>"),
        ("</h3>", "</p>"),
    ],
    ("2013", "1042"): [("SANESUL**.**", "SANESUL.")],
    ("2013", "1043"): [
        ("### CAPÍTULO III — DOS ÓRGÃOS EXECUTORES DA POLÍTICA MUNICIPAL DE { .centro }\n\nSANEAMENTO BÁSICO",
         "### CAPÍTULO III — DOS ÓRGÃOS EXECUTORES DA POLÍTICA MUNICIPAL DE SANEAMENTO BÁSICO { .centro }"),
        ("Conselho Municipal de Saneamento**.**", "Conselho Municipal de Saneamento."),
        ('1.  A Política Municipal de Saneamento Básico de Batayporã, com fundamento na Lei Federal n°. 11.445/07, tem como objetivo, respeitadas as competências da União e do Estado, melhorar a qualidade da sanidade pública e manter o meio ambiente equilibrado buscando o desenvolvimento sustentável e fornecendo diretrizes ao poder público e à coletividade para a defesa, conservação e recuperação da qualidade e salubridade ambiental, cabendo a todos o direito de exigir a adoção de medidas nesse sentido.', '**Art. 1º** A Política Municipal de Saneamento Básico de Batayporã, com fundamento na Lei Federal n°. 11.445/07, tem como objetivo, respeitadas as competências da União e do Estado, melhorar a qualidade da sanidade pública e manter o meio ambiente equilibrado buscando o desenvolvimento sustentável e fornecendo diretrizes ao poder público e à coletividade para a defesa, conservação e recuperação da qualidade e salubridade ambiental, cabendo a todos o direito de exigir a adoção de medidas nesse sentido.\n{ #art-1 }'),
        ('10. Para os efeitos desta lei considera-se saneamento básico o conjunto de serviços, infraestrutura e instalações operacionais de:', 'Parágrafo único. Para os efeitos desta lei considera-se saneamento básico o conjunto de serviços, infraestrutura e instalações operacionais de:'),
        ('1.  Os recursos hídricos não integram os serviços de saneamento básico.', '**Art. 2º** Os recursos hídricos não integram os serviços de saneamento básico.\n{ #art-2 }'),
        ('11. A utilização de recursos hídricos na prestação de serviços públicos de saneamento básico, inclusive para a disposição ou diluição de esgotos e outros resíduos líquidos, é sujeita a outorga de direito de uso, nos termos da Lei Federal nº. 9.433, de 08 de janeiro de 1997, de seus regulamentos e da legislação estadual.', 'Parágrafo único. A utilização de recursos hídricos na prestação de serviços públicos de saneamento básico, inclusive para a disposição ou diluição de esgotos e outros resíduos líquidos, é sujeita a outorga de direito de uso, nos termos da Lei Federal nº. 9.433, de 08 de janeiro de 1997, de seus regulamentos e da legislação estadual.'),
        ('2.  Não constitui serviço público de saneamento a ação executada por meio de soluções individuais, desde que o usuário não dependa de terceiros para operar os serviços, bem como as ações de saneamento básico de responsabilidade privada, incluindo o manejo de resíduos de responsabilidade do gerador.', '**Art. 2º** Não constitui serviço público de saneamento a ação executada por meio de soluções individuais, desde que o usuário não dependa de terceiros para operar os serviços, bem como as ações de saneamento básico de responsabilidade privada, incluindo o manejo de resíduos de responsabilidade do gerador.\n{ #art-2-b }'),
        ('3.  O lixo originário de atividades comerciais, industriais e de serviços cuja responsabilidade pelo manejo não seja atribuída ao gerador pode, por decisão do poder público, ser considerado resíduo sólido urbano.', '**Art. 3º** O lixo originário de atividades comerciais, industriais e de serviços cuja responsabilidade pelo manejo não seja atribuída ao gerador pode, por decisão do poder público, ser considerado resíduo sólido urbano.\n{ #art-3 }'),
        ('4.  Para o estabelecimento da Política Municipal de Saneamento Básico serão observados os seguintes princípios fundamentais:', '**Art. 4º** Para o estabelecimento da Política Municipal de Saneamento Básico serão observados os seguintes princípios fundamentais:\n{ #art-4 }'),
        ('5.  Para o cumprimento do disposto no art. 30 da Constituição Federal e artigo 142 ao 155 da Lei Orgânica de Batayporã no que concerne ao saneamento básico consideram-se como de interesse local:', '**Art. 5º** Para o cumprimento do disposto no art. 30 da Constituição Federal e artigo 142 ao 155 da Lei Orgânica de Batayporã no que concerne ao saneamento básico consideram-se como de interesse local:\n{ #art-5 }'),
        ('6.  No acondicionamento, coleta, transporte, tratamento e disposição final dos resíduos sólidos deverão ser observados, além de outros previstos, os seguintes procedimentos:', '**Art. 6º** No acondicionamento, coleta, transporte, tratamento e disposição final dos resíduos sólidos deverão ser observados, além de outros previstos, os seguintes procedimentos:\n{ #art-6 }'),
        ('1.  A separação e o acondicionamento dos resíduos de que trata o inciso I é de responsabilidade do gerador, sendo a coleta, transporte e destino final de responsabilidade do Município no caso em que a produção semanal do gerador não seja superior a 600 litros.', '§ 1º A separação e o acondicionamento dos resíduos de que trata o inciso I é de responsabilidade do gerador, sendo a coleta, transporte e destino final de responsabilidade do Município no caso em que a produção semanal do gerador não seja superior a 600 litros.'),
        ('2.  O acondicionamento, coleta, transporte e disposição final dos resíduos de que trata os incisos II e III é de responsabilidade do gerador.', '§ 2º O acondicionamento, coleta, transporte e disposição final dos resíduos de que trata os incisos II e III é de responsabilidade do gerador.'),
        ('3.  Os resíduos da construção civil, poda de árvores e manutenção de jardins, até 1m³ (um metro cúbico), produzido a cada 30 (trinta) dias por unidade geradora, e os objetos volumosos poderão ser encaminhados às estações de depósitos (ecopontos) indicados pela Prefeitura ou recolhido por esta nos locais geradores conforme definição da Administração.', '§ 3º Os resíduos da construção civil, poda de árvores e manutenção de jardins, até 1m³ (um metro cúbico), produzido a cada 30 (trinta) dias por unidade geradora, e os objetos volumosos poderão ser encaminhados às estações de depósitos (ecopontos) indicados pela Prefeitura ou recolhido por esta nos locais geradores conforme definição da Administração.'),
        ('4.  Os resíduos da construção civil e de poda de árvores e manutenção de jardins poderão ser coletados pela Prefeitura, quando não superior a 30 (trinta) quilos e dimensões de até 40 (quarenta) centímetros e acondicionado separadamente dos demais resíduos.', '§ 4º Os resíduos da construção civil e de poda de árvores e manutenção de jardins poderão ser coletados pela Prefeitura, quando não superior a 30 (trinta) quilos e dimensões de até 40 (quarenta) centímetros e acondicionado separadamente dos demais resíduos.'),
        ('5.  Constitui infração grave a não separação dos resíduos recicláveis nas áreas ou nas atividades determinadas pelo Poder Público Municipal.', '§ 5º Constitui infração grave a não separação dos resíduos recicláveis nas áreas ou nas atividades determinadas pelo Poder Público Municipal.'),
        ('6.  A deposição de qualquer espécie de resíduo gerado em outro município no Município Batayporã só poderá ser feita se autorizado por este.', '§ 6º A deposição de qualquer espécie de resíduo gerado em outro município no Município Batayporã só poderá ser feita se autorizado por este.'),
        ('7.  A Política Municipal de Saneamento Básico de Batayporã será executada pela Secretaria Municipal de Meio Ambiente e distribuída de forma transdisciplinar em todas as secretarias e órgãos da Administração Municipal, respeitadas as suas competências.', '**Art. 7º** A Política Municipal de Saneamento Básico de Batayporã será executada pela Secretaria Municipal de Meio Ambiente e distribuída de forma transdisciplinar em todas as secretarias e órgãos da Administração Municipal, respeitadas as suas competências.\n{ #art-7 }'),
        ('8.  Os serviços básicos de saneamento de que trata o parágrafo único do art. 1º desta Lei poderão ser executados das seguintes formas:', '**Art. 8º** Os serviços básicos de saneamento de que trata o parágrafo único do art. 1º desta Lei poderão ser executados das seguintes formas:\n{ #art-8 }'),
        ('1.  A prestação de serviços públicos de saneamento básico por entidade que não integre a administração municipal depende de celebração de contrato, sendo vedado a sua disciplina mediante convênios, termos de parceria ou outros instrumentos de natureza precária.', '§ 1º A prestação de serviços públicos de saneamento básico por entidade que não integre a administração municipal depende de celebração de contrato, sendo vedado a sua disciplina mediante convênios, termos de parceria ou outros instrumentos de natureza precária.'),
        ('2.  Excetuam do disposto no artigo anterior os serviços autorizados para usuários organizados em cooperativas, associações ou condomínios, desde que se limite a:', '§ 2º Excetuam do disposto no artigo anterior os serviços autorizados para usuários organizados em cooperativas, associações ou condomínios, desde que se limite a:'),
        ('1.  Da autorização prevista no parágrafo anterior deverá constar a obrigação de transferir ao titular os bens vinculados aos serviços por meio de termo específicos, com os respectivos cadastros técnicos.', '§ 2º Da autorização prevista no parágrafo anterior deverá constar a obrigação de transferir ao titular os bens vinculados aos serviços por meio de termo específicos, com os respectivos cadastros técnicos.'),
        ('10. São condições de validade dos contratos que tenham por objeto a prestação de serviços públicos de saneamento básico;', '**Art. 10.** São condições de validade dos contratos que tenham por objeto a prestação de serviços públicos de saneamento básico;\n{ #art-10 }'),
        ('11. Nos casos de serviços prestados mediante contratos de concessão ou de programa, as normas previstas no inciso II do artigo anterior deverão prever:', '**Art. 11.** Nos casos de serviços prestados mediante contratos de concessão ou de programa, as normas previstas no inciso II do artigo anterior deverão prever:\n{ #art-11 }'),
        ('1.  Os contratos não poderão conter cláusulas que prejudiquem as atividades de regulação e de fiscalização ou de acesso ás informações sobre serviços contratados.', '§ 1º Os contratos não poderão conter cláusulas que prejudiquem as atividades de regulação e de fiscalização ou de acesso ás informações sobre serviços contratados.'),
        ('1.  Na prestação regionalizada, o disposto neste artigo e no anterior poderá se referir ao conjunto de municípios por ela abrangidos.', '§ 2º Na prestação regionalizada, o disposto neste artigo e no anterior poderá se referir ao conjunto de municípios por ela abrangidos.'),
        ('12. Nos serviços públicos de saneamento básico em que mais de um prestador execute atividade interdependente com outra, a relação entre elas deverá se regulada por contrato e haverá órgão único encarregado das funções de regulação e de fiscalização.', '**Art. 12.** Nos serviços públicos de saneamento básico em que mais de um prestador execute atividade interdependente com outra, a relação entre elas deverá se regulada por contrato e haverá órgão único encarregado das funções de regulação e de fiscalização.\n{ #art-12 }'),
        ('12. Na regulação deverá ser definido, pelos menos:', 'Parágrafo único. Na regulação deverá ser definido, pelos menos:'),
        ('13. O contrato a ser celebrado entre os prestadores de serviços a que se refere o artigo anterior deverá conter cláusulas que estabeleçam pelo menos:', '**Art. 13.** O contrato a ser celebrado entre os prestadores de serviços a que se refere o artigo anterior deverá conter cláusulas que estabeleçam pelo menos:\n{ #art-13 }'),
        ('14. O Município poderá participar de prestação regionalizada de serviços de saneamento básico que é caracterizada por:', '**Art. 14.** O Município poderá participar de prestação regionalizada de serviços de saneamento básico que é caracterizada por:\n{ #art-14 }'),
        ('1.  Na prestação de serviços de que trata este artigo, as atividades de regulação e fiscalização poderão ser exercidas:', '§ 1º Na prestação de serviços de que trata este artigo, as atividades de regulação e fiscalização poderão ser exercidas:'),
        ('1.  No exercício das atividades de planejamento dos serviços a que se refere o caput deste Art., o titular poderá receber cooperação técnica do Estado e basear-se em estudos fornecidos pelos prestadores.', '§ 2º No exercício das atividades de planejamento dos serviços a que se refere o caput deste Art., o titular poderá receber cooperação técnica do Estado e basear-se em estudos fornecidos pelos prestadores.'),
        ('15. A prestação regionalizada de serviços públicos de saneamento básico poderá ser realizada por:', '**Art. 15.** A prestação regionalizada de serviços públicos de saneamento básico poderá ser realizada por:\n{ #art-15 }'),
        ('1.  O serviço regionalizado de saneamento básico poderá obedecer o plano de saneamento básico elaborado para o conjunto dos municípios.', '§ 1º O serviço regionalizado de saneamento básico poderá obedecer o plano de saneamento básico elaborado para o conjunto dos municípios.'),
        ('1.  Os prestadores deverão manter sistema contábil que permita registrar e demonstrar, separadamente, os custos e as receitas de cada serviço para cada um dos municípios atendidos.', '§ 3º Os prestadores deverão manter sistema contábil que permita registrar e demonstrar, separadamente, os custos e as receitas de cada serviço para cada um dos municípios atendidos.'),
        ('16. O exercício da função de regular não poderá ser exercido por quem presta o serviço e atenderá aos seguintes princípios:', '**Art. 16.** O exercício da função de regular não poderá ser exercido por quem presta o serviço e atenderá aos seguintes princípios:\n{ #art-16 }'),
        ('17. São objetivos da regulação:', '**Art. 17.** São objetivos da regulação:\n{ #art-17 }'),
        ('18. O órgão ou entidade reguladora editará normas relativas às dimensões técnica, econômica e social de prestação dos serviços, que abrangerão, pelo menos, os seguintes aspectos:', '**Art. 18.** O órgão ou entidade reguladora editará normas relativas às dimensões técnica, econômica e social de prestação dos serviços, que abrangerão, pelo menos, os seguintes aspectos:\n{ #art-18 }'),
        ('1.  As normas previstas neste artigo deverão fixar prazo para os prestadores de serviços comunicarem aos usuários as providências adotadas em face de queixas ou de reclamações relativas aos serviços.', '§ 1º As normas previstas neste artigo deverão fixar prazo para os prestadores de serviços comunicarem aos usuários as providências adotadas em face de queixas ou de reclamações relativas aos serviços.'),
        ('1.  O órgão ou entidade fiscalizadora deverá receber e se manifestar conclusivamente sobe as reclamações que, a juízo do interessado, não tenham sido suficientemente atendidas pelos prestadores dos serviços.', '§ 4º O órgão ou entidade fiscalizadora deverá receber e se manifestar conclusivamente sobe as reclamações que, a juízo do interessado, não tenham sido suficientemente atendidas pelos prestadores dos serviços.'),
        ('19. Em caso de gestão associada ou prestação regionalizada dos serviços, poderão ser adotados os mesmos critérios econômicos, sociais e técnicos da regulação em toda a área de abrangência da associação ou prestação.', '**Art. 19.** Em caso de gestão associada ou prestação regionalizada dos serviços, poderão ser adotados os mesmos critérios econômicos, sociais e técnicos da regulação em toda a área de abrangência da associação ou prestação.\n{ #art-19 }'),
        ('20. Os prestadores de serviços de saneamento básico deverão fornecer ao órgão ou entidade reguladora todos os dados e informações necessárias para o desempenho de suas atividades, na forma das normas legais, regulamentares e contratuais.', '**Art. 20.** Os prestadores de serviços de saneamento básico deverão fornecer ao órgão ou entidade reguladora todos os dados e informações necessárias para o desempenho de suas atividades, na forma das normas legais, regulamentares e contratuais.\n{ #art-20 }'),
        ('1.  Inclui-se entre os dados e informações a que se refere o caput deste artigo aquelas produzidas por empresas ou profissionais contratados para executar serviços ou fornecer materiais e equipamentos específicos.', '§ 1º Inclui-se entre os dados e informações a que se refere o caput deste artigo aquelas produzidas por empresas ou profissionais contratados para executar serviços ou fornecer materiais e equipamentos específicos.'),
        ('1.  Compreendem-se nas atividades de regulação a interpretação e a fixação de critérios para a fiel execução dos contratos, dos serviços e para a correta administração de subsídios.', '§ 5º Compreendem-se nas atividades de regulação a interpretação e a fixação de critérios para a fiel execução dos contratos, dos serviços e para a correta administração de subsídios.'),
        ('21. Deve ser assegurada publicidade aos relatórios, estudos, decisões e instrumentos equivalentes que se refiram à regulação ou a fiscalização dos serviços, bem como aos direitos e deveres dos usuários e prestadores, com acesso permitido a todos, independente da existência de interesse direto.', '**Art. 21.** Deve ser assegurada publicidade aos relatórios, estudos, decisões e instrumentos equivalentes que se refiram à regulação ou a fiscalização dos serviços, bem como aos direitos e deveres dos usuários e prestadores, com acesso permitido a todos, independente da existência de interesse direto.\n{ #art-21 }'),
        ('1.  Excluem-se do disposto no caput deste artigo os documentos considerados sigilosos em razão de interesse público relevante, mediante prévia e motivada decisão.', '§ 1º Excluem-se do disposto no caput deste artigo os documentos considerados sigilosos em razão de interesse público relevante, mediante prévia e motivada decisão.'),
        ('1.  A publicidade a que se refere o caput deste artigo deverá se efetivar por diversos meios, inclusive por meio de sítio atualizado na rede mundial de computadores – Internet, devendo em sua divulgação, manter as informações atualizadas.', '§ 6º A publicidade a que se refere o caput deste artigo deverá se efetivar por diversos meios, inclusive por meio de sítio atualizado na rede mundial de computadores – Internet, devendo em sua divulgação, manter as informações atualizadas.'),
        ('22. É assegurado aos usuários dos serviços públicos de saneamento básico:', '**Art. 22.** É assegurado aos usuários dos serviços públicos de saneamento básico:\n{ #art-22 }'),
        ('23. Os serviços de saneamento básico de que trata esta Lei terão a sustentabilidade econômico-financeira assegurada, sempre que possível, mediante remuneração pela cobrança dos serviços:', '**Art. 23.** Os serviços de saneamento básico de que trata esta Lei terão a sustentabilidade econômico-financeira assegurada, sempre que possível, mediante remuneração pela cobrança dos serviços:\n{ #art-23 }'),
        ('1.  Na instituição das tarifas, preços públicos e taxas para aos serviços básicos serão observadas as seguintes diretrizes:', '§ 1º Na instituição das tarifas, preços públicos e taxas para aos serviços básicos serão observadas as seguintes diretrizes:'),
        ('1.  O Município poderá adotar subsídios tarifários e não tarifários para os usuários e localidades que não tenham capacidade de pagamento ou escala econômica suficiente para cobrir o custo integral dos serviços.', '§ 2º O Município poderá adotar subsídios tarifários e não tarifários para os usuários e localidades que não tenham capacidade de pagamento ou escala econômica suficiente para cobrir o custo integral dos serviços.'),
        ('24. Observado o disposto no artigo anterior, a estrutura de remuneração e cobrança dos serviços públicos de saneamento básico poderá levar em consideração os seguintes fatores:', '**Art. 24.** Observado o disposto no artigo anterior, a estrutura de remuneração e cobrança dos serviços públicos de saneamento básico poderá levar em consideração os seguintes fatores:\n{ #art-24 }'),
        ('25. Os subsídios necessários ao atendimento de usuários e localidades de baixa renda poderão ser:', '**Art. 25.** Os subsídios necessários ao atendimento de usuários e localidades de baixa renda poderão ser:\n{ #art-25 }'),
        ('26. As taxas ou tarifas decorrentes da prestação de serviço público de limpeza urbana e de manejo de resíduos sólidos urbanos devem levar em conta a adequada destinação dos resíduos coletados e poderão considerar em conjunto ou separadamente:', '**Art. 26.** As taxas ou tarifas decorrentes da prestação de serviço público de limpeza urbana e de manejo de resíduos sólidos urbanos devem levar em conta a adequada destinação dos resíduos coletados e poderão considerar em conjunto ou separadamente:\n{ #art-26 }'),
        ('27. A cobrança pela prestação do serviço público de drenagem e manejo de águas pluviais urbanas deve levar em conta, em cada lote, os percentuais de impermeabilização e a existência de dispositivos de amortecimento ou de retenção de água de chuva, podendo considerar também;', '**Art. 27.** A cobrança pela prestação do serviço público de drenagem e manejo de águas pluviais urbanas deve levar em conta, em cada lote, os percentuais de impermeabilização e a existência de dispositivos de amortecimento ou de retenção de água de chuva, podendo considerar também;\n{ #art-27 }'),
        ('28. O reajuste de tarifas de serviços públicos de saneamento básico será realizado observando-se o intervalo mínimo de 12 (doze) meses, de acordo com as normas legais, regulamentares e contratuais.', '**Art. 28.** O reajuste de tarifas de serviços públicos de saneamento básico será realizado observando-se o intervalo mínimo de 12 (doze) meses, de acordo com as normas legais, regulamentares e contratuais.\n{ #art-28 }'),
        ('29. As revisões tarifárias compreenderão a reavaliação das condições da prestação dos serviços e das tarifas praticadas e poderão ser:', '**Art. 29.** As revisões tarifárias compreenderão a reavaliação das condições da prestação dos serviços e das tarifas praticadas e poderão ser:\n{ #art-29 }'),
        ('1.  As revisões tarifárias terão suas pautas definidas pelo órgão ou entidade reguladora, ouvidos os usuários e os prestadores dos serviços.', '§ 1º As revisões tarifárias terão suas pautas definidas pelo órgão ou entidade reguladora, ouvidos os usuários e os prestadores dos serviços.'),
        ('1.  Poderão ser estabelecidos mecanismos tarifários de indução à eficiência, inclusive fatores de produtividade, assim como de antecipação de metas de expansão e qualidade dos serviços.', '§ 7º Poderão ser estabelecidos mecanismos tarifários de indução à eficiência, inclusive fatores de produtividade, assim como de antecipação de metas de expansão e qualidade dos serviços.'),
        ('2.  O órgão ou entidade reguladora poderá autorizar o prestador dos serviços a repassar aos usuários custos e encargos tributários não previstos originalmente e por ele não administrados, nos termos da Lei Federal nº. 8.987/95.', '§ 8º O órgão ou entidade reguladora poderá autorizar o prestador dos serviços a repassar aos usuários custos e encargos tributários não previstos originalmente e por ele não administrados, nos termos da Lei Federal nº. 8.987/95.'),
        ('30. As tarifas devem ser fixadas de forma clara e objetiva, devendo os reajustes e as revisões tornados públicos com antecedência mínima de 30 (trinta) dias com relação à sua aplicação.', '**Art. 30.** As tarifas devem ser fixadas de forma clara e objetiva, devendo os reajustes e as revisões tornados públicos com antecedência mínima de 30 (trinta) dias com relação à sua aplicação.\n{ #art-30 }'),
        ('13. A fatura a ser entregue ao usuário final deverá ter seu modelo aprovado pelo órgão ou entidade reguladora, que definirá os itens e custos a serem explicitados.', 'Parágrafo único. A fatura a ser entregue ao usuário final deverá ter seu modelo aprovado pelo órgão ou entidade reguladora, que definirá os itens e custos a serem explicitados.'),
        ('31. Os serviços poderão ser interrompidos pelo prestador das seguintes hipóteses:', '**Art. 31.** Os serviços poderão ser interrompidos pelo prestador das seguintes hipóteses:\n{ #art-31 }'),
        ('1.  As interrupções dos programas serão previamente comunicadas ao regulador e aos usuários.', '§ 1º As interrupções dos programas serão previamente comunicadas ao regulador e aos usuários.'),
        ('1.  A suspensão dos serviços prevista nos incisos III e V será precedida de prévio aviso ao usuário, não inferior a 30 (trinta) dias da data prevista para a suspensão.', '§ 9º A suspensão dos serviços prevista nos incisos III e V será precedida de prévio aviso ao usuário, não inferior a 30 (trinta) dias da data prevista para a suspensão.'),
        ('2.  A interrupção ou a restrição do fornecimento de água por inadimplência a estabelecimentos de saúde, a instituições educacionais e de internação de pessoas e a usuário residencial de baixa renda beneficiário de tarifa social deverá obedecer a prazos e critérios que preservem condições mínimas de manutenção da saúde das pessoas atingidas.', '§ 10º A interrupção ou a restrição do fornecimento de água por inadimplência a estabelecimentos de saúde, a instituições educacionais e de internação de pessoas e a usuário residencial de baixa renda beneficiário de tarifa social deverá obedecer a prazos e critérios que preservem condições mínimas de manutenção da saúde das pessoas atingidas.'),
        ('32. Desde que previsto nas normas de regulação, grandes usuários poderão negociar suas tarifas com o prestador dos serviços, mediante contrato específico, ouvido previamente o regulador.', '**Art. 32.** Desde que previsto nas normas de regulação, grandes usuários poderão negociar suas tarifas com o prestador dos serviços, mediante contrato específico, ouvido previamente o regulador.\n{ #art-32 }'),
        ('33. Os valores investidos em bens reversíveis pelos prestadores constituirão créditos perante o titular, a serem recuperados mediante a exploração dos serviços, nos termos das normas regulamentares e contratuais.', '**Art. 33.** Os valores investidos em bens reversíveis pelos prestadores constituirão créditos perante o titular, a serem recuperados mediante a exploração dos serviços, nos termos das normas regulamentares e contratuais.\n{ #art-33 }'),
        ('1.  Não gerarão crédito perante o titular os investimentos feitos sem ônus para o prestador, tais como os decorrentes de exigência legal aplicável à implantação de empreendimentos imobiliários e os provenientes de subvenções ou transferências fiscais voluntárias.', '§ 1º Não gerarão crédito perante o titular os investimentos feitos sem ônus para o prestador, tais como os decorrentes de exigência legal aplicável à implantação de empreendimentos imobiliários e os provenientes de subvenções ou transferências fiscais voluntárias.'),
        ('1.  Os investimentos realizados, os valores amortizados, a depreciação e os respectivos saldos serão anualmente auditados e certificados pelo órgão ou ente regulador.', '§ 11º Os investimentos realizados, os valores amortizados, a depreciação e os respectivos saldos serão anualmente auditados e certificados pelo órgão ou ente regulador.'),
        ('2.  Os créditos decorrentes de investimentos devidamente certificados poderão constituir garantia de empréstimos aos delegatários, destinados exclusivamente a investimentos nos sistemas de saneamento objeto do respectivo contrato.', '§ 12º Os créditos decorrentes de investimentos devidamente certificados poderão constituir garantia de empréstimos aos delegatários, destinados exclusivamente a investimentos nos sistemas de saneamento objeto do respectivo contrato.'),
        ('34. O serviço prestado atenderá a requisitos mínimos de qualidade, incluindo a regularidade, a continuidade e às condições operacionais e de manutenção dos sistemas.', '**Art. 34.** O serviço prestado atenderá a requisitos mínimos de qualidade, incluindo a regularidade, a continuidade e às condições operacionais e de manutenção dos sistemas.\n{ #art-34 }'),
        ('35. Toda edificação permanente urbana será conectada às redes públicas de abastecimento de água e de esgotamento sanitário disponível e sujeita ao pagamento das tarifas e de outros preços públicos decorrentes da conexão e do uso desses serviços, ressalvadas as disposições em contrário da entidade de regulação e do meio ambiente.', '**Art. 35.** Toda edificação permanente urbana será conectada às redes públicas de abastecimento de água e de esgotamento sanitário disponível e sujeita ao pagamento das tarifas e de outros preços públicos decorrentes da conexão e do uso desses serviços, ressalvadas as disposições em contrário da entidade de regulação e do meio ambiente.\n{ #art-35 }'),
        ('1.  Na ausência de redes públicas de saneamento básico, serão admitidas soluções individuais de abastecimento de água e de esgotamento sanitário, observadas as normas reguladoras.', '§ 1º Na ausência de redes públicas de saneamento básico, serão admitidas soluções individuais de abastecimento de água e de esgotamento sanitário, observadas as normas reguladoras.'),
        ('1.  A instalação hidráulica predial ligada à rede de abastecimento de água não poderá ser também alimentada por outras fontes.', '§ 13º A instalação hidráulica predial ligada à rede de abastecimento de água não poderá ser também alimentada por outras fontes.'),
        ('14. Os recursos do FMSB serão aplicados exclusivamente em saneamento básico no Município, após consulta ao Conselho Municipal de Saneamento.', 'Parágrafo único. Os recursos do FMSB serão aplicados exclusivamente em saneamento básico no Município, após consulta ao Conselho Municipal de Saneamento.'),
        ('15. O resultado dos recolhimentos financeiros será depositado em conta bancária exclusiva e poderão ser aplicados no mercado financeiro ou de capitais de maior rentabilidade, sendo que tanto o capital como os rendimentos somente poderão ser usados para as finalidades específicas descritas nesta Lei.', 'Parágrafo único. O resultado dos recolhimentos financeiros será depositado em conta bancária exclusiva e poderão ser aplicados no mercado financeiro ou de capitais de maior rentabilidade, sendo que tanto o capital como os rendimentos somente poderão ser usados para as finalidades específicas descritas nesta Lei.'),
        ('38. O Orçamento e a Contabilidade do FMSB obedecerão às normas estabelecidas pela Lei n° 4.320/64, bem como as instruções normativas do Tribunal de Contas do Estado e as estabelecidas no Orçamento Geral do Município e de acordo com o princípio da unidade e universalidade, bem como o disposto na Lei Complementar nº 101/2000 .', '**Art. 38.** O Orçamento e a Contabilidade do FMSB obedecerão às normas estabelecidas pela Lei n° 4.320/64, bem como as instruções normativas do Tribunal de Contas do Estado e as estabelecidas no Orçamento Geral do Município e de acordo com o princípio da unidade e universalidade, bem como o disposto na Lei Complementar nº 101/2000 .\n{ #art-38 }'),
        ('1.  Os procedimentos contábeis do Fundo serão executados pela Contabilidade Geral do Município.', '§ 1º Os procedimentos contábeis do Fundo serão executados pela Contabilidade Geral do Município.'),
        ('1.  A administração executiva do FMSB será de exclusiva responsabilidade do Executivo Municipal.', '§ 14º A administração executiva do FMSB será de exclusiva responsabilidade do Executivo Municipal.'),
        ('36. Fica criado o Conselho Municipal de Saneamento como órgão superior de assessoramento e consulta da administração municipal, com funções fiscalizadoras e deliberativas no âmbito de sua competência, conforme dispõe esta Lei.', '**Art. 36.** Fica criado o Conselho Municipal de Saneamento como órgão superior de assessoramento e consulta da administração municipal, com funções fiscalizadoras e deliberativas no âmbito de sua competência, conforme dispõe esta Lei.\n{ #art-36 }'),
        ('37. São atribuições do Conselho Municipal de Saneamento:', '**Art. 37.** São atribuições do Conselho Municipal de Saneamento:\n{ #art-37 }'),
        ('38. O Conselho será composto de 11 (onze) membros efetivos, além de seus respectivos suplentes, com mandato de 02 (dois) anos, admitida a recondução, sendo o Secretário Municipal de Agricultura e Meio Ambiente membro nato, e os demais, nomeados por decreto do Prefeito, da seguinte forma:', '**Art. 38.** O Conselho será composto de 11 (onze) membros efetivos, além de seus respectivos suplentes, com mandato de 02 (dois) anos, admitida a recondução, sendo o Secretário Municipal de Agricultura e Meio Ambiente membro nato, e os demais, nomeados por decreto do Prefeito, da seguinte forma:\n{ #art-38-b }'),
        ('1.  Os membros devem exercer seus mandatos de forma gratuita, vedada a percepção de qualquer vantagem de natureza pecuniária.', '§ 1º Os membros devem exercer seus mandatos de forma gratuita, vedada a percepção de qualquer vantagem de natureza pecuniária.'),
        ('1.  O suporte técnico e administrativo necessário ao funcionamento do Conselho será prestado pela Secretaria Municipal de Meio Ambiente.', '§ 15º O suporte técnico e administrativo necessário ao funcionamento do Conselho será prestado pela Secretaria Municipal de Meio Ambiente.'),
        ('2.  As reuniões do Conselho são públicas, facultado aos munícipes solicitar, por escrito e com justificativa, que se inclua assunto de seu interesse na pauta da primeira reunião subsequente.', '§ 16º As reuniões do Conselho são públicas, facultado aos munícipes solicitar, por escrito e com justificativa, que se inclua assunto de seu interesse na pauta da primeira reunião subsequente.'),
        ('3.  O Conselho será presidido pelo titular da Secretaria Municipal de Meio Ambiente, órgão responsável pela implementação do Plano de Saneamento Básico, a as deliberações deverão ser aprovadas por voto da maioria, cabendo ao presidente o voto de desempate.', '§ 17º O Conselho será presidido pelo titular da Secretaria Municipal de Meio Ambiente, órgão responsável pela implementação do Plano de Saneamento Básico, a as deliberações deverão ser aprovadas por voto da maioria, cabendo ao presidente o voto de desempate.'),
        ('39. São atribuições do Presidente do Conselho:', '**Art. 39.** São atribuições do Presidente do Conselho:\n{ #art-39 }'),
        ('40. A Participação Popular tem por objetivo valorizar e garantir a participação e o envolvimento da comunidade, de forma organizada, na gestão pública e nas atividades políticas administrativas.', '**Art. 40.** A Participação Popular tem por objetivo valorizar e garantir a participação e o envolvimento da comunidade, de forma organizada, na gestão pública e nas atividades políticas administrativas.\n{ #art-40 }'),
        ('41. A garantia da participação dos cidadãos é responsabilidade do governo municipal e tem por objetivos:', '**Art. 41.** A garantia da participação dos cidadãos é responsabilidade do governo municipal e tem por objetivos:\n{ #art-41 }'),
        ('42. Faz parte integrante desta Lei, como anexos, o Volume I do Plano Municipal de Saneamento Básico de Batayporã contendo o Plano de Mobilização Social, Diagnóstico Técnico-participativo, Prospectiva e Planejamento Estratégico, Programas, Projetos e Ações, Plano de Execução e Minuta de Projeto de Lei.', '**Art. 42.** Faz parte integrante desta Lei, como anexos, o Volume I do Plano Municipal de Saneamento Básico de Batayporã contendo o Plano de Mobilização Social, Diagnóstico Técnico-participativo, Prospectiva e Planejamento Estratégico, Programas, Projetos e Ações, Plano de Execução e Minuta de Projeto de Lei.\n{ #art-42 }'),
        ('43. A Prefeitura Municipal e seus órgãos da administração indireta competem promover a capacitação sistemática dos funcionários para garantir a aplicação e a eficácia desta Lei e demais normas pertinentes.', '**Art. 43.** A Prefeitura Municipal e seus órgãos da administração indireta competem promover a capacitação sistemática dos funcionários para garantir a aplicação e a eficácia desta Lei e demais normas pertinentes.\n{ #art-43 }'),
        ('44. Este plano e sua implementação ficam sujeitos a contínuo acompanhamento, revisão e adaptação às circunstâncias emergentes e será revisto em prazo não superior 04 (quatro) anos.', '**Art. 44.** Este plano e sua implementação ficam sujeitos a contínuo acompanhamento, revisão e adaptação às circunstâncias emergentes e será revisto em prazo não superior 04 (quatro) anos.\n{ #art-44 }'),
        ('45. Ao Poder Executivo Municipal compete dar ampla divulgação do PMSB e das demais normas municipais referentes ao saneamento básico.', '**Art. 45.** Ao Poder Executivo Municipal compete dar ampla divulgação do PMSB e das demais normas municipais referentes ao saneamento básico.\n{ #art-45 }'),
        ('46. Fica o Poder Executivo autorizado a firmar Convênio de Cooperação com o Governo do Estado de Mato Grosso do Sul, com vistas à Gestão Associada com a Empresa de Saneamento de Mato Grosso do Sul – SANESUL, para a prestação dos serviços públicos de abastecimento de água e coleta e disposição de esgotos sanitários, em todo o território do Município, através de Contrato de Programa, conforme previsto nas Leis nº. 11.107/05 e 11.445/07, pelo prazo de 30 (trinta) anos.', '**Art. 46.** Fica o Poder Executivo autorizado a firmar Convênio de Cooperação com o Governo do Estado de Mato Grosso do Sul, com vistas à Gestão Associada com a Empresa de Saneamento de Mato Grosso do Sul – SANESUL, para a prestação dos serviços públicos de abastecimento de água e coleta e disposição de esgotos sanitários, em todo o território do Município, através de Contrato de Programa, conforme previsto nas Leis nº. 11.107/05 e 11.445/07, pelo prazo de 30 (trinta) anos.\n{ #art-46 }'),
        ('16. O prazo estabelecido neste artigo poderá ser prorrogado, uma vez, por igual tempo e por novo ajustamento.', 'Parágrafo único. O prazo estabelecido neste artigo poderá ser prorrogado, uma vez, por igual tempo e por novo ajustamento.'),
    ],
    ("2012", "949"): [
        ("> ***“Art 3º-** Fica", "> “Art 3º- Fica"),
        ("da seguinte forma:*\n\nI - O valor", "da seguinte forma:\n>\n> I - O valor"),
        ("dependências hospitalares;*\n\nII - *O valor", "dependências hospitalares;\n>\n> II - O valor"),
        ("quatro) horas;*\n\nIII - *O valor", "quatro) horas;\n>\n> III - O valor"),
        ("e/ou estadual;*\n\nIV - *O valor", "e/ou estadual;\n>\n> IV - O valor"),
        ("São Lucas.*\n\n§ 1º", "São Lucas.\n>\n> § 1º"),
        ("dependências hospitalares.*\n\n§ 2º", "dependências hospitalares.\n>\n> § 2º"),
        ("São Lucas.*\n\n§ 3º", "São Lucas.\n>\n> § 3º"),
        ("São Lucas.*\n\n§ 4º", "São Lucas.\n>\n> § 4º"),
        ("Municipal de Saúde.*", "Municipal de Saúde.”"),
    ],
    ("2012", "950"): [
        ("\n\nI-\n\n", "\n\nI - "),
        ("\n\nII-\n\n", "\n\nII - "),
        ("\n\nIII-\n\n", "\n\nIII - "),
        ("\n\nIV-\n\n", "\n\nIV - "),
        ("\n\nV-\n\n", "\n\nV - "),
        ("\n\nVI-\n\n", "\n\nVI - "),
        ("\n\nVII-\n\n", "\n\nVII - "),
        ("\n\nVIII-\n\n", "\n\nVIII - "),
    ],
    ("2012", "957"): [
        ("unidade operacional da\\\nSecretaria", "unidade operacional da Secretaria"),
    ],
    ("2012", "959"): [
        (
            "**CLASSIFICAÇÃO DE CARGOS DE PROVIMENTO EFETIVO**\n\n**TABELA 1 – PROFISSIONAIS DE SAÚDE**",
            "**CLASSIFICAÇÃO DE CARGOS DE PROVIMENTO EFETIVO**\n{ .centro }\n\n**TABELA 1 – PROFISSIONAIS DE SAÚDE**\n{ .centro }",
        ),
    ],
    ("2012", "961"): [("\n\n**.**\n\n", "\n\n")],
    ("2012", "965"): [
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
    ("2012", "975"): [("II\\. ", "II - ")],
    ("2012", "976"): [("II\\. ", "II - ")],
    ("2012", "978"): [("<u>", ""), ("</u>", "")],
    ("2012", "979"): [("<u>", ""), ("</u>", "")],
    ("2012", "982"): [
        (
            "**Parágrafo único - O projeto será desenvolvido nas Escolas Públicas Municipais, em conjunto com a Secretaria Municipal de Educação e Cultura, Professores, Coordenadores e direção nos períodos de julho a dezembro de cada ano.**\n{ .centro }",
            "Parágrafo único. O projeto será desenvolvido nas Escolas Públicas Municipais, em conjunto com a Secretaria Municipal de Educação e Cultura, Professores, Coordenadores e direção nos períodos de julho a dezembro de cada ano.",
        ),
    ],
    ("2012", "983"): [("<u>", ""), ("</u>", "")],
    ("2012", "984"): [("<u>", ""), ("</u>", "")],
    ("2012", "985"): [("<u>", ""), ("</u>", "")],
    ("2012", "986"): [("<u>", ""), ("</u>", "")],
    ("2012", "987"): [("<u>", ""), ("</u>", "")],
    ("2012", "989"): [("<u>", ""), ("</u>", "")],
    ("2012", "990"): [("<u>", ""), ("</u>", "")],
    ("2012", "993"): [
        (
            "**Art. 2º** O Sistema Municipal de Ensino de Batayporã/MS**",
            "**Art. 2º** O **Sistema Municipal de Ensino de Batayporã/MS**",
        ),
    ],
    ("2012", "995"): [
        ("2.1 - POR FUNÇÕES DE GOVERNO", "**2.1 - POR FUNÇÕES DE GOVERNO**"),
        ("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**"),
    ],
    ("2011", "900"): [("**I. -** ", "I - "), ("**II. -** ", "II - ")],
    ("2011", "905"): [
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
        (
            "***Edson Peres Ibrahim***\n\n***Prefeito Municipal***",
            "**Edson Peres Ibrahim**\n{ .centro }\n\nPrefeito Municipal\n{ .centro }",
        ),
    ],
    ("2011", "913"): [("**Sr. Diego Sanches Marchi***,*", "**Sr. Diego Sanches Marchi**,")],
    ("2011", "914"): [
        (
            "**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO DO ANEXO I DA LEI Nº 729/2007**\n\n**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO**",
            "**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO DO ANEXO I DA LEI Nº 729/2007**\n{ .centro }\n\n**TABELA 4 – CARGOS DE ATIVIDADES PROFISSIONAIS DE APOIO ADMINISTRATIVO**\n{ .centro }",
        ),
    ],
    ("2011", "918"): [
        ("I - multa de 100 a 500 UFERMs** :", "I - **multa de 100 a 500 UFERMs**:"),
        (
            "a) **aos que desobedecerem a quaisquer das exigências sanitárias em relação ao funcionamento do estabelecimento, à higiene do equipamento e dependências, bem como dos trabalhos de manipulação e preparo de matérias-primas e produtos, inclusive aos que fornecerem leite adulterado, fraudado ou falsificado;**",
            "a) aos que desobedecerem a quaisquer das exigências sanitárias em relação ao funcionamento do estabelecimento, à higiene do equipamento e dependências, bem como dos trabalhos de manipulação e preparo de matérias-primas e produtos, inclusive aos que fornecerem leite adulterado, fraudado ou falsificado;",
        ),
        ("II - multas de 501 a 1000 UFERMs:**", "II - **multas de 501 a 1000 UFERMs:**"),
        ("III - multa de 1001 a 1500 UFERMs:**", "III - **multa de 1001 a 1500 UFERMs:**"),
        ("IV - multa de 1501 a 2000 UFERMs:**", "IV - **multa de 1501 a 2000 UFERMs:**"),
    ],
    ("2011", "923"): [
        (
            "**Arrecadação do período de Janeiro a Julho de 2010......................................................R$ 11.895.535,32**\nArrecadação do período de Agosto a Dezembro de 2010............................................. R$ 9.985.022,23\nArrecadação do período de Janeiro a Julho de 2011..................................................... R$ 13.764.274,04\nReceita Total prevista para 2011................................................................................... R$ 19.294.716,11\n{ .centro }",
            "1- Arrecadação do período de Janeiro a Julho de 2010......................................................R$ 11.895.535,32\n\n2- Arrecadação do período de Agosto a Dezembro de 2010............................................. R$ 9.985.022,23\n\n3- Arrecadação do período de Janeiro a Julho de 2011..................................................... R$ 13.764.274,04\n\n4- Receita Total prevista para 2011................................................................................... R$ 19.294.716,11",
        ),
    ],
    ("2011", "924"): [("**I. -** ", "I - "), ("**II. -** ", "II - ")],
    ("2011", "933"): [
        (
            "**Art. 2º** As diárias correspondentes serão baseadas em UFERMS – Unidade Fiscal de Referência do Estado de Mato Grosso do Sul, conforme Tabelas a seguir:*\n{ #art-2 }",
            "> “Art. 2º As diárias correspondentes serão baseadas em UFERMS – Unidade Fiscal de Referência do Estado de Mato Grosso do Sul, conforme Tabelas a seguir:",
        ),
        ("{ #art-2-b }", "{ #art-2 }"),
        (
            "| *DENTRO DO ESTADO* | UFERMS |\n|---|---|\n| *a- Prefeito Municipal* | *40,00* |\n| *b- Vice-Prefeito* | *32,00* |\n| *c- Secretários Municipais* | *20,00* |\n| *d- Assessor Contábil, Assessor Especial I, Assessor Especial II, Assessor Especial III, Diretores de Departamento, Assessor Técnico I, Coordenadores, Diretores de Escola, Bioquímico, Enfermeiro, Farmacêutico, Fisioterapeuta, Fonoaudiólogo, Odontólogo, Psicólogo, Médico Clinico Geral, Educador Social, Médico Veterinário, Psicopedagogo, Advogado, Engenheiro Civil, Assistente Social, Nutricionista, Técnico de Contabilidade* | *15,00* |\n| *e- Assessor Técnico II, Assessor Técnico III, Supervisores, Chefes de Serviços, Chefes de Setores, Professores, Coordenadores Pedagógicos, Assistente de Administração, Agente Fiscal de Obras e Posturas, Fiscal de Tributos, Atendente de Creche, Secretário de Escola, Instrutor de Informática, Técnico de Informática, Coreografo, Instrutor de Banda* | *9,50* |\n| *f- Outros Servidores* | *6,50* |",
            "| DENTRO DO ESTADO | UFERMS |\n|---|---|\n| a- Prefeito Municipal | 40,00 |\n| b- Vice-Prefeito | 32,00 |\n| c- Secretários Municipais | 20,00 |\n| d- Assessor Contábil, Assessor Especial I, Assessor Especial II, Assessor Especial III, Diretores de Departamento, Assessor Técnico I, Coordenadores, Diretores de Escola, Bioquímico, Enfermeiro, Farmacêutico, Fisioterapeuta, Fonoaudiólogo, Odontólogo, Psicólogo, Médico Clinico Geral, Educador Social, Médico Veterinário, Psicopedagogo, Advogado, Engenheiro Civil, Assistente Social, Nutricionista, Técnico de Contabilidade | 15,00 |\n| e- Assessor Técnico II, Assessor Técnico III, Supervisores, Chefes de Serviços, Chefes de Setores, Professores, Coordenadores Pedagógicos, Assistente de Administração, Agente Fiscal de Obras e Posturas, Fiscal de Tributos, Atendente de Creche, Secretário de Escola, Instrutor de Informática, Técnico de Informática, Coreografo, Instrutor de Banda | 9,50 |\n| f- Outros Servidores | 6,50 |",
        ),
        (
            "| ***PARA OUTROS ESTADOS*** | UFERMS |\n|---|---|\n| *a- Prefeito Municipal* | *70,00* |\n| *b- Vice Prefeito* | *56,00* |\n| *c- Secretários Municipais* | *35,00* |\n| *d- Assessor Contábil, Assessor Especial I, Assessor Especial II, Assessor Especial III, Diretores de Departamento, Assessor Técnico I, Coordenadores, Diretores de Escola, Bioquímico, Enfermeiro, Farmacêutico, Fisioterapeuta, Fonoaudiólogo, Odontólogo, Psicólogo, Médico Clinico Geral, Educador Social, Médico Veterinário, Psicopedagogo, Advogado, Engenheiro Civil, Assistente Social, Nutricionista, Técnico de Contabilidade* | *26,25* |\n| *e- Assessor Técnico II, Assessor Técnico III, Supervisores, Chefes de Serviços, Chefes de Setores, Professores, Coordenadores Pedagógicos, Assistente de Administração, Agente Fiscal de Obras e Posturas, Fiscal de Tributos, Atendente de Creche, Secretário de Escola, Instrutor de Informática, Técnico de Informática, Coreografo, Instrutor de Banda* | *14,00* |\n| *f- Outros Servidores* | *8,75* |",
            "| **PARA OUTROS ESTADOS** | UFERMS |\n|---|---|\n| a- Prefeito Municipal | 70,00 |\n| b- Vice Prefeito | 56,00 |\n| c- Secretários Municipais | 35,00 |\n| d- Assessor Contábil, Assessor Especial I, Assessor Especial II, Assessor Especial III, Diretores de Departamento, Assessor Técnico I, Coordenadores, Diretores de Escola, Bioquímico, Enfermeiro, Farmacêutico, Fisioterapeuta, Fonoaudiólogo, Odontólogo, Psicólogo, Médico Clinico Geral, Educador Social, Médico Veterinário, Psicopedagogo, Advogado, Engenheiro Civil, Assistente Social, Nutricionista, Técnico de Contabilidade | 26,25 |\n| e- Assessor Técnico II, Assessor Técnico III, Supervisores, Chefes de Serviços, Chefes de Setores, Professores, Coordenadores Pedagógicos, Assistente de Administração, Agente Fiscal de Obras e Posturas, Fiscal de Tributos, Atendente de Creche, Secretário de Escola, Instrutor de Informática, Técnico de Informática, Coreografo, Instrutor de Banda | 14,00 |\n| f- Outros Servidores | 8,75 |",
        ),
    ],
    ("2011", "936"): [
        (
            "> ***“Art. 4º.** A remuneração será feita diretamente ao profissional, pessoa física e ou pessoa jurídica, no mês seguinte ao da prestação de serviços, constante do artigo primeiro, mediante Certidão Mensal fornecida pela Sociedade Hospitalar São Lucas de Batayporã, CNPJ 03.211.935/0001-05.*",
            "> “Art. 4º. A remuneração será feita diretamente ao profissional, pessoa física e ou pessoa jurídica, no mês seguinte ao da prestação de serviços, constante do artigo primeiro, mediante Certidão Mensal fornecida pela Sociedade Hospitalar São Lucas de Batayporã, CNPJ 03.211.935/0001-05.",
        ),
    ],
    ("2011", "937"): [
        (
            "**TABELA 3– CARGOS DE ATIVIDADES PROFISSIONAIS DE FISCALIZAÇÃO DO ANEXO I DA LEI Nº 729/2007**",
            "**TABELA 3– CARGOS DE ATIVIDADES PROFISSIONAIS DE FISCALIZAÇÃO DO ANEXO I DA LEI Nº 729/2007**\n{ .centro }",
        ),
    ],
    ("2011", "940"): [
        ("2.1 - POR FUNÇÕES DE GOVERNO", "**2.1 - POR FUNÇÕES DE GOVERNO**"),
        ("1.  **- POR ÓRGÃOS DA ADMINISTRAÇÃO**", "**3.1 - POR ÓRGÃOS DA ADMINISTRAÇÃO**"),
    ],
    ("2011", "944"): [("**TH TERRAPLANAGEM LTDA-ME*,***", "**TH TERRAPLANAGEM LTDA-ME**,")],
    ("2011", "945"): [("**JOAQUIM LORONHA PEREIRA-ME*,***", "**JOAQUIM LORONHA PEREIRA-ME**,")],
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
    s = re.sub(r"<img[^>]*>", "", s)
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
    md = md.replace('<span class="mark"></span>', "")  # marca-texto vazio do Word
    md = re.sub(r'\*\*([“”"])\*\*', r"\1", md)  # aspa sozinha em negrito
    # sobrescritos do Word (1^o^, 3^a^) viram os ordinais
    md = re.sub(r"\^(?:o|º)\.?\\?\s*\^", "º", md)
    md = re.sub(r"\^a\^", "ª", md)
    md = re.sub(r"\^([^\^\s]+)\^", r"\1", md)
    saida = []
    for b in re.split(r"\n\s*\n", md):
        # artigo ou parágrafo inteiro sublinhado (texto acrescido depois, marcado pela prefeitura): sem o sublinhado,
        # o artigo é reconhecido e ganha âncora
        if re.match(r"^<u>(\*\*)?(Art|Par[áa]grafo|§)", b) and b.rstrip().endswith("</u>"):
            b = b[3:].rstrip()[:-4]
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
    # descarta parágrafos vazios, mas não os que só têm imagem (plano() tira as <img>)
    return [b.strip("\n") for b in saida if b.strip() and (plano(b) or "<img" in b or "![" in b)]


def maiusculo(s):
    letras = [c for c in s if c.isalpha()]
    return len(letras) > 2 and all(c.isupper() for c in letras)


def data_lei(t):
    m = re.search(r"(\d{1,2})[º°]?(?:\s*de\s+|\s+)(" + "|".join(MESES) + r")(?:\s*de\s+|\s+)(\d{4})", t, re.I)
    return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def tabela_de_colunas(html):
    """Tabelas do orçamento em que o Word pôs cada coluna numa célula só (itens com pontilhado | R$ | valores):
    vira uma tabela com uma linha por item. Itens sem pontilhado e sem valor (ex.: Poder Executivo) viram subtítulos."""
    col0, col_last = [], []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cel = [[s for p in re.findall(r"<(?:p|h\d)[^>]*>(.*?)</(?:p|h\d)>", c, re.S) if (s := re.sub(r"<[^>]+>", "", p).strip())]
               for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        cel = [c for c in cel if c]
        if cel:
            col0.extend(cel[0])
            col_last.extend(cel[-1])
    rotulos, valores = col0, col_last
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
        if not any(re.sub(r"<[^>]+>|&nbsp;|\s", "", c) for c in cels):
            return ""  # caixa vazia (só o desenho do Word)
        return "<table>\n<tbody>\n<tr>\n" + "\n".join(tds) + "\n</tr>\n</tbody>\n</table>"

    texto = re.sub(r"(?:\A|(?<=\n\n))(\|[^\n]*\|)\n(\|(?:\s*:?-+:?\s*\|)+)(?=\n\n|\n?\Z)", caixa, texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip("\n")


def citacoes(texto):
    """Nova redação citada (“Art ...”): o pandoc só põe o primeiro parágrafo na citação e deixa o itálico
    do Word solto; junta os parágrafos até o fecha-aspas numa citação só, sem o itálico."""
    bs, out, k = texto.split("\n\n"), [], 0
    limpa = lambda b: re.sub(r"^(>\s*)+", "", b).replace("*", "").strip()
    fecha = lambda b: re.search(r"”\.?$", limpa(b))
    while k < len(bs):
        b = bs[k]
        if b.startswith("> ") and "\n>" not in b and re.match(r"^[“\"](?:Art|§|Par[áa]grafo|[IVXL]+\s*[-–])", limpa(b)):
            fim = next((j for j in range(k, min(k + 40, len(bs))) if fecha(bs[j])), None)
            if fim is not None:
                # tabela no meio da citação fica fora do ">" (dentro dela o HTML da tabela quebra)
                grupo = []
                for x in bs[k:fim + 1] + [None]:
                    if x is None or limpa(x).startswith(("<table", "|")):
                        if grupo:
                            out.append("\n>\n".join("> " + limpa(y) for y in grupo))
                            grupo = []
                        if x is not None:
                            out.append(re.sub(r"^(>\s*)+", "", x))
                    else:
                        grupo.append(x)
                k = fim + 1
                continue
        out.append(b)
        k += 1
    return "\n\n".join(out)


# títulos de capítulo das Leis de Diretrizes Orçamentárias que no Word ocupam duas linhas: o pandoc faz da primeira o
# título e deixa a segunda como parágrafo em negrito embaixo dele
TITULOS_LDO = [
    ("DAS PRIORIDADES E METAS DA", "ADMINISTRAÇÃO PÚBLICA MUNICIPAL"),
    ("DA ESTRUTURA E ORGANIZAÇÃO", "DOS ORÇAMENTOS"),
    ("DAS DIRETRIZES ESPECÍFICAS", "PARA O PODER LEGISLATIVO"),
    ("DAS DIRETRIZES GERAIS PARA A ELABORAÇÃO E EXECUÇÃO", "DOS ORÇAMENTOS DO MUNICÍPIO E SUAS ALTERAÇÕES"),
    ("DAS DIRETRIZES DOS ORÇAMENTOS", "FISCAL E DA SEGURIDADE SOCIAL"),
    ("LIMITES E CONDIÇÕES PARA EXPANSÃO DAS", "DESPESAS OBRIGATÓRIAS DE CARÁTER CONTINUADO"),
    ("DAS DISPOSIÇÕES RELATIVAS ÀS DESPESAS", "COM PESSOAL E ENCARGOS SOCIAIS"),
    ("DAS NORMAS DE CONTROLE DE CUSTOS", "E AVALIAÇÃO DOS RESULTADOS DOS PROGRAMAS"),
]


def juntar_titulos_ldo(texto):
    """Junta as duas linhas desses títulos (pode rodar de novo sobre uma página pronta sem mudar nada)."""
    for a, b in TITULOS_LDO:
        texto = re.sub(rf"^(### CAPÍTULO [IVXL]+ — {re.escape(a)}) \{{ \.centro \}}\n\n\*\*{re.escape(b)}\*\*$",
                       lambda m: f"{m.group(1)} {b} {{ .centro }}", texto, flags=re.M)
    return texto.replace("CARÁTER SUPLETIVOSOBRE", "CARÁTER SUPLETIVO SOBRE")


def citacao_em_italico(bs):
    """Leis complementares: o texto novo de uma lei alterada vem em itálico e/ou entre aspas depois de "passa a vigorar
    com a seguinte redação", às vezes com capítulos e artigos inteiros. Sem tratamento, esses artigos seriam lidos
    como artigos da própria lei (com âncora e no índice). O trecho até o fecha-aspas (ou o "(NR)") vira um bloco de
    citação pronto, marcado com CITACAO para o conversor deixar como está."""
    out, k = [], 0
    anuncia = re.compile(r"(?i)seguinte reda[çc][ãa]o|passa(?:ndo|m)? a vigorar|acrescid[oa]s?|nova reda[çc][ãa]o")
    sem_q = lambda b: re.sub(r"^(>\s*)+", "", b.strip())
    italico = lambda b: re.match(r"^\*(?!\*[^*])", sem_q(b))
    abre = lambda b: re.match(r"^\**[“\"]", sem_q(b))
    limpa = lambda b: sem_q(b).replace("*", "").strip()
    fecha = lambda b: re.search(r"(?:[”\"]\.?|\(NR\))\s*$", limpa(b))
    k = -1  # k: último parágrafo já copiado; a citação começa no seguinte
    apos_citacao = False
    while k + 1 < len(bs):
        lead = k >= 0 and (anuncia.search(plano(bs[k])) or apos_citacao)
        if lead and (italico(bs[k + 1]) or abre(bs[k + 1])):
            j = k + 1
            # artigo da própria lei (sem itálico e sem aspas) encerra a citação mesmo sem fecha-aspas
            proprio = lambda b: re.match(r"^\**Art\.?\s*\d", sem_q(b)) and not italico(b) and not abre(b)
            limite = next((x for x in range(j + 1, min(j + 80, len(bs))) if proprio(bs[x])), min(j + 80, len(bs)))
            fim = next((x for x in range(j, limite) if fecha(bs[x])), None)
            if fim is None:  # sem fecha-aspas: os parágrafos em itálico, ou até o próximo artigo da lei
                fim = j
                comecou_com_aspas = bool(abre(bs[j]))
                while fim + 1 < limite and (comecou_com_aspas or italico(bs[fim + 1])):
                    fim += 1
            tabela = lambda x: limpa(x).startswith(("<table", "|"))
            run = [x if tabela(x) else limpa(x) for x in bs[j:fim + 1]]
            if not run[0].startswith(("“", '"')) and not tabela(run[0]):
                run[0] = "“" + run[0]
            if not tabela(run[-1]) and not fecha(run[-1]):
                run[-1] += "”"
            # tabelas ficam fora do ">" (dentro da citação o HTML da tabela quebra)
            grupo = []
            for x in run + [None]:
                if x is None or tabela(x):
                    if grupo:
                        out.append(CITACAO + "\n>\n".join("> " + y for y in grupo))
                        grupo = []
                    if x is not None:
                        out.append(CITACAO + re.sub(r"^\*+(?=<table|\|)", "", sem_q(x)))
                else:
                    grupo.append(x)
            k = fim
            apos_citacao = True  # outra citação logo depois (vários artigos alterados em seguida) continua
            continue
        apos_citacao = False
        k += 1
        out.append(bs[k])
    return out


CITACAO = "\x00CIT"


def sumario_do_word(texto):
    """Sumário gerado pelo Word ("[Gari 6](#gari)", com o número da página impressa): os destinos não existem na
    página. O parágrafo em negrito com o mesmo nome ganha a âncora e o link aponta para ela, sem o número da página;
    sem destino, fica só o nome."""
    def troca(m):
        rotulo = m.group(1).strip()
        alvo = para_ancora(rotulo)
        if f"{{ #{alvo} }}" in texto or re.search(rf"^\*\*{re.escape(rotulo)}\*\*$", texto, re.M | re.I):
            alvos.append((rotulo, alvo))
            return f"[{rotulo}](#{alvo})"
        return rotulo
    alvos = []
    texto = re.sub(r"\[([^\]]+?)\s+\d+\]\(#[^)]*[^\x00-\x7f][^)]*\)|\[([^\]]+?)\s+\d+\]\(#[a-z0-9-]+\)",
                   lambda m: troca(type("M", (), {"group": lambda s, i: m.group(1) or m.group(2)})()), texto)
    for rotulo, alvo in alvos:
        if f"{{ #{alvo} " in texto:
            continue
        rot = rf"^(\*\*{re.escape(rotulo)}\*\*)$"
        if re.search(rot + r"\n\{ \.", texto, re.M | re.I):  # já tem atributo ({ .centro }): a âncora entra nele
            texto = re.sub(rot + r"\n\{ \.", rf"\1\n{{ #{alvo} .", texto, count=1, flags=re.M | re.I)
        else:
            texto = re.sub(rot, rf"\1\n{{ #{alvo} }}", texto, count=1, flags=re.M | re.I)
    return texto


def para_ancora(texto):
    s = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def secoes_pme(texto):
    """Lei 1100/2015 (Plano Municipal de Educação, ~3.500 linhas): as seções do Anexo I, que no Word são só parágrafos
    em negrito, viram títulos com âncora, e o sumário (com as páginas do documento impresso) vira uma lista de links."""
    lei, anexo = texto.split("\n## ANEXO I ", 1)
    atual = ""

    def titulo(m):
        nonlocal atual
        t = m.group(1).strip()
        if re.fullmatch(r"PALAVRAS DO PREFEITO|CONSIDERAÇÕES INICIAIS|SUMÁRIO|INTRODUÇÃO|REFERÊNCIAS|COLABORADORES", t):
            return f"### {t} {{ #{para_ancora(t)} }}"
        if mm := re.fullmatch(r"(METAS?) (\d+(?:(?:, | e )\d+)*)\s*[–-]?\s*(.+)", t):
            nums = [str(int(n)) for n in re.findall(r"\d+", mm.group(2))]
            atual = ("meta-" if len(nums) == 1 else "metas-") + "-".join(nums)
            return f"### {t} {{ #{atual} }}"
        if t == "ANÁLISE SITUACIONAL":
            return f"#### {t} {{ #{atual}-analise }}"
        if mm := re.fullmatch(r"ESTRATÉGIAS (?:DA )?META (\d+)", t):
            return f"#### {t} {{ #estrategias-meta-{mm.group(1)} }}"
        return m.group(0)

    anexo = re.sub(r"^\*\*([^*\n]+)\*\*$", titulo, anexo, flags=re.M)

    def item(linha):
        rotulo = re.sub(r"\s+\d+$", "", linha.strip())
        if m := re.fullmatch(r"(METAS? [\d, e]+?) Análise Situacional", rotulo):
            nums = re.findall(r"\d+", m.group(1))
            alvo = ("meta-" if len(nums) == 1 else "metas-") + "-".join(nums) + "-analise"
            rotulo = f"{m.group(1).capitalize()} — Análise Situacional"
        elif m := re.fullmatch(r"Estratégias da Meta (\d+).*", rotulo):
            alvo = f"estrategias-meta-{m.group(1)}"
        else:
            alvo = para_ancora(rotulo)
            rotulo = rotulo.capitalize() if rotulo.isupper() else rotulo
        assert f"{{ #{alvo} }}" in anexo, (linha, alvo)
        return f"- [{rotulo}](#{alvo})"

    ini = anexo.index("### SUMÁRIO { #sumario }\n\n") + len("### SUMÁRIO { #sumario }\n\n")
    fim = anexo.index("\n\n### INTRODUÇÃO")
    anexo = anexo[:ini] + "\n".join(item(l) for l in anexo[ini:fim].split("\n\n")) + anexo[fim:]
    return lei + "\n## ANEXO I " + anexo


SECOES = {("2015", "1100"): secoes_pme}


def ler_md2(nome):
    return next(f for f in (SCR / "md2").iterdir() if nfc(f.name) == nome).read_text()


def converter(num, extras=None, complementar=False):
    """Lei ordinária (md2/LEI Nº num.ANO.md) ou, com complementar=True, lei complementar (md2/LEI COMP 0num.ANO.md,
    título "Lei Complementar nº ..."; nas tabelas de acertos a chave é "LC" + número, ex.: ("2023", "LC61"))."""
    chave = f"LC{int(num)}" if complementar else num
    extras = EXTRAS.get((ANO, chave), []) if extras is None else extras
    bs = blocos(ler_md2(f"LEI COMP {int(num):03d}.{ANO}.md" if complementar else f"LEI Nº {num}.{ANO}.md"))
    for e in extras:
        bs += blocos(e[3:] if e.startswith("md:") else ler_md2(e))
    # cabeçalho: título e ementa
    if complementar:
        titulo_re = rf"(?i)^lei\s+complementar\s+(?:municipal\s+)?(?:n[º°o]?\s*\.?\s*)?0*{int(num)}\b"
    else:
        num_pat = f"{num[0]}\\.?{num[1:]}" if len(num) == 4 else num
        titulo_re = rf"(?i)^lei\s+(?:n[º°o]?\s*\.?\s*)?{num_pat}"
    if complementar:
        bs = citacao_em_italico(bs)
    i = next(k for k, b in enumerate(bs) if re.match(titulo_re, plano(b)))
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
        if b.startswith(CITACAO):  # citação já pronta (citacao_em_italico)
            fecha_assinatura()
            out.append(b[len(CITACAO):])
            k += 1
            continue
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
        elif re.match(r"^[“\"](?:Art|§|Par[áa]grafo|[IVXL]+\s*[-–])", p):
            out.append("> " + re.sub(r"^(>\s*)+", "", b))
        else:
            out.append(re.sub(r"^(>\s*)+", "", b))
        k += 1
    fecha_assinatura()
    texto = "\n\n".join(out)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = tabelar_cargos(texto)
    if (chave, ANO) in ORCAMENTOS:
        texto = re.sub(r"<table.*?</table>", lambda m: tabela_de_colunas(m.group(0)), texto, flags=re.S)
    else:
        texto = re.sub(r"<table.*?</table>", lambda m: html_simples(m.group(0)), texto, flags=re.S)
    texto = acertar_tabelas(texto)
    texto = limpar_tabelas(texto)
    texto = re.sub(r"(\{ \.centro \}\n)+", "{ .centro }\n", texto)
    if ANO >= "2006" or complementar:
        texto = citacoes(texto)
    for a, b in CORRECOES.get((ANO, chave), []):
        assert a in texto, (num, a)
        texto = texto.replace(a, b)
    texto = juntar_titulos_ldo(texto)
    if (ANO, chave) in SECOES:
        texto = SECOES[(ANO, chave)](texto)
    if re.search(r"\]\(#[^)]*[^\x00-\x7f]", texto):  # links para âncoras com acento: sumário do Word
        texto = sumario_do_word(texto)
    # imagens que o pandoc deixa como <img> (com largura em polegadas) viram imagem Markdown: o tamanho fica por conta
    # do site, e o exportar.py leva as imagens em Markdown para o PDF e o Word (as <img> ficavam de fora)
    texto = re.sub(r'<img src="(media/[^"]+)"[^>]*?/?>', r"![](\1)", texto)
    texto = texto.replace("\\$", "$")  # o pandoc escapa o cifrão, mas o Markdown do site mostraria a barra
    # CPF e RG de pessoas citadas nas leis (doações, cessões) não vão para o site
    texto = re.sub(r"\b\d{3}\s?\.\s?\d{3}\s?\.\s?\d{3}\s?[-–]\s?\d{2}\b", "[omitido]", texto)
    texto = re.sub(r"\b[\dX.\-]*\d[\dX.\-]*\s?(?:/\s?)?(?:SSP|SEJUSP|SESP)\s?[/-]?\s?[A-Z]{2}\b", "[omitido]", texto)  # RG: número/órgão/UF
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
    if (ANO, chave) in MAPAS:
        corte, novo = MAPAS[(ANO, chave)]
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
