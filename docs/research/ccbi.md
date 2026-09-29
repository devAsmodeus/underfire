# CocosBuilder (.ccbi) в Under Fire: формат, статистика макетов, перенос UI в браузер

Дата: 2026-09-29. Всё рабочее — в `research/ccbi/` рядом с этим файлом (скрипты, JSON, клоны эталонов).
В `~/PycharmProjects/` ничего не менялось.

Обозначения: **[П]** — проверено (файл, команда, дизассемблер, ссылка); **[Г]** — гипотеза или оценка.

---

## 0. Коротко

- **Формат.** Все 306 файлов — **CCBI версии 5** (CocosBuilder 3.x, писатель `kCCBXVersion 5`), `jsControlled=false` [П].
  Это **диалект Inferno**: у свойства `Block` (колбэк кнопки) после стандартных полей идут ещё `soundFile` и
  `soundEnabled`, плюс есть тип свойства 28 без значения (`makeCopy`). Оба расширения подтверждены
  дизассемблированием `libinferno.so` [П]. Из-за расширения `Block` стандартный ридер ломается на 253 из 306 файлов [П].
- **Парсер** (`research/ccbi/ccbi_parser.py`) читает все 306 файлов строго до последнего байта. Обратный писатель
  (`ccbi_writer.py`) собирает **все 306 файлов байт-в-байт**, то есть разбор без потерь [П]. Писатель же конвертирует
  диалект Inferno в стандартный v5 (306 из 306 после этого читаются стандартным ридером) [П].
- **Макеты.** Эффективный набор — 177 путей, из них 145 для 1024×768 (единственное разрешение в `interface.xml`).
  В коде игры по имени упоминаются 84 файла; вместе со списочными шаблонами получается **112 «живых» макетов**:
  80 окон/сцен/виджетов и 32 шаблона строк списков. Около 4 600 нод [П].
- **Что внутри.** Стандартные классы: CCSprite, CCNode, CCLabelTTF, CCMenu, CCMenuItemImage, немного CCLayer и
  CCLayerColor. Свои классы: **CCTextLayout, CCTextButton, CCNodeSelector, CCScrollListView, CCTableNode,
  CCCheckBox, CCLabelTTFLocalized**; ещё у CCProgressTimer и CCSpriteBatchNode свои загрузчики.
  **Не используются:** CCScale9Sprite, CCControlButton, CCLabelBMFont, частицы, вложенные CCBFile [П].
  Таймлайны примитивны: opacity, scale и position, только линейная интерполяция, 246 ключей в 24 файлах,
  колбэков и звуков в таймлайнах нет [П].
- **Рекомендация.** ccbi остаются источником правды. На сборке — наш конвертер в JSON, в рантайме — свой тонкий
  «CCB-загрузчик» и ~10 виджетов **на том же движке, что и вся игра**. Для одного только UI PixiJS v8 чуть удобнее
  Phaser 4. Phaser тоже годится (+~5–10 % к UI-слою) и даёт общий стек с Under Control. Cocos Creator — только если на
  него переезжает вся игра. cocos2d-html5 как продукт не брать. HTML/CSS не подходит для основного UI.
- **Объём [Г].** UI-слой (конвертеры, загрузчик, виджеты, таймлайны, инфраструктура диалогов, просмотрщик) —
  **~22–33 чел.-дня на PixiJS** (Phaser ~23–35). Логика 80 окон (аналоги ~83 C++-классов `Rj*Dialog/Widget/Popup`) —
  **~65–160 чел.-дней** при любом движке; это основная часть работы, и она завязана на перенос игровой модели.

---

## 1. Формат: эталоны, версии, наши файлы

### 1.1. Эталонные реализации (склонированы в `research/ccbi/refs/`) [П]

| Что | Где | Версия формата |
|---|---|---|
| CocosBuilder (сам редактор), ветка `v3.5.0`, коммит `021d741` (2013-05-22) | `refs/CocosBuilder/CocosBuilder/Cocos2D iPhone/CCBXCocos2diPhoneWriter.{h,m}` — писатель ccbi | `#define kCCBXVersion 5` |
| Спецификация | `refs/CocosBuilder/Documentation/X4. CCBi File Format.md` | описывает **v4**; v5 отличается только блоком последовательностей (см. ниже) |
| cocos2d-x ветка `v2`, `extensions/CCBReader/` (`CCBReader.cpp`, `CCNodeLoader.cpp`, …) | `refs/cocos2d-x-v2/` | `#define kCCBVersion 5` |
| cocos2d-x ветка `v3`, `cocos/editor-support/cocosbuilder/` | `refs/cocos2d-x-v3/` | `#define CCB_VERSION 5` |
| cocos2d-html5 (`develop`, «Cocos2d-JS v3.17»), `extensions/ccb-reader/CCBReader.js` | `refs/cocos2d-html5/` | `var CCB_VERSION = 5;` |
| Примеры `.ccbi` из CocosBuilder (11 файлов) | `refs/CocosBuilder/Examples/CocosBuilderExample/Resources/` | v5 |

Ссылки: <https://github.com/cocos2d/CocosBuilder>, <https://github.com/cocos2d/cocos2d-x> (ветки v2/v3),
<https://github.com/cocos2d/cocos2d-html5>.

### 1.2. Какие версии бывают [П]

История `kCCBVersion` в cocos2d-x (`extensions/CCBReader/CCBReader.h`, по коммитам через `gh api`):

| Версия | Когда | Что добавилось (по заголовкам коммитов) |
|---|---|---|
| 2 | 2012-07 | CocosBuilder 2.0 |
| 3 | 2012-09 | «support Cocosbuilder v2.1 beta0»: последовательности (таймлайны) |
| 4 | 2012-11 | синхронизация с cocos2d-iphone, JS-контроллеры (`jsControlled`) |
| **5** | 2013-03-15 | «Sound, Callbacks and skew»: у каждой последовательности каналы колбэков и звуков, плюс `autoPlaySequenceId` |
| 6…10+ | SpriteBuilder / cocos2d-objc 3.x | в `cocos2d-objc` `kCCBVersion 10` и **другое кодирование целых** («byte flipped» Elias gamma); с v5 несовместимо |

**Наши файлы: 306 из 306 — версия 5** (заголовок `69 62 63 63 | 0c | 00`: магия `'ccbi'` little-endian, UINT 5,
jsControlled = 0) [П].

### 1.3. Структура v5 (кратко)

- Базовые типы: `UINT` и `SINT` — Elias gamma с битами LSB-first и выравниванием на байт (для SINT знак
  через биекцию); `FLOAT` — байт-тип (0 → 0, 1 → 1, 2 → −1, 3 → 0.5, 4 → SINT, 5 → float32 LE); строка — 2 байта длины
  (BE) + UTF-8; `CSTRING` — индекс в кэше строк.
- Документ: заголовок → кэш строк → последовательности (`duration, name, id, chainedId`, в v5 ещё
  колбэк- и звук-ключи) → `autoPlaySequenceId` → дерево нод.
- Нода: класс; `memberVarAssignment` (0 — нет, 1 — корень документа, 2 — owner) и имя; анимированные свойства
  по последовательностям (ключ: время, easing, опция easing, значение); N обычных и M «extra» (custom) свойств
  (тип, имя, платформа, значение); дети.
- 28 типов свойств (0 — Position … 27 — FloatXY); список и сериализация совпадают в писателе и во всех ридерах.

### 1.4. Диалект Inferno (расширения RJ Games) [П]

Движок — cocos2d-x ветки 2.x: символы `cocos2d::extension::CCNodeLoader::parsePropType*`, CocoStudio Armature,
пути `inferno_mobile/sources/.../cocos2d-x/` в `libinferno.so`. Номер минорной версии (2.1 или 2.2) — [Г].
`libinferno.so` извлечён из `../UnderControl/underfire_apk/mobi.rjg.underfire.apk` в `research/ccbi/bin/`.

1. **`Block` (тип 21) = `selector` CSTRING, `target` UINT, `soundFile` CSTRING, `soundEnabled` BOOL.**
   Дизассемблер `CCNodeLoader::parsePropTypeBlock` (адрес `0x9e10fc`) показывает цепочку вызовов
   `readCachedString`, `readInt(false)`, `readCachedString`, `readBool`. В движке есть
   `CCMenuItem::setSoundFile` и `CCMenuItem::setSoundEnabled`. В данных звук стоит один раз:
   `champion_close_attack.wav` в мёртвом `mainmenu/MainMenuScene.ccbi`; у остальных 1 251 Block во всех 306
   файлах — `('', false)`.
2. **Тип свойства 28 — без значения.** В `CCNodeLoader::parseProperties` стоит `cmp r5, #0x1c` и таблица
   переходов на 29 случаев; case 28 сразу переходит к следующему свойству. В данных это только `makeCopy`
   у `CCTextButton` (20 вхождений в 4 файлах, в основном `*_test`), по смыслу кнопка инспектора редактора [Г].
3. **Кадры спрайтов ищутся по имени в глобальном кэше.** `sheet` во всех 3 294 ссылках пустой.
   Стандартный ридер в этом случае грузит отдельный PNG. Движок же в `parsePropTypeSpriteFrame` сначала вызывает
   `CCSpriteFrameCache::spriteFrameByName(frame)` (кэш заполняют атласы сцены или диалога), и только если кадра нет,
   грузит текстуру-файл.
4. **Масштаб «MultiplyResolution».** Движок использует раздельные `CCBReader::setResolutionScaleX/Y`, а
   `CRjInterface::CreateFromFile` выставляет их из `CRjInterface::getSdScale()`: **2.0 при SD-атласах (`*_sd`), иначе 1.0**.
   Значит, при HD-атласах (`textures_etc/interface/1024x768`) масштабы из ccbi конечные. Проверка на
   `yes_no_popup`: фон `back_popup_delete_yes_no_popup.png` с оригиналом 1172×837 при `scale 0.5` даёт
   586×418.5, это ровно `contentSize` корня.
5. **Платформенные свойства.** Для платформы iOS пишется `touchEnabled`, для Mac — `mouseEnabled`, у CCMenu, CCLayer
   и CCTextLayout. На Android ридер их не применяет, в порте их тоже игнорируем.

Остальные функции (`readSequences`, `readKeyframe`, `readNodeGraph`, `parsePropTypeBlockCCControl`) по порядку чтения
совпадают со стандартом [П]. Это подтверждает и побайтовый round-trip.

### 1.5. Что это значит для «читает ccbi сам» (cocos2d-html5) [П]

- В `CCNodeLoader.js` `parsePropTypeBlock` читает только `selector` и `target`, поэтому поток съезжает на первом же
  Block: 253 из 306 файлов. Тип 28 уходит в `default:` с логом без чтения байтов, то есть безвреден.
  При пустом `sheet` `parsePropTypeSpriteFrame` грузит `ccbRootPath + frame` как отдельную текстуру.
- Обойтись можно без патчей движка: `ccbi_writer.py --to-vanilla` убирает расширения (306 из 306 затем читаются
  строгим стандартным ридером). При конвертации можно заодно вписать в `sheet` имя атласа: соответствие
  «кадр → атлас» известно (§3.6).

---

## 2. Прототип: парсер, проверка, выгрузки

### 2.1. Файлы (`research/ccbi/`)

| Файл | Назначение |
|---|---|
| `ccbi_parser.py` | ccbi → JSON; диалекты `inferno` (по умолчанию) и `vanilla`; строгие проверки (неизвестный тип, конец файла, лишние байты); float32 — кратчайшая запись без потерь |
| `ccbi_writer.py` | JSON → ccbi: `--roundtrip` (проверка всех файлов), `--to-vanilla in out` (конвертация в стандартный v5) |
| `ccbi_stats.py` | прогон по всем файлам → `stats.json`, `stats.txt`, `json_all/**` (177 JSON эффективного набора) |
| `ccbi_tree.py` | читаемое дерево макета |
| `samples/` | 4 характерных макета: JSON + `.tree.txt` (см. §2.4) |
| `bin/` | `libinferno.so` (из APK), `strings.txt`, `resscale_calls.txt` |
| `refs/` | sparse-клоны эталонов (§1.1) |

### 2.2. Проверка [П]

```
$ python3 ccbi_writer.py --roundtrip
round-trip: 306/306 байт-в-байт
round-trip CocosBuilder examples (vanilla): 11/11
inferno -> vanilla: 306/306 читаются стандартным ридером
$ python3 ccbi_stats.py        # parse_fail_inferno_dialect: [], parse_fail_vanilla_dialect: 253
```

### 2.3. Схема JSON (кратко)

```json
{ "version": 5, "jsControlled": false, "stringCacheSize": 22,
  "sequences": [{"duration": 10.0, "name": "Default Timeline", "sequenceId": 0, "chainedSequenceId": -1,
                 "callbacks": [...], "sounds": [...]}],
  "autoPlaySequenceId": 0,
  "root": { "class": "CCNode", "memberVar": {"target": "Owner", "name": "buttonYes"},
            "animated": {"1": {"opacity": {"type": "Byte", "keyframes": [{"time":0,"easing":"Linear","value":0}, ...]}}},
            "props": [ {"name":"position","type":"Position","value":{"x":46,"y":45,"type":"RelativeBottomLeft"}},
                       {"name":"block","type":"Block","value":{"selector":"close","target":"Owner","soundFile":"","soundEnabled":false}},
                       {"name":"touchEnabled","type":"Check","value":true,"platform":"iOS"},
                       {"name":"texture","type":"String","value":"frames","custom":true} ],
            "children": [ ... ] } }
```

### 2.4. Выгрузки характерных макетов (`samples/`)

- `yes_no_popup` (`city/popups/`, 14 нод) — типичный модальный попап: фон из атласа, CCMenu с крестиком,
  3 × CCTextButton, CCLabelTTF с `dimensions`, CCNodeSelector на закрытие.
- `construction_menu` + `construction_menu_template` (52 и 61 нода) — окно-список: CCScrollListView с `_template`,
  вкладки на CCCheckBox, строка шаблона с CCTableNode, CCTextLayout, таймлайнами `timelineShow` и `timelineHide`
  (opacity), рамками из кусков (масштабы вроде `(10, 0.5)`).
- `CityScene` (96 нод, 55 outlets, 22 колбэка) — HUD: позиции `Percent`, `RelativeTopRight`, `RelativeBottomRight`,
  CCProgressTimer, зацикленные таймлайны.

---

## 3. Статистика

Основной срез — **эффективный набор 1024×768**: patch перекрывает main, main перекрывает apk; 145 файлов, 5 362 ноды,
медиана 24 ноды на файл, максимум 200, глубина до 7. Там, где разница важна, в скобках — **живые** (112 файлов,
4 615 нод). Полные цифры — `stats.txt` и `stats.json`; там же срез по всем 306 файлам (11 457 нод) [П].

### 3.1. Файлы [П]

- 306 файлов: main 161, patch 143, apk 2. Разрешения: 1024×768 — 273 файла, 2048×1536 — 33.
  Уникальных путей 177: 145 для 1024×768 и 32 для 2048×1536.
- 128 путей есть сразу в нескольких источниках (patch/main/apk); 69 из них побайтно совпадают, 59 различаются.
- `interface.xml` описывает только `1024x768` (`type="tablet"`) и атласы по сценам. Папка `2048x1536` есть
  только в main и, судя по всему, унаследована [Г]. `fileLookup.plist` пуст, переименований нет.
- В `libinferno.so` по имени упоминаются 84 ccbi. С учётом транзитивных `_template` получается 112 живых файлов
  (верхняя оценка: сопоставление по суффиксу пути). 33 файла не упоминаются: `*_old`, `*_test`, `fake`, `test_menu`,
  `MainMenuScene`, `win`/`lose` и т. п. (список — `stats.txt`, `dead_files`).

### 3.2. Классы нод [П]

| Класс | Ноды (живые) | Файлы | Чей | Примечание |
|---|---:|---:|---|---|
| CCSprite | 2 068 (1 791) | 139 | cocos2d | кадр по имени; 99 с blendFunc (все обычные SRC_ALPHA/ONE_MINUS_SRC_ALPHA) |
| CCNode | 1 003 (837) | 144 | cocos2d | группировка, корни |
| CCLabelTTF | 890 (778) | 119 | cocos2d, загрузчик движка `CCLabelTTFSize` | TTF, `dimensions`, выравнивание h/v, цвет у 246 |
| CCMenu | 400 (348) | 117 | cocos2d | контейнер тач-кнопок, `ignoreAnchor` = true |
| CCMenuItemImage | 297 (260) | 106 | cocos2d | 3 кадра состояний + Block |
| **CCTextLayout** | 216 (193) | 64 | свой | поточная раскладка детей (`calcPositions`, `dynamicContent`, `horizTextAlignment`) |
| **CCTextButton** | 168 (151) | 68 | свой | кнопка: 3 кадра + подпись со шрифтом, размером, выравниванием, смещением, цветом и прозрачностью на каждое состояние |
| **CCNodeSelector** | 83 (77) | 54 | свой | невидимая тач-зона + Block (`canBeMoved`) |
| CCSpriteBatchNode | 57 (51) | 28 | загрузчик движка | extra-свойство `texture` (атлас `frames`, `city/frames`, …) |
| **CCScrollListView** (класс `CRjScrollListView`) | 44 (36) | 31 | свой | список: `_template` (ccbi строки), `_count`, `horizontal`, выравнивания, drag, клиппинг |
| **CCCheckBox** | 40 (25) | 11 | свой | 3 кадра, `selected`, `group` (радио-группы) |
| **CCTableNode** | 30 (30) | 19 | свой | сетка: `colcount`, `offset`, выравнивания |
| CCProgressTimer | 21 (20) | 11 | загрузчик движка | бар (17) и радиальный (4) |
| CCLayer | 20 (11) | 20 | cocos2d | корни-слои |
| **CCLabelTTFLocalized** | 19 (4) | 11 | свой | строка через `CRjInterface::GetLocalizedString` |
| CCLayerColor | 3 (3) | 3 | cocos2d | затемнение |
| CRjScrollListView, MainMenuScene, CCScrollView | 1 / 1 / 1 (0) | — | — | только в мёртвых файлах; в движке не зарегистрированы |

- **Не встречаются нигде:** CCScale9Sprite, CCLabelBMFont, CCParticleSystemQuad, CCLayerGradient, ноды CCBFile.
  CCControlButton есть только в устаревшем `2048x1536/battle/BattleScene.ccbi` (4 шт.).
  **9-slice эмулировать не нужно**: рамки собраны из кусков-спрайтов с масштабами вроде `70×2` или `10×0.5`.
- В `libinferno.so` зарегистрированы загрузчики для CCProgressTimer, CCLabelTTF (класс CCLabelTTFSize),
  CCLabelTTFLocalized, CCScrollListView, CCCheckBox, CCTextButton, CCTableNode, CCSpriteBatchNode, CCTextLayout,
  CCNodeSelector (строки подряд в `bin/strings.txt`; методы классов — по символам `objdump -T | c++filt`).

### 3.3. Позиционирование и трансформации [П]

- **Типы позиций** (4 210): RelativeBottomLeft 3 785 (90 %), Percent 200, RelativeTopRight 111,
  RelativeBottomRight 80, RelativeTopLeft 33, MultiplyResolution 1. Процент в эталоне обрезается до `int`.
- **Типы размеров:** `contentSize` Absolute 1 120, Percent 34 (корни на весь экран), MultiplyResolution 1;
  `dimensions` у меток Absolute 909 (у 570 из них 0×0, то есть авторазмер).
- **Масштаб:** Absolute 3 130, MultiplyResolution 2 230 (типично 0.5 при HD-атласе в 2×). Шрифты (`FloatScale`) —
  все Absolute. Отрицательный масштаб (зеркало) встречается часто: `(-1,1)` 111 раз, `(-0.5,0.5)` 51.
- **anchorPoint:** (0.5,0.5) 3 458, (0,0) 1 450, (0,1) 147, дальше ~15 редких вариантов.
  `ignoreAnchorPointForPosition = true`: CCMenu 363, CCTextLayout 60, CCScrollListView 41, CCLayer 9 и др.
- Поворот ≠ 0 у 35 нод, skew нет. `visible = false` у 361 ноды. Opacity ≠ 255 у 46: только спрайты, метки и
  CCLayerColor, контейнеров нет. Цвет ≠ белого у 256 (почти все — метки). Свойств `tag` и `zOrder` нет: порядок
  отрисовки = порядок детей.
- **Корни:** 124 CCNode, 20 CCLayer, 1 MainMenuScene. `contentSize`: `1024×768` у 36, `100%×100%` у 28, остальные —
  абсолютные размеры окон (586×418.5, 540×660, …).

### 3.4. Колбэки и outlets [П]

- `Block`: 588 (живые 513). target: Owner 581, DocumentRoot 3, None 4. Уникальных селекторов 306; `close` — 102 раза.
  `BlockCCControl` в наборе 1024×768 нет.
- `memberVar`: 2 543 (живые 2 225), все на Owner, 1 687 уникальных имён (`buttonYes`, `textDelete`, …).
  Владелец — C++-диалог: базовый `CRjDialog` (`initFile`, `onAssignMemberVariable`, `onResolveMenuItemSelector`,
  `addCancelLayer`, `show`/`hide`, звуки открытия и закрытия) и ~83 класса `Rj*Dialog/Widget/Popup` по символам.
- В живых окнах медиана — 13.5 outlets на окно. По числу outlets окна делятся так: 26 малых (<10),
  42 средних (10–39), 12 больших (40+; `building_science_center` — 109, `building_units_upgrade` — 101,
  `resources_buy_menu` — 87 …).

### 3.5. Таймлайны [П]

- Хотя бы `Default Timeline` (чаще всего пустой, 10 с, autoplay) есть у 144 из 145 файлов. Реальные ключи или
  несколько последовательностей — в **24 файлах** (живых 22): 77 анимированных нод, 246 ключей.
- Анимируются только **opacity** (51 дорожка), **scale** (18) и **position** (10). Easing — 100 % **Linear**.
  **Колбэк-ключей 0, звук-ключей 0.** Цепочек `chainedSequenceId` — 14 (петли, включая самоцикл,
  например `building_widget`).
- Имена, которые запускает код (`runAnimationsForSequenceNamed`; строки есть в `.so`): `timelineShow`/`timelineHide`,
  `showTimeline`/`hideTimeline`, `radio`, `attackEnd`, `fat arrows`, `zebra_arrow`, `awayTimeline`, `limit1…3`,
  `Timeline1…3`, `show`/`hide`, `move`.

### 3.6. Ресурсы [П]

- **Кадры:** 3 294 ссылки, 1 073 уникальных имени. Интерфейсные атласы 1024×768 (patch > main): 93 файла,
  1 025 кадров, **93 кадра повёрнуты** (`r`). Найдено в них 1 019 имён. 1 имя (`battle.png`) нашлось только как
  PNG в `icons/`, вероятно, случайное совпадение [Г]. **Отсутствуют 53 имени, из них в живых макетах только одно:**
  `button_green_menu_settings_city_black.png` (кадр «disabled» в `menu_settings_city`). 6 имён есть сразу в
  нескольких атласах; при глобальном кэше выигрывает последний загруженный.
- Атласов на живой макет: медиана 4, максимум 11. Чаще всего используются `city/glow_short` (61 макет),
  `city/icons` (44), `city/frames_additional` (34), `worldmap/icons` (34).
- Текстуры атласов по заголовку PKM: 73 шт. 2048×2048, 9 — 1024², 6 — 256², 5 — 512². Всё сразу в RGBA8 — около
  1.2 ГБ, поэтому нужна загрузка по требованию, как в оригинале (`CRjInterface::loadAtlasForScene/unloadAtlasForScene`).
- Формат `.atlas`: `x y w h` — прямоугольник в пространстве текстуры (у повёрнутых уже повёрнутый), затем смещение
  trim и исходный размер. У 27 кадров смещение и размер не укладываются в простую trim-модель; при написании
  конвертера атласов их нужно разобрать отдельно (TODO).
- **Шрифты** (`FontTTF`): `fonts/Play.ttf` 526, `Play_button.ttf` 398, `Play-Bold.ttf` 350, `Helvetica` 59
  (системный, на вебе нужна замена), `LiquidCrystal-Regular.ttf` 58, `a_SimplerDnm.ttf` 21,
  `LiquidCrystal-Bold.ttf` 1. Все TTF лежат в `raw/apk/assets/fonts/`. `FntFile` (bitmap-шрифтов) нет.
- **Тексты в макетах** — заглушки и дизайнерский текст: 1 121 строка, 481 уникальная; `Sample Text` 123 раза,
  цифры, смесь RU/EN. Настоящие строки подставляет код по ключам вида `window_technology::title` из
  **`config/locales/{ru,en}_locale.xml`, раздел `gui`** (142 окна, ~867 строк на язык). Нынешний
  `data/locale_*.json` покрывает только шаблоны абилок (327), поэтому раздел `gui` для UI ещё предстоит извлечь.
- Шаблоны списков (`_template` у CCScrollListView): ~30 уникальных имён; ноды CCBFile не используются, шаблоны
  инстанцирует код.

---

## 4. Перенос на движки

### 4.1. Что должен уметь любой порт (семантика cocos2d-x v2)

Опорная точка — `CCNode::nodeToParentTransform` в cocos2d-x v2. Трансформацию нужно повторить формулой, а не
приближением:

- позиция задаётся в системе координат родителя, где (0,0) — **левый нижний угол его contentSize**, ось Y смотрит вверх;
- `anchorPoint` нормирован к `contentSize` ноды; при `ignoreAnchorPointForPosition = true` позиция — это угол,
  но масштаб и поворот всё равно идут вокруг anchor;
- **неочевидные умолчания классов**: CCMenu и CCLayer получают `contentSize = winSize` и `ignoreAnchor = true`.
  Поэтому у CCMenu с масштабом ≠ 1 (таких 25: 0.8, 0.5, 0.4) центр масштабирования — середина экрана, и без
  этой формулы меню «уедут» [П: код cocos2d-x v2 и данные];
- относительные позиции (5 типов) и процентные размеры считаются при загрузке от размера родителя, для корня — от
  `winSize`; процент обрезается до int;
- у CCSprite `contentSize` = исходный (нетримленный) размер кадра; поворот в cocos2d v2 — градусы по часовой.

Политику адаптации экрана в оригинале (какой `winSize` на не-4:3 экранах) по коду восстановить не удалось:
прямых вызовов `setDesignResolutionSize` не найдено. Для веба разумно высота 768, ширина по аспекту, пересчёт
раскладки при resize [Г].

### 4.2. Что ложится 1:1, а что эмулировать

| Аспект | PixiJS v8 | Phaser 3/4 | Cocos Creator 3.8 | cocos2d-html5 v3 | HTML/CSS |
|---|---|---|---|---|---|
| Дерево, порядок отрисовки | 1:1 | 1:1 | 1:1 | 1:1 | 1:1 (DOM-порядок) |
| anchorPoint | `Sprite.anchor` и `Container.pivot` — 1:1 | у Image/Text `origin`; **у Container нет origin/pivot** — обёртки | `UITransform.anchorPoint` — 1:1 | 1:1 | `transform-origin` |
| Y вверх, начало слева снизу | переворот на каждом уровне: `y' = H_родителя − y`, `anchorY' = 1 − ay` | так же | 1:1, но позиция ребёнка отсчитывается от **anchor родителя**, а не от угла (сдвиг) | 1:1 | переворот |
| Поворот | рад., по часовой — совпадает | по часовой — совпадает | `angle = −rotation` | 1:1 | `rotate(deg)` совпадает |
| Относительные позиции, % размеры, умолчания CCMenu | свой резолвер | свой резолвер | свой резолвер (или Widget) | **нативно** | свой резолвер |
| Кадры атласа (trim, 93 повёрнутых) | Spritesheet JSON (TexturePacker, `rotated`) | Atlas JSON (TexturePacker, `rotated`) | SpriteFrame (`rotated`, `offset`, `originalSize`) | plist | вручную (фон-срезы; повёрнутые — обёртка или перепаковка) |
| TTF-метки с `dimensions` и v-выравниванием | Text + обёртка-бокс | Text + обёртка-бокс | Label (overflow, h/v align) — почти 1:1 | LabelTTF — 1:1 | нативно, лучшее качество |
| Кнопки (MenuItemImage, CCMenu) | эмуляция на pointer events | эмуляция | Button (transition SPRITE) | **нативно** | `<button>` и CSS |
| 9-slice | не нужен | не нужен | не нужен | не нужен | не нужен |
| Скролл-список с шаблонами | @pixi/ui ScrollBox/List или свой (маска + drag + инерция) | свой или rexUI (есть пакет `phaser4-rex-plugins`); маски в v4 через Mask filter | ScrollView + Mask + Layout | cc.ScrollView + свой загрузчик | `overflow:auto` (лучше всех) |
| ProgressTimer (бар и радиальный) | маска/crop, для радиального — Graphics-сектор | crop / маска | Sprite FILLED — 1:1 | cc.ProgressTimer — 1:1 | clip-path / conic-gradient |
| Таймлайны (opacity, scale, position, linear, петли) | свой плеер на ~150 строк | свой или Tween chain | AnimationClip в рантайме или tween | **нативно** (CCBAnimationManager) | WAAPI или CSS-анимации |
| Свои 7 классов + 2 загрузчика | писать | писать | писать (часть — композиция штатных компонентов) | писать загрузчики поверх cc.* | писать |
| Outlets и селекторы | свой binder (`ui[name]`, `this[selector]`) | так же | так же | **нативно** (`cc.BuilderReader.load(file, owner)`) | так же |
| Opacity | alpha каскадная, но у нас opacity только на листьях — совпадает | так же | UIOpacity каскадная — так же | 1:1 | так же |

### 4.3. Оценки по вариантам [Г]

Единица — чел.-день одного опытного TS-разработчика. Отдельно от вариантов идут **общие работы** (нужны всегда):

| Общая работа | Оценка |
|---|---:|
| C1. Конвертер ccbi → JSON в `tools/` (прототип готов: CLI, нормализация, тест round-trip) | 1–1.5 |
| C2. Конвертер `.atlas` → TexturePacker JSON или plist (trim, rotated, разбор 27 аномалий). **Без** ETC1-декодера: он уже в roadmap | 1–2 |
| C3. Строки UI: раздел `gui` из `config/locales/*_locale.xml` → JSON | 0.5–1 |
| C4. Шрифты: TTF → woff2, предзагрузка, замена Helvetica | 0.5 |
| **Итого общего** | **3–5** |

UI-слой по вариантам:

| Работа | PixiJS v8 | Phaser 3/4 | Cocos Creator 3.8 | cocos2d-html5 | HTML/CSS (генерация DOM из JSON) |
|---|---:|---:|---:|---:|---:|
| L1. Ядро загрузчика: трансформы по §4.1, кадры, outlets, селекторы | 4–6 | 5–8 | 3–5 | 0.5 (конвертация в vanilla + `sheet`) | 5–7 |
| L2. Метки: бокс, выравнивания, шрифты, цвет | 1.5–2.5 | 1.5–2.5 | 1 | 0.5 | 0.5–1 |
| L3. Кнопки: CCMenu/MenuItemImage, CCTextButton, CCCheckBox (+группы), CCNodeSelector | 3–4 | 3–4 | 1.5–2.5 | 1.5–2.5 | 1.5–2 |
| L4. Контейнеры: CCScrollListView (шаблоны, клип, drag), CCTableNode, CCTextLayout | 4–6 | 4–6 (rexUI: −1…2) | 2–3 | 2.5–4 | 2–3 |
| L5. CCProgressTimer | 0.5–1 | 0.5–1 | 0.5 | 0.25 | 0.5 |
| L6. Плеер таймлайнов | 1–1.5 | 1–1.5 | 1–1.5 | 0 | 1 |
| L7. Инфраструктура диалогов (стек, модальный блокер, затемнение, back/ESC, звуки, атласы по требованию) | 2–3 | 2–3 | 1.5–2 | 1.5–2 | 2–3 |
| L8. Адаптация к экрану (winSize, resize) | 1 | 1 | 0.5–1 | 0.5–1 | 1 |
| L9. Просмотрщик всех 112 макетов с заглушками и сверкой по скриншотам | 2–3 | 2–3 | 2 | 1.5–2 | 2 |
| Освоение платформы (редактор, импорт ассетов, сборка) | — | — | 3–6 | 1–2 | — |
| Связка DOM ↔ canvas (виджеты над объектами мира, z-порядок, ввод) | — | — | — | — | 2–4 |
| **Итого UI-слой** | **19–28** | **20–30** | **16–25** | **9–15** | **17–24** |
| **С общими работами** | **22–33** | **23–35** | **19–30** | **12–20** | **20–29** |

Логика окон, **общая для всех вариантов**: 80 окон и 32 шаблона, 2 225 outlets, 513 колбэков, в оригинале — ~83
C++-класса. По порогам малые / средние / большие (26 / 42 / 12) примерно по 0.3–0.75 / 0.8–2 / 2–5 дня, итого
**~65–160 чел.-дней**. Цифра грубая: C++-логика окон не декомпилирована, а объём сильно зависит от того, насколько
готова модель игры (экономика, здания, армия, квесты). HTML/CSS «вручную» (вместо генерации) добавляет ещё
**~35–110 дней** на разметку 112 макетов.

### 4.4. Комментарии по вариантам

**(а) PixiJS v8** (последняя версия 8.21.0, 2026-09-17 [П: GitHub releases]). Самая прямая модель: `pivot` у любого
Container, `anchor` у Sprite, произвольные маски, trim и rotated в Spritesheet. Готовые компоненты @pixi/ui (2.3.2)
закрывают ScrollBox, List, CheckBox, RadioGroup и ProgressBar [П: pixijs.io/ui]. Это просто рендер-библиотека:
сцены, звук, загрузчик и твины — свои или сторонние. Риск низкий.

**(б) Phaser 3/4** (Phaser 4.0.0 вышел 2026-04-10, текущая 4.2.1 от 2026-07-09 [П: GitHub releases]).
Главная разница для UI: **у Container нет origin и pivot**, поэтому ноды с anchor ≠ (0,0), которые масштабируются
или поворачиваются, нужно заворачивать во внутренний контейнер со сдвигом. Это одна обёртка в загрузчике, +1–2 дня.
В Phaser 4 маски в WebGL — через Mask filter (GeometryMask остался только для Canvas-рендера) [П: migration guide];
на клиппинг списков это не влияет. Плюсы: сцены, твины, ввод, звук, лоадер «из коробки», и **единый стек с
реконструкцией Under Control** (TS + Phaser), то есть общий код и опыт.

**(в) Cocos Creator 3.8** (движок 3.8.8, 2025-12-16 [П]). Семантически ближе всех: UITransform, Button, Toggle,
ScrollView, Layout, Sprite FILLED, Label с выравниваниями. Но:
1. это редактор-центричный движок: сцены и префабы с UUID, импорт ассетов через редактор. Под наш кодогенерирующий
   конвейер (Python → JSON) он ложится хуже;
2. встроенный импорт CocosBuilder («Import Project») задокументирован в руководствах 1.9–2.4 и 3.0, но **требует
   исходников `.ccbproj` и `.ccb` (XML)**, а у нас только опубликованные `.ccbi`. Свои классы (CCTextButton и др.)
   импортёр не знает. В руководстве 3.8 соответствующей страницы не нашлось (404), поддержка в 3.8 не проверена [Г];
3. имеет смысл только если **вся игра** переезжает на Creator; держать его ради UI рядом с Pixi или Phaser нельзя
   (два движка).

**(г) cocos2d-html5 v3** («Cocos2d-JS v3.17»; последний коммит в `develop` 2020-03-13, README: «evolved to Cocos
Creator»; не архивирован [П]). Быстрее всех даёт *идентичную* раскладку: та же семантика, CCBAnimationManager,
owner-outlets. Патчи не нужны, если файлы заранее сконвертировать нашим писателем (`--to-vanilla` плюс `sheet`).
Свои 7 классов всё равно писать как JS-загрузчики. Минусы решающие: движок фактически заморожен (ES5, без типов,
WebGL1-эпоха), а игру целиком тоже пришлось бы делать на нём. **Как продукт — нет.** Как эталонный рендерер для сверки
стандартных классов — возможно, но свои классы там будут заглушками, так что пользы ограниченно.

**(д) HTML/CSS поверх канваса.**
- Плюсы: лучший текст (кириллица, переносы, чёткость на любом DPI), родной скролл с инерцией, простые формы и чекбоксы,
  devtools, быстрый цикл правок, UI не зависит от выбора рендер-движка.
- Минусы:
  - макеты — это «пиксельный арт» (рамки из кусков, свечения, куски с масштабом 70×2), поэтому семантической
    вёрстки не получится: либо генерировать абсолютно спозиционированные div (выигрыш только в тексте и скролле),
    либо переписывать руками 112 макетов (+35–110 дней);
  - повёрнутые и тримленные кадры в CSS неудобны, при дробном масштабе на стыках кусков возможны щели в 1 px;
  - виджеты, привязанные к миру (`building_widget`, `citizen_widget`, `arrows_template`, `helper_move`,
    боевой HUD), придётся синхронизировать с камерой каждый кадр или оставлять в канвасе, то есть держать две
    UI-системы;
  - DOM всегда поверх канваса, из-за чего подсказки туториала «между миром и UI» и маршрутизация ввода усложняются.
- Вывод: для основного UI — нет. Точечно можно использовать для чисто текстовых окон (почта, описания квестов) или
  отладочных панелей.

---

## 5. Вывод и рекомендуемый путь

1. **Источник правды — ccbi.** Руками макеты не переписываем. Прототип (`ccbi_parser.py`, `ccbi_writer.py`) переносится
   в `tools/`. На сборке: ccbi → JSON (нормализованный, с именем атласа для каждого кадра), `.atlas` → JSON
   TexturePacker, `gui`-локали → JSON, шрифты → woff2.
2. **Рантайм — на движке всей игры.** Нужен свой «CCB-загрузчик», который повторяет `nodeToParentTransform`
   cocos2d-x v2 (§4.1), плюс ~10 виджетов (§3.2), плеер таймлайнов и базовый `Dialog` (аналог `CRjDialog`: outlets в
   `ui[name]`, селекторы в методы, модальность, атласы по требованию). Если движок ещё не выбран, то для UI
   **PixiJS v8 немного удобнее**. **Phaser 4 приемлем** (+~5–10 % к UI-слою) и выигрывает единым стеком с Under
   Control. Решать нужно по игровой части (карта, бой), UI этот выбор не определяет. Cocos Creator — только при
   переезде всей игры; cocos2d-html5 и HTML/CSS для основного UI — нет.
3. **Порядок работ:** ETC1-декодер и атласы → загрузчик и просмотрщик всех 112 макетов с заглушками (сверка с
   видео или скриншотами оригинала) → виджеты → окна по приоритету: HUD `CityScene` и `BattleScene`,
   меню здания, строительство, армия, магазин ресурсов → остальные.
4. **Объём [Г]:** UI-слой **~4.5–7 недель** (22–33 чел.-дня на Pixi, 23–35 на Phaser). Логика окон
   **~65–160 чел.-дней** при любом выборе, и её сроки определяет перенос игровой модели.

### Открытые вопросы (что проверить дальше)

- Политика `winSize` оригинала на не-4:3 экранах и смысл `ScaleType` 1/2 в `CRjInterface::CreateFromFile`
  (после загрузки корень дополнительно масштабируется; код не разобран).
- Точные алгоритмы `CCTextLayout::calcPositions`, `CCTableNode::PlaceRow`, `CRjScrollListView::RecalcPositions` и
  коэффициент `CCLabelTTFSize::SetScaleCoef`: либо дизассемблировать, либо подобрать по скриншотам.
- 27 кадров атласов с нестандартными trim-данными; 6 имён кадров, которые есть в нескольких атласах.
- Эталонные скриншоты: APK только armeabi (32-бит), на Apple Silicon оригинал не запустить. Нужны видео или
  скриншоты либо ARM-эмулятор Android.

### Как воспроизвести

```
cd research/ccbi
python3 ccbi_writer.py --roundtrip          # 306/306 байт-в-байт, 11/11 примеров, 306/306 → vanilla
python3 ccbi_stats.py                        # stats.json, stats.txt, json_all/
python3 ccbi_tree.py samples/CityScene.json  # читаемое дерево
python3 ccbi_parser.py <file.ccbi> -o out.json
# дизассемблер (Xcode CLT llvm-objdump):
objdump -d --triple=thumbv5te-linux-androideabi --start-address=0x009e10fc --stop-address=0x009e1278 bin/libinferno.so
```
