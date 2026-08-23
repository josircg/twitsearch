import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings

from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.tl.functions.channels import GetFullChannelRequest

from telethon.errors import FloodWaitError, RPCError

from core.apps import alog_message
from telegram.models import Canal


async def sync_channels(client: TelegramClient):
    """
    Obtem todos os canais ainda não verificados e busca seus atributos no Telegram
    """
    tot_atualizados = 0
    tot_desabilitados = 0
    tot_erros = 0
    async for canal in Canal.objects.filter(id_numerico__isnull=True, status=Canal.Status.ATIVO):
        try:
            # Esta chamada faz a requisição de rede e preenche o cache do Telethon
            entity = await client.get_entity(canal.username)

            if isinstance(entity, Channel):
                canal.id_numerico = entity.id
                canal.titulo = entity.title
                canal.access_hash = entity.access_hash
                canal.num_participantes = getattr(entity, 'participants_count') or 0
                canal.megagroup = getattr(entity, 'megagroup', False)
                canal.dtcriacao = getattr(entity, 'date', None)
                full_info = await client(GetFullChannelRequest(channel=entity))
                if full_info and full_info.full_chat:
                    canal.sobre = full_info.full_chat.about
                await canal.asave()
                await alog_message(canal, "Canal sincronizado com sucesso")
                tot_atualizados += 1
            else:
                canal.status = Canal.Status.DESATIVADO
                await canal.asave(update_fields=['status'])
                await alog_message(canal, "Canal não encontrado")
                tot_desabilitados += 1

        except FloodWaitError as e:
            # Tratamento específico para o Rate Limit do Telegram
            await asyncio.sleep(e.seconds)

        except RPCError as e:
            # Trata erros específicos da API do Telegram (ex: UsernameInvalidError, ChannelPrivateError)
            canal.status = Canal.Status.DESATIVADO
            await canal.asave(update_fields=["status"])
            await alog_message(canal, f"Erro RPC do Telegram ao obter dados: {e}")
            tot_erros += 1

        except Exception as e:
            # Captura erros genéricos e formata a f-string corretamente
            await alog_message(canal, f"Erro inesperado ao obter dados do canal: {e}")
            tot_erros += 1

    print(f'Total de Canais atualizados:{tot_atualizados}')
    print(f'Total de Canais desabilitados:{tot_desabilitados}')
    print(f'Total de Erros:{tot_erros}')


class Command(BaseCommand):
    label = 'Captura dados dos canais'

    def handle(self, *args, **options):
        # Garante que o loop asyncio rode de forma limpa no processo principal
        api_id = settings.AUTH_KEYS.get('TELEGRAM_ID')
        api_hash = settings.AUTH_KEYS.get('TELEGRAM_HASH')
        if not api_id or not api_hash:
            print('Chaves de API do Telegram não definidas')
        else:
            # asyncio.run(test_log())
            asyncio.run(self.main(api_id, api_hash))

    async def main(self, api_id, api_hash):
        async with TelegramClient('sync_channels', api_id, api_hash) as client:
            if await client.is_user_authorized():
                await sync_channels(client)
            else:
                print("Usuário não autorizado. Faça o login primeiro.")

