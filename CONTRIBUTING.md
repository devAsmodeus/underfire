# Как вносить изменения

## Порядок работы

Все изменения попадают в `main` только через pull request; напрямую в `main` не пушим.

1. **Ветка** от свежего `main`, имя в kebab-case по сути изменения:
   ```bash
   git switch main && git pull --ff-only
   git switch -c etc1-decoder
   ```
2. **Коммиты**: одна логическая правка — один коммит. Сообщение по-русски в формате
   `Область: что сделано`, например `Ассеты: декодер ETC1 с альфой из нижней половины`.
3. **Pull request** с описанием: что сделано, зачем и как проверено.
   ```bash
   git push -u origin etc1-decoder
   gh pr create --title "Ассеты: декодер ETC1" --body-file pr.md
   ```
4. **Слияние** — только после зелёного CI (локально: `ruff check . && pytest -q`, для `web/` —
   `npm run typecheck && npm test && npm run build`) и только squash (остальные способы в
   репозитории выключены), чтобы в `main` была одна запись на PR:
   ```bash
   gh pr merge --squash --delete-branch
   ```
5. **Удаление ветки**: на GitHub она удаляется автоматически после слияния, а
   `--delete-branch` убирает и локальную.

## Что не коммитим

- Оригинал игры: `raw/`, `*.xapk`, `*.apk`, `*.obb`, текстуры `*.pkm` / `*.ccz`.
- Декодированные ассеты `assets/` — пока: как их публиковать, решим, когда станет ясен объём.
- Личные настройки: `.idea/`, `.claude/settings*.json`.

`data/` лежит в git, но руками его не правим — только пересборкой через `tools/parse_config.py`.

## Окружение

- Python 3 (проверено на 3.12) и зависимости: `pip install -r requirements.txt`, для проверок —
  `pip install -r requirements-dev.txt`.
- Node.js 22.12+ (в CI — 24) для клиента: `cd web && npm install`.
- Подготовка данных и запуск инструментов — в [README](README.md#подготовка-данных).
