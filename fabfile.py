from fabric import task, Connection


def deploy(connection):
    with connection.cd('/var/webapp/twitsearch/twitsearch/'):
        connection.run('git pull')
        print('Iniciando a migração')
        connection.run('../bin/python manage.py migrate')
        connection.run('../bin/python manage.py collectstatic --noinput')
        connection.run('supervisorctl restart twitsearch')
        print('Atualização efetuada')


@task
def deploy_producao(context):
    deploy(Connection('webapp@monitor.farmi.pro.br', port=8090))


@task
def deploy_teste(context):
    deploy(Connection('', port=8090))
