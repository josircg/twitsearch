1) Como administrador da máquina (com poderes de sudo):

```
sudo apt-get update
sudo apt-get upgrade -y
sudo apt install mysql-server
sudo mysql_secure_installation
```

2) No console do Mysql:

```
sudo mysql -u root
CREATE DATABASE twitsearch DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
create user twitsearch identified by 'xxxx';
grant all privileges on twitsearch.* to 'twitsearch'@'%';
```

3) Instalação do NGINX e Supervisor

```
sudo apt install build-essential libssl-dev python3-dev python3-setuptools libmysqlclient-dev
sudo apt-get install -y nginx python-dev python-setuptools libxml2-dev supervisor git libfreetype6 libfreetype6-dev zlib1g-dev virtualenv
sudo apt-get install mysql-client libsqlclient-dev 
```

4) Criar o usuário webapp e continuar a instalação a partir dele:

```
cd var
mkdir webapp
cd /var/webapp
virtualenv -p python3 twitsearch
cd twitsearch
source ./bin/twitsearch
git clone git@bitbucket.org:josir/twitsearch.git
cd twitsearch
git checkout dev
pip install -r requirements.txt
cp configs/local.py twitsearch/
cp configs/supervisor.conf /etc/supervisor/conf.d/twitsearch.conf
cp configs/defaults/nginx.conf /etc/nginx/sites-available/twitsearch.conf
cd /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/twitsearch.conf
```

5) Altere em seguida, as configurações do twitsearch.conf do nginx e do supervisor para o domínio e a senha criada no mysql

6) Teste se a configuração do django está ok:

```
cd /var/webapp/twitsearch/twitsearch/
python manage.py check
```
7) Crie a base de dados:

```
python manage.py migrate
python manage.py createsuperuser
```

8) Configurar o crontab

15 * * * * /var/webapp/twitsearch/twitsearch/crawler.sh >> /var/webapp/twitsearch/logs/crawler.log
20 * * * * /var/webapp/twitsearch/twitsearch/import.sh >> /var/webapp/twitsearch/logs/import.log
