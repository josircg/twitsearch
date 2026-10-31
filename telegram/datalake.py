from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from core.apps import connect_postgresql

TABELA = 'telegram'
PG_ALIAS = 'pg_baoba'

MIDIAS = {'photo': 'Foto', 'document': 'Documento', 'MessageMediaWebPage': 'Link'}

# Mesmos filtros na contagem e na página; a expressão telegram_ts(...) deve ser idêntica à do índice
FILTROS = r"""
 WHERE (source->>'channel_id')::bigint = %(canal)s
   AND (%(ini)s::timestamptz IS NULL OR telegram_ts(source->>'timestamp') >= %(ini)s)
   AND (%(fim)s::timestamptz IS NULL OR telegram_ts(source->>'timestamp') <= %(fim)s)
   AND (%(termo)s::text IS NULL OR source->>'message' ILIKE %(termo)s ESCAPE '\')
"""

SQL_TOTAL = f"SELECT count(*) FROM {TABELA}" + FILTROS

SQL_PAGINA = (f"SELECT source FROM {TABELA}" + FILTROS +
              " ORDER BY telegram_ts(source->>'timestamp') DESC, (source->>'message_id')::bigint DESC"
              " LIMIT %(limit)s OFFSET %(offset)s")


def escapa_like(termo: str) -> str:
    termo = termo.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{termo}%'


SQL_PERIODO = (f"SELECT min(telegram_ts(source->>'timestamp')), max(telegram_ts(source->>'timestamp')) FROM {TABELA}"
               " WHERE (source->>'channel_id')::bigint = %(canal)s")


def formata_mensagem(source: dict) -> dict:
    data = source.get('timestamp')
    if data:
        data = datetime.fromisoformat(data)
        if timezone.is_naive(data):
            data = timezone.make_aware(data, dt_timezone.utc)
        data = timezone.localtime(data)
    media = source.get('media_type')
    return {
        'message_id': source.get('message_id'),
        'texto': source.get('message') or None,
        'data': data or None,
        'views': int(source.get('views') or 0),
        'forwards': int(source.get('forwards') or 0),
        'midia': MIDIAS.get(media, 'Mídia') if media else None,
        'url': f"https://t.me/{source.get('username')}/{source.get('message_id')}",
    }


def busca_mensagens(channel_id, dt_inicio=None, dt_final=None, termo=None, limit=25, offset=0):
    params = {'canal': channel_id, 'ini': dt_inicio, 'fim': dt_final,
              'termo': escapa_like(termo) if termo else None}
    conn = connect_postgresql(PG_ALIAS)
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_TOTAL, params)
            total = cur.fetchone()[0]
            cur.execute(SQL_PAGINA, {**params, 'limit': limit, 'offset': offset})
            linhas = cur.fetchall()
    finally:
        conn.close()
    return total, [formata_mensagem(linha[0]) for linha in linhas]


def periodo_canal(channel_id):
    # (primeira, última) data das mensagens coletadas do canal; () quando não há nenhuma
    conn = connect_postgresql(PG_ALIAS)
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_PERIODO, {'canal': channel_id})
            inicio, fim = cur.fetchone()
    finally:
        conn.close()
    if inicio is None:
        return ()
    return timezone.localtime(inicio), timezone.localtime(fim)


def paginas_visiveis(atual: int, total: int) -> list:
    # 1, última, vizinhas da atual; None = reticências
    exibir = {1, total, atual - 1, atual, atual + 1}
    if atual <= 4:
        exibir.update(range(1, 6))
    if atual >= total - 3:
        exibir.update(range(total - 4, total + 1))
    numeros = sorted(n for n in exibir if 1 <= n <= total)
    resultado = []
    for n in numeros:
        if resultado and n - resultado[-1] > 1:
            resultado.append(None)
        resultado.append(n)
    return resultado


class PaginaMensagens:
    # imita a API de django.core.paginator.Page para o mesmo template servir aos dois grids
    def __init__(self, page, per_page, count):
        self.per_page = per_page
        self.count = count
        self.num_pages = max(1, -(-count // per_page))
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 1
        self.number = min(max(page, 1), self.num_pages)

    def has_previous(self):
        return self.number > 1

    def has_next(self):
        return self.number < self.num_pages

    def previous_page_number(self):
        return self.number - 1

    def next_page_number(self):
        return self.number + 1

    def start_index(self):
        return 0 if self.count == 0 else (self.number - 1) * self.per_page + 1

    def end_index(self):
        return min(self.number * self.per_page, self.count)

    @property
    def paginator(self):
        # Page.paginator.num_pages / .count: o mesmo objeto responde pelos dois
        return self

    @property
    def paginas_visiveis(self):
        return paginas_visiveis(self.number, self.num_pages)
