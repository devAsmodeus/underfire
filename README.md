# Under Fire: Invasion — реконструкция под браузер

Восстановление игры RJ Games **Under Fire: Invasion** (RU: «Пекло! Космическая стратегия!»,
внутр. код SpaceHeat) для запуска в браузере. Оригинал — Android/iOS/Windows на собственном
движке **Inferno** (cocos2d-x). Серверы мертвы, но игра офлайновая — вся логика в клиенте.

## Источник (проверен на подлинность)

- `mobi.rjg.underfire` **v1.3.12** (последняя, 29.05.2016), XAPK из APKPure, 649 МБ.
- Подпись APK: `O=RJ Games, OU=Mobile Games, Moscow, RU`, MD5 `F8:07:8F:CE:59:A8:54:8A:D1:27:94:CD:1E:D8:66:7C` — оригинал, без модов.
- Движок `libinferno.so` (cocos2d-x) + FMOD, только armeabi (32-бит). 64-битной сборки нет →
  на Apple Silicon не запускается; поэтому цель — браузерная пересборка.

## Структура проекта

```
raw/            # извлечённый оригинал (в .gitignore — большой)
  apk/assets/   # config, шейдеры, шрифты, интерфейс, звуки
  obb_main/     # main.13 OBB: графика (текстуры .pkm.ccz ETC1, атласы)
  obb_patch/    # patch.59 OBB: АВТОРИТЕТНЫЕ данные (config.xml 5.4 МБ) + графика
data/           # распарсенный JSON (результат сбора)
  config.json           # 50 секций, 13 511 сущностей (см. config_sections.json)
  config_sections.json  # сводка «секция → количество»
  locale_ru.json / locale_en.json  # шаблонные строки абилок (@ = значение)
assets/         # декодированные PNG/атласы для браузера (TODO)
web/            # браузерный клиент (TODO)
tools/          # парсеры/декодеры
  parse_config.py       # config.xml (Inferno, lxml recover) → data/*.json
```

## Модель данных (config.xml)

Склейка XML-документов namespace `inferno:` без общего корня. Ключевые секции:
`buildings` (665), `soldiers` (320), `units` (86), `turrets`, `resources` (182),
`currency_groups`/`order_prices`/`offers`/`packs`/`spaceport_store` (экономика),
`chapters`/`missions` (143)/`maps` (121), `star_systems`/`territories` (120, галактика),
`quests` (2355), `perks`, `abilities` (180), `behaviors`, `contracts`, `invasions`,
`requirements` (5105). Модель совпадает по духу с Under Control.

## Сделано

- [x] XAPK получен, подпись проверена, распакован (APK + 2 OBB).
- [x] Полная инвентаризация ассетов и данных.
- [x] `parse_config.py`: config.xml → `data/config.json` (lossless по секциям) + локали.

## Дальше (roadmap сборки под браузер)

1. **Ассеты**: декодер `.pkm.ccz` (ccz=zlib → PKM ETC1 → PNG) + атласы cocos2d-x → спрайты.
2. **Каталоги**: из config.json собрать читаемые каталоги (юниты со статами/уроном,
   здания по уровням, экономика, дерево миссий/глав) — как каталоги UC.
3. **Локализация**: сшить inline `<name>/<description>` из config + шаблоны локалей.
4. **Рендер**: браузерный клиент (PixiJS, как UC-клон) — карта-колония, бой, миссии.
5. **Логика боя**: разобрать `behaviors`/`abilities`/`missions` (волны, ИИ).

## Запуск инструментов

```bash
cd ~/PycharmProjects/UnderFire
python3 tools/parse_config.py    # пересобрать data/*.json из raw/
```
Требуется `lxml` (устойчивый парсер для склеенных документов с namespace).
