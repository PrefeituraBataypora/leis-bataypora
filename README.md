# Legislação Municipal de Batayporã

Legislação municipal de Batayporã (MS) convertida de PDF para Markdown, para que as leis
possam ser lidas, pesquisadas e versionadas no Git. O site é gerado com
[Zensical](https://zensical.org/) (sucessor do MkDocs Material) e publicado no GitHub Pages.

> **Textos em revisão.** Os PDFs de origem estão em
> <https://bataypora.ms.gov.br/cidadao/legislacao-municipal>. Toda lei aqui tem o link e o
> hash SHA-256 do PDF de origem.

## Estrutura

```
docs/                 Markdown das leis (uma pasta por categoria) — é isto que vira o site
data/fontes.json      Origem de cada lei: link do PDF, página do site, sha256, método de extração
scripts/coletar.py    Lê as páginas de categoria do site e baixa os PDFs para .cache-leis/pdfs/
scripts/converter.py  Extrai o texto (embutido ou por OCR) e gera docs/ e o menu do zensical.toml
scripts/exportar.py   Gera em docs/baixar/ as versões para download: PDF, DOCX, TXT e MD
zensical.toml         Configuração do site
```

Os PDFs não ficam no repositório (alguns têm mais de 30 MB); ficam só em `.cache-leis/`, que
está no `.gitignore`. Não use `.cache/` para isso: é a pasta de cache do Zensical, e
`zensical build --clean` apaga tudo o que estiver lá.

## Rodando localmente

Requer Python 3.12+, `poppler` e `tesseract` com o idioma português
(no macOS: `brew install poppler tesseract tesseract-lang`).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/coletar.py      # baixa os PDFs
.venv/bin/python scripts/converter.py    # gera docs/ (o OCR é lento na 1ª vez; depois usa cache)
.venv/bin/python scripts/exportar.py     # gera os arquivos para download (PDF, DOCX, TXT, MD)
.venv/bin/zensical serve                 # abre o site em http://localhost:8000/leis-bataypora/
```

Para adicionar categorias, inclua o slug da página do site em `CATEGORIAS`, no início de
`scripts/coletar.py`.

Os arquivos de download não vão para o git: o workflow de publicação os gera de novo a cada
push, a partir do texto em `docs/` (incluindo as correções feitas à mão). Se você corrigir uma
lei e quiser ver o download atualizado localmente, rode o `exportar.py` de novo.

## Publicando no GitHub Pages

1. Crie o repositório no GitHub (público) e envie o código.
2. Em **Settings → Pages → Source**, escolha **GitHub Actions**.
3. Endereço publicado: <https://prefeiturabataypora.github.io/leis-bataypora/>.

A cada push na `main`, o workflow `.github/workflows/pages.yml` gera e publica o site.

## Revisão dos textos

Cada lei tem no cabeçalho `revisao: pendente` e `extracao: texto | OCR | misto`. Ao revisar uma
lei comparando com o PDF, corrija o texto e troque para `revisao: revisada`. Leis extraídas por
OCR precisam de mais atenção, principalmente em números de artigos, valores e datas.

Pode editar os arquivos em `docs/` à vontade: o `scripts/converter.py` **não sobrescreve páginas
editadas à mão**. Ele guarda em `data/fontes.json` o hash do texto que gerou e, se o arquivo não
bate mais com ele, mantém o arquivo como está e avisa no final. Para descartar as edições de
todas as leis e gerar tudo de novo a partir dos PDFs, use `python scripts/converter.py --forcar`.

Depois de corrigir uma lei, rode `scripts/exportar.py` para atualizar os downloads.

## Versionamento das alterações

Hoje cada lei (a original e as que a alteram) é um arquivo separado. O passo seguinte é manter
também um **texto compilado** da lei base, em que cada lei alteradora vira um commit com a data
dela. Assim o `git log` e o `git diff` do arquivo mostram a evolução de cada artigo.
