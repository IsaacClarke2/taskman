# Instructions for Claude Code

Эта папка содержит инструкции для разработки проекта через Claude Code.

---

## Файлы

| Файл | Описание |
|------|----------|
| `DEVELOPMENT_INSTRUCTIONS.md` | **Главный файл.** Полная инструкция по разработке: порядок, код, примеры |
| `DEPLOYMENT.md` | **Деплой.** Скрипт установки, автовыбор портов, Nginx, SSL для corben.pro |
| `OAUTH_SETUP.md` | Пошаговая настройка OAuth для Google, Microsoft, Notion, Telegram |
| `APPLE_NOTES_SHORTCUT.md` | Как реализовать интеграцию с Apple Notes через Shortcuts |
| `DOCUMENTATION_LINKS.md` | Ссылки на документацию всех библиотек и API |

---

## Порядок чтения

1. **Сначала:** `DEVELOPMENT_INSTRUCTIONS.md` — понять что и как делать
2. **Перед OAuth:** `OAUTH_SETUP.md` — получить credentials
3. **При работе с Apple Notes:** `APPLE_NOTES_SHORTCUT.md`
4. **Для деплоя:** `DEPLOYMENT.md` — скрипт установки на сервер
5. **При проблемах:** `DOCUMENTATION_LINKS.md` — найти актуальную документацию

---

## Связанные файлы в проекте

- `/CLAUDE.md` — конфигурация для Claude Code
- `/docs/PROJECT_SPEC.md` — полные требования к продукту
- `/docs/ARCHITECTURE.md` — архитектура системы
- `/docs/PROJECT_STATUS.md` — текущий прогресс (обновлять!)
- `/docs/CHANGELOG.md` — история изменений

---

## Quick Start для Claude Code

```
1. Прочитай /CLAUDE.md
2. Прочитай /docs/PROJECT_SPEC.md  
3. Прочитай /instructions/DEVELOPMENT_INSTRUCTIONS.md
4. Начни с БЛОК 1: Database & Core API
5. После каждого блока обновляй /docs/PROJECT_STATUS.md
```

---

## Важные напоминания

- ✅ Всегда проверяй последние версии библиотек на PyPI/npm
- ✅ Все секреты только через environment variables
- ✅ Type hints обязательны
- ✅ Async/await для всех I/O операций
- ✅ Обработка ошибок для внешних API
- ✅ Логирование важных операций
- ❌ Никогда не коммить .env файлы
- ❌ Никогда не хардкодить токены и ключи
