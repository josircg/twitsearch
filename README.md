# Capitu - versão 1.1

Captura de Dados de Redes sociais a partir da API do Twitter e do Telegram 

O software permite que usuários finais (que não tem expertise de programação de computadores) possam coletar dados e armazenar do Twitter a partir de critérios de busca por eles definidos. A partir dos dados coletados, o usuário pode exportá-los em formato CSV para que possam ser utilizados em planilhas eletrônicas ou em outros softwares de análise de rede social.

Uma vez que o projeto é definido, o programa inicia a busca e registro dos tweets e permite que o usuário possa ver o resultado em tempo real. Ao final gerar arquivos CSV com os tweets de cada projeto.

![Python version](https://img.shields.io/badge/python-3.12-blue)
![Django version](https://img.shields.io/badge/django-4.2-blue)

# Histórico

Versão 0.2: busca pelos retweets (Ok)

Versão 0.3: Geração de Totalizações e Nuvem de Palavras (Ok)

Versão 0.4: Exportação GEPHI (via Formato Tags) (Ok)

Versão 0.5: Busca Local. Permite buscar tweets na base local de tweets já coletados (Ok)

Versão 0.6: Implementação da API v2 (Ok)

Versão 0.7: Utilização de várias credenciais para maximizar a coleta

Versão 0.8: Integração com o Visão (visao.ibict.br)

Versão 0.9: Backup S3 (Ok)

Versão 0.9: Desidratar bases de tweets (Importação Tweet ID) (Ok) 

Versão 1.0: Integração com o Opensearch (Ok)

Versão 1.1: Registro de Canais 

# Tarefas a realizar

* Importar retweets após a Importação de Tweets
* Integração com canais do Telegram / Youtube

# Planejamento de como realizar o restore de uma base

* Backup da base no S3
* Em outra instalação, baixar o backup na pasta "restore"
* Executar: python manage.py importjson --restore
 

