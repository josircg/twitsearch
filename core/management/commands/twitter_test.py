import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Recupera um tweet específico pelo ID'

    def add_arguments(self, parser):
        parser.add_argument('twit_id', type=str, help='ID do Tweet')

    def handle(self, *args, **options):
        twit_id = options['twit_id']
        
        url = f"https://api.twitter.com/2/tweets/{twit_id}"

        # Somente campos válidos permitidos
        queryparams = {
            "tweet.fields": "article,attachments,author_id,card_uri,community_id,context_annotations,conversation_id,created_at,display_text_range,entities,geo,id,in_reply_to_user_id,lang,media_metadata,note_tweet,possibly_sensitive,referenced_tweets,reply_settings,scopes,source,text,withheld",
            "media.fields": "alt_text,duration_ms,height,media_key,preview_image_url,promoted_metrics,public_metrics,type,url,variants,width",
            "expansions": "article.cover_media,article.media_entities,attachments.media_keys,attachments.media_source_tweet,author_id,entities.mentions.username,geo.place_id,in_reply_to_user_id,entities.note.mentions.username,referenced_tweets.id,referenced_tweets.id.attachments.media_keys,referenced_tweets.id.author_id",
            "user.fields": "username,name,public_metrics,created_at,location",
            
        }

        headers = {
            "Authorization": f"Bearer {settings.BEARED_TOKEN}"
        }

        response = requests.get(url, headers=headers, params=queryparams)        
        data = response.json()
        if 'errors' in data:
            self.stdout.write(self.style.ERROR(f'Erro: {data}'))
            return
        
        
        # Corrige erro de acesso a 'response.data'
        filename = '%s/data/%s.json' % (settings.BASE_DIR,twit_id)
        with open(filename, 'w') as arquivo:
            json.dump(data, arquivo)        
            

        self.stdout.write(self.style.SUCCESS(
            f'Comando de teste do Twitter executado com sucesso! twit_id: {twit_id}'))
