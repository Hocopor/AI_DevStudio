# AI DevStudio — Фаза 2
## Полная команда 13 AI-агентов

---

## Что нового в Фазе 2

- **13 агентов** с детальными системными промптами и ролями
- **Unified LLM Provider** — единый слой для DeepSeek / Google AI Studio / Codex OAuth
- **Мультиаккаунт Codex** с авто-переключением при исчерпании лимита
- **Skills-система** — создание, версионирование, распространение навыков агентами
- **Авто-создание Skills** — агент сам определяет, стоит ли оформить решение в Skill
- **Страница Команда** — управление агентами, настройка провайдера/модели/промпта, Skills
- **Страница Настройки** — провайдеры AI, Codex OAuth аккаунты, уведомления
- **Страница Финансы** — расходы на AI по провайдерам / агентам / дням, лог запросов
- **Роут /api/finance** — детальная аналитика расходов на AI API

---

## Команда агентов

| Агент | ID | Провайдер по умолчанию | Специализация |
|-------|----|------------------------|---------------|
| Директор | `director` | DeepSeek Reasoner | Оркестрация, декомпозиция задач |
| Аналитик рынка | `analyst` | DeepSeek Reasoner | Исследования, конкуренты, ниши |
| Продуктовый менеджер | `pm` | DeepSeek Reasoner | ТЗ, roadmap, user stories |
| Backend Dev | `backend_dev` | DeepSeek Chat | API, БД, серверная логика |
| Frontend Dev | `frontend_dev` | Codex (GPT-4o) | React/Next.js, TypeScript, UI |
| UX/UI Дизайнер | `ux_ui` | DeepSeek Chat | Прототипы, дизайн-система |
| QA-инженер | `qa` | DeepSeek Chat | Тест-кейсы, баг-репорты |
| DevOps | `devops` | DeepSeek Chat | Docker, CI/CD, инфраструктура |
| Маркетолог | `marketer` | DeepSeek Reasoner | Стратегия, воронки, реклама |
| Копирайтер | `copywriter` | DeepSeek Chat | Тексты, лендинги, tone of voice |
| SMM-менеджер | `smm` | DeepSeek Chat | Соцсети, контент-план |
| SEO-специалист | `seo` | DeepSeek Chat | Семантика, оптимизация |
| Финансовый аналитик | `finance` | DeepSeek Chat | Unit-экономика, P&L |

> Провайдер и модель для каждого агента меняются через веб-панель без перезапуска системы.

---

## Быстрый старт

### 1. Настроить окружение

```bash
cp .env.example .env
# Отредактировать .env — заполнить все переменные
```

### 2. Сгенерировать хэш пароля

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'ВАШ_ПАРОЛЬ', bcrypt.gensalt()).decode())"
# Вставить результат в ADMIN_PASSWORD_HASH в .env
```

### 3. Запустить

```bash
docker compose up -d --build
```

### 4. Инициализировать всех агентов

```bash
docker compose exec backend python seed.py
```

### 5. Добавить Codex OAuth аккаунты (опционально)

Через веб-панель: **Настройки → Codex OAuth → Добавить**

### 6. Открыть панель

`https://ai-devstudio.mak-o.ru`

---

## Структура иерархии агентов

```
Владелец
  └── Директор (оркестратор)
        ├── Аналитик рынка
        ├── Продуктовый менеджер
        ├── Backend Dev ──────────── [код, API, БД]
        ├── Frontend Dev ─────────── [React, UI]
        ├── UX/UI Дизайнер ────────── [макеты, прототипы]
        ├── QA-инженер ────────────── [тесты, баги]
        ├── DevOps ─────────────────── [инфра, деплой]
        ├── Маркетолог ─────────────── [стратегия, реклама]
        ├── Копирайтер ─────────────── [тексты, TOV]
        ├── SMM-менеджер ───────────── [соцсети, контент]
        ├── SEO-специалист ─────────── [семантика, оптимизация]
        └── Финансовый аналитик ────── [P&L, unit-экономика]
```

---

## API маршруты Фазы 2

```
# Skills
GET    /api/skills                       — список Skills (фильтр: agent_id)
POST   /api/skills                       — создать Skill
PUT    /api/skills/{id}                  — обновить (content, description, is_active)
DELETE /api/skills/{id}                  — удалить
POST   /api/skills/{id}/distribute       — распространить на других агентов

# Codex OAuth аккаунты
GET    /api/codex-accounts               — список аккаунтов
POST   /api/codex-accounts               — добавить аккаунт
PUT    /api/codex-accounts/{id}          — обновить (label, priority, is_active)
DELETE /api/codex-accounts/{id}          — удалить
POST   /api/codex-accounts/{id}/set-current — сделать активным

# Финансы / расходы на AI
GET    /api/finance/summary?period=month — сводка (day/week/month/all)
GET    /api/finance/usage-log            — лог запросов к AI API
```

---

## Skills-система

### Как работает

1. **Агент выполняет задачу** → после завершения LLM анализирует: стоит ли оформить решение в Skill?
2. **Если да** → автоматически создаётся Skill и привязывается к агенту
3. **Skill попадает в системный промпт** → агент использует его в следующих задачах
4. **Директор может распространить** полезный Skill на других агентов

### Управление через веб-панель

`Команда → [Агент] → Skills → Добавить / Редактировать / Распространить`

---

## Мультиаккаунт Codex OAuth

- Добавить несколько OAuth-аккаунтов через `Настройки → Codex OAuth`
- Установить приоритет (1 = первый в очереди)
- При исчерпании лимита — автоматическое переключение на следующий
- Уведомление в VK при каждом переключении
- Мониторинг статуса аккаунтов: `Мониторинг → API`

---

## Управление системой

```bash
# Статус сервисов
docker compose ps

# Логи агентов (Celery workers)
docker compose logs celery -f

# Логи API
docker compose logs backend -f

# Перезапуск
docker compose restart

# Обновление после изменений
docker compose up -d --build

# Остановка
docker compose down

# Полный сброс (включая данные!)
docker compose down -v
```

---

## Файловая структура

```
ai-devstudio/
├── .env.example                  ← шаблон переменных окружения
├── .gitignore
├── README.md
├── docker-compose.yml
│
├── nginx/
│   ├── nginx.conf               ← reverse proxy + защита
│   └── robots.txt               ← запрет индексирования
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                  ← FastAPI app
│   ├── seed.py                  ← инициализация 13 агентов
│   ├── core/
│   │   ├── auth.py              ← JWT + bcrypt (.env)
│   │   ├── config.py            ← настройки из .env
│   │   ├── database.py          ← SQLAlchemy async
│   │   └── redis.py
│   ├── models/
│   │   └── all_models.py        ← все таблицы БД
│   ├── schemas/
│   │   └── __init__.py          ← Pydantic схемы
│   ├── api/routes/
│   │   ├── auth.py              ← login/logout/refresh
│   │   ├── dashboard.py         ← метрики дашборда
│   │   ├── projects.py
│   │   ├── tasks.py
│   │   ├── agents.py
│   │   ├── notifications.py
│   │   ├── skills.py            ← [NEW] Skills CRUD
│   │   ├── codex_accounts.py    ← [NEW] Codex OAuth
│   │   └── finance.py           ← [NEW] расходы на AI
│   ├── services/
│   │   ├── llm_provider.py      ← [NEW] unified LLM layer
│   │   ├── skills_service.py    ← [NEW] Skills логика
│   │   ├── notification_service.py ← уведомления + VK
│   │   ├── minio_service.py     ← файловое хранилище
│   │   └── ws_manager.py
│   ├── agents/
│   │   ├── base_agent.py        ← [UPDATED] base class
│   │   ├── all_agents.py        ← [NEW] 11 агентов + директор v2
│   │   └── backend_dev_agent.py
│   └── workers/
│       └── celery_app.py        ← [UPDATED] все 13 агентов
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── tsconfig.json
    ├── postcss.config.js
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx        ← auth guard + sidebar
        │   ├── globals.css
        │   ├── login/page.tsx
        │   ├── dashboard/page.tsx
        │   ├── monitoring/page.tsx   ← [UPDATED] + API tab
        │   ├── projects/page.tsx
        │   ├── projects/[id]/page.tsx
        │   ├── projects/[id]/tasks/[taskId]/page.tsx
        │   ├── notifications/page.tsx
        │   ├── team/page.tsx         ← [NEW] команда агентов
        │   ├── finance/page.tsx      ← [NEW] финансы AI
        │   └── settings/page.tsx     ← [NEW] провайдеры + настройки
        ├── components/
        │   ├── ui/Sidebar.tsx
        │   ├── kanban/KanbanBoard.tsx
        │   └── kanban/CreateTaskModal.tsx  ← [UPDATED] все 13 агентов
        ├── lib/
        │   ├── api.ts            ← [UPDATED] все endpoint-ы
        │   └── websocket.ts
        └── store/
            └── authStore.ts
```

---

*Фаза 2 завершена. Следующая — Фаза 3: первые продукты, монетизация, полный бизнес-цикл.*
