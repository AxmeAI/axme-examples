# Axme Examples

Примеры использования AXME — полный набор сценариев для всех delivery bindings, human runtime, internal runtime, и durability-сценариев.

## Быстрый старт

```bash
# 1. Установи SDK
pip install axme

# 2. Войди в аккаунт
axme login

# 3. Запусти интерактивный picker
python run.py

# Или сразу конкретный сценарий
python run.py scenarios/delivery/01-stream.json
```

## Структура

```
axme-examples/
├── runner/           ← общая инфраструктура (один раз, не трогать)
│   ├── auth.py       ← загрузка api_key / actor_token
│   ├── bundle.py     ← строит ScenarioBundleRequest из JSON-спека
│   ├── keys.py       ← создание и кэш API ключей агентов
│   ├── render.py     ← весь вывод в терминал
│   ├── agents.py     ← AgentHandler per delivery binding
│   └── runner.py     ← ScenarioRunner — оркестратор
│
├── scenarios/        ← сами примеры (только JSON, без кода)
│   ├── delivery/     ← Группа A: delivery bindings
│   ├── human/        ← Группа B: human as runtime
│   ├── internal/     ← Группа C: internal runtime types
│   ├── durability/   ← Группа D: retry, timeout, reminders
│   └── full/         ← Группа E: комплексные production-сценарии
│
├── examples/         ← готовые к запуску примеры (используют runner/)
│   └── approval-workflow/python/main.py
│
└── run.py            ← точка входа
```

## Сценарии

### Группа A — Delivery Bindings
| Файл | Что тестирует |
|---|---|
| `delivery/01-stream.json` | Агент через SSE `listen()` — основной native binding |
| `delivery/02-poll.json` | Агент через polling loop |
| `delivery/03-http.json` | AXME пушит на HTTP endpoint агента (managed delivery) |
| `delivery/04-inbox-reply.json` | Initiator использует reply_to inbox (disconnect-safe) |

### Группа B — Human Runtime
| Файл | Что тестирует |
|---|---|
| `human/05-human-email.json` | Email magic link — one-click approve |
| `human/06-human-cli.json` | `axme tasks list` + `axme tasks approve` |
| `human/07-human-form.json` | Structured form_schema + task_result validation |

### Группа C — Internal Runtime
| Файл | Что тестирует |
|---|---|
| `internal/08-delay.json` | `delay` built-in — авто-продвижение после паузы |
| `internal/09-notification.json` | `notification` built-in — email + inbox side effect |
| `internal/10-escalation.json` | `reminder` + escalation chain |

### Группа D — Durability
| Файл | Что тестирует |
|---|---|
| `durability/11-retry-failure.json` | Агент недоступен → retry → FAILED + `intent.delivery_failed` |
| `durability/12-timeout.json` | `deadline_at` → `TIMED_OUT` + `intent.timed_out` webhook |
| `durability/13-reminder-escalation.json` | Human SLA breach → reminders → escalation |

### Группа E — Полные сценарии
| Файл | Что тестирует |
|---|---|
| `full/00-approval-workflow.json` | 2 auto agents + human CAB sign-off (классический) |
| `full/14-full-workflow.json` | stream + http + internal notification + human в одном workflow |

## Создание нового сценария

Создай новый `.json` файл в нужной папке `scenarios/`. Никакого Python кода писать не нужно — runner берёт всё на себя.

Минимальная структура:
```json
{
  "scenario_id": "my.scenario.v1",
  "title": "My scenario",
  "agents": [
    {
      "role": "processor",
      "address": "my-processor-agent",
      "delivery_mode": "stream",
      "handler": { "type": "auto_complete", "delay_seconds": 1 }
    }
  ],
  "humans": [],
  "workflow_steps": [
    {
      "step_id": "process",
      "tool_id": "tool.approval.check_window",
      "assigned_to": "processor"
    }
  ],
  "intent": {
    "type": "intent.my.type.v1",
    "payload": { "key": "value" }
  },
  "durability": { "deadline_minutes": 10 }
}
```

### `delivery_mode` агента
| Значение | Как получает интент |
|---|---|
| `internal` | agent_core built-in (по умолчанию) |
| `stream` | SSE `listen()` — runner запускает StreamAgentHandler в потоке |
| `poll` | Polling loop — runner запускает PollAgentHandler в потоке |
| `http` | AXME POSTит на callback_url — runner запускает локальный HTTP-сервер |

### `handler.type` — поведение агента в примере
| Значение | Поведение |
|---|---|
| `auto_complete` | Ждёт `delay_seconds`, вызывает `resume_intent(COMPLETED)` |
| `auto_fail` | Ждёт `delay_seconds`, вызывает `resume_intent(FAILED)` |
| `no_op` | Получает, но не отвечает (для тестов timeout/retry) |
| `interactive` | Спрашивает пользователя в терминале |
| `human_cli_hint` | Печатает `axme tasks approve <id>`, ждёт Enter |

## Команды

```bash
python run.py                                      # интерактивный picker
python run.py scenarios/delivery/01-stream.json   # конкретный сценарий
python run.py --list                               # список всех сценариев
python run.py --validate scenarios/01-stream.json # валидация без запуска
SCENARIO=delivery/01-stream python run.py         # через env var
```
