# Generated by Django 2.2.28 on 2022-09-17 22:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_auto_20220313_1928'),
    ]

    operations = [
        migrations.AlterField(
            model_name='processamento',
            name='tipo',
            field=models.CharField(choices=[('I', 'Importação'), ('A', 'Importação Premium'), ('U', 'Importação User'), ('G', 'Busca Global'), ('H', 'Busca Histórica'), ('P', 'Busca no Projeto'), ('M', 'Match de Tweets orfãos'), ('T', 'Exportação Tags'), ('N', 'Montagem Rede')], default='I', max_length=1),
        ),
        migrations.AlterField(
            model_name='retweet',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.TweetUser'),
        ),
        migrations.AlterField(
            model_name='termo',
            name='tipo_busca',
            field=models.CharField(choices=[('I', 'Importação Regular'), ('A', 'Importação Premium'), ('U', 'Importação Usuário'), ('G', 'Busca Global'), ('P', 'Busca no Projeto')], default='I', max_length=1, verbose_name='Tipo da Busca'),
        ),
        migrations.AlterField(
            model_name='tweetuser',
            name='created_at',
            field=models.DateField(blank=True, null=True),
        ),
    ]