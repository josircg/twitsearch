O Monitor Twitter funciona com Python 3.6, Django 1.2 e banco MySQL/MariaDb 
Sob Debian 9 ou Ubuntu 18.04 ou superior

1) Preparação do servidor

> sudo apt install pkg-config

2) Preparação do Virtualenv

3) Criar virtualenv
> virtualenv twitsearch

Outra opção é utilizar: mkvirtualenv odorico -p python3

4) Ativar virtualenv
```
cd twitsearch
source bin/activate
mkdir logs
```
5) Clonar o repositório
> git clone git@github.com:larhud/twitsearch.git

6. Entrar na pasta e instalar as libs
> cd twitsearch
> pip install -r requirements.txt

7. Preparar o Banco de Dados. A criação do banco MySQL deve utilizar o collate mais geral para aceitar emojis: 

> CREATE DATABASE twitsearch DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;'''

7. Copie o local.py de configs/local.py para a pasta onde se encontra o settings.py e altere
os parâmetros necessários, como nome do site, domínio, secret_key, senha do banco de dados

Para criar o secret key da sua instalação, use:

>>> from django.core.management.utils import get_random_secret_key
>>> print(get_random_secret_key())
   
8. Teste se a configuração do local.py está ok:
> python manage.py check
> python manage.py migrate
> python manage.py collectstatic

9. Caso queira instalar o twitsearch em servidor externo, recomendamos que utilize o servidor NGINX e o supervisord
* Copie o arquivo /configs/nginx.conf para /etc/nginx/sites-available
* Copie supervisor.conf para a pasta /etc/supervisor/conf.d/
* Nos 2 arquivos, altere os parâmetros necessários para configurar o seu servidor.
* Instale também os pacotes específicos para produção: pip install -r req-prod.txt 

10. Cria o superuser
> python manage.py createsuperuser

11. Rode a aplicação
> python manage.py runserver


