# Guardrails MVP OS

**Платформа для безопасного взаимодействия с LLM-агентами через систему динамических guardrails.**

Версия: 0.2.0

---

## Оглавление

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Технологический стек](#технологический-стек)
- [Основной функционал](#основной-функционал)
- [Структура проекта](#структура-проекта)
- [API](#api)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)

---

## Обзор

Guardrails MVP OS — полнофункциональное приложение для взаимодействия с LLM-агентами, оснащённое многоуровневой системой защиты (guardrails). Система автоматически классифицирует тематику диалога и применяет соответствующие правила безопасности, обеспечивая контролируемое и прозрачное поведение AI-агента.

---

## Архитектура

### Общая схема

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│         Mantine UI · Zustand · TypeScript            │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────┐
│                 Backend (FastAPI)                     │
│                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Guardrails │  │  LangGraph   │  │  Dynamic     │ │
│  │  Runtime    │  │  Agent       │  │  Rails Engine│ │
│  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘ │
│        │                │                  │         │
│  ┌─────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐ │
│  │ NeMo /     │  │ Tool Proxy   │  │ LLM          │ │
│  │ LangChain  │  │ (sandbox)    │  │ Classifier   │ │
│  └────────────┘  └──────────────┘  └──────────────┘ │
└──────────┬───────────────┬───────────────┬──────────┘
           │               │               │
     ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
     │   Redis    │  │ PostgreSQL│  │ LLM Provider│
     │ (сессии)   │  │ (аудит)   │  │ (OpenAI и  │
     └───────────┘  └───────────┘  │  др.)       │
                                    └─────────────┘
```

### Пайплайн обработки сообщения

```
Сообщение пользователя
        │
        ▼
┌───────────────────────────┐
│   Параллельная обработка: │
│  ├─ Детекция PII          │
│  ├─ Детекция unsafe       │
│  └─ Генерация дин. правил │
└───────────┬───────────────┘
            ▼
   Проверка безопасности входа
            │
            ▼
   Guardrails Backend (input check)
            │
            ▼
   LangGraph Agent + Tool Calls
            │
            ▼
   Проверка безопасности выхода
            │
            ▼
      ChatResponse
  (сообщение, rail events,
   tool calls, generated rules)
```

---

## Технологический стек

### Backend

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | FastAPI |
| LLM-оркестрация | LangChain + LangGraph |
| Guardrails | NeMo Guardrails / LangChain (LLM-as-Judge) |
| Сессии | Redis |
| База данных | PostgreSQL (AsyncPG + SQLAlchemy 2.0) |
| Логирование | structlog |
| Метрики | Prometheus |

### Frontend

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | React 18 + TypeScript |
| UI-библиотека | Mantine 7 |
| Стейт-менеджмент | Zustand |
| Сборка | Vite |
| Markdown | react-markdown + remark-gfm |

### Инфраструктура

- **Docker Compose** — оркестрация сервисов (API, Redis, PostgreSQL)
- Поддержка hot-reload при разработке

---

## Основной функционал

### 1. Мультипровайдерная поддержка LLM

Агент поддерживает несколько LLM-провайдеров с переключением в runtime без перезапуска:

- **OpenAI** (GPT-4o и др.)
- **Anthropic** (Claude)
- **Ollama** (локальные модели)
- **vLLM** (self-hosted)

### 2. Подключаемые Guardrails-бэкенды

| Бэкенд | Описание |
|--------|----------|
| **LangChain** | LLM-as-Judge — быстрая модель-классификатор оценивает вход/выход на соответствие правилам |
| **NeMo** | NVIDIA NeMo Guardrails — декларативные правила на Colang |
| **None** | Passthrough — guardrails отключены |

Режимы работы: `enforce` (блокировка) и `monitor` (только логирование).

### 3. Динамическая генерация правил

Ключевая особенность системы — автоматическое определение тематики диалога и применение соответствующих правил:

- **Классификация** — LLM определяет домен сообщения (медицина, финансы, юриспруденция и др.)
- **Шаблоны** — для каждого домена предусмотрены готовые шаблоны правил
- **Накопление** — правила сохраняются на протяжении всей сессии
- **Дедупликация** — предотвращение дублирования правил

Примеры доменов: `medical`, `financial`, `legal`, `coding`, `general`.

### 4. Безопасность ввода/вывода

- **PII-детекция** — обнаружение персональных данных (номера карт, SSN, email, телефоны, IP)
- **Safety-детекция** — определение небезопасного контента (насилие, нелегальная активность, самоповреждение)
- **Проверка выхода** — фильтрация ответов агента

### 5. Tool Proxy — безопасное выполнение инструментов

Агент имеет доступ к набору инструментов через защищённый прокси:

| Инструмент | Описание |
|------------|----------|
| `read_file` | Чтение файлов (с защитой от path traversal) |
| `write_file` | Запись файлов в рабочую директорию |
| `list_directory` | Просмотр содержимого директории |
| `run_python` | Выполнение Python-кода (sandbox) |
| `web_search` | Поиск через DuckDuckGo API |
| `calculate` | Безопасное вычисление математических выражений |

Механизмы защиты:
- Rate limiting (ограничение частоты вызовов)
- Loop detection (обнаружение зацикливания)
- Таймауты на выполнение
- Аудит-логирование каждого вызова

### 6. Управление сессиями

- **Серверная сторона** — Redis с TTL (по умолчанию 1 час)
- **Клиентская сторона** — LocalStorage для истории и настроек

### 7. Observability

- Структурированное логирование (structlog)
- Метрики Prometheus (`/metrics`)
- Trace ID для каждого запроса

### 8. Инспектор (Frontend)

Правая панель интерфейса для отладки и мониторинга:

- **Guardrails Tab** — события сработавших правил
- **Generated Rails Tab** — динамически сгенерированные правила
- **Actions Tab** — выполненные действия агента

---

## Структура проекта

```
├── app/                            # Backend
│   ├── main.py                     # Точка входа FastAPI, endpoint /chat
│   ├── config.py                   # Конфигурация (pydantic-settings)
│   ├── agent/                      # LLM-агент
│   │   ├── langgraph_runtime.py    # LangGraph StateGraph
│   │   ├── llm_factory.py          # Фабрика LLM-провайдеров
│   │   └── tools.py                # Определение инструментов
│   ├── guardrails/                 # Guardrails-бэкенды
│   │   ├── runtime.py              # Оркестратор guardrails
│   │   ├── base.py                 # Абстрактный интерфейс
│   │   ├── langchain_backend.py    # LLM-as-Judge
│   │   ├── nemo_backend.py         # NeMo Guardrails
│   │   └── rails_profiles/         # Конфигурации NeMo
│   ├── dynamic_rails/              # Динамические правила
│   │   ├── rule_engine.py          # Оркестрация правил
│   │   ├── llm_classifier.py       # Классификатор тематики
│   │   ├── rule_registry.py        # Реестр шаблонов
│   │   └── builder.py              # Построение правил
│   ├── tool_proxy/                 # Прокси инструментов
│   │   ├── registry.py             # Реестр инструментов
│   │   ├── proxy.py                # Прокси выполнения
│   │   └── policies.py             # Политики доступа
│   ├── utils/                      # Утилиты
│   │   ├── pii_detector.py         # Детекция PII
│   │   ├── safety_detector.py      # Детекция unsafe-контента
│   │   └── rail_generator.py       # Генерация правил
│   ├── sessions.py                 # Управление сессиями (Redis)
│   └── observability.py            # Логирование и метрики
│
├── frontend/                       # Frontend
│   └── src/
│       ├── App.tsx                 # Корневой компонент
│       ├── api/client.ts           # HTTP-клиент
│       ├── components/
│       │   ├── chat/               # Чат (ChatView, MessageBubble)
│       │   ├── inspector/          # Панель инспектора
│       │   ├── guardrails/         # Тогглы guardrails
│       │   ├── settings/           # Настройки рантайма
│       │   └── sessions/           # Управление сессиями
│       ├── store/                  # Zustand-сторы
│       └── types/                  # TypeScript-типы
│
├── tests/                          # Тесты
├── scripts/                        # Вспомогательные скрипты
├── docker-compose.yml              # Docker Compose
├── Dockerfile                      # Контейнер бэкенда
└── requirements.txt                # Python-зависимости
```

---

## API

### Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/chat` | Отправка сообщения с обработкой guardrails |
| `GET` | `/config` | Получение текущей конфигурации |
| `POST` | `/config` | Обновление конфигурации (бэкенд guardrails, LLM-провайдер) |
| `GET` | `/health` | Проверка здоровья сервисов |
| `GET` | `/metrics` | Метрики Prometheus |

### Формат запроса `/chat`

```json
{
  "session_id": "uuid",
  "user_message": "текст сообщения",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "guardrails": {
    "enabled": true,
    "monitor_only": false,
    "toggles": {"pii_detection": true, "safety_check": true}
  }
}
```

### Формат ответа `/chat`

```json
{
  "assistant_message": "ответ агента",
  "status": "ok | refused | escalated",
  "trace_id": "uuid",
  "tool_calls": [...],
  "rail_events": [
    {
      "railName": "pii_detection",
      "stage": "input",
      "severity": "warn",
      "reason": "Обнаружен email-адрес"
    }
  ],
  "generated_rails": {
    "profileId": "medical",
    "summary": "Применены медицинские ограничения",
    "rules": [...]
  }
}
```

---

## Конфигурация

Настройка через переменные окружения (`.env`):

```bash
# LLM
LLM_PROVIDER=openai          # openai | anthropic | ollama | vllm
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...

# Guardrails
GUARDRAILS_BACKEND=langchain  # langchain | nemo | none
GUARDRAILS_MODE=enforce        # enforce | monitor
DYNAMIC_RAILS_ENABLED=true

# Инфраструктура
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/guardrails_mvp

# Tool Proxy
TOOL_MAX_CALLS_PER_REQUEST=10
TOOL_RATE_LIMIT_PER_MIN=30
TOOL_TIMEOUT_SECONDS=15
```

---

## Запуск

### Docker Compose (рекомендуется)

```bash
docker-compose up --build
```

Сервисы:
- **API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **Redis**: localhost:6379
- **PostgreSQL**: localhost:5432

### Локальная разработка

**Backend:**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
