<![CDATA[<div align="center">

```
╔════════════════════════════════════════╗
║         🤖  TG AI USERBOT             ║
║   Твой Telegram, управляемый AI        ║
╚════════════════════════════════════════╝
```

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Telethon](https://img.shields.io/badge/Telethon-1.24+-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-009CDE?style=flat-square&logo=telegram&logoColor=white)](https://aiogram.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**AI-юзербот, который отвечает на сообщения в Telegram от твоего имени.**  
Управляется через отдельный бот-администратор. Серверы не нужны — работает на твоей машине.

</div>

---

## ✨ Возможности

- 🤖 **AI-ответы** — через KiloCode API (есть бесплатные модели)
- 💬 **Умные триггеры** — отвечает в ЛС, на @упоминания и на реплаи к сообщениям бота
- 🎛️ **Управляющий бот** — настраивай всё без изменения кода
- 📊 **Статистика** — аптайм, кол-во AI-вызовов, счётчик ошибок
- 🚦 **Rate limiting** — кулдаун по чатам, чтобы бот не спамил
- 🔁 **Retry с backoff** — автоматические повторы при ошибках API
- 💾 **Персистентная история** — контекст разговора сохраняется при перезапуске
- 📝 **Ротируемые логи** — `bot.log` с автоматической ротацией (5 МБ × 3 файла)
- 🛡️ **Атомарная запись** — `storage.json` никогда не побьётся при сбое
- ⚡ **Graceful shutdown** — корректно обрабатывает SIGTERM (systemd дружественный)

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────┐
│                   main.py                        │
│  (логирование · валидация env · SIGTERM)         │
└──────────────┬──────────────┬───────────────────┘
               │              │
       ┌───────▼──────┐ ┌────▼──────────┐
       │  userbot.py  │ │control_bot.py │
       │  (Telethon)  │ │  (aiogram)    │
       │  твой акк    │ │  UI для админа│
       └───────┬──────┘ └────┬──────────┘
               │              │
       ┌───────▼──────────────▼──────────┐
       │         ai_service.py            │
       │  (KiloCode API · retry · история)│
       └───────────────┬─────────────────┘
                       │
              ┌────────▼────────┐
              │   storage.py    │
              │ (JSON · лок)    │
              └─────────────────┘
```

---

## 🚀 Быстрый старт

### 1. Клонируй репозиторий

```bash
git clone https://github.com/yourname/tg-ai-bot.git
cd tg-ai-bot
```

### 2. Установи зависимости

```bash
pip install -r requirements.txt
```

### 3. Настрой окружение

```bash
cp .envexample .env
nano .env  # заполни данные
```

### 4. Запусти

```bash
python main.py
```

При первом запуске Telethon попросит ввести код из SMS от Telegram.

---

## ⚙️ Конфигурация

Все переменные окружения — в файле `.env`:

| Переменная | Описание | Где взять |
|---|---|---|
| `TG_API_ID` | Telegram API ID | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TG_API_HASH` | Telegram API Hash | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TG_PHONE` | Твой номер телефона | Например `+79001234567` |
| `CONTROL_BOT_TOKEN` | Токен управляющего бота | [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | Твой Telegram user ID | [@userinfobot](https://t.me/userinfobot) |
| `KILOCODE_API_KEY` | API ключ KiloCode | [kilo.codes](https://kilo.codes) |
| `BOT_NAME` | Имя бота | Что угодно |

Настройки во время работы (управляются через бота, хранятся в `storage.json`):

| Настройка | По умолчанию | Описание |
|---|---|---|
| `enabled` | `true` | Главный переключатель |
| `reply_in_dm` | `true` | Отвечать в личных сообщениях |
| `reply_to_mentions` | `true` | Отвечать на @упоминания в группах |
| `reply_to_replies` | `true` | Отвечать на реплаи к сообщениям бота |
| `response_delay` | `1.5` | Задержка перед ответом (сек) |
| `rate_limit_seconds` | `3.0` | Минимальное время между ответами в одном чате |
| `ai_model` | `minimax/minimax-m2.5:free` | AI-модель |
| `ai_temperature` | `0.85` | Креативность ответов (0.0–2.0) |
| `ai_max_tokens` | `500` | Максимальная длина ответа |

---

## 🎛️ Команды управляющего бота

Запусти управляющий бот командой `/start`. Появится клавиатура:

| Кнопка | Действие |
|---|---|
| 📊 Статус | Полная информация о боте |
| ⚙️ Настройки | Переключатели, имя, задержка, модель |
| 💬 Чаты | Управление белым/чёрным списком |
| 🗑️ Очистить историю | Сбросить весь контекст AI |
| 🔄 Перезапустить AI | То же что очистить историю |
| 📈 Статистика | Аптайм + статистика API |

**Команды:**

```
/ping               — проверить что бот жив
/add_white <id>     — добавить чат в белый список
/del_white <id>     — убрать из белого списка
/add_black <id>     — добавить чат в чёрный список
/del_black <id>     — убрать из чёрного списка
/clear_white        — очистить весь белый список
/clear_chat <id>    — очистить историю одного чата
```

---

## 📦 Доступные AI-модели

Можно менять прямо из ⚙️ Настройки → 🤖 Сменить модель:

- `minimax/minimax-m2.5:free` *(по умолчанию)*
- `google/gemini-2.0-flash-exp:free`
- `meta-llama/llama-3.3-70b-instruct:free`
- `deepseek/deepseek-r1:free`
- `qwen/qwen3-235b-a22b:free`

Все модели работают через [KiloCode](https://kilo.codes) (бесплатный тир).

---

## 📁 Структура проекта

```
tg-ai-bot/
├── main.py           # Точка входа: логи, проверка env, SIGTERM
├── userbot.py        # Логика Telethon юзербота
├── control_bot.py    # Управляющий бот на aiogram
├── ai_service.py     # Клиент KiloCode API
├── storage.py        # Потокобезопасное JSON-хранилище
├── requirements.txt
├── .envexample       # Шаблон окружения
├── storage.json      # Настройки во время работы (создаётся автоматически)
├── histories.json    # Персистентная история чатов (создаётся автоматически)
└── bot.log           # Ротируемый лог-файл (создаётся автоматически)
```

---

## 🔧 Запуск как systemd-сервис

```ini
# /etc/systemd/system/tg-ai-bot.service
[Unit]
Description=TG AI Userbot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/tg-ai-bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable tg-ai-bot
sudo systemctl start tg-ai-bot
sudo journalctl -u tg-ai-bot -f
```

---

## ❓ FAQ

**Бот отвечает в каждом чате?**  
Нет. По умолчанию отвечает везде, но можно настроить белый список через управляющий бот.

**Как узнать ID чата?**  
Перешли любое сообщение из нужного чата боту [@userinfobot](https://t.me/userinfobot).

**История сохраняется при перезапуске?**  
Да, с этой версии — в `histories.json`.

**Можно запустить несколько аккаунтов?**  
Пока нет — один экземпляр, один аккаунт.

---

## 📄 Лицензия

MIT — делай что хочешь.
]]>
