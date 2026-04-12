# AI DevStudio

Автономная AI-студия разработки. Полный цикл: исследование рынка → разработка → маркетинг → монетизация.

## Быстрый старт

### 1. Клонировать и настроить

```bash
git clone <repo>
cd ai-devstudio
cp .env.example .env
```

### 2. Заполнить .env

```bash
# Сгенерировать хэш пароля
python3 -c "import bcrypt; print(bcrypt.hashpw(b'ВАШ_ПАРОЛЬ', bcrypt.gensalt()).decode())"

# Вставить в .env:
# ADMIN_LOGIN=ваш_логин
# ADMIN_PASSWORD_HASH=сгенерированный_хэш
# JWT_SECRET=случайная_строка_64_символа
```

### 3. Запустить

```bash
docker compose up -d --build
```

### 4. Инициализировать агентов

```bash
docker compose exec backend python seed.py
```

### 5. Открыть панель

Перейти на `https://ai-devstudio.mak-o.ru` (или `http://localhost` для локальной разработки).

---

## Структура

```
ai-devstudio/
├── backend/          FastAPI + Celery + агенты
├── frontend/         Next.js панель управления
├── nginx/            Reverse proxy + robots.txt
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## Переменные окружения

Все переменные описаны в `.env.example`.  
**Никогда не коммить `.env` в git.**

## Cloudflared туннель

```bash
cloudflared tunnel login
cloudflared tunnel create ai-devstudio
cloudflared tunnel route dns ai-devstudio ai-devstudio.mak-o.ru
cloudflared service install
systemctl start cloudflared
```

## Управление

```bash
# Статус
docker compose ps

# Логи агентов
docker compose logs celery -f

# Перезапуск
docker compose restart

# Остановка
docker compose down

# Обновление
docker compose up -d --build
```

## Фазы разработки

- **Фаза 1** (текущая): Фундамент. 2 агента: Директор + Backend Dev.
- **Фаза 2**: Полная команда 13 агентов. Skills-система.
- **Фаза 3**: Первые продукты. Монетизация.
- **Фаза 4**: Автономный рост.
