#!/usr/bin/env bash
set -e

PROFILES=""
API_PORT="${API_PORT:-8002}"
export API_PORT

echo "=== Проверка окружения ==="
echo ""

# --- Проверка порта API ---
if ss -tlnp 2>/dev/null | grep -q ":${API_PORT} "; then
    echo "[!] Порт ${API_PORT} занят. Укажи другой: API_PORT=8003 ./start.sh"
    exit 1
fi
echo "[✓] Порт ${API_PORT} свободен для API"

# --- Проверка Redis ---
# Проверяем слушает ли Redis на 0.0.0.0 (доступен из Docker) или только на 127.0.0.1
if ss -tlnp 2>/dev/null | grep ':6379 ' | grep -q '0.0.0.0'; then
    echo "[✓] Redis на 0.0.0.0:6379 — доступен из Docker"
    export REDIS_URL="redis://host.docker.internal:6379/0"
elif ss -tlnp 2>/dev/null | grep -q ':6379 '; then
    echo "[!] Redis на 127.0.0.1:6379 — из Docker недоступен, подниму отдельный на :6380"
    PROFILES="$PROFILES --profile redis"
else
    echo "[+] Redis не найден — подниму в Docker"
    PROFILES="$PROFILES --profile redis"
fi

# --- Проверка PostgreSQL ---
if ss -tlnp 2>/dev/null | grep ':5432 ' | grep -q '0.0.0.0'; then
    echo "[✓] PostgreSQL на 0.0.0.0:5432 — доступен из Docker"
    export DATABASE_URL="postgresql+asyncpg://guardrails:password@host.docker.internal:5432/guardrails_mvp"

    # Создаём базу и юзера если их нет
    PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i postgres | head -1)
    if [ -n "$PG_CONTAINER" ]; then
        # Определяем суперюзера из env контейнера
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
echo "=== Запуск docker-compose (API на порту ${API_PORT}) ==="

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
echo "API: http://localhost:${API_PORT}"
