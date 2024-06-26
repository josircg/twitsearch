# Generated by Django 2.2.28 on 2024-05-04 16:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_retweet_related_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='processamento',
            name='tipo',
            field=models.CharField(choices=[('I', 'Importação'), ('A', 'Importação Premium'), ('D', 'Importação Rapid'), ('U', 'Importação User'), ('G', 'Busca Global'), ('P', 'Busca no Projeto'), ('B', 'Backup JSON'), ('E', 'Calcula Estimativa'), ('M', 'Match de Tweets orfãos'), ('T', 'Exportação Tags'), ('J', 'Importação JSON'), ('N', 'Montagem Rede')], default='I', max_length=1),
        ),
        migrations.RunSQL(
            'delete from core_tweetinput where id not in (select triplic.id from '
            ' (select max(duplic.id) as id from core_tweetinput as duplic '
            '   group by duplic.tweet_id, duplic.termo_id) as triplic)'
        ),
        migrations.AlterField(
            model_name='tweetinput',
            name='termo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Termo'),
        ),
        migrations.AlterUniqueTogether(
            name='tweetinput',
            unique_together={('tweet', 'termo')},
        ),
    ]
