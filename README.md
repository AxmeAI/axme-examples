# AXME Examples

Примеры использования AXME — полный набор сценариев для всех delivery bindings, human runtime, internal runtime, и durability-сценариев.

## Быстрый старт

```bash
# 1. Установи CLI
pip install axme

# 2. Войди в аккаунт
axme login

# 3. Запусти сценарий
axme scenarios apply examples/delivery/stream/scenario.json --watch
```

## Структура

```
axme-examples/
└── examples/
    ├── delivery/
    │   ├── stream/       ← SSE listen() — основной native binding
    │   ├── poll/         ← polling loop
    │   ├── http/         ← AXME пушит на HTTP endpoint (managed delivery)
    │   └── inbox/        ← reply_to inbox (disconnect-safe)
    ├── human/
    │   ├── email/        ← email magic link — one-click approve
    │   ├── cli/          ← axme tasks list + axme tasks approve
    │   └── form/         ← structured form_schema + task_result validation
    ├── internal/
    │   ├── delay/        ← delay built-in — авто-продвижение после паузы
    │   ├── notification/ ← notification built-in — email + inbox side effect
    │   └── escalation/   ← reminder + escalation chain
    ├── durability/
    │   ├── retry-failure/        ← агент недоступен → retry → FAILED
    │   ├── timeout/              ← deadline_at → TIMED_OUT
    │   └── reminder-escalation/  ← human SLA breach → reminders → escalation
    └── full/
        └── multi-agent/          ← stream + http + internal + human в одном workflow
```

## Запуск сценариев

Каждый сценарий — папка с `scenario.json` и `agent.py`.

```bash
# Запустить сценарий (создаёт агентов, отправляет intent, следит за lifecycle)
axme scenarios apply examples/delivery/stream/scenario.json --watch

# Только создать/обновить агентов без отправки intent
axme scenarios apply examples/delivery/stream/scenario.json

# Запустить агента вручную (для stream/poll/http)
python examples/delivery/stream/agent.py
```

## Сценарии

### Группа A — Delivery Bindings

| Папка | Что тестирует | Команда запуска |
|---|---|---|
| `delivery/stream` | Агент через SSE `listen()` | `axme scenarios apply examples/delivery/stream/scenario.json --watch` |
| `delivery/poll` | Агент через polling loop | `axme scenarios apply examples/delivery/poll/scenario.json --watch` |
| `delivery/http` | AXME пушит на HTTP endpoint | `axme scenarios apply examples/delivery/http/scenario.json --watch` |
| `delivery/inbox` | Initiator использует reply_to inbox | `axme scenarios apply examples/delivery/inbox/scenario.json --watch` |

### Группа B — Human Runtime

| Папка | Что тестирует |
|---|---|
| `human/email` | Email magic link — one-click approve |
| `human/cli` | `axme tasks list` + `axme tasks approve` |
| `human/form` | Structured form_schema + task_result validation |

### Группа C — Internal Runtime

| Папка | Что тестирует |
|---|---|
| `internal/delay` | `delay` built-in — авто-продвижение после паузы |
| `internal/notification` | `notification` built-in — email + inbox side effect |
| `internal/escalation` | `reminder` + escalation chain |

### Группа D — Durability

| Папка | Что тестирует |
|---|---|
| `durability/retry-failure` | Агент недоступен → retry → FAILED + `intent.delivery_failed` |
| `durability/timeout` | `deadline_at` → `TIMED_OUT` + `intent.timed_out` webhook |
| `durability/reminder-escalation` | Human SLA breach → reminders → escalation |

### Группа E — Полные сценарии

| Папка | Что тестирует |
|---|---|
| `full/multi-agent` | stream + http + internal notification + human в одном workflow |

## Структура сценария

Каждый пример состоит из двух файлов:

**`scenario.json`** — декларативное описание: агенты, workflow, intent:

```json
{
  "scenario_id": "my.scenario.v1",
  "title": "My scenario",
  "agents": [
    {
      "role": "processor",
      "address": "my-processor-agent",
      "display_name": "My Processor",
      "delivery_mode": "stream",
      "create_if_missing": true
    }
  ],
  "workflow": {
    "steps": [
      {
        "step_id": "process",
        "tool_id": "tool.agent.task.v1",
        "assigned_to": "processor",
        "step_deadline_seconds": 60
      }
    ]
  },
  "intent": {
    "type": "intent.my.type.v1",
    "payload": { "key": "value" },
    "max_delivery_attempts": 3
  }
}
```

**`agent.py`** — агент, который обрабатывает intent:

```python
import axme

client = axme.Client()

for intent in client.listen():
    print(f"Received: {intent.payload}")
    intent.resume(status="COMPLETED", result={"ok": True})
```

## `delivery_mode` агента

| Значение | Как получает intent |
|---|---|
| `stream` | SSE `listen()` — агент держит соединение, события приходят в реальном времени |
| `poll` | Polling loop — агент периодически вызывает `poll()` |
| `http` | AXME POSTит на `callback_url` — агент запускает HTTP-сервер |
| `inbox` | Initiator передаёт `reply_to`, исполнитель отвечает через inbox |
