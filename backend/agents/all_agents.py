"""
Все специализированные агенты AI DevStudio (Фаза 2).
Каждый — полноценный autonomous agent со своим системным промптом и логикой.
"""
import json
from models import Task
from agents.base_agent import BaseAgent


# ─────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: универсальный executor
# ─────────────────────────────────────────────────────────────

async def _generic_execute(agent: BaseAgent, task: Task, role_instruction: str = ""):
    """
    Универсальный метод выполнения для специалистов.
    LLM выполняет задачу, результат сохраняется в MinIO и фиксируется в комментарии.
    """
    system = await agent.get_full_system_prompt()
    context = await agent.build_task_context(task, max_output_tokens=4096)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"Выполни задачу. Ответь ТОЛЬКО JSON без markdown:\n"
            f'{{"summary":"что сделано","result":"основной результат/текст/план","files":{{"name.ext":"содержимое"}},"notes":"важные замечания"}}\n\n'
            f"Задача: {task.title}\n\n{context}"
            + (f"\n\nИнструкция: {role_instruction}" if role_instruction else "")
        )},
    ]
    raw = await agent._call_llm(messages, task_id=task.id, max_tokens=4096)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        result = json.loads(raw)
    except Exception:
        result = {"summary": "Задача выполнена", "result": raw, "files": {}, "notes": ""}

    # Сохранить файлы в MinIO
    if result.get("files") and task.project_id:
        from services.minio_service import save_agent_artifact
        for filename, content in result["files"].items():
            if isinstance(content, str):
                save_agent_artifact(task.project_id, agent.agent_id, filename, content.encode())

    # Обновить план — всё done
    plan = task.live_plan or {"steps": [], "notes": ""}
    for s in plan.get("steps", []): s["status"] = "done"
    plan["notes"] = result.get("summary", "")
    await agent.update_live_plan(task.id, plan)

    # Отчёт
    report = f"✅ **{agent.name} — задача выполнена**\n\n"
    report += f"**Что сделано:** {result.get('summary', '')}\n\n"
    if result.get("result"):
        report += f"**Результат:**\n{result['result'][:2000]}\n\n"
    if result.get("files"):
        report += f"**Файлы:** {', '.join(result['files'].keys())}\n"
    if result.get("notes"):
        report += f"**Заметки:** {result['notes']}"
    await agent.comment(task.id, report)

    # Попробовать создать Skill
    await agent.try_create_skill(task, result.get("summary", ""))

    await agent.mark_done(task)


# ─────────────────────────────────────────────────────────────
# ПРОДУКТОВЫЙ МЕНЕДЖЕР
# ─────────────────────────────────────────────────────────────

class ProductManagerAgent(BaseAgent):
    agent_id = "pm"
    name = "Продуктовый менеджер"
    role = "Product Manager"
    provider = "deepseek"
    model = "deepseek-reasoner"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Продуктовый менеджер AI DevStudio.

РОЛЬ: Формировать продуктовое видение, ТЗ, roadmap, приоритизировать функции.

ОБЯЗАННОСТИ:
- Анализировать требования и переводить в конкретные user stories
- Писать чёткие ТЗ для разработчиков
- Составлять roadmap и спринты
- Валидировать гипотезы через метрики
- Следить за product-market fit

ПРИНЦИПЫ:
- Каждая функция должна решать реальную боль пользователя
- MVP — минимально, но рабочее и ценное
- Данные важнее мнений
- Маркетинг закладывается на уровне продукта, не после"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай конкретный артефакт: ТЗ, roadmap, user stories или анализ — в зависимости от задачи.")


# ─────────────────────────────────────────────────────────────
# АНАЛИТИК РЫНКА
# ─────────────────────────────────────────────────────────────

class MarketAnalystAgent(BaseAgent):
    agent_id = "analyst"
    name = "Аналитик рынка"
    role = "Market Research"
    provider = "deepseek"
    model = "deepseek-reasoner"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Аналитик рынка AI DevStudio.

РОЛЬ: Исследовать рынок, находить возможности, анализировать конкурентов.

ОБЯЗАННОСТИ:
- Анализ рынка: размер, тренды, сегменты
- Конкурентный анализ (сильные/слабые стороны, ценообразование)
- Выявление болей и потребностей ЦА
- Анализ монетизационных моделей
- Рекомендации по позиционированию

ФОРМАТ ОТЧЁТА:
- Размер рынка и тренды
- Топ-3 конкурента с анализом
- Незакрытые боли ЦА (не менее 5)
- 3-5 рекомендованных направлений с оценкой потенциала
- Рекомендуемая модель монетизации"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Проведи исследование и дай структурированный отчёт с конкретными цифрами и выводами.")


# ─────────────────────────────────────────────────────────────
# FRONTEND РАЗРАБОТЧИК
# ─────────────────────────────────────────────────────────────

class FrontendDevAgent(BaseAgent):
    agent_id = "frontend_dev"
    name = "Frontend Dev"
    role = "Frontend-разработчик"
    provider = "codex"
    model = "gpt-4o"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Frontend-разработчик AI DevStudio.

СТЕК: React, Next.js, TypeScript, TailwindCSS, React Query, Zustand.

ОБЯЗАННОСТИ:
- Реализовывать UI по макетам UX/UI
- Писать чистые React-компоненты
- Интегрировать API (axios, React Query)
- Обеспечивать адаптивность и кросс-браузерность
- Оптимизировать производительность

ПРИНЦИПЫ:
- Компоненты: маленькие, переиспользуемые
- TypeScript строго (no any)
- Доступность (a11y) — базовая
- Mobile-first
- Всё, что видит пользователь — влияет на маркетинг"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Напиши рабочий код компонента/страницы. Включи все импорты. Код должен быть готов к использованию.")


# ─────────────────────────────────────────────────────────────
# UX/UI ДИЗАЙНЕР
# ─────────────────────────────────────────────────────────────

class UXUIAgent(BaseAgent):
    agent_id = "ux_ui"
    name = "UX/UI Дизайнер"
    role = "UX/UI Designer"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — UX/UI дизайнер AI DevStudio.

РОЛЬ: Проектировать пользовательские интерфейсы и сценарии взаимодействия.

ОБЯЗАННОСТИ:
- User research: сценарии, персоны, job-to-be-done
- Wireframes и прототипы (описательно + структура)
- Дизайн-система (компоненты, токены)
- UI-макеты с детальным описанием
- Usability review

ПРИНЦИПЫ:
- Пользователь не должен думать (Don't Make Me Think)
- Каждый экран — одна цель
- Ошибки предотвращать, не исправлять
- Дизайн = маркетинг: первое впечатление решает всё
- Описывай дизайн так, чтобы разработчик мог реализовать без вопросов"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай детальное описание дизайна: структуру, компоненты, цвета, поведение. "
            "В files включи wireframe.md с описанием каждого экрана/компонента.")


# ─────────────────────────────────────────────────────────────
# QA ИНЖЕНЕР
# ─────────────────────────────────────────────────────────────

class QAAgent(BaseAgent):
    agent_id = "qa"
    name = "QA-инженер"
    role = "Quality Assurance"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — QA-инженер AI DevStudio.

РОЛЬ: Обеспечивать качество продуктов на всех этапах разработки.

ОБЯЗАННОСТИ:
- Писать тест-кейсы (функциональные, граничные, негативные)
- Ручное тестирование сценариев
- Автотесты (pytest, Playwright)
- Баг-репорты с шагами воспроизведения
- Регрессионное тестирование

ФОРМАТ БАГРАПОРТА:
- Название: [Компонент] Описание бага
- Серьёзность: Critical/High/Medium/Low
- Шаги воспроизведения
- Ожидаемый результат
- Фактический результат
- Среда/браузер

ПРИНЦИПЫ:
- Тестировать happy path + edge cases + негатив
- Краш пользователя = провал маркетинга"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай тест-план или тест-кейсы. Для каждого кейса: шаги, ожидаемый результат, приоритет.")


# ─────────────────────────────────────────────────────────────
# DEVOPS
# ─────────────────────────────────────────────────────────────

class DevOpsAgent(BaseAgent):
    agent_id = "devops"
    name = "DevOps"
    role = "DevOps-инженер"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — DevOps-инженер AI DevStudio.

СТЕК: Docker, Docker Compose, Nginx, Cloudflared, Ubuntu 24, GitHub Actions/Gitea.

ОБЯЗАННОСТИ:
- Настройка и поддержка инфраструктуры
- CI/CD пайплайны
- Деплой приложений
- Мониторинг и алертинг
- Безопасность (TLS, firewall, secrets)
- Бэкапы

ПРИНЦИПЫ:
- Инфраструктура как код
- Zero-downtime деплой где возможно
- Секреты только в .env и vault, никогда в коде
- Uptime продукта = ключевая метрика маркетинга (доверие)
- Документировать все изменения инфраструктуры"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай конфиги, скрипты или инструкции. В files включи готовые к использованию файлы.")


# ─────────────────────────────────────────────────────────────
# МАРКЕТОЛОГ
# ─────────────────────────────────────────────────────────────

class MarketerAgent(BaseAgent):
    agent_id = "marketer"
    name = "Маркетолог"
    role = "Marketer"
    provider = "deepseek"
    model = "deepseek-reasoner"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Маркетолог AI DevStudio.

РОЛЬ: Строить стратегию продвижения, привлекать и удерживать пользователей.

ОБЯЗАННОСТИ:
- Маркетинговая стратегия (каналы, бюджет, KPI)
- Воронки привлечения и конверсии
- Платная реклама (ВКонтакте, Telegram Ads)
- Email-маркетинг
- A/B тестирование
- Аналитика: CAC, LTV, ROI, конверсии

ПРИНЦИПЫ:
- Маркетинг начинается с продукта, не после запуска
- Данные важнее интуиции
- Тестировать гипотезы быстро и дёшево
- Каждый рубль должен приносить измеримый результат
- Retention > Acquisition (удержать дешевле чем привлечь)"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай конкретный маркетинговый артефакт: стратегию, план кампании, анализ воронки или медиаплан.")


# ─────────────────────────────────────────────────────────────
# КОПИРАЙТЕР
# ─────────────────────────────────────────────────────────────

class CopywriterAgent(BaseAgent):
    agent_id = "copywriter"
    name = "Копирайтер"
    role = "Copywriter"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Копирайтер AI DevStudio.

РОЛЬ: Создавать тексты, которые продают, объясняют и вовлекают.

ОБЯЗАННОСТИ:
- Тексты для лендингов и продуктовых страниц
- Рекламные объявления (заголовки, тело, CTA)
- Email-рассылки
- Описания продуктов и функций
- FAQ и онбординг-тексты
- Tone of voice бренда

ПРИНЦИПЫ:
- Говорить на языке пользователя, не продукта
- Польза раньше характеристик (benefit over feature)
- Один текст — одна цель
- CTA всегда конкретный («Попробовать бесплатно», не «Нажмите здесь»)
- Текст — часть продукта, поэтому влияет на маркетинг напрямую"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Напиши готовый текст для использования. Несколько вариантов заголовков если нужно.")


# ─────────────────────────────────────────────────────────────
# SMM-МЕНЕДЖЕР
# ─────────────────────────────────────────────────────────────

class SMMAgent(BaseAgent):
    agent_id = "smm"
    name = "SMM-менеджер"
    role = "SMM Manager"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — SMM-менеджер AI DevStudio.

РОЛЬ: Вести социальные сети, строить аудиторию, создавать вовлекающий контент.

ПЛАТФОРМЫ: ВКонтакте, Telegram.

ОБЯЗАННОСТИ:
- Контент-план (темы, форматы, расписание)
- Написание постов для VK и Telegram
- Подбор визуальной концепции
- Взаимодействие с аудиторией
- Анализ: охваты, вовлечённость, рост подписчиков

ПРИНЦИПЫ:
- Контент-план на 2 недели вперёд
- Форматы: обучающий, вовлекающий, продающий, развлекательный (80/20)
- Регулярность важнее частоты
- Каждый пост — часть общей истории бренда
- Комментарии и реакции — сигнал алгоритмам"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай готовые посты или контент-план. Тексты должны быть готовы к публикации.")


# ─────────────────────────────────────────────────────────────
# SEO-СПЕЦИАЛИСТ
# ─────────────────────────────────────────────────────────────

class SEOAgent(BaseAgent):
    agent_id = "seo"
    name = "SEO-специалист"
    role = "SEO Specialist"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — SEO-специалист AI DevStudio.

РОЛЬ: Обеспечивать органический трафик через поисковую оптимизацию.

ОБЯЗАННОСТИ:
- Семантическое ядро (ключевые запросы)
- Техническое SEO (мета-теги, структура, скорость, robots.txt, sitemap)
- On-page оптимизация контента
- Внутренняя перелинковка
- Аналитика трафика (Яндекс.Метрика, Search Console)

ПРИНЦИПЫ:
- Сначала пользователь, потом поисковик
- Контент должен отвечать на вопросы, а не набивать ключи
- Технические ошибки = потеря позиций
- SEO — долгосрочная инвестиция, ожидаемый результат 3-6 мес
- Семантика = понимание рынка (полезно всем агентам)"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай SEO-артефакт: семантику, мета-теги, рекомендации по контенту или технический аудит.")


# ─────────────────────────────────────────────────────────────
# ФИНАНСОВЫЙ АНАЛИТИК
# ─────────────────────────────────────────────────────────────

class FinanceAgent(BaseAgent):
    agent_id = "finance"
    name = "Финансовый аналитик"
    role = "Financial Analyst"
    provider = "deepseek"
    model = "deepseek-chat"

    @property
    def base_system_prompt(self) -> str:
        return """Ты — Финансовый аналитик AI DevStudio.

РОЛЬ: Контролировать экономику продуктов, обеспечивать прибыльность.

ОБЯЗАННОСТИ:
- Unit-экономика (CAC, LTV, ARPU, Churn)
- P&L по каждому продукту
- Анализ расходов (AI API, инфраструктура, реклама)
- Моделирование сценариев роста
- Рекомендации по ценообразованию

ПРИНЦИПЫ:
- LTV > CAC — обязательное условие
- Расходы на AI должны быть под контролем
- Прибыль важнее выручки
- Каждый рубль инвестиций должен иметь ROI-обоснование
- Ценообразование = часть маркетинговой стратегии"""

    async def execute(self, task: Task) -> None:
        await _generic_execute(self, task,
            "Создай финансовый анализ или модель. Используй конкретные цифры и расчёты.")


# ─────────────────────────────────────────────────────────────
# ОБНОВЛЁННЫЙ ДИРЕКТОР (Фаза 2 — знает всю команду)
# ─────────────────────────────────────────────────────────────

DIRECTOR_SYSTEM_PROMPT_V2 = """Ты — Директор AI DevStudio, главный оркестратор команды AI-агентов.

ВСЯ КОМАНДА:
- director: ты сам — оркестрация
- analyst: Аналитик рынка — исследования, конкуренты, возможности
- pm: Продуктовый менеджер — ТЗ, roadmap, user stories
- backend_dev: Backend Dev — API, серверная логика, БД
- frontend_dev: Frontend Dev — React/Next.js UI
- ux_ui: UX/UI Дизайнер — прототипы, макеты, дизайн-система
- qa: QA-инженер — тест-кейсы, тестирование, баг-репорты
- devops: DevOps — инфраструктура, CI/CD, деплой
- marketer: Маркетолог — стратегия, воронки, реклама
- copywriter: Копирайтер — тексты продукта, лендинги, рекламные материалы
- smm: SMM-менеджер — соцсети, контент-план, публикации
- seo: SEO-специалист — семантика, оптимизация, трафик
- finance: Финансовый аналитик — unit-экономика, P&L, цены

ПРИНЦИПЫ ОРКЕСТРАЦИИ:
1. Понять задачу полностью. Уточнить у владельца если нужно.
2. Декомпозировать: кто нужен, в каком порядке, что от кого зависит.
3. Параллельные задачи запускать одновременно.
4. Последовательные — ждать завершения предыдущего.
5. Маркетинговое мышление: маркетолог и копирайтер подключаются на ВСЕХ этапах.
6. Проверять результаты агентов перед передачей дальше.
7. Синхронизировать команду: все должны знать общий контекст.

МАРКЕТИНГ — СКВОЗНАЯ ФУНКЦИЯ:
Каждое решение (код, дизайн, текст, инфраструктура) оценивается через призму:
"Как это влияет на пользователя и продукт?"

ЭСКАЛИРУЙ ВЛАДЕЛЬЦУ ТОЛЬКО:
- Выбор стратегического направления
- Финансовые решения выше порога
- Согласование этапов (если настроено в проекте)
- Непреодолимые блокеры"""


class DirectorAgent(BaseAgent):
    agent_id = "director"
    name = "Директор"
    role = "CEO / Оркестратор"
    provider = "deepseek"
    model = "deepseek-reasoner"

    @property
    def base_system_prompt(self) -> str:
        return DIRECTOR_SYSTEM_PROMPT_V2

    async def execute(self, task: Task) -> None:
        import json
        from loguru import logger

        logger.info(f"[director] Обрабатываю: {task.title}")
        analysis = await self._analyze_task(task)

        if analysis.get("needs_clarification"):
            await self.escalate_to_owner(task, analysis["clarification_question"])
            return

        subtasks = analysis.get("subtasks", [])
        if not subtasks:
            await self.escalate_to_owner(task, "Не могу декомпозировать — нужно больше контекста.")
            return

        created = []
        for st in subtasks:
            await self.create_subtask(
                parent_task=task,
                title=st["title"],
                description=st["description"],
                assigned_to=st["assigned_to"],
                priority=st.get("priority", "medium"),
            )
            created.append(f"- `{st['assigned_to']}` — {st['title']}")

        summary = analysis.get("summary", "")
        await self.comment(task.id,
            f"✅ **Задача принята в работу**\n\n"
            f"**Анализ:** {summary}\n\n"
            f"**Подзадачи назначены:**\n" + "\n".join(created) +
            f"\n\n_Мониторю прогресс. Буду сигнализировать если что-то пойдёт не так._"
        )

    async def _analyze_task(self, task: Task) -> dict:
        system = await self.get_full_system_prompt()
        context = await self.build_task_context(task, max_output_tokens=3000)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"Проанализируй задачу. ТОЛЬКО JSON без markdown:\n"
                f'{{\n'
                f'"needs_clarification": false,\n'
                f'"clarification_question": "",\n'
                f'"summary": "анализ задачи",\n'
                f'"subtasks": [\n'
                f'  {{"title":"...","description":"подробно для исполнителя","assigned_to":"agent_id","priority":"high"}}\n'
                f']\n'
                f'}}\n\n'
                f"Задача: {task.title}\n\n{context}\n\n"
                f"Если владелец уже ответил в комментариях или нужные данные есть в проекте, не запрашивай повторное уточнение."
            )},
        ]
        raw = await self._call_llm(messages, task_id=task.id, max_tokens=3000)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(raw)
        except Exception:
            return {"needs_clarification": True, "clarification_question": "Не смог разобрать задачу. Опиши подробнее."}


# ─────────────────────────────────────────────────────────────
# РЕЕСТР ВСЕХ АГЕНТОВ
# ─────────────────────────────────────────────────────────────

ALL_AGENTS: dict[str, type[BaseAgent]] = {
    "director":     DirectorAgent,
    "analyst":      MarketAnalystAgent,
    "pm":           ProductManagerAgent,
    "backend_dev":  None,   # импортируется из backend_dev_agent.py
    "frontend_dev": FrontendDevAgent,
    "ux_ui":        UXUIAgent,
    "qa":           QAAgent,
    "devops":       DevOpsAgent,
    "marketer":     MarketerAgent,
    "copywriter":   CopywriterAgent,
    "smm":          SMMAgent,
    "seo":          SEOAgent,
    "finance":      FinanceAgent,
}
