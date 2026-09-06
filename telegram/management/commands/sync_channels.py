#
# Obtem os metadados dos canais ativos
# Bonfim - 09/2026
#
import asyncio
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.tl.functions.channels import GetFullChannelRequest

from telethon.errors import FloodWaitError, RPCError

from core.apps import alog_message
from telegram.models import Canal

logger = logging.getLogger(__name__)


async def sync_channels(client: TelegramClient):
    """
    Obtem todos os canais ainda não verificados e busca seus atributos no Telegram
    """
    tot_atualizados = 0
    tot_desabilitados = 0
    tot_erros = 0
    tot_processados = 0

    total_canais = await Canal.objects.filter(
        id_numerico__isnull=True, status=Canal.Status.ATIVO
    ).acount()
    logger.info(f"Iniciando sincronização de {total_canais} canal(is) pendente(s)")

    async for canal in Canal.objects.filter(id_numerico__isnull=True, status=Canal.Status.ATIVO)[:5]:
        tot_processados += 1
        logger.info(
            "[%s/%s] Processando canal id=%s titulo=%s",
            tot_processados, total_canais, canal.pk, canal.titulo,
        )
        try:
            # Esta chamada faz a requisição de rede e preenche o cache do Telethon
            # (a busca precisa do username; o título só é preenchido após a sincronização)
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
                    canal.num_participantes = full_info.full_chat.participants_count
                    canal.localizacao = full_info.full_chat.location
                    if canal.localizacao:
                        canal.localizacao = canal.localizacao[:100]
                await canal.asave()
                await alog_message(canal, "Canal sincronizado com sucesso")
                logger.info(
                    "[%s/%s] Canal id=%s titulo=%r sincronizado (id_numerico=%s)",
                    tot_processados, total_canais, canal.pk, canal.titulo,
                    canal.id_numerico,
                )
                tot_atualizados += 1
            else:
                canal.status = Canal.Status.NAO_EXISTE
                await canal.asave(update_fields=['status'])
                await alog_message(canal, "Canal não encontrado")
                logger.warning(
                    "[%s/%s] Canal id=%s titulo=%s não é um Channel (%s) - desativado",
                    tot_processados, total_canais, canal.pk, canal.titulo,
                    type(entity).__name__,
                )
                tot_desabilitados += 1

        except FloodWaitError as e:
            # Tratamento específico para o Rate Limit do Telegram
            logger.warning(
                "[%s/%s] FloodWaitError no canal id=%s titulo=%s - aguardando %ss",
                tot_processados, total_canais, canal.pk, canal.titulo, e.seconds,
            )
            await asyncio.sleep(e.seconds)

        except RPCError as e:
            # Trata erros específicos da API do Telegram (ex: UsernameInvalidError, ChannelPrivateError)
            canal.status = Canal.Status.NAO_EXISTE
            await canal.asave(update_fields=["status"])
            await alog_message(canal, f"Erro RPC do Telegram ao obter dados: {e}")
            logger.error(
                "[%s/%s] RPCError no canal id=%s titulo=%s - desativado: %s",
                tot_processados, total_canais, canal.pk, canal.titulo, e,
            )
            tot_erros += 1

        except ValueError as e:
            # Telethon levanta ValueError ('No user has "x" as username') quando o
            # username não existe/não resolve na API do Telegram
            canal.status = Canal.Status.NAO_EXISTE
            await canal.asave(update_fields=["status"])
            await alog_message(canal, f"Username inexistente no Telegram: {e}")
            logger.warning(
                "[%s/%s] Username inexistente no canal id=%s titulo=%s - desativado: %s",
                tot_processados, total_canais, canal.pk, canal.titulo, e,
            )
            tot_desabilitados += 1

        except Exception as e:
            # Captura erros genéricos e formata a f-string corretamente
            await alog_message(canal, f"Erro inesperado ao obter dados do canal: {e}")
            logger.exception(
                "[%s/%s] Erro inesperado no canal id=%s titulo=%s: %s",
                tot_processados, total_canais, canal.pk, canal.titulo, e,
            )
            tot_erros += 1

    logger.info(
        "Sincronização finalizada: %s processados, %s atualizados, %s desabilitados, %s erros",
        tot_processados, tot_atualizados, tot_desabilitados, tot_erros,
    )
    print(f'Total de Canais atualizados:{tot_atualizados}')
    print(f'Total de Canais desabilitados:{tot_desabilitados}')
    print(f'Total de Erros:{tot_erros}')


class Command(BaseCommand):
    label = 'Captura dados dos canais'

    def handle(self, *args, **options):
        # Garante que o loop asyncio rode de forma limpa no processo principal
        api_id = settings.AUTH_KEYS.get('TELEGRAM_ID')
        api_hash = settings.AUTH_KEYS.get('TELEGRAM_HASH')
        # bot_token = settings.AUTH_KEYS.get('BOT_TOKEN')
        if not api_id or not api_hash:
            print('Chaves de API do Telegram não definidas')
        else:
            # asyncio.run(test_log())
            asyncio.run(self.main(api_id, api_hash))

    async def main(self, api_id, api_hash):
        async with TelegramClient('sync_channels', api_id, api_hash) as client:
            if await client.is_user_authorized():
                try:
                    await sync_channels(client)
                except Exception:
                    # Qualquer falha que "vaze" do loop de sincronização é registrada com stacktrace
                    logger.exception("Falha não tratada em sync_channels - execução interrompida")
                    raise
            else:
                print("Usuário não autorizado. Faça o login primeiro.")

