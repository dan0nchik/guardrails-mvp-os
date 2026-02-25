#!/usr/bin/env bash
set -e

PROFILES=""
UI_PORT="${UI_PORT:-8002}"
export UI_PORT

echo "=== Проверка окружения ==="
echo ""

# --- Проверка порта UI ---
if ss -tlnp 2>/dev/null | grep -q ":${UI_PORT} "; then
    echo "[!] Порт ${UI_PORT} занят. Укажи другой: UI_PORT=3002 ./start.sh"
    exit 1
fi
echo "[✓] Порт ${UI_PORT} свободен для UI"

# --- Проверка Redis ---
REDIS_LISTEN=$(ss -tlnp 2>/dev/null | grep ':6379 ' | awk '{print $4}' | head -1)
if echo "$REDIS_LISTEN" | grep -q '^0.0.0.0:'; then
    echo "[✓] Redis на 0.0.0.0:6379 — доступен из Docker"
    export REDIS_URL="redis://host.docker.internal:6379/0"
elif [ -n "$REDIS_LISTEN" ]; then
    echo "[!] Redis на ${REDIS_LISTEN} — из Docker недоступен, подниму в Docker на :6380"
    PROFILES="$PROFILES --profile redis"
    # Внутри docker-сети Redis доступен как redis:6379 (дефолт в compose)
else
    echo "[+] Redis не найден — подниму в Docker на :6380"
    PROFILES="$PROFILES --profile redis"
fi

# --- Проверка PostgreSQL ---
PG_LISTEN=$(ss -tlnp 2>/dev/null | grep ':5432 ' | awk '{print $4}' | head -1)
if echo "$PG_LISTEN" | grep -q '^0.0.0.0:'; then
    echo "[✓] PostgreSQL на 0.0.0.0:5432 — доступен из Docker"
    export DATABASE_URL="postgresql+asyncpg://guardrails:password@host.docker.internal:5432/guardrails_mvp"

    # Создаём базу и юзера если их нет
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i postgres | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        PG_ENV=$(docker inspect "$PG_CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}')
        PG_USER=$(echo "$PG_ENV" | grep POSTGRES_USER | cut -d= -f2)
        PG_USER="${PG_USER:-postgres}"
        PG_DB=$(echo "$PG_ENV" | grep POSTGRES_DB | cut -d= -f2)
        PG_DB="${PG_DB:-postgres}"

        echo "    Контейнер: ${PG_CONTAINER}, юзер: ${PG_USER}, база: ${PG_DB}"
        echo "    Проверяю базу guardrails_mvp..."
        if docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -lqt 2>/dev/null | grep -qw guardrails_mvp; then
            echo "    [✓] База guardrails_mvp существует"
        else
            echo "    [+] Создаю пользователя и базу..."
            docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c "
                DO \$\$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'guardrails') THEN
                        CREATE ROLE guardrails WITH LOGIN PASSWORD 'password';
                    END IF;
                END
                \$\$;
            "
            docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c "CREATE DATABASE guardrails_mvp OWNER guardrails;" \
                && echo "    [✓] База создана" \
                || echo "    [!] Не удалось создать базу — проверь доступ"
        fi
    else
        echo "    [!] Postgres-контейнер не найден, базу создай вручную"
    fi
else
    echo "[+] PostgreSQL не найден — подниму в Docker"
    PROFILES="$PROFILES --profile postgres"
fi

echo ""
echo "=== Запуск ==="

# Определяем команду: docker compose (v2) или docker-compose (v1)
if docker compose version &>/dev/null; then
    DC="docker compose"
elif docker-compose version &>/dev/null; then
    DC="docker-compose"
else
    echo "[!] docker compose не найден"
    exit 1
fi

# shellcheck disable=SC2086
$DC $PROFILES up -d --build

echo ""
echo "=== Готово ==="
$DC ps
echo ""
echo "UI:      http://localhost:${UI_PORT}"
echo "API:     http://localhost:${UI_PORT}/api/health"
echo "Metrics: http://localhost:9090/metrics"
