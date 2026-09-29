# CLAUDE.md

Реконструкция мобильной игры RJ Games «Under Fire: Invasion» (v1.3.12, 2016, движок Inferno
на cocos2d-x) для браузера. Обзор, форматы и roadmap — в README.md, порядок работы —
в CONTRIBUTING.md, план — в milestones и issues на GitHub. Стек клиента — PixiJS 8 + TypeScript
+ Vite (docs/engine-decision.md, исследование — docs/research/). Платформа: сначала браузеры на
компьютере, телефоны — позже.

## Правила работы

- В `main` — только через PR: ветка → коммит → PR с описанием → squash-merge → удаление ветки.
  `main` защищена: прямой push отклоняется, слияние — только после зелёного CI (`lint-test`).
- Одна логическая правка — один PR. Ветки — kebab-case по сути изменения (`etc1-decoder`).
- Коммиты и заголовки PR — по-русски, в формате `Область: что сделано`. Описание PR — что
  сделано, зачем, как проверено.
- Слияние: `gh pr merge N --squash --delete-branch`.
- Документация, комментарии и общение — по-русски.

## Команды

```bash
pip install -r requirements-dev.txt              # зависимости + pytest и ruff
python3 tools/extract_xapk.py <путь к XAPK>     # оригинал → raw/ (--force — перезаписать)
python3 tools/parse_config.py                    # raw/ → data/*.json
python3 tools/build_assets.py                    # raw/ → assets/ (весь конвейер ассетов)
python3 tools/fetch_assets.py [--only json]      # без raw/: готовый assets/ из релиза
ruff check . && pytest -q                        # то же, что проверяет CI (Python)
cd web && npm install && npm run dev             # клиент: http://localhost:5173
npm run typecheck && npm test && npm run build   # то же, что проверяет CI (web/)
```

## Данные

- `raw/` — распакованный оригинал, не в git. Без него работают только тесты.
- `data/` — в git, но руками не правится: только пересборкой через `tools/parse_config.py`.
  Если разбор меняется осознанно — обновить эталонные итоги в `tests/test_data.py`.
- `assets/` — ассеты для браузера; не в git. Без `raw/` (например, в облачной сессии) их берут
  из релиза `assets-v1.3.12`: `python3 tools/fetch_assets.py`.
- Код игры (`lib/armeabi/libinferno.so`) — только внутри APK, в `raw/` не распаковывается.
- Большие файлы (`data/config.json` — 14 МБ, `raw/`) читать скриптами, а не целиком.

## Код

- Инструменты — Python 3.12 в `tools/`, по скрипту на шаг. Вверху docstring: что делает,
  вход, выход, как запускать.
- Тесты — в `tests/`, без файлов игры: синтетические данные на лету (`tmp_path`).
- Клиент — TypeScript в `web/src`, PixiJS закреплён точной версией. Геометрию узлов cocos2d-x
  повторять формулой (`web/src/engine/cocos.ts`), а не подгонкой; тесты — Vitest рядом с кодом.
