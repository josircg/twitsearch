# Generated by Django 2.1.7 on 2019-04-05 11:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_auto_20190403_2043'),
    ]

    operations = [
        migrations.AddField(
            model_name='tweet',
            name='retwit_id',
            field=models.CharField(max_length=21, null=True),
        ),
        migrations.AddField(
            model_name='tweetuser',
            name='name',
            field=models.CharField(default='Teste', max_length=200),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='tweetuser',
            name='username',
            field=models.CharField(max_length=100),
        ),
    ]
