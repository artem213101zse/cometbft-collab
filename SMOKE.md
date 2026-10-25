# Результаты smoke-теста (25.10.2026, Linux, Docker 29)
`docker compose up --build -d` → 9 контейнеров Up, init Exited(0).

`sh scripts/smoke.sh`:
- insert "Hello world" → height 15; insert ", dear" @5 → height 16
- две **параллельные** вставки `[A]` и `[B]` @0 → обе в блоке 17
- delete pos 0 len 3 → height 18
- `/document?node=0..3` → у всех `"[A]Hello, dear world"`, version=5
- `/status` → все 4 ноды height 18, одинаковый app_hash `FFA075C5…08C0AE`

Отказ:
- `docker compose stop node3`, insert "(без node3) " → ok, height 33
- дополнительно stop node0 (2 из 4 down) → insert "x" не подтвердился за 20 с (нет кворума)
- `docker compose start node0 node3` → через 15 с у всех 4 нод:
  `"x(без node3) [A]Hello, dear world"`, version=7, height 41, одинаковый app_hash `1B2B7323…2833DB`.
