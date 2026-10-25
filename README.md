# Совместное редактирование текста на CometBFT (FastAPI + Docker)

## Что это
Backend «общего блокнота»: несколько клиентов правят один plain-text документ (без жирного/курсива), и у всех получается одинаковый текст.

**CometBFT** — движок *консенсуса* (не нейросеть!). Несколько серверов (**нод**) голосуют за порядок транзакций и собирают их в блоки. Каждая нода применяет блоки в одном и том же порядке, поэтому состояние везде одинаковое. Алгоритм BFT выдерживает `f` сломанных/злонамеренных нод при `n ≥ 3f+1` → 4 ноды переживают падение 1.

Отдельного UI «как Word» нет: текст правится через HTTP API. Удобнее всего через встроенный Swagger FastAPI.

---

## Быстрый старт

Нужен **Docker Desktop** (должен быть запущен).

```bash
cd cometbft-collab
docker compose up --build -d
docker compose ps
```

Подожди ~20 секунд, пока все контейнеры станут healthy / Up. Потом открой в браузере:

**http://localhost:8000/docs**

Остановить: `docker compose down`  
С нуля (новый пустой документ): `docker compose down -v`

**Порты:** API `8000`; RPC нод `26657` (node0), `26667`, `26677`, `26687` (node1..3).

---

## Как пользоваться (Swagger)

1. Открой **http://localhost:8000/docs**
2. Разверни нужный метод → **Try it out** → заполни тело → **Execute**

### Посмотреть документ
- `GET /document`
- Ответ: `text` (текущая строка), `height` (высота блока), `app_hash` (sha256 текста)
- Параметр `node` (0–3): спросить конкретную ноду. Без параметра — любая доступная.

### Вставить текст
- `POST /insert`
```json
{"pos": 0, "text": "Привет, мир"}
```
- `pos` — позиция вставки (0 = в начало; если больше длины — в конец)
- После успеха снова вызови `GET /document` — должен появиться текст

### Вставить в середину
Документ сейчас `Привет, мир` (длина 11). Вставим слово после «Привет,» (позиция 7):
```json
{"pos": 7, "text": "дорогой "}
```
Получится примерно: `Привет, дорогой мир`

### Удалить кусок
- `POST /delete`
```json
{"pos": 0, "length": 7}
```
Удалит 7 символов начиная с позиции 0.

### Проверить, что все ноды согласны
1. `GET /status` — высоты и `app_hash` у всех четырёх нод  
2. Или четыре раза `GET /document?node=0` … `node=3`  
Текст и `app_hash` должны совпасть — это и есть доказательство консенсуса.

### Здоровье
- `GET /health` — API живо и видит хотя бы одну ноду

---

## То же самое через curl

В PowerShell лучше `curl.exe` (не алиас `curl`):

```bash
curl.exe -X POST http://localhost:8000/insert -H "Content-Type: application/json" -d "{\"pos\":0,\"text\":\"Hello world\"}"
curl.exe -X POST http://localhost:8000/insert -H "Content-Type: application/json" -d "{\"pos\":5,\"text\":\", dear\"}"
curl.exe http://localhost:8000/document
curl.exe "http://localhost:8000/document?node=2"
curl.exe http://localhost:8000/status
curl.exe -X POST http://localhost:8000/delete -H "Content-Type: application/json" -d "{\"pos\":0,\"length\":6}"
```

Готовый сценарий: `sh scripts/smoke.sh` (Linux / macOS / Git Bash / WSL).

---

## Демо на защите: «упала нода»

```bash
docker compose ps
docker compose stop node3
# снова POST /insert — должно пройти (3 из 4 > 2/3 голосов)
curl.exe http://localhost:8000/document
docker compose start node3
# подожди несколько секунд — node3 догонит блоки
curl.exe "http://localhost:8000/document?node=3"
```

Если остановить **2 ноды из 4** — консенсус встаёт (нет 2/3 голосов), insert будет висеть/таймаут. После запуска нод транзакция из mempool всё равно применится.

Имена сервисов в compose: `node0`…`node3`, `abci0`…`abci3`, `api`. Смотри `docker compose ps`.

---

## Архитектура

```
клиент (Swagger/curl) ─HTTP─> api (FastAPI :8000)
                                 │ broadcast_tx_commit / abci_query (RPC :26657)
              ┌──────────┬───────┴──┬──────────┐
            node0      node1      node2      node3   (CometBFT v0.34.35, консенсус)
              │ABCI      │          │          │
            abci0      abci1      abci2      abci3   (Python, состояние = одна строка)
```

- `abci/app.py` — ABCI-приложение (`abci==0.8.3`):
  - `check_tx` — проверка формата до mempool;
  - `deliver_tx` — применяет insert/delete к строке (детерминированно);
  - `commit` — `app_hash = sha256(документ)`;
  - `query` `/document` — вернуть текст.
- `api/main.py` — HTTP → транзакции. Если node0 недоступна, пробует node1..3.
- `scripts/init.sh` — один раз создаёт 4-валидаторный testnet (`cometbft testnet --v 4`), общий genesis, peers, `proxy_app = tcp://abciN:26658`.

Транзакция = JSON в UTF-8:
```json
{"op":"insert","pos":0,"text":"hi"}
{"op":"delete","pos":0,"len":2}
```

Конфликты «двое пишут одновременно» решает консенсус: обе транзакции попадают в блок в одном порядке на всех нодах.

**Почему CometBFT 0.34, а не 0.38:** в 0.38 ABCI++ (`FinalizeBlock`), а py-abci реализует протокол 0.34 (`DeliverTx`). Для Python это самый простой рабочий вариант.

Состояние в памяти. При перезапуске ABCI сообщает высоту 0, CometBFT проигрывает все блоки из своей БД → документ восстанавливается (журнал событий).

---

## Вопросы на защите

- **Зачем CometBFT?** Одинаковый порядок операций на всех нодах (state machine replication).
- **Что такое нода?** Один экземпляр CometBFT + своё ABCI-приложение. Не «обучение модели».
- **Что такое ABCI?** Интерфейс между консенсусом и логикой приложения по TCP `:26658`. CometBFT не знает про «документ», он доставляет байты.
- **Почему 4 ноды?** BFT: `n ≥ 3f+1`, для `f=1` нужно 4. Блок принимается при > 2/3 голосов.
- **Как решаются конфликты?** Порядок задаёт консенсус. Позиции относительно состояния на момент применения. Проще OT/CRDT; при одновременных правках позиция может «сдвинуться» — для лабы ок.
- **Детерминизм?** `deliver_tx` зависит только от текущей строки и tx (без `time`/`random`). Проверка — одинаковый `app_hash`.
- **CheckTx vs DeliverTx?** CheckTx — фильтр mempool; DeliverTx — реальное применение в блоке.
- **broadcast_tx_commit?** Ждёт включения в блок и возвращает высоту.
- **Где UI?** Не нужен по заданию; есть Swagger. Простую HTML-страницу можно прикрутить к FastAPI позже.
- **Ограничения:** без авторизации, состояние в RAM (восстановление через replay), одна Docker-сеть.

---

## Структура репозитория

```
cometbft-collab/
  docker-compose.yml   # init + 4 abci + 4 node + api
  abci/                # логика документа (ABCI)
  api/                 # FastAPI
  scripts/init.sh      # генерация testnet
  scripts/smoke.sh     # автопроверка
  SMOKE.md             # зафиксированный прогон
  README.md
```

Проверенный прогон: см. `SMOKE.md`.
