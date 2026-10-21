# Contexto do Projeto — Capitu

A Capitu é um sistema de captura de Dados de Redes sociais a partir da API do Twitter, do Telegram e Youtube.

O software permite que usuários finais (que não tem expertise de programação de computadores) possam coletar dados e armazenar do Twitter a partir de critérios de busca por eles definidos. A partir dos dados coletados, o usuário pode exportá-los em formato CSV para que possam ser utilizados em planilhas eletrônicas ou em outros softwares de análise de rede social.

Uma vez que o projeto é definido, o programa inicia a busca e registro dos tweets e permite que o usuário possa ver o resultado em tempo real. Ao final gerar arquivos CSV com os tweets de cada projeto.


## Stack confirmada

- **Python**: 3.12
- **Django**: 4.2.x (`requirements.txt` fixa `Django<5` — NÃO subir para 5.x)
- **Banco**: MySQL (padrão, definido em `twitsearch/local.py` na variável `DATABASES`).
  Algumas rotinas usam PostgreSQL como fonte externa (`connect_postgresql` em
  `core/apps.py`, via `settings.PG_SERVERS`).
- **Settings module**: `twitsearch.settings` (carregado pelo `manage.py`)

## Como rodar comandos

O virtualenv do projeto chama-se `capitu`. Em shell interativo: `workon capitu`.

Em execução não-interativa (agentes/scripts), o `workon` não está disponível
(é função do virtualenvwrapper carregada só em shells interativos). Use o Python
do venv resolvido via `WORKON_HOME` — a variável que o virtualenvwrapper usa para
localizar os venvs. Ela é específica de cada máquina (não versionada), então o
nome do venv (`capitu`) é a única parte fixa aqui:

    "$WORKON_HOME/capitu/bin/python" manage.py check

Se `WORKON_HOME` não estiver definido na máquina, descubra o diretório onde os
venvs ficam (comum: `~/.virtualenvs`; nesta máquina: `/dados/venv`) e use
`<dir>/capitu/bin/python`.

### Comandos de verificação

    "$WORKON_HOME/capitu/bin/python" manage.py check

### Testes

Os testes ficam em `tests/` (nível do projeto). Há um runner que dispensa a
criação do banco em `tests/test_apps.py::NoDbTestRunner`, útil para testes que
não tocam o DB (ex.: `SimpleTestCase` com mocks).

Rodar um módulo de teste específico sem banco:

    "$WORKON_HOME/capitu/bin/python" manage.py test tests.test_deploy --testrunner=tests.test_apps.NoDbTestRunner

## Armadilhas de ambiente

## Configuração de settings

- Base: `capitu/local.py` que não é versionado pois contém os secrets do projeto  

## Arquitetura

Toda a parte administrativa é gerenciada pelo próprio admin do Django. A construção de formulários customizados é feito apenas para os usuários externos.

## Convenções

## Fluxo de trabalho com specs


