# libinferno.so (Under Fire: Invasion 1.3.12): архитектура по символам и строкам

Дата: 2026-09-29. Всё извлечено и посчитано в `research/native/` (scratch). Проект и APK не изменялись.

Обозначения: **[Ф]** — проверенный факт (команда или скрипт и их вывод есть в `research/native/`),
**[Г]** — гипотеза или вывод, не подтверждённый кодом до конца.

---

## 0. Главное (TL;DR)

1. **[Ф] Библиотека «stripped» только формально.** `.symtab` и DWARF нет, но в `.dynsym` лежат
   **61 203 символа** (54 702 C++-символа, 47 475 функций). Экспортировано почти всё, включая классы
   игры. Имена классов и методов с сигнатурами есть у ~70 % кода `.text`.
2. **[Ф] Движок — cocos2d-x 2.2.0.** Функция `cocos2d::cocos2dVersion()` возвращает строку `"2.2.0"`.
   В нём есть правки RJ: ETC1 с альфой в нижней половине текстуры, `CCRjArchive`, touch-logger и
   масштаб CCBReader по X/Y. Интерфейс собран в CocosBuilder: 306 файлов `.ccbi`, все формата **v5**.
   Их читает штатный `CCBReader` с 10 собственными загрузчиками узлов.
3. **[Ф] Внутри клиента скомпилирован игровой сервер** (`server/server/src/...`, namespace
   `inferno::`). `RjCommander` собирает XML-команды, `RjCommandProxy` передаёт их в локальный
   `inferno::CRequestHandler::handle()`, ответ приходит событиями `UserEvent*`, их разбирают
   парсеры и хендлеры в клиентскую модель. `CRequestHandler::needServerAuth()` — это
   `movs r0,#0; bx lr`: HTTP-авторизация на `10.0.1.184` не вызывается никогда. **Игра полностью
   офлайновая.**
4. **[Ф] Логика в основном задана данными.** Из 13 192 id сущностей config в коде упоминаются
   только **144** (≈1 %): 4 пушки, ресурсы, особые здания, туториал. Поведения юнитов, эффекты и
   действия города — **интерпретируемые XML-DSL**; их полный словарь извлечён из парсеров
   (`dsl_vocabularies.txt`). В коде зашиты: семантика операторов (урон, лечение, цели), движение и
   поиск пути, конечный автомат юнита, тики, правила экономики сервера и весь UI.
5. **[Ф] В `data/config.json` не хватает половины экономики.** Есть второй конфиг — `config/server.xml`
   (4,6 МБ, 477 документов). В нём **2 431 action** — награды всех 2 355 квестов (все ссылки
   разрешаются), а также серверные requirements и timings. Текущий `parse_config.py` его не читает.
6. **[Ф] Сохранения — открытый XML без шифрования.** `profile.xml` — полное состояние игрока, пишется
   через `fopen`/`fwrite`. Рядом лежат `mailbox.xml`, `last_waypoint.xml` (чекпойнт боя) и
   CCUserDefault: 68 функций-писателей, там много клиентского состояния. Облако — снимок GPGS:
   profile + mailbox + userdefaults + CRC32.
7. **[Ф] Бой детерминирован.** В `CRjGame`, `CRjUnit`, `CRjMapObject`, `inferno::Simulator` и
   `Entity*` нет вызовов `lrand48`. Случайность есть только в `animation_random` (визуал), в
   экономике и в магазинах. Ключевые формулы очень маленькие: `calculateDamage` — 30 байт,
   `receiveDamage` — 198 байт. Две из них разобраны в §6.
8. **Выбор стека.** Логика кастомная, её придётся переписывать при любом движке. От движка нужны
   спрайты, батчинг, TTF-текст, меню, actions, RenderTexture, 9 файлов GLSL из assets плюс 2 встроенных шейдера (ETC-альфа, маска) и **CCB**. Частицы,
   TMX, Spine, CocoStudio, Box2D и Chipmunk в бинарнике есть, но игрой не вызываются. Семейство
   Cocos даёт реальную экономию только на UI: cocos2d-js 3.x умеет читать ccbi v5, но движок
   заброшен. Cocos Creator ccbi не читает. Для PixiJS или Phaser нужен конвертер ccbi→JSON и плеер
   таймлайнов CCB: это ограниченная задача, в ccbi используется 19 типов узлов.

---

## 1. Что извлечено и чем

```
unzip -p mobi.rjg.underfire.apk lib/armeabi/libinferno.so > bin/libinferno.so   (и libfmod, libgnustl_shared, classes.dex, AndroidManifest.xml)
```
SHA-256: `libinferno.so f0bca79d…79db`, `classes.dex f2ebcc69…ec85` (полные хэши см. `bin/`, `shasum -a 256 bin/*`).

Инструменты — только системные (ничего не ставилось): `/Library/Developer/CommandLineTools/usr/bin/llvm-nm`,
`llvm-objdump`, `llvm-cxxfilt` (Apple LLVM 21), `strings`, `python3` (stdlib). pyelftools не понадобился:
ELF и DEX разобраны своим кодом на `struct`.

Собственные скрипты (`research/native/scripts/`):

| Скрипт | Что делает |
|---|---|
| `group_symbols.py` | Группирует demangled-символы по namespace и классу, пишет `classes_*.txt` и `symbols_*.txt` |
| `extract_cstrings.py` | Все NUL-строки из `.rodata`/`.data` с адресами → `cstrings.tsv` |
| `config_vs_strings.py`, `serverxml_vs_strings.py`, `xmldir_vs_strings.py` | Сверяют имена тегов, атрибутов и id из данных со строками бинарника |
| `thumb_xrefs.py` | **Лёгкий сканер Thumb-кода, не дизассемблер.** Распознаёт только `LDR Rt,[PC,#]` + `ADD Rt,PC` (адреса строк) и пары `BL`/`BLX`. Разрешает линкерные стабы gold и PLT. Результат: `xref_strings.tsv` (25 130 ссылок функция→строка) и `callgraph.tsv` (191 685 рёбер, из них 68 803 — в импорты) |
| `modules.py` | Раскладывает классы по модулям с суммой размеров кода |

Точность xref и графа проверена на известных местах. `cocos2dVersion` → `"2.2.0"`, `RjCommandProxy()` →
`"config/server.xml"`, `saveProfileLocal` → `fopen`/`fwrite`. Ограничения: виртуальные вызовы, указатели
на функции и код без экспортного символа (лямбды, static) в граф не попадают. Поэтому «0 вызовов»
означает «прямых вызовов не найдено». Для самых важных случаев сделан полный линейный проход по `.text`
(§5.2).

---

## 2. Бинарник: факты

**Цель сборки.** ELF32 ARM, ABI armeabi (ARMv5TE, `.ARM.attributes` = `5TE`). Код в основном Thumb-1:
43 039 Thumb-функций и 4 436 ARM (libgcc, asm OpenSSL). Проверено по биту 0 в `st_value`.

**Сборка.** В `.comment` видны GCC 4.4.3/4.6/4.7/4.8/**4.9 20150123** — это тулчейн NDK r10. Линкер —
`gold 1.11`. В `DT_FLAGS` стоят `SYMBOLIC|BIND_NOW`. Сторонние библиотеки взяты из
`cocos2d-x-3rd-party-libs-src` (NDK r11b, 2016 г.).

**NEEDED.** `libfmod.so`, `libgnustl_shared.so`, `libGLESv2.so`, `liblog`, `libz`, `libstdc++`, `libm`,
`libc`, `libdl`. Рендер — только GLES2.

**Секции.**

| Секция | Размер |
|---|---|
| `.text` | 0x5cec30 (5,8 МБ) |
| `.rodata` | 1,0 МБ, 25 001 строка |
| `.dynsym` | 0xef140 = 61 204 записи |
| `.dynstr` | 4,4 МБ |
| `.ARM.exidx` | 0x4cf70 ≈ 39 400 unwind-записей, это границы почти всех функций; удобно для Ghidra |
| `.debug_*` | нет |

**Stripped.** `file` показывает `stripped` (нет `.symtab`). `llvm-nm` без `-D` → `no symbols`.
`llvm-nm -D` → 61 203 символа:

| Всего | Определено | Импорт | T | W | V | D | R | B |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 61 203 | 60 645 | 558 | 21 881 | 25 594 | 8 832 | 2 757 | 1 394 | 184 |

**Импорты.** FMOD (только `System`/`Sound`/`Channel`/`ChannelGroup`), libstdc++, pthread, сокеты, GL и
zlib: `syms_undefined_demangled.txt`.

**Встроены статически** (строки и символы):

| Библиотека | Версия / объём |
|---|---|
| OpenSSL | 3 872 символа |
| libcurl | 7.48.0 |
| libwebsockets | — |
| Crypto++ | 17 127 символов (!) |
| protobuf | через Google Play Games C++ SDK, `gpg::` |
| libpng | 1.2.46 |
| libjpeg, libtiff, libwebp | — |
| Box2D, Chipmunk, kazmath | — |
| pugixml | клиентский XML |
| rapidxml | серверный XML |
| tinyxml2 | — |
| CSJson | jsoncpp |
| twitCurl + oAuth | — |
| EziSocial | Facebook |
| avalon | IAP и i18n |
| `skzk` | фреймворк сервера RJ |

**Пути исходников** (≈120 путей игры): `source_paths.txt`. Важные:
- `inferno_mobile/sources/proj.android/../../cocos2d-x/...` — движок;
- `jni/../../Classes/{BattleScene,CityScene,ChaptersScene,RjPreloader}.cpp`,
  `Classes/Interface/Dialogs/*.cpp` (≈80 диалогов);
- **`cocos2d-x/../server/server/src/{CRequestHandler.cpp, game/User.cpp, game/BattleSystem.cpp,
  game/missions/Simulator.cpp, game/missions/entities/*.cpp, game/configuration/*.cpp,
  game/city_actions/*.cpp}`**, `server/server/libskzk/...`.

  Это исходники игрового сервера, собранные в клиент.

**Java-часть (classes.dex, 4 685 классов)** — тонкая обвязка:
- `org.cocos2dx.lib` (стандартная для 2.x);
- `mobi.rjg.underfire.*` — Activity, MailHelper, GCM, Facebook Like, GA, Parse;
- `RjOfflineChecker`, `RjPushManager`;
- `com.avalon.payment` (Google Billing), EziSocial, Facebook SDK, Google Play Services, expansion
  downloader (OBB).

Игровой логики в Java нет (`dex_classes.txt`).

---

## 3. Символы по пространствам имён

`symbols_namespace_counts.txt`, `classes_*.txt`, `symbols_all_grouped.tsv` (все символы: адрес, размер,
тип, группа, класс, член, полное имя).

| Группа | C++-символов | Классов с vtable | Код, байт (sized T/W) | Доля |
|---|---:|---:|---:|---:|
| Игра, клиент (глобальный ns: `CRj*`, `Rj*`, `*Library`, `*System`…) | ≈10 300 | ≈690 | 1 155 562 | 27 % |
| Crypto++ | 17 127 | 1 336 | 710 264 | 17 % |
| OpenSSL (C) | 3 872 | — | 539 244 | 13 % |
| cocos2d / CocosDenshion / extension | 8 460 | 408 | 493 226 | 12 % |
| std (инстанции шаблонов) | 11 854 | 544 | 332 162 | 8 % |
| **`inferno::` (сервер внутри клиента)** | 2 276 | 208 | 218 220 | 5 % |
| gpg (Play Games), Box2D, libpng, jpeg, tiff, webp, chipmunk, pugi, rapidxml, tinyxml2, CSJson, avalon… | — | — | остальное | — |

Размеры по классам лежат в `modules_map.txt`. Это нижняя оценка: статические функции и лямбды не
экспортированы.

### 3.1 cocos2d-x

**[Ф] Версия 2.2.0.**
```
llvm-objdump -d --triple=thumbv5te --start-address=0xa31fb0 ...  →  ldr r0,[pc,#4]; add r0,pc; bx lr; .word 0x2f54b1
0x2f54b1 + 0xa31fb6 = 0xd27467 → "2.2.0"
```
Рядом лежит строка `cocos2d.x.fps`. Структура каталогов — `extensions/CocoStudio/Armature`,
`extensions/physics_nodes`, `external/chipmunk`. Набор классов — `UIWidget`/`UILayer` (GUI CocoStudio),
`CCSkeleton` (Spine), `CCTextureETC`, `WebSocket`, `AssetsManager`. Всё это соответствует линии 2.2.x.

Классы: 293 в core и 150 в `cocos2d::extension` (`classes_cocos2d.txt`).

**Правки RJ в движке [Ф]:**
- `cocos2d::CCRjArchive` / `CCRjArchiveController`: собственные архивы с сигнатурой `rjmp`. Прямых
  вызовов из игры не найдено.
- `CCDirector::setTouchLogger`, `cocos2d::touchLogger::ITouchLogger`: нужны для `RjMonkeyTouchLogger`.
- `CCBReader::setResolutionScaleX/Y` вместо стандартного одного scale.
- `CCTextureETC` читает `.pkm.ccz` и `.pkm.gz`.
- **ETC1 с альфой.** Шейдер из `.rodata`:
  - `v_texCoord = a_texCoord * vec2(1.0, 0.5); v_alphaCoord = v_texCoord + vec2(0.0, 0.5);`
  - `color.a = texture2D(CC_Texture0, v_alphaCoord).r;`

  Гипотеза README подтверждена: альфа лежит в нижней половине и берётся из канала R.

**Extensions.**

| Подсистема | Используется игрой? |
|---|---|
| `CCBReader`, `CCNodeLoaderLibrary`, `CCBAnimationManager` | **есть и используются** |
| CCControl*, CCEditBox, CCScale9Sprite, WebSocket, CocoStudio (Armature и GUI), Spine, AssetsManager, Box2D, Chipmunk | вызовов из игры не найдено |
| `CCHttpClient` | только скачивание event-пакетов (`RjFileDownloader`) и мёртвый `SendAuth` |

**CCB.**
- `CRjInterface::CRjInterface` регистрирует загрузчики `CCProgressTimer`, `CCLabelTTF`,
  `CCLabelTTFLocalized`, `CCScrollListView`, `CCCheckBox`, `CCTextButton`, `CCTableNode`,
  `CCSpriteBatchNode`, `CCTextLayout`, `CCNodeSelector` (xref).
- Файлы читаются через `CRjInterface::CreateFromFile/CreateFromData` → `CCBReader`.
- Все 306 `.ccbi` — магия `ibcc` и **версия 5** (декодирование Elias-gamma в заголовке). Это
  совпадает с `kCCBVersion` в 2.2.
- **Ответ: да, ccbi читаются стандартным ридером плюс 10 кастомных загрузчиков.**
- Типы узлов по всем ccbi: CCNode, CCSprite, CCLabelTTF, CCMenu, CCMenuItemImage, CCTextButton,
  CCTextLayout, CCNodeSelector, CCSpriteBatchNode, CCScrollListView, CCTableNode, CCLayer,
  CCLabelTTFLocalized, CCProgressTimer, CCCheckBox, CCLayerColor, CCScrollView, CRjScrollListView,
  CCControlButton (1 раз).
- Частиц, Scale9 и BMFont в ccbi нет.

### 3.2 Собственные классы

- **`inferno::`** (243 scope, `classes_inferno_ns.txt`) — серверная логика:
  - `User` (66 методов), `CRequestHandler` (34 метода `command*`), `LocalGameContext`;
  - `configuration::*` (41 класс: `LogicConfiguration`, `Building`, `Unit`, `Soldier`, `Behavior`,
    `Mission`, `BattleFieldMap`, `CityScript`, `GlobalParams`, `Jackpot`, `SlotMachine`, `Auction`…);
  - `Simulator`, `Field`, `Entity*` + компоненты, `UserEvent*` (29 событий);
  - копия скриптовой VM (`*Operator`, `*Condition*`), действия города (`GiveItem`, `TakeItem`,
    `StartTiming`, `ModifyTicker`, `ApplyPerk`…) и условия (`BuildingCountGE`, `DateL`,
    `SecondsHavePassedE`…).
- **Глобальный namespace, клиент** (`classes_game_global.txt`): сцены, бой, город, ≈75 диалогов,
  библиотеки данных, системы, протокол, сохранения, соцсети. Модули описаны в §4.

---

## 4. Карта архитектуры

### 4.1 Слои (по графу вызовов и xref)

```
 Java (Cocos2dxActivity, billing, FB, GPGS, push)            ── JNI ──┐
 ┌──────────────────────────── libinferno.so ─────────────────────────┴──────────┐
 │ UI: CRjInterface (CCBReader + 10 loaders), ~75 Rj*Dialog/Popup, 306 .ccbi     │
 │     CityScene / BattleScene / ChaptersScene / RjPreloader                     │
 │ Клиентская модель: LocalWorldModel ─ 46 *Library + Localization (pugixml)        │
 │     GameSystem<Key,T,LocalWorldModel> ×26 + Broadcaster<T> (observer)         │
 │     City (колония), QuestSystem+RequirementSystem, InvasionSystem, Spaceport… │
 │ Бой (клиент): CRjGame ─ CRjUnit(FSM) ─ CRjMapObject ─ Component* ─ script VM  │
 │     IsometricMap(A*) ─ CRjBatleScheduler ─ CRjGlobalAbility(пушки)            │
 │        │ команды (pugi XML)                          ▲ события (XML)         │
 │ RjCommander ─► RjCommandProxy::CheckSend ─► [локально] inferno::CRequestHandler::handle(ctx, req, resp)
 │                                                     │                         │
 │ «Сервер»: inferno::User ─ configuration::LogicConfiguration(config/server.xml, rapidxml)
 │     CityScript(actions) ─ city conditions ─ timers/tickers ─ contracts ─ territories
 │     [мёртвое в 1.3.12] Simulator/Entity*, BattleRoom/Battle, Pvp, Jackpot, SlotMachine, Auction
 │ Персистентность: LocalGameContext → saveProfileLocal → profile.xml; mailbox.xml; CCUserDefault
 └───────────────────────────────────────────────────────────────────────────────┘
```

**[Ф] Путь команды.**
1. `RjCommander::request*` строит `pugi::xml_document` и вызывает `RjCommandProxy::SendCommand`, та
   ставит его в очередь.
2. `CheckSend()`: `xml_document::save`, атрибуты `auth_key`/`sid`/`uid`, затем
   `LocalGameContext::instance()` и `CRequestHandler::needServerAuth()`. Эта функция всегда возвращает
   `false`. `CheckSend` не зовёт `CCHttpClient::send`; его зовёт только `SendAuth`.
3. `RjCommandProxy::update` → `processResponseData` → разбор pugi →
   `RjConnection::ProcessResponce(worldModel, RjConnectionData)`.
4. Дальше срабатывают зарегистрированные `*Parser` и `*Handler::process(LocalWorldModel, data)`.

Конструктор `RjCommandProxy` грузит `config/server.xml` в `LogicConfiguration` и создаёт
`CRequestHandler`.

### 4.2 Модули: классы, код, данные

| Модуль | Ключевые классы | Код* | Данные |
|---|---|---:|---|
| **Бой, клиент** | `BattleScene` (88 методов), `CRjGame` (97: update, loadMission, waypoints, defend, schedule…), `CRjUnit` + FSM `Think/Moving/Action/Dying/Dead State`, `CRjMapObject` (все операторы DSL как методы), `CRjTurret`, `CRjPlayer`, `CRjBatleScheduler`, `CRjGlobalAbility`, `CRjMapEffect{Curse,Totem,Voodoo}`, `RjEffect/RjTracer/RjEffectController`, `ComponentHealth/Position/Cooldowns/Variables/ScriptExecutor`, `RjBattleSaver` | ≈62 КБ + сцена 66 КБ | missions/*.xml, maps/*.xml, soldiers, units, turrets, effects, behaviors, splatters, tracers_scheme, cruising_guns, guns_shaders, rage |
| **ИИ / поведения** | VM: `ScriptOperator{If,While,Sleep,Halt,Animation*}`, `*Operator` (Damage, Heal, Cast, CastVisual, Stun, Spawn, Query{Target,TargetsInArea,TargetsInSector,Friends}, CooldownStart/Stop, Variable{Set,Inc,Dec}, AddSplatter/AddTracer, SwapLayer, ShakeScreen, GunBoost, ApplyShield), условия (DistanceToTarget, Health, TargetHealth, Variable, Item — по 5 сравнений E/G/GE/L/LE; OnCooldown, HasAbility, CanShootTarget, And/Or/Not). Парсер `BehaviorLibrary::loadScript/loadScriptCondition` | ≈16 КБ (VM) + 10 КБ (парсер) | behaviors (362). Блоки `attack`, `effect`, `die`, `idle`, `charge`; soldier ссылается через `attack_behavior`/`defend_behavior`, effect и turret — через `behavior` |
| **Способности** | `AbilityLibrary` (только визуал), `StatsData::abilities`, `HasAbility` | мало | abilities (180): ни один id не упомянут в коде; 48 проверяются через `has_ability` в поведениях; «технологии» — это abilities из `unit/stuff/thing` |
| **Эффекты** | `EffectLibrary` (class = totem/curse/voodoo, behavior, time, pct, stats) → `RjMapEffect*` (клиент), `inferno::Entity{Totem,Curse,Voodoo}` (сервер) | мало | effects (264) |
| **Колония** | `City` (94), `CityScene` (113), `IsometricMap`, `RjCityRoads`, `CRjObjectBuilder` (генерирует свет и тени), `BuildingSystem`, `ContractSystem`, `TimingSystem`, `TickerSystem`, `TerritorySystem`, `ResourceSystem`, `ItemSystem`, `IndicatorSystem`, `CitizenSystem`+`RjCitizen`, `InvasionSystem`, `SpaceportSystem`, `ExpendableSystem`, `CruisingGunSystem`, `UnitSystem`, `PerksSystem`, `TaxSystem` | ≈174 КБ | buildings, contracts, timings, tickers, territories, citizens, invasions, spaceport_store, expendables, taxes, scenes, decorations (не читается) |
| **Экономика (авторитет)** | `inferno::User` (constructBuilding, upgradeBuilding, start/collect/removeContract, skipTimer, exploreTerritory, give/take/setItem, applyPerk, executeAction, updateTimersRelatedStuff…), `configuration::CityScript`, city conditions | ≈177 КБ (весь `inferno` без боя) | **server.xml**: actions (2 431), requirements, timings, contracts, buildings, units, items, tickers, perks, global_params, initial_users, ladders, interactions |
| **Квесты / требования** | `QuestSystem`, `Quest`, `QuestLibrary`, `RequirementSystem`, `RequirementLibrary::createCondition`, 45 `Condition*`, 41 `Provider*`, 27 `Task*`, `ConditionGroups`, `AchieveSystem` | ≈79 КБ | quests (2 355), requirements (5 105), achievements, sharings. Сабмит квеста → `execute_action <имя>` → action из server.xml |
| **Миссии / кампании / галактика** | `MissionLibrary::parseMission/parseWaypointOperator`, `MapLibrary::parseMap`, `ChaptersLibrary`/`ChaptersScene`/`Campaign`, `RjWorldDialog`, `StarSystem*`, `Explorers*` (экспедиции), `InvasionSystem` | — | chapters, missions, maps, star_systems, territories, explorers, invasions. Награды: `parseItemActions` (give_item/take_item/give_item_random) → `City::orderResource`/`takeItem` |
| **Туториал** | `TutorialLibrary`, `TutorialExecutor`, `TutorialLayer`, 21 `TutorialOperator*` | ≈8,5 КБ | tutorials (12) |
| **Сохранения** | `RjSaveManager`, `saveProfileLocal`, `RjSavedGames`/`GPGSManager`/`RjSnapshot`/`RjSavedGameData`/`RjSavedGameMeta`, `RjBattleSaver`, `NotificationSystem::save`, `RjFixes` (миграции) | ≈28 КБ | — |
| **Сеть / протокол** | `RjCommander` (46 методов), `RjCommandProxy`, ≈40 классов `*Parser` и столько же `*Handler`, `RjConnection`, `RjOfflineChecker`, `RjFileDownloader`/`RjEventsManager`/`RjPackageManager` | ≈39 КБ | — |
| **Соцсети** | `RjSocialManager`, EziSocial (FB), `twitCurl`/`oAuth` (Twitter), `GPGSManager` (ачивки, снапшоты), `RjAchievementManager`, `RjFriendsDialog`, `RjSocialQuests*` | ≈53 КБ | sharings, global_params (vip_bar, invite…) |
| **Платежи** | `avalon::payment::*`, `RjInAppManager` (`config/payment.ini`), `RjBuyCreditsDialog`, `RjOfferDialog` | ≈25 КБ | offers, order_prices, packs, credits (не читается) |
| **Аналитика / пуши** | `RjAnalyticsManager`, `RjGAHandler` (GA UA-55973659-1), `RjParseHandler` (Parse), Adjust (`adjust_events.xml`), `RjPushManager` | ≈16 КБ | тег `analytics_submit_event` повсюду |
| **UI и локализация** | `CRjInterface`, ≈75 `Rj*Dialog/Popup`, собственные виджеты (`CCTextButton`, `CCTextLayout`, `CCNodeSelector`, `CCTableNode`, `CCCheckBox`, `CRjScrollListView`, `CCLayerPanZoom`, `CCMaskSprite`…), `LocalizationLibrary` (формулы, склонения, время) | ≈470 КБ (самый большой модуль) | interface/*.ccbi, locales, notifications |
| **Звук** | `CRjSoundSystem` → `FSoundManager` (FMOD, эффекты) + CocosDenshion (музыка) | ≈20 КБ | sounds, sound_schemes |

\* Сумма размеров экспортированных функций (`modules_map.txt`). Thumb — примерно 2 байта на инструкцию.

### 4.3 Связь кода с данными

**Секции config и загрузчики.** `section_coverage.tsv`. Библиотеку определяет строка из
`*Library::getDataType()`, серверную часть — `LogicConfiguration::loadFromNode`.

| Секция | Клиент | Сервер | Примечание |
|---|---|---|---|
| behaviors, buildings, contracts, effects, expendables, interactions, items, ladders, perks, requirements, soldiers, territories, tickers, timings, turrets, units | ✓ | ✓ | общие документы: в XML стоят `client="1" server="1"` |
| abilities, achievements, catalogs, chapters, citizens, cruising_guns, explorers, guns_shaders, indicators, invasions, maps, missions, notifications, offers, order_prices, packs, quests, rage, resources, scenes, sharings, sounds, sound_schemes, spaceport_store, splatters, star_systems, taxes, tracers_scheme, tutorials | ✓ | (maps и missions сервер умеет парсить, но в server.xml их нет) | только клиент |
| **actions** (112 документов, 2 431 action), league_stage_technologies | — | ✓ (только actions) | **только server.xml** |
| global_params, initial_users | — (клиент берёт их через синглтон серверного конфига) | ✓ | `ticks_per_second` = 30 читает `inferno::configuration::GlobalParams` |
| **defense_technology_boosts** | ✗ | — | **несовпадение**: `DefenseBoostsLibrary` ждёт секцию `defense_boosts` и атрибут `soldier_type`, а в данных `defense_technology_boosts` и `squad_type` |
| credits, decorations | ✗ | ✗ | ни имени секции, ни её атрибутов в бинарнике нет — мёртвые данные |
| currency_groups, galaxies, stars | — | — | пустые |

**Теги и атрибуты** (`config_names_vs_binary.txt`, `serverxml_names_vs_binary.txt`,
`xmldirs_names_vs_binary.txt`):
- `config.json`: найдено 224 из 238 имён атрибутов и 344 из 1 133 тегов.
- Большинство «отсутствующих» тегов — это данные в роли тегов: 499 из 528 тегов catalogs — имена
  товаров; также коды стран в order_prices и названия тем в sound_schemes. Библиотеки обходят детей
  без проверки имени.
- Миссии, карты и visuals покрыты почти полностью: атрибутов 38/41, 26/27, 12/12.

**Семантические теги в данных, которых нет в словаре парсера** (кандидаты на «игнорируется кодом»):
- **behaviors:** `animation_set` (52 раза), `animation_current` (47), `has_voodoo`. Их нет в словарях
  `BehaviorLibrary::loadScript`/`loadScriptCondition` (проверено по xref).
- missions: опечатка `sllep`.
- server actions: `social_set_user_level`, `on_interact`.
- атрибуты: `unlock_upgrade_requirement`, `squad_type`, `related_item`, `item_level`,
  `swap_trade_area`, `min_count`/`max_count`, `rating_*`, `photo_url`, `extra`, `popular`,
  `sharing_quest`, `level_end`.
- **[Г]** Такие узлы молча пропускаются. Поведение `if` с пустым условием нужно проверить в Ghidra.

**DSL, восстановленные по парсерам** (`dsl_vocabularies.txt`):
- **Поведения (клиент).** Операторы: `if/condition/then/else`, `while/do`, `sleep`, `return`,
  `animation_{if,play(type,frame),cooldown(time),random(type,list),stop}`, `apply_shield(pct,time)`,
  `add_splatter_to_target(type)`, `damage(type=long|short, pct; <damage_type>*)`, `heal(amount)`,
  `cast(effect, inherit_stats)`, `cast_visual(effect, self_target)`, `stun(time)`,
  `spawn(x,y,defend,direction)`, `cooldown_start(cooldown,time)`, `cooldown_stop`,
  `add_tracer_to_target(type,duration,blink)`, `variable_{set,inc,dec}(variable,value)`,
  `query_target`, `query_targets_in_area(range)`, `query_targets_in_sector(range,angle)`,
  `query_friends(range)`, `swap_layer(staged)`, `gun_boost`,
  `shake_screen(start_value,end_value,time)`.

  Условия: `and/or/not`, `distance_to_target_*`, `health_*`, `target_health_*` (health_pct),
  `variable_*`, `item_count_*`, `can_shoot_target`, `is_on_cooldown`, `has_ability`.
- **Поведения (сервер).** Тот же язык без визуальных операторов.
- **Действия города (сервер, CityScript).** `give_item(item,count,respect_limits,silent)`,
  `give_item_random`, `take_item`, `set_item`, `move_item`, `move_day_in_item`, `start_timing`,
  `start_ticker`, `stop_ticker`, `modify_ticker(ticker,interval,time)`, `apply_perk`, `remove_perk`,
  `jackpot_add`, `send_notification`, `analytics_submit_event`.
- **Условия города.** `and/or/not`, `date_*`, `building_count_*(building,level,end_level,count,strict)`,
  `indicator_*`, `item_count_*`, `level_*(ladder)`, `seconds_have_passed_*`, `unit_level_*`,
  `is_contract_producing`, `is_requirement_granted`, `is_territory_explored`, `is_timing_in_progress`.
- **Туториал.** 21 оператор: `show_arrow`, `focus_area`, `move_camera`, `wait_for_waypoint`,
  `set_guns`…

**Зашитые id** (`hardcoded_ids.txt`): 144 из 13 192.
- 4 пушки `air_strike`, `gravibomb`, `artillery`, `orbital_hit` — в `CRjGame::init` и жестах
  `BattleScene`.
- Ресурсы: `credit`, `metal`, `crystal`, `fuel`, `experience`, `influence_points`…
- Здания с особыми окнами: `base`, `factory`, `bar`, `research_station`, `upgrader_*`, `spaceport`,
  `invasion_house`.
- Туториалы `tutorial_01_mission`, `tutorial_02_mission`, `star_1_mission_01`/`_03`.
- 11 типов уведомлений; категории каталога UI; сплэттеры `shield`, `hero`, `champion`,
  `mob_teleport`; тикеры `expendables_wait`, `spaceport_store_update`; `city_1`.

**Квесты и server.xml.** Все 2 355 ссылок `quest/actions/submit` указывают на `<action type>` в
`server.xml` (2 355/2 355).

---

## 5. Сохранения и сеть (для офлайн-версии)

### 5.1 Сохранения [Ф]

| Что | Где и как | Формат |
|---|---|---|
| **Профиль игрока** (авторитетное состояние) | `RjSaveManager::saveProfile` → `saveProfileLocal(name, …)` → `fopen(… ".xml","w")`/`fwrite`. Имя — `profile.xml` в writable path. Данные из `LocalGameContext`, сериализация `inferno::User::serializeToNode` (rapidxml) | **Открытый XML** без шифрования и сжатия (у `saveProfileLocal` вызовы только `fopen`/`fwrite`/`fclose`/`time`). Узлы: `user` → `battle`, `buildings/building(id,x,y,level,direction,construction_timing_id)`, `contracts/contract(building_id,production_timing_id)`, `interactions`, `items`, `mission`, `notifications`, `perks`, `pvp`, `scheduled_events`, `slot_machine`, `territories(exploration_timing_id)`, `tickers/ticker(till_time,last_tick_time,interval)`, `timings/timer(start_time,finish_time)`, `sid`, `uid` |
| Новый игрок | `LocalGameContext::getGameData` → `getInitialUser` | секция `initial_users` / `global_params/default_user` |
| Почта / уведомления | `NotificationSystem::save/load` (pugi) → `mailbox.xml` | XML с `hash` |
| Клиентские флаги и состояние | CCUserDefault (на Android это `shared_prefs/Cocos2dxPrefsFile.xml`); ≈96 игровых функций обращаются, 68 из них пишут | ключи: состояние вторжений (`InvasionSystem::save`), сиды магазинов и наёмников, экспедиции, «новое», звук, туториалы, `first_inferno_start`… |
| Чекпойнт боя | `RjBattleSaver::writeToDisk/loadFromDisk` → `last_waypoint.xml` | XML: `mission_type`, `waypoint_id`, `tick_counter`, `players`, `units`, `indexed_objects`, `logic_defend_points`… Waypoint с `restore_cost` позволяет продолжить за плату |
| Облако | `saveProfileRemote` → `GPGSManager::SaveSnapshot` | `RjSavedGameData::createSnapshot` = profile.xml + mailbox.xml + userdefaults с длинами + **CRC32** (`RJCrypt::RJGetCRC32`); мета: уровень, жители, оборона, влияние, устройство, дата |
| Event-пакеты | `RjEventsManager::save` | XML: `version`, `downloaded`, `unpacked`, `checksum_sd/hd`, `expired_time` |

`RJCrypt` (MD5, RSA, «мусор», Base64) из кода сохранений не вызывается. `<пароль из бинарника — не публикуем>` —
пароль zip `info.zip` для письма в поддержку (`RjEmailHelper::saveInfo`). **SQLite нет**:
`Cocos2dxLocalStorage` существует только в Java-обвязке cocos.

### 5.2 Протокол команд [Ф]

**Активные команды** — есть call-sites (`RjCommander::*`):
- `get_game_info`, `update`/`echo`;
- `construct_building(type,x,y,direction,instant)`, `move_building`, `remove_building`,
  `upgrade_building(id,instant)`;
- `start_contract`, `collect_contract`, `remove_contract`;
- `skip_timing(id)`, `explore_territory`;
- `execute_action(type)` — квесты, паки, экспедиции, магазин; `order(order_type)` — офферы;
- `admin_give_item`, `admin_take_item`, `cheat_set_item(item_type,amount,target_uid)` — клиент
  напрямую меняет ресурсы, в том числе **награды миссий**.

**Мёртвые в 1.3.12** — полный линейный проход по `.text` не нашёл ни одного BL:
`start_mission`, `finish_mission`, `fail_mission`, `prepare_mission`, `pvp_*`, `battle_sign_up`,
`get_battle_room`, `auction_*`, `jackpot`, `slot_machine_*`, `interact`, `rating_top`,
`produce_contract_instantly`, `get_user_info`, `cheat_change_user_scheme`.

**Следствие.** Серверный `Simulator` — повтор боя с проверками `Ticks mismatch.`/`Too fast.`,
вызывается только из `User::finishMission`. PvP, джекпот, аукцион и слот-машина недостижимы. В
server.xml нет миссий, а `getMission` бросает `ConfigError` на неизвестной миссии — ещё одно
подтверждение, что PvE-миссии идут мимо сервера.

**События сервера → клиент.** `init_game`, `building_{created,moved,removed,upgrade_started,upgraded}`,
`contract_{started,finished,removed,collected}`, `timing_{started,finished}`,
`ticker_{started,modified,finished}`, `territory_{exploration_started,explored}`, `item_count_changed`,
`perk_{applied,removed}`, `notification`, `current_time_changed`, `mission_{updated,finished}`,
`pvp_*`, `slot_machine_updated`, `interaction_*`, `unknown_user`, `echo`.

### 5.3 Что уходило в сеть

| Направление | Статус |
|---|---|
| Игровой сервер `http://10.0.1.184:10000` (команды) и `:10015` (авторизация, `mobile_id`) | адреса внутренней сети, в релизе недостижимы (`needServerAuth()=false`) |
| CDN `http://media-r05and.rjgplay.com/` | event-пакеты (`version.xml`, `.zip`, `patch`, контрольные суммы) и OBB. **[Г]** Часть событийного контента могла приходить только отсюда; нужно сверить с OBB |
| Остальное | Google Play Billing, Play Games (ачивки, облако), Facebook/Twitter, Parse, GA, Adjust, push |

`RjOfflineChecker` блокирует только покупки, соцквесты и облачные сохранения. **Для офлайна нужен
только локальный «сервер» (User + server.xml) и персистентность; сетевой протокол можно выбросить,
сохранив формат событий как внутреннюю шину.**

---

## 6. Что восстанавливается по данным и именам, а что — только реверсом

**Без дизассемблера** (данные + имена + xref):
- Полная структура данных и DSL поведений, эффектов, действий и условий; кто что парсит.
- Какие секции и атрибуты живые, а какие мёртвые.
- Граф модулей и точные точки входа.
- Протокол команд и событий, формат сохранений.
- Список пушек, ресурсов и спецзданий, завязанных на код.
- `ticks_per_second` = 30; детерминизм боя (§0 п.7).

**Только кодом** — формулы и порядок исполнения:
- семантика каждого оператора: выбор цели в `query_*`, дальность, сектор, приоритет; что делает
  `cast` с `inherit_stats`; стакинг эффектов;
- движение: `IsometricMap` A*, `inferno::Field::move` (зоны, порталы, занятость тайлов);
- FSM юнита (`CRjUnit::ThinkState::update` — 1 028 байт) и шаг исполнения скрипта за тик;
- `CRjBatleScheduler::Process` (волны, слоты), логика waypoint/defend в `CRjGame`;
- `CRjGlobalAbility` (пушки: заряд, кулдаун);
- экономика `inferno::User` (таймеры, производство контрактов, skip, лимиты `respect_limits`);
- формулы описаний `LocalizationLibrary::getFormulaResult`.

**Пример: насколько это дёшево.** Две функции прочитаны в `llvm-objdump` за минуты.
- `CRjMapObject::calculateDamage` (30 байт): `damage = max(stat,0) * pct / 100`, где `stat` —
  `long_attack` при type=long, иначе `short_attack`.
- `ComponentHealth::receiveDamage` (198 байт):
  1. если `hp ≤ 0` — выход;
  2. щит поглощает `min(dmg, shield)`; при обнулении щита сбрасывается его таймер;
  3. `total = dmg`, если набор `damage_type` пуст, иначе `Σ dmg·(100+sensitivity[type])/100` по
     каждому типу, где `100+s > 0`; при `s ≤ −100` тип даёт иммунитет — отсюда в данных `-1000`;
  4. `hp = max(hp − total, 0)`, затем колбэк смерти или урона.

**Оценка объёма реверса.** Весь боевой код клиента — ≈62 КБ, сцена и карта — 66 КБ, VM — 16 КБ;
серверный симулятор — ещё ≈37 КБ как чистый «эталон без графики». Это ≈1 300 экспортированных функций
среднего размера 100–600 байт, и **все с именами и сигнатурами**. Ghidra сама подхватит `.dynsym` и
деманглинг GNU, а `.ARM.exidx` даст границы функций.

**Полный дизассемблер (Ghidra headless)** полезен точечно, а не для всего подряд:
- декомпилировать `CRjMapObject::*`, `CRjUnit::*State::update`, `CRjGame::update`/waypoints,
  `CRjBatleScheduler`, `CRjGlobalAbility`, `IsometricMap::getNearDestinationAStar`,
  `Component*`, `inferno::User::*` (экономика), `LocalizationLibrary` (формулы);
- восстановить раскладку полей: смещения вроде `+0x5c` у stats;
- проверить обработку неизвестных тегов DSL.

Реверсить не нужно: cocos2d, Crypto++, OpenSSL, gpg — около 70 % кода.

---

## 7. Выводы для стека

**Что реально использует игра** (прямые вызовы из игровых функций, `cocos_subsystems_usage.txt`):

| Используется | Не используется (прямых вызовов нет) |
|---|---|
| CCSprite (33 функции), CCSpriteBatchNode (IsometricMap), CCSpriteFrameCache (14, свой формат `.atlas` → frames), CCLabelTTF (63), CCMenu/MenuItemImage, actions (23: Move/Scale/Fade/Sequence…), CCAnimation/CCAnimate (кадровые анимации из `visuals/*.xml`), CCProgressTimer, CCRenderTexture (IsometricMap, скриншоты), CCGLProgram/ShaderCache (`CCMaskSprite`, `RjShaderEffectAction`: 9 шейдеров из assets + ETC-альфа), CCScrollView/TableView (через `CRjScrollListView`), CCBReader + CCBAnimationManager (таймлайны в 17 местах), CCUserDefault (96), CCTextureCache, kazmath, CocosDenshion (музыка) + FMOD (эффекты) | частицы (ни в коде, ни в ccbi), CCLabelBMFont, TMX, CCDrawNode, CCClippingNode, CCMotionStreak, CCScale9Sprite, CCControl*, CCEditBox, WebSocket, CocoStudio, Spine, AssetsManager, Box2D, Chipmunk, CCRjArchive, переходы сцен |

**Перенос, по порядку выгоды:**

1. **Логика (≈2/3 работы)** не зависит от движка. Это сервер (User + server.xml actions/conditions +
   таймеры), клиентские системы и квесты, VM поведений, бой. От cocos2d в ней нет ничего, кроме
   `CCPoint`.
2. **UI** — 306 ccbi и ≈75 диалогов; здесь семейство Cocos помогает.
   - **cocos2d-js / cocos2d-html5 3.x** — тот же API (`cc.Sprite`, `cc.SpriteBatchNode`,
     `cc.RenderTexture`, `cc.GLProgram`, `cc.ProgressTimer`, `cc.Menu`), штатный `cc.BuilderReader`
     для ccbi v5 и `CCBAnimationManager`. **[Г]** по исходникам cocos2d-js, в этой сессии не
     проверялось. Можно почти механически переносить код диалогов по именам классов. Минусы: движок
     не развивается с ~2019 г., WebGL1, слабая типизация. ETC и свой `.atlas` всё равно придётся
     конвертировать.
   - **Cocos Creator 2.x/3.x** не импортирует ccbi, архитектура «редактор + компоненты» —
     преимуществ перед Pixi/Phaser почти нет.
   - **PixiJS / Phaser 3** — нужен свой конвертер `ccbi → JSON` и плеер CCB-таймлайнов
     (sequences, keyframes, easing, callback- и sound-keyframes); ≈1–2 недели. Плюс 7 собственных
     виджетов RJ. Actions ≈ tweens Phaser, шейдеры ≈ фильтры Pixi, изометрия и свет/тени пишутся
     заново в любом движке.
3. **Ассеты** — конвейер одинаков для всех: `.pkm.ccz` → PNG (ETC1, альфа из R нижней половины), `.atlas` → JSON или plist,
   `visuals/*.xml` → анимации, звук → WebAudio. FMOD здесь — простой плеер wav.

**Рекомендация [Г].**
- Phaser 3 (как в Under Control) или PixiJS плюс тонкий «cocos-подобный» слой:
  узлы/anchor/zOrder, actions, CCB-loader.
- cocos2d-js 3.17 — как инструмент: быстро открыть ccbi, посмотреть вёрстку и сверить конвертер.
- Выигрыш Cocos-семейства ограничен UI-слоем. Его перевешивают поддерживаемость и единый стек с
  Under Control.

---

## 8. Рекомендации проекту (следующие шаги)

1. Расширить `tools/parse_config.py`: читать `server.xml` (actions, серверные requirements, timings,
   `global_params`, `initial_users`), а также `missions/*.xml`, `maps/*.xml`, `visuals/*.xml`. Без
   actions награды квестов неизвестны.
2. Взять `dsl_vocabularies.txt` как спецификацию интерпретаторов. Реализовать VM поведений,
   CityScript и условия. Неизвестные теги `animation_set`, `animation_current`, `has_voodoo`
   пропускать, пока Ghidra не покажет точную семантику.
3. Модель сохранения — перенести `profile.xml` (схема в §5.1) + key-value (аналог CCUserDefault) +
   mailbox в IndexedDB. Импорт настоящих сейвов с Android возможен напрямую: XML открытый.
4. Точечный реверс в Ghidra по списку из §6: бой, экономика `User`, формулы локализации.
5. Сверить event-пакеты CDN с содержимым OBB (§5.3).

---

## 9. Файлы в `research/native/`

| Файл | Содержимое |
|---|---|
| `bin/` | извлечённые `libinferno.so`, `libfmod.so`, `libgnustl_shared.so`, `classes.dex`, `AndroidManifest.xml` |
| `syms_defined_raw.txt`, `syms_defined_sized_raw.txt`, `syms_undefined_raw.txt` | сырой вывод `llvm-nm -D` |
| `syms_defined.tsv` | адрес, размер, тип, mangled, demangled |
| `syms_undefined_demangled.txt` | импорты |
| `symbols_all_grouped.tsv` | все символы с группой, классом и членом |
| `symbols_namespace_counts.txt` | счётчики по namespace и C-библиотекам |
| `classes_cocos2d.txt`, `classes_inferno_ns.txt`, `classes_game_global.txt`, `classes_thirdparty.txt` | классы → методы |
| `modules_map.txt` | модули → классы → размер кода |
| `cstrings.tsv`, `strings_all.txt` | строки с адресами и `strings -a` |
| `source_paths.txt` | пути исходников из строк |
| `xref_strings.tsv`, `callgraph.tsv` | функция → строка и граф вызовов, лёгкий Thumb-скан |
| `config_names_vs_binary.txt`, `serverxml_names_vs_binary.txt`, `xmldirs_names_vs_binary.txt` | сверка данных с бинарником |
| `section_coverage.tsv` | секция → клиентская и серверная загрузка |
| `hardcoded_ids.txt` | зашитые id и кто их использует |
| `dsl_vocabularies.txt` | словари всех XML-DSL по парсерам |
| `cocos_subsystems_usage.txt` | какие подсистемы cocos зовёт игра |
| `dex_classes.txt`, `dex_strings.txt` | Java-классы и строки DEX |
| `scripts/` | все скрипты анализа (только stdlib python3) |
