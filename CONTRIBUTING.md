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
4. **Слияние** — только после зелёного CI (локально: `uv run ruff check . && uv run pytest -q`, для `web/` —
   `npm run typecheck && npm test && npm run build`) и только squash (остальные способы в
   репозитории выключены), чтобы в `main` была одна запись на PR:
   ```bash
   gh pr merge --squash --delete-branch
   ```
5. **Удаление ветки**: на GitHub она удаляется автоматически после слияния, а
   `--delete-branch` убирает и локальную.

## Что не коммитим

- Оригинал игры: `raw/`, `*.xapk`, `*.apk`, `*.obb`, текстуры `*.pkm` / `*.ccz`.
- Ассеты `assets/`: они публикуются архивами в релизе `assets-v1.3.12`
  (`tools/build_assets.py --pack`), а не в git.
- Личные настройки: `.idea/`, `.env` с адресом сервера для `web/deploy/deploy.sh` (образец — `.env.example`).

`data/` лежит в git, но руками его не правим — только пересборкой через `tools/parse_config.py`.
Если разбор меняется осознанно — обновить эталонные итоги в `tests/test_data.py`.

## Соглашения

- Документация, комментарии и сообщения коммитов — по-русски.
- Инструменты — Python 3.12 в `tools/`, по скрипту на шаг. Вверху docstring: что делает, вход,
  выход, как запускать. Зависимости — через `uv add`, `uv.lock` лежит в git.
- Тесты — в `tests/`, без файлов игры: синтетические данные на лету (`tmp_path`).
- Клиент — TypeScript в `web/src`, PixiJS закреплён точной версией. Геометрию узлов cocos2d-x
  повторять формулой (`web/src/engine/cocos.ts`), а не подгонкой; тесты — Vitest рядом с кодом.

## Окружение

- [uv](https://github.com/astral-sh/uv): `uv sync` ставит Python 3.12 из `.python-version` и зависимости
  из `uv.lock` в `.venv`. Новая зависимость — `uv add <пакет>` (`uv add --group dev` — для проверок);
  `pyproject.toml` и `uv.lock` коммитятся вместе, CI ставит строго по lock-файлу (`uv sync --locked`).
- Node.js 22.12+ (в CI — 24) для клиента: `cd web && npm install`.
- Подготовка данных и запуск инструментов — в [README](README.md#подготовка-данных).
