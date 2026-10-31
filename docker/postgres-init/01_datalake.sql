/*
   Criação do Datalake (Twitter/YouTube/Telegram) - baseado em data/datalake.sql
   Executado automaticamente pelo container Postgres na primeira inicialização
   (docker-entrypoint-initdb.d). Divergências em relação ao script original:
   - a tabela "twitter" estava duplicada no datalake.sql; aqui é criada uma única vez
   - CREATE TABLE ganhou IF NOT EXISTS para permitir reexecução manual segura
*/

CREATE TABLE IF NOT EXISTS processo (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    provenance text NOT NULL
);

CREATE UNLOGGED TABLE IF NOT EXISTS twitter (
    id text PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE INDEX IF NOT EXISTS idx_twitter_id ON twitter(id);
CREATE INDEX IF NOT EXISTS idx_twitter_processo ON twitter(processo);
CREATE INDEX IF NOT EXISTS idx_data_search ON twitter USING GIN (source);

CREATE TABLE IF NOT EXISTS fila_twitter (
    sequence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE TABLE IF NOT EXISTS fila_youtube (
    sequence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE TABLE IF NOT EXISTS fila_telegram (
    sequence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE UNLOGGED TABLE IF NOT EXISTS historico (
    id text,
    processo bigint,
    source JSONB,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para busca rápida no histórico por ID
CREATE INDEX IF NOT EXISTS idx_historico_id ON historico(id);
CREATE INDEX IF NOT EXISTS idx_historico_processo ON historico(processo);

CREATE UNLOGGED TABLE IF NOT EXISTS youtube_video (
    id text PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE INDEX IF NOT EXISTS idx_youtube_video_id ON youtube_video(id);
CREATE INDEX IF NOT EXISTS idx_youtube_video_processo ON youtube_video(processo);

CREATE UNLOGGED TABLE IF NOT EXISTS telegram (
    id text PRIMARY KEY,
    processo bigint,
    source JSONB
);

CREATE INDEX IF NOT EXISTS idx_telegram_id ON telegram(id);
CREATE INDEX IF NOT EXISTS idx_telegram_processo ON telegram(processo);

-- Índice para a consulta de mensagens por canal e período (telegram/datalake.py).
-- O timestamp é sempre ISO 8601 com offset explícito (isoformat() de datetime aware),
-- então o resultado não depende de DateStyle/TimeZone e a função pode ser IMMUTABLE.
-- O cast direto ::timestamptz não é IMMUTABLE e seria recusado no índice.
CREATE OR REPLACE FUNCTION telegram_ts(text) RETURNS timestamptz
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT $1::timestamptz $$;

CREATE INDEX IF NOT EXISTS idx_telegram_canal_data
    ON telegram (((source->>'channel_id')::bigint), telegram_ts(source->>'timestamp'));
