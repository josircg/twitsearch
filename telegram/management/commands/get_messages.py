import asyncio
import json
import os
import random
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import InputPeerChannel, MessageMediaPhoto, MessageMediaDocument

from core.apps import alog_message, get_management_logger
from telegram.models import APIKeys, Canal

logger = get_management_logger('get_messages')

MAX_ERROS_CONSECUTIVOS = 10
DATA_LIMITE = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)


def filtro_canal(valor):
    """
    Constrói o filtro de um único canal, aceitando tanto username quanto id_numerico.
    """
    filtro = Q(username=valor)
    try:
        filtro |= Q(id_numerico=int(valor))
    except ValueError:
        pass
    return filtro


def monta_peer(canal):
    """
    Monta o InputPeerChannel diretamente com os dados já persistidos no banco,
    evitando um round-trip via get_entity (fonte comum de FloodWait).
    Retorna None se não for possível montar o peer sem consultar o Telegram.
    """
    if canal.access_hash:
        try:
            return InputPeerChannel(channel_id=canal.id_numerico, access_hash=int(canal.access_hash))
        except (TypeError, ValueError):
            pass
    return None


def serializa_mensagem(message, canal):
    """
    Monta o dicionário de uma mensagem do Telegram para gravação em disco,
    já no formato consumido pelo exportador do Datalake.
    """
    from_id = getattr(message, 'from_id', None)
    author_id = getattr(from_id, 'user_id', None) if from_id else None
    author_type = 'user' if author_id else 'anonymous'

    reply_to = getattr(message, 'reply_to', None)
    reply_to_msg_id = getattr(reply_to, 'reply_to_msg_id', None) if reply_to else None

    fwd_from = getattr(message, 'fwd_from', None)
    fwd_from_author_id = None
    fwd_from_author_username = None
    if fwd_from:
        fwd_from_id = getattr(fwd_from, 'from_id', None)
        fwd_from_author_id = getattr(fwd_from_id, 'user_id', None) if fwd_from_id else None
        fwd_from_author_username = getattr(fwd_from, 'from_name', None)

    media = getattr(message, 'media', None)
    if media is None:
        media_type = None
    elif isinstance(media, MessageMediaPhoto):
        media_type = 'photo'
    elif isinstance(media, MessageMediaDocument):
        media_type = 'document'
    else:
        media_type = type(media).__name__

    edit_date = getattr(message, 'edit_date', None)

    return {
        'id': f'{canal.id_numerico}_{message.id}',
        'message_id': message.id,
        'channel_id': canal.id_numerico,
        'username': canal.username,
        'channel_title': canal.titulo,
        'message': message.message,
        'timestamp': message.date.isoformat() if message.date else None,
        'type': 'group' if canal.megagroup else 'channel',
        'views': message.views,
        'forwards': message.forwards,
        'edit_date': edit_date.isoformat() if edit_date else None,
        'grouped_id': message.grouped_id,
        'post_author': message.post_author,
        'media_type': media_type,
        'media_description': message.message if media else None,
        'author_type': author_type,
        'author_id': author_id,
        'reply_to_msg_id': reply_to_msg_id,
        'fwd_from_author_id': fwd_from_author_id,
        'fwd_from_author_username': fwd_from_author_username,
        'canal': canal.id,
    }


async def grava_lote(dest_dir, canal, buffer, fake):
    """
    Grava o buffer de mensagens em um único arquivo JSON e o esvazia.
    Retorna o nome do arquivo gravado (ou None, no modo --fake).
    """
    if not buffer:
        return None
    primeiro_id = buffer[0]['message_id']
    ultimo_id = buffer[-1]['message_id']
    nome_arquivo = f'{canal.id_numerico}_{primeiro_id}_{ultimo_id}.json'
    if not fake:
        caminho = os.path.join(dest_dir, nome_arquivo)
        with open(caminho, 'w', encoding='utf-8') as arquivo:
            json.dump(buffer, arquivo, ensure_ascii=False)
    return nome_arquivo


async def processa_canal(client, canal, dest_dir, limite, lote, fake):
    """
    Captura as mensagens novas de um canal, de forma incremental e resumível,
    gravando em disco a cada `lote` mensagens.
    """
    peer = monta_peer(canal)
    if peer is None:
        # Fallback: resolve o peer via get_entity e regrava os dados no canal
        entity = await client.get_entity(canal.username)
        canal.id_numerico = entity.id
        canal.access_hash = str(entity.access_hash)
        if not fake:
            await canal.asave(update_fields=['id_numerico', 'access_hash'])
        peer = InputPeerChannel(channel_id=canal.id_numerico, access_hash=int(canal.access_hash))

    min_id = canal.ultima_mensagem or 0
    if min_id:
        intervalo = {'min_id': min_id}
    else:
        intervalo = {'offset_date': DATA_LIMITE}
    buffer = []
    tot_canal = 0

    async for message in client.iter_messages(peer, reverse=True, limit=limite, **intervalo):
        buffer.append(serializa_mensagem(message, canal))

        if len(buffer) >= lote:
            await grava_lote(dest_dir, canal, buffer, fake)
            canal.ultima_mensagem = buffer[-1]['message_id']
            tot_canal += len(buffer)
            if not fake:
                await canal.asave(update_fields=['ultima_mensagem'])
            buffer = []

    if buffer:
        await grava_lote(dest_dir, canal, buffer, fake)
        canal.ultima_mensagem = buffer[-1]['message_id']
        tot_canal += len(buffer)
        if not fake:
            await canal.asave(update_fields=['ultima_mensagem'])

    canal.dt_ultima_carga = timezone.now()
    canal.num_mensagens = (canal.num_mensagens or 0) + tot_canal
    if not fake:
        await canal.asave(update_fields=['ultima_mensagem', 'dt_ultima_carga', 'num_mensagens'])
        await alog_message(canal, f'{tot_canal} mensagens capturadas')

    return tot_canal


async def coleta_mensagens(client, options):
    dest_dir = os.path.join(settings.BASE_DIR, 'data', 'telegram')
    os.makedirs(dest_dir, exist_ok=True)    

    fake = options['fake']
    limite = options['limite']
    lote = options['lote']

    canais = Canal.objects.filter(status=Canal.Status.ATIVO,
                                   id_numerico__isnull=False).order_by('dt_ultima_carga')
    if options.get('canal'):
        canais = canais.filter(filtro_canal(options['canal']))

    tot_canais_processados = 0
    tot_mensagens = 0
    tot_canais_erro = 0
    tot_canais_desabilitados = 0
    erros_consecutivos = 0

    async for canal in canais:
        try:
            tot_canal = await processa_canal(client, canal, dest_dir, limite, lote, fake)
            tot_mensagens += tot_canal
            tot_canais_processados += 1
            logger.info(f'{canal.username}: {tot_canal} mensagens capturadas')
            erros_consecutivos = 0

        except FloodWaitError as e:
            logger.info(f'{canal.username}: FloodWait de {e.seconds}s, aguardando e seguindo para o próximo canal')
            if not fake:
                await alog_message(canal, f'FloodWait de {e.seconds}s, aguardando e seguindo para o próximo canal')
            await asyncio.sleep(e.seconds)
            tot_canais_erro += 1
            erros_consecutivos += 1

        except RPCError as e:
            canal.status = Canal.Status.NAO_EXISTE
            if not fake:
                await canal.asave(update_fields=['status'])
                await alog_message(canal, f'Erro RPC do Telegram ao capturar mensagens: {e}')
            logger.error(f'{canal.username}: erro RPC, canal desativado: {e}')
            tot_canais_desabilitados += 1
            tot_canais_erro += 1
            erros_consecutivos += 1

        except Exception as e:
            if not fake:
                await alog_message(canal, f'Erro inesperado ao capturar mensagens: {e}')
            logger.error(f'{canal.username}: erro inesperado ao capturar mensagens', exc_info=True)
            tot_canais_erro += 1
            erros_consecutivos += 1

        if erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
            logger.error(f'Abortando execução: {erros_consecutivos} erros consecutivos')
            break

        await asyncio.sleep(random.uniform(1.5, 3.5))

    logger.info(f'Total de canais processados: {tot_canais_processados}')
    logger.info(f'Total de mensagens capturadas: {tot_mensagens}')
    logger.info(f'Total de canais com erro: {tot_canais_erro}')
    logger.info(f'Total de canais desabilitados: {tot_canais_desabilitados}')


class Command(BaseCommand):
    help = 'Captura mensagens dos canais do Telegram, de forma incremental'

    def add_arguments(self, parser):
        parser.add_argument('--canal', type=str,
                             help='Username ou id_numerico de um único canal')
        parser.add_argument('--limite', type=int, default=1000,
                             help='Máximo de mensagens por canal nesta execução')
        parser.add_argument('--lote', type=int, default=100,
                             help='Mensagens por arquivo JSON')
        parser.add_argument('--session', type=str, default='sync_channels',
                             help='Arquivo de sessão do Telethon')
        parser.add_argument('--fake', action='store_true',
                             help='Não grava arquivos nem atualiza os canais')

    def handle(self, *args, **options):
        chave = APIKeys.objects.filter(status=APIKeys.Status.ATIVO).first()
        if not chave:
            logger.error('Nenhuma chave de API cadastrada (telegram.APIKeys)')
            return
        asyncio.run(self.main(chave.api_id, chave.api_hash, options))

    async def main(self, api_id, api_hash, options):
        async with TelegramClient(options['session'], api_id, api_hash) as client:
            if not await client.is_user_authorized():
                logger.error('Usuário não autorizado. Faça o login primeiro.')
                return
            await coleta_mensagens(client, options)
