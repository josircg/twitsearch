from fabric import task, Connection


def deploy(connection):
    with connection.cd('/var/webapp/twitsearch/twitsearch/'):
        connection.run('git pull')
        print('Iniciando a migração')
        connection.run('../bin/python manage.py migrate')
        connection.run('../bin/python manage.py collectstatic --noinput')
        connection.run('supervisorctl restart tm')
        print('Atualização efetuada')


@task
def deploy_producao(context):
    deploy(Connection('webapp@172.16.16.98', port=25000))
