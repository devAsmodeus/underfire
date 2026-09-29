# Выбор движка для браузерной реконструкции Under Fire: Invasion

Дата обзора: **29.09.2026**. Версии, даты релизов, звёзды и загрузки проверены в этот день через GitHub API,
npm registry, bundlephobia и официальные сайты. Ссылки даны в тексте и собраны в разделе «Источники».
Цифры по самой игре получены из `raw/` и APK (только чтение). Баллы 0–5 и выводы — моя экспертная оценка,
она помечена как оценка.

Черновые данные: `scratchpad/research/engines/` (`npm_meta.txt`, `gh_repos.txt`, `gh_releases.txt`,
`scores.py`, `ccbi_paths.txt`).

---

## 0. Коротко

**Рекомендация — PixiJS 8** (сейчас [8.21.0 от 17.09.2026](https://github.com/pixijs/pixijs/releases/tag/v8.21.0))
**+ TypeScript + Vite.** Поверх него нужен тонкий собственный слой «cocos-совместимости»: узел с
anchorPoint и contentSize, actions, сборщик сцен из ccbi, виджеты. **Запасной вариант — Phaser 4**
([4.2.1 от 09.07.2026](https://github.com/phaserjs/phaser/releases/tag/v4.2.1)).

| # | Кандидат | Итог (из 100, оценка) | Вердикт |
|---|---|---:|---|
| 1 | PixiJS 8 + TS + свой каркас | **90** | Рекомендую |
| 2 | Phaser 4 | **82** | Запасной вариант, «всё включено» |
| 3 | Phaser 3.90 | 79 | Заморожен с 05.2025, для нового проекта это тупик |
| 4 | Cocos Creator 3.8 / Cocos 4 | 72 | Семантически ближе всех, но привязан к редактору; Cocos 4 пока альфа |
| 5 | Axmol 2.11 (cocos2d-x → WASM) | 69 | Точный API cocos2d-x, но C++/WASM и тяжёлый цикл сборки |
| 6 | Godot 4.7 | 66 | Нет TS, wasm ≈40 МБ, у Safari проблемы с WebGL2 |
| 7 | cocos2d-html5 (Cocos2d-JS 3.17) | 57 | Код заброшен в 2018 г.; пригоден только как эталон для порта CCBReader |
| 8 | Defold 1.13 | 56 | Lua и работа через редактор; у GUI только 9 фиксированных pivot |

Почему именно PixiJS:
1. **Граф сцены устроен как в cocos2d-x.** `Container.pivot` работает как anchorPoint×contentSize: позиция
   узла — это проекция pivot в систему координат родителя. Экспериментальный `Container.origin` задаёт
   центр вращения и масштаба без сдвига позиции, что соответствует `ignoreAnchorPointForPosition`
   ([API Container](https://pixijs.download/release/docs/scene.Container.html)). Поэтому для переноса
   145 макетов ccbi достаточно пересчитать ось Y.
2. **Лучшее сочетание code-first и знания API моделями.** Исходники на TS, лицензия MIT, релизы раз в
   1–2 месяца. Есть 25 официальных skills для ИИ-агентов (с 8.19 они лежат прямо в npm-пакете) и
   llms.txt ([блог, 12.06.2026](https://pixijs.com/blog/june-2026)). Пакет скачивают 1,24 млн раз в неделю.
3. **Лёгкий рантайм и контроль памяти.** Полный пакет весит 261 КБ gz. В продакшне работает WebGL2,
   WebGPU остаётся в запасе. KTX2/Basis поддерживаются штатно — это важно, потому что наш объём текстур
   в RGBA8 займёт гигабайты видеопамяти (см. §1).

Главные риски PixiJS: объём своего каркаса (оценка — 3–5 тыс. строк TS), изменения поведения в минорных
релизах, путаница моделей между API v7 и v8, нехватка памяти GPU в iOS Safari. Меры против них — в §6.

---

## 1. Что важно именно для Under Fire (проверено по `raw/` и APK)

- **Базовый движок — cocos2d-x 2.x, а не 3.x.** В `libinferno.so` 275 строк с типом `cocos2d::CCNode`
  и ни одной с `cocos2d::Node` из 3.x. Есть `CCTouchDispatcher` (система касаний 2.x с приоритетами
  и «проглатыванием»), `CCBReader` и `CCBAnimationManager`. Значит, переносить нужно семантику 2.x:
  приоритеты касаний у `CCMenu` и `CCLayer`, `CCAction`, таймлайны CocosBuilder.
- **Макеты ccbi.** В `raw/` 306 файлов, из них 177 уникальных путей: **145 уникальных макетов
  1024×768** (city 99, battle 32, worldmap 11, mainmenu 2, splashscreen 1) и 32 HD-копии в 2048×1536.
  **У всех 306 файлов формат версии 5.** Это совпадает с `CCB_VERSION = 5` в ридерах cocos2d-x
  2.x/3.x и cocos2d-html5.
- **Классы нод** (в скольких файлах из 306 встречается класс): `CCNode` 303, `CCSprite` 294,
  `CCLabelTTF` 257, `CCMenu` 240, `CCMenuItemImage` 217, `CCSpriteBatchNode` 65, `CCLayer` 48,
  `CCProgressTimer` 27, `CCControlButton` 1. Кастомные классы Inferno: `CCNodeSelector` 92,
  `CCScrollListView` 63, `CCTableNode` 50, `CCLabelTTFLocalized` 29, `CCCheckBox` 24,
  `CRjScrollListView` 3. **`CCScale9Sprite` и частиц в макетах нет**, поэтому 9-slice нужен разве что
  в коде.
- **Свойства:** `anchorPoint`, `ignoreAnchorPointForPosition`, `contentSize`, `position`, `scale`,
  `color`/`opacity`, `blendFunc` (87 файлов), `rotation` (25). «Default Timeline» есть в 301 файле,
  именованные таймлайны (`timelineShow`/`timelineHide` и др.) — в единичных.
- **Шрифты TTF:** Play-Bold (197 файлов), Play (144), Play_button (128), LiquidCrystal (66),
  a_SimplerDnm (18).
- **Шейдеры** (GLSL ES 1.0 с юниформами cocos `CC_Texture0`/`CC_MVPMatrix`): Grayscale, Monochrome,
  GaussianBlur (vert+frag), RadialBlur, Focus, Circle, Lines, Splash. У первых четырёх есть готовые
  аналоги в любом движке, остальные четыре небольшие и портируются вручную.
- **Анимации:** 1 156 файлов `config/visuals/**/*.xml`. Структура: `visual` (fps, атласы) →
  `direction` (префикс, смещение, размер) → `state` (run/idle/attack_*/die_*) → `layer` (номера кадров).
  Многослойную анимацию с 8 направлениями придётся писать самим на любом движке.
- **Атласы `.atlas`:** на каждый кадр строка `имя x y w h offX offY srcW srcH [r]`, где `r` означает
  повёрнутый кадр. Формат напрямую конвертируется в JSON TexturePacker, который читают и PixiJS, и Phaser.
- **Текстуры и видеопамять — главный технический риск для мобильных.** Моя оценка по заголовкам PKM:
  3 503 текстуры, 2 299 Мпкс в закодированном виде.
  - Все текстуры в ETC1, как в оригинале, заняли бы ≈1,1 ГБ VRAM.
  - После перекодирования в PNG/WebP браузер хранит их в GPU как RGBA8, и суммарно выходит **≈4,4 ГБ**.
    Это в 4 раза больше, чем у оригинала, где альфа лежит второй половиной ETC1, то есть 8 бит на пиксель
    против 32.
  - По категориям в RGBA8: maps ≈1,27 ГБ, buildings ≈1,09 ГБ, interface HD ≈605 МБ (SD ≈156 МБ),
  units ≈460 МБ, mobs ≈415 МБ, background ≈230 МБ, effects ≈75 МБ.

  PNG/WebP подходят только для передачи по сети. Для iOS Safari нужны загрузка и выгрузка по сценам,
  SD-набор (в оригинале он уже есть: `interface/1024x768_sd`) и **KTX2/Basis**. Поэтому поддержка сжатых
  текстур — реальный критерий выбора, а не формальность.

## 2. Чем наш случай отличается от Under Control

В обосновании Under Control (`../UnderControl/docs/engine-decision.md`,
22.09.2026) Phaser 3
выбран за соответствие Flash→Phaser один к одному, за TS и Vite, за бандл около 1 МБ против 30–40 МБ
у Godot, за удобный найм и за связку с Colyseus. К Under Fire эти доводы переносятся не все:

| Аргумент UC | Для Under Fire |
|---|---|
| Flash display list ≈ Phaser Container | **Не переносится.** Во Flash точка регистрации «запечена» в координаты детей, pivot нет, и Phaser Container с неизменяемым origin (0,0) ложится естественно. В cocos2d-x у узла есть anchorPoint + contentSize, вращение и масштаб идут вокруг anchor, координаты детей отсчитываются от левого нижнего угла content-box родителя, ось Y смотрит вверх. Это ровно модель `pivot` из PixiJS |
| Colyseus / сервер | Не нужен: игра офлайновая |
| DragonBones / SWFTY | Не нужен: у нас кадровые атласы и visuals XML |
| TS + Vite + маленький бандл против Godot | **Переносится полностью** |
| Кругозор разработчиков и ИИ | Переносится; у PixiJS и Phaser он сопоставим (§4) |

Попутно для UC: **Phaser 3.90.0 (23.05.2025) — последний релиз ветки v3.** Команда тогда писала, что
«this is likely the last version in the v3 tree» ([phaser.io](https://phaser.io/news/2025/05/phaser-v390-released)).
Phaser 4 стабилен с 10.04.2026. В документе UC указано «Phaser 3.90+», но версий 3.91+ не существует.

## 3. Статус кандидатов на 29.09.2026 (факты)

| Кандидат | Последняя версия (дата) | Лицензия | Язык и типы | Рендер в браузере | Рантайм (min / gz) | Популярность |
|---|---|---|---|---|---|---|
| **PixiJS** | [8.21.0](https://github.com/pixijs/pixijs/releases/tag/v8.21.0) (17.09.2026). В 2026 г. 7 минорных релизов, 8.15–8.21 | MIT | TS (исходники на TS) | WebGL/WebGL2 рекомендован для продакшна. WebGPU «feature complete», но в [документации](https://pixijs.com/8.x/guides/components/renderers) советуют WebGL. Canvas экспериментальный, с [8.16](https://pixijs.com/blog/8.16.0) | 913 КБ / **261 КБ** | 48,2k★; 1,24 млн загрузок npm в неделю |
| **Phaser 4** | [4.2.1](https://github.com/phaserjs/phaser/releases/tag/v4.2.1) (09.07.2026). 4.0.0 — 10.04.2026, 4.1.0 — 30.04, 4.2.0 — 19.06 | MIT | JS + сгенерированные `types/phaser.d.ts` | WebGL: новый рендерер на render nodes, поддержка WebGL2-контекстов, восстановление контекста. Canvas объявлен устаревшим ([23.04.2026](https://phaser.io/news/2026/04/phaser-4-renderer-faster-cleaner-and-built-for-modern-games)). WebGPU нет | 1,37 МБ / **356 КБ** | 40,4k★; 468 тыс. в неделю (все версии) |
| **Phaser 3.90** | 3.90.0 (23.05.2025), «вероятно, последняя в v3» | MIT | JS + d.ts | WebGL1/Canvas | 1,19 МБ / 315 КБ | — |
| **Cocos Creator / Cocos 4** | Creator [3.8.8](https://github.com/cocos/cocos-engine/releases/tag/3.8.8) (16.12.2025, LTS). Cocos 4 — `4.0.0-alpha.34` (20.09.2026) | Движок 3.x под MIT, редактор со своим EULA. Cocos 4 и cocos-cli полностью под MIT | TS | WebGL/WebGL2 ([бэкенды](https://docs.cocos.com/creator/3.8/manual/en/graphics-backend/overview.html)) | Пустой web-mobile ≈1,8 МБ ([форум, 2021](https://forum.cocosengine.org/t/cocos-creator-3-build-size/53154)). Для Cocos 4 открыт [issue](https://github.com/cocos/cocos4/issues/197) (11.07.2026) про движок в 33 МБ JS для простой 2D-сборки | 9,8k★ у cocos-engine |
| **cocos2d-html5 (Cocos2d-JS 3.17)** | Последний код — 16.04.2018. В README (2019–2020): «эволюционировал в Cocos Creator» ([repo](https://github.com/cocos2d/cocos2d-html5)) | MIT | ES5, глобальный `cc`, пакета v3 в npm нет | WebGL1/Canvas | — | 3,2k★ |
| **Godot** | [4.7.2](https://github.com/godotengine/godot/releases/tag/4.7.2-stable) (18.08.2026). 4.7 — 18.06.2026 | MIT | GDScript. C# на web не экспортируется | Только WebGL 2.0 ([docs](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)) | wasm ≈40 МБ, ≈**5 МБ brotli** (данные [4.3](https://godotengine.org/article/progress-report-web-export-in-4-3/)) | 117,9k★ |
| **Defold** | [1.13.1](https://github.com/defold/defold/releases/tag/1.13.1) (17.08.2026). 1.14.0-alpha — 10.09.2026 | [Defold License](https://defold.com/license/): на базе Apache 2.0, нельзя продавать сам движок | Lua (TS только через community) | WebGL1/2, по умолчанию 2 ([docs](https://defold.com/llms/manuals/html5/)) | wasm 2,39 МБ, бандл ≈1,3 МБ ([build-size](https://github.com/defold/build-size)) | 6,3k★ |
| **Axmol** | [2.11.5](https://github.com/axmolengine/axmol/releases/tag/v2.11.5) (25.09.2026) | MIT | C++23/Lua | WebAssembly + WebGL | Демо: fairygui-tests.wasm 4,2 МБ, cpp-tests.wasm 13,2 МБ без сжатия (HEAD-запрос, 29.09.2026) | 1,5k★ |
| Excalibur | [0.32.0](https://github.com/excaliburjs/Excalibur/releases/tag/v0.32.0) (23.12.2025) | BSD-2 | TS | HTML5 canvas | 571 КБ / 145 КБ | 2,3k★; 9,5 тыс. в неделю |
| melonJS | 20.7.0 (22.09.2026) | MIT | JS | — | 888 КБ / 262 КБ | 6,4k★; 1,6 тыс. в неделю |

Источники столбцов: версии и даты — GitHub Releases API и npm `time`; ★ — GitHub API; загрузки —
api.npmjs.org за 21–27.09.2026; размеры — bundlephobia (полный пакет) на 29.09.2026.

Про WebGPU: с ноября 2025 г. он есть во всех основных браузерах. Chrome/Edge — с версии 113, на Android —
с 121 (Android 12+, GPU Qualcomm/ARM). Firefox — с 141 (Windows) и 145 (macOS ARM). Safari — в macOS,
iOS и iPadOS 26 ([web.dev, 25.11.2025](https://web.dev/blog/webgpu-supported-major-browsers)). Для
нашей 2D-игры это только запас: достаточно WebGL2.

## 4. Сравнение по критериям (оценка)

Шкала 0–5, итог — взвешенная сумма в пересчёте на 100. Веса отражают приоритеты проекта: код пишет ИИ,
поэтому code-first и знание API весят больше всего.

| Критерий (вес, %) | PixiJS 8 | Phaser 4 | Phaser 3.90 | Cocos Cr. 3.8/4 | Axmol WASM | Godot 4.7 | cocos2d-html5 | Defold |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Поддержка 2025–26, лицензия (10) | 5 | 5 | 2 | 3 | 4 | 5 | 0 | 4 |
| TypeScript / типизация (10) | 5 | 4 | 4 | 5 | 3 | 2 | 1 | 1 |
| Рендер: батчинг, WebGL2/WebGPU (5) | 5 | 4 | 4 | 4 | 4 | 4 | 2 | 5 |
| Изометрия, сортировка, анимации из атласов (8) | 4 | 5 | 5 | 4 | 4 | 5 | 3 | 3 |
| UI: дерево, anchor, 9-slice, TTF + разметка, скролл (12) | 4 | 3 | 3 | 5 | 4 | 5 | 4 | 3 |
| Ввод, звук, мобильные браузеры и iOS Safari (10) | 4 | 5 | 5 | 4 | 3 | 2 | 1 | 4 |
| Размер бандла и время старта (8) | 5 | 4 | 4 | 3 | 2 | 1 | 3 | 4 |
| Code-first (15) | 5 | 5 | 5 | 2 | 3 | 3 | 5 | 2 |
| Знание API моделями, документация (12) | 4 | 4 | 5 | 2 | 3 | 3 | 3 | 2 |
| Близость к cocos2d-x, перенос ccbi (10) | 4 | 2 | 2 | 5 | 5 | 3 | 5 | 2 |
| **Итог (из 100)** | **89,6** | **82,2** | 78,6 | 72,0 | 69,4 | 65,8 | 57,4 | 56,2 |

**Проверка чувствительности** (`scores.py`):
- Если поднять вес «близости к cocos2d-x» до 20 %, UI до 15 %, а code-first снизить до 10 %:
  PixiJS 88,0 → Cocos Creator 77,2 → Phaser 4 76,0 → Axmol 74,0.
- Если поднять вес мобильных браузеров и бандла до 15 % каждый: PixiJS 90,4 → Phaser 4 84,2 → Phaser 3 79,8.
- **PixiJS остаётся первым при любых разумных весах.** Второе место делят Phaser 4 и Cocos Creator:
  Cocos выходит вперёд, только если принять работу через редактор.

Что решает по ключевым критериям:
- **Code-first.** Проект PixiJS или Phaser — это обычный TS-проект: Vite, HMR, Vitest, Playwright,
  ИИ может править всё. У Cocos Creator 3.8 импорт ассетов (meta-файлы с UUID), превью и отладка идут
  через редактор. Сборка из CLI тоже требует установленного редактора и GUI-окружения
  ([docs](https://docs.cocos.com/creator/3.8/manual/en/editor/publish/publish-in-command-line.html)).
  Сцены и префабы — JSON с UUID, генерировать их ИИ неудобно. У Godot есть headless-экспорт
  (`--headless --export-release`, [docs](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)),
  но процесс по сути редакторный. У Defold GUI собирается в редакторе (`.gui`), хотя
  `gui.new_box_node`/`new_text_node` тоже есть.
- **Знание API моделями.**
  - PixiJS: [25 официальных skills](https://github.com/pixijs/pixijs-skills) (репозиторий создан
    01.04.2026, MIT) и [llms.txt](https://pixijs.com/llms.txt). Команда прямо пишет, что skills нужны,
    чтобы модели не «галлюцинировали паттерны v7».
  - Phaser: [28 skills в репозитории](https://github.com/phaserjs/phaser/tree/master/skills), включая
    `v3-to-v4-migration`, и [llms.txt](https://phaser.io/llms.txt) с индексом примеров v4. Но основной
    массив знаний у моделей — про Phaser 3, а v4 вышел только 10.04.2026.
  - Defold: полноценный [llms.txt](https://defold.com/llms.txt).
  - У `docs.godotengine.org/llms.txt` и `docs.cocos.com/llms.txt` на 29.09.2026 ответ 404.
- **Близость к cocos2d-x.** Лучше всех здесь Cocos Creator (`UITransform` с `anchorPoint` и
  `contentSize`, ось Y вверх), Axmol (это и есть cocos2d-x) и cocos2d-html5 (штатно читает ccbi).
  У PixiJS есть настоящий граф сцены, `pivot`, `origin`, `zIndex` и наследование alpha, но ось Y
  направлена вниз, а action, Director и приоритетов касаний нет — их придётся дописать. У Phaser
  «[Container origin is always 0,0. The transform point cannot be changed](https://github.com/phaserjs/phaser/tree/master/skills)»
  (skill groups-and-containers). Для ввода контейнеру нужен `setSize`, а depth действует только
  внутри своего контейнера. Значит, каждый CCNode с anchor≠0 и вращением или масштабом придётся делать
  из двух вложенных контейнеров.
- **Мобильные браузеры.** В документации Godot сказано, что у Safari «several issues with WebGL 2.0»,
  и советуют Chromium или Firefox. На iOS это не выход: там все браузеры работают на WebKit.
  У cocos2d-html5 есть незакрытые проблемы на iOS: игры не загружаются в режиме WebGL на iOS 14
  ([issue #20555](https://github.com/cocos2d/cocos2d-x/issues/20555), 16.07.2020, без ответа) и браузер
  зависает на iOS 16.4 ([форум, 03.2023](https://forum.cocosengine.org/t/cocos-js-3-17-2-ios-16-4-beta-hangs-due-to-glweb-via-metal/58319),
  патча нет).

## 5. Кандидаты подробно

### 5.1 PixiJS 8 + TypeScript + свой каркас — рекомендую

**Статус.** 8.21.0 от 17.09.2026, минорный релиз каждые 1–2 месяца. MIT, 48k★. Анонсов v9 на странице
релизов нет.

**Сильные стороны**
- Граф сцены повторяет cocos2d-x.
  - `pivot` = anchor×size, `origin` = `ignoreAnchorPointForPosition`, у `Sprite.anchor` нормированные
    координаты.
  - Alpha наследуется ([scene graph](https://pixijs.com/8.x/guides/concepts/scene-graph.md)), `tint`
    можно задать на контейнере.
  - Порядок отрисовки задаётся через `zIndex` и `sortableChildren`.
- Изометрия. [RenderLayer](https://pixijs.com/8.x/guides/concepts/render-layers) (с 8.7) принимает
  собственную `sortFunction`, например по глубине изометрии, и не зависит от иерархии. Это удобно, когда
  юниты, здания и эффекты лежат в разных ветках дерева. Есть RenderGroups для статичных слоёв и Culler.
- UI.
  - [NineSliceSprite](https://pixijs.com/8.x/guides/components/scene-objects/nine-slice-sprite).
  - Text и HTMLText со **встроенной цветной разметкой** `tagStyles`, с 8.16
    ([блог, 04.02.2026](https://pixijs.com/blog/8.16.0)). BitmapText её пока не поддерживает.
  - [@pixi/ui 2.3.2](https://github.com/pixijs/ui): Button, FancyButton, CheckBox, ScrollBox, List,
    ProgressBar (в том числе круговой), Slider, Select, Input.
  - @pixi/layout 3.2.1 на Yoga (для абсолютных координат ccbi не нужен).
- Текстуры. [DDS, KTX, KTX2, Basis](https://pixijs.com/8.x/guides/components/assets/compressed-textures)
  подключаются импортом `pixi.js/ktx2`. Resolver выбирает формат и разрешение под устройство (SD/HD),
  есть ручной `unload()` и единый GC (8.15).
- Бандл 261 КБ gz, старт мгновенный. Всё на TS, отладка обычная для браузера.
- ИИ: официальные skills (с 8.19 в `node_modules/pixi.js/skills/`), llms.txt, огромный объём примеров.

**Слабые стороны**
- Это рендер-библиотека, а не движок. Сцены, Director, actions и твины, звук, камера, модальность ввода
  и таймлайны CocosBuilder придётся писать самим (оценка — 3–5 тыс. строк TS) или собирать из
  сторонних библиотек:
  - GSAP 3.15: бесплатный «Standard no-charge license» с 30.04.2025, но не OSI и с запретом на
    визуальные конструкторы ([gsap.com](https://gsap.com/standard-license/));
  - [@pixi/sound 6.0.1](https://www.npmjs.com/package/@pixi/sound) (последний релиз 27.07.2024) или
    Howler 2.2.4 (19.09.2023): стабильны, но почти не развиваются;
  - pixi-viewport 6.0.3 (11.2024) для панорамирования и зума.
- Минорные релизы иногда меняют поведение: в 8.17 изменилась картинка BlurFilter по умолчанию, в 8.19 —
  обработка нулевого масштаба, в 8.21 — разложение отражённой матрицы
  ([releases](https://github.com/pixijs/pixijs/releases)).
- WebGPU официально не рекомендован для продакшна, поэтому работаем на WebGL2.

**Как ляжет ccbi.** Генератор создаёт Container или Sprite, выставляет `pivot`/`anchor` и
`y = Hродителя − y`. Размер contentSize храним в своём поле, потому что у Container есть только bounds.
Кастомные классы Inferno реализуем как свои компоненты.

### 5.2 Phaser 4 — запасной вариант

**Статус.** 4.0.0 «Caladan» вышел 10.04.2026, потом 4.1.0 (30.04) и 4.2.0 (19.06: Mesh2D, Stencil, новый
Spine-рендерер), последний — 4.2.1 от 09.07.2026 ([releases](https://github.com/phaserjs/phaser/releases)).
MIT, 40k★.

**Сильные стороны**
- «Всё включено»: сцены, загрузчик, твины и цепочки, таймеры, звук с разблокировкой на iOS, камеры,
  ScaleManager, анимации из атласов, тайлмапы, частицы.
- Новый рендерер ([23.04.2026](https://phaser.io/news/2026/04/phaser-4-renderer-faster-cleaner-and-built-for-modern-games)):
  4 вершины на спрайт вместо 6, восстановление контекста «из коробки», SpriteGPULayer на миллионы
  спрайтов за один draw call. Единая система Filters заменила FX и маски.
- [NineSlice](https://docs.phaser.io/api-documentation/class/gameobjects-nineslice).
  [rexUI](https://rexrainbow.github.io/phaser3-rex-notes/docs/site/bbcodetext/) поддерживает v4:
  `phaser4-rex-plugins` 4.2.0 от 01.07.2026 даёт BBCodeText, ScrollablePanel и GridTable.
- ИИ: 28 skills, включая миграцию с v3, и llms.txt с примерами. Большая часть API объектов и сцен
  совпадает с Phaser 3.
- Один и тот же движок с Under Control (при условии, что UC тоже перейдёт на v4).

**Слабые стороны**
- Модель контейнеров неудобна для cocos: origin всегда 0,0, нет размера без `setSize`, depth работает
  только внутри контейнера, у контейнеров есть накладные расходы на матрицы.
- Цветной разметки и скролла из коробки нет, нужен rexUI. Это сторонний проект одного автора.
- Мажорной версии всего полгода. Модели обучены в основном на v3 и будут подсовывать пайплайны, FX и
  BitmapMask, которых в v4 уже нет. Custom-шейдеры в v4 делаются через новые Filters и render nodes,
  примеров к ним меньше.
- Сжатые текстуры — только контейнеры KTX и PVR с конкретным GPU-форматом (ETC, ASTC, S3TC и т. п.,
  с 3.60). Basis-транскодера нет, поэтому нужно по файлу на каждое семейство GPU.
- Бандл 356 КБ gz; отсечь неиспользуемые модули не получится.
- WebGPU нет (для нас это некритично).

### 5.3 Phaser 3.90

Самый известный моделям API и огромная экосистема. Но с 23.05.2025 релизов нет, а команда называла 3.90
«likely the last version in the v3 tree». Все минусы контейнерной модели Phaser для cocos-макетов при
этом остаются. Выбирать Phaser 3 имеет смысл только ради общего кода с Under Control. Даже в этом случае
разумнее перевести оба проекта на Phaser 4.

### 5.4 Cocos Creator 3.8.8 / Cocos 4

**Статус.**
- Creator 3.8.8 вышел 16.12.2025 и объявлен LTS: только исправления и оптимизация
  ([анонс 3.8.7, 22.08.2025](https://forum.cocos.org/t/topic/170142)).
- 12.11.2025 компания SUD купила Cocos за $72 млн
  ([PR Newswire](https://www.prnewswire.com/news-releases/sud-fully-acquires-cocos-302612392.html)).
  Анонс Cocos 4 под MIT вышел 30.12.2025, пресс-релиз — 05.01.2026
  ([PR Newswire](https://www.prnewswire.com/apac/news-releases/cocos-4-is-here-fully-open-source-302652633.html)).
  В нём движок отделён от редактора: новая AI-IDE PinK проприетарная, а [cocos-cli](https://github.com/cocos/cocos-cli)
  (MIT) умеет `create`/`build` и `start-mcp-server`.
- На 29.09.2026 и `cocos/cocos4`, и `cocos-cli` всё ещё альфа (4.0.0-alpha.35 и 1.0.0-alpha.6).
- В апреле 2026 сообщество жаловалось, что за полгода после открытия исходников документации нет,
  а функционально движок почти не отличается от 3.x ([форум, 16–17.04.2026](https://forum.cocos.org/t/topic/175255)).

**Сильные стороны.** Прямой потомок cocos2d-x:
- `UITransform` с `contentSize` и `anchorPoint`, ось Y вверх;
- Sprite типов SLICED (9-slice) и FILLED с радиальным заполнением — прямой аналог `CCProgressTimer`
  ([docs](https://docs.cocos.com/creator/3.8/manual/en/ui-system/components/editor/sprite.html));
- Label с TTF, RichText, Button (normal/pressed/disabled), Toggle, ScrollView, Mask, tween и Animation;
- TS по умолчанию, сильный мобильный веб.

**Слабые стороны.**
- Работа через редактор: импорт ассетов, UUID, превью. Сборка из CLI в 3.8 требует редактора и GUI.
- Меньше англоязычных материалов, модели путают API 2.x (`cc.Class`) и 3.x (декораторы) — это оценка.
- Неясное будущее: смена владельца и Cocos 4 в альфе. Тяжелее бандл.

**Когда пересмотреть.** Когда Cocos 4 и cocos-cli выйдут из альфы и headless-режим с MCP позволит
вести проект без GUI. Тогда Cocos станет самым «родным» вариантом для переноса ccbi.

### 5.5 cocos2d-html5 / Cocos2d-JS v3.17 (legacy)

**Статус.** В ветке develop значение `cc.ENGINE_VERSION = "Cocos2d-JS v3.17"`. Последний значимый merge —
16.04.2018, README обновлялся в 2019–2020 гг. и направляет в Cocos Creator. В npm есть только 2.2.2.

**Плюсы.**
- `cc.BuilderReader` читает ccbi версии 5 (`CCB_VERSION = 5` в
  [CCBReader.js](https://github.com/cocos2d/cocos2d-html5/tree/develop/extensions/ccb-reader)).
- Неизвестные классы превращаются в `CCNode`, то есть макеты откроются даже без кода Inferno.
- API почти как у оригинала.

**Минусы.**
- Движок мёртв: ES5 и глобальный `cc`, нет TS и ESM, только WebGL1.
- Известные незакрытые проблемы на iOS (см. §4).
- Для `CCProgressTimer` нет штатного загрузчика. Кастомные классы и формат `.atlas` всё равно
  потребуют своих загрузчиков.

**Как использовать.** Не как движок, а как **эталон**: портировать `CCBReader.js`,
`CCBAnimationManager.js` и `CCNodeLoader.js` (MIT, ≈150 КБ JS) в свой конвертер ccbi→JSON.
При необходимости поднять его локально как «оракул» и снять эталонные скриншоты макетов.

### 5.6 Godot 4.7

**Статус.** 4.7 вышел 18.06.2026, 4.7.2 — 18.08.2026. MIT, 118k★, очень активен.

**Плюсы.** Лучший UI из коробки: Control, NinePatchRect, RichTextLabel с BBCode
([docs](https://docs.godotengine.org/en/stable/tutorials/ui/bbcode_in_richtextlabel.html)),
TextureProgressBar с радиальным заполнением
([docs](https://docs.godotengine.org/en/stable/classes/class_textureprogressbar.html)), ScrollContainer.
Y-sort и изометрические TileMapLayer.

**Минусы для нас.**
- Нет TypeScript, а C# на web официально не экспортируется: «Projects written in C# using Godot 4
  currently cannot be exported to the web» ([docs 4.7](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)).
- Только WebGL 2.0, с оговорками про Safari.
- В режиме Sample не работают AudioEffects.
- wasm ≈40 МБ, ≈5 МБ в brotli, плюс `.pck`: старт на телефоне займёт секунды.
- Модели путают синтаксис Godot 3 и 4 (оценка).

### 5.7 Defold 1.13

**Статус.** Выпуск ежемесячный: 1.13.1 — 17.08.2026, 1.14.0-alpha — 10.09.2026.

**Плюсы.**
- Очень маленький и быстрый рантайм: wasm 2,39 МБ, бандл ≈1,3 МБ.
- В GUI есть slice9, stencil-обрезка и pie-ноды — аналог радиального `CCProgressTimer`
  ([docs](https://defold.com/manuals/gui-pie/)). Ось Y вверх.
- Есть полноценный llms.txt.

**Минусы.**
- Lua вместо TS.
- У GUI **только 9 фиксированных pivot** («Center, North, … South East»,
  [docs](https://defold.com/manuals/gui/)), тогда как у ccbi anchorPoint произвольный.
- GUI и коллекции обычно собираются в редакторе.
- Модели знают Defold хуже. Лицензия не OSI.

### 5.8 Axmol 2.11 (cocos2d-x → WebAssembly)

**Статус.** 2.11.5 от 25.09.2026. MIT, форк cocos2d-x v4.0 с ноября 2019 г., C++23, есть цель
WebAssembly ([repo](https://github.com/axmolengine/axmol)).

**Плюсы.** Тот же API, что у оригинала: Node, Sprite, Label, ProgressTimer, actions, Director. Модели
хорошо знают C++ API cocos2d-x.

**Минусы.**
- Ридер CocosBuilder убран ещё в cocos2d-x v4: в `editor-support` у v3 есть `cocosbuilder`, у v4 — только
  `cocostudio` и `spine`. Его придётся переносить из 3.x.
- Тяжёлый цикл: C++, CMake, emsdk и PowerShell 7. Отладка WASM сложнее, wasm весит мегабайты,
  на iOS есть ограничения памяти.
- Сообщество маленькое (1,5k★).

Axmol интересен, если однажды понадобится почти побайтная верность оригиналу. Для браузерного проекта,
который пишет ИИ, он хуже TS-вариантов.

### 5.9 Кратко: Excalibur, melonJS

- **Excalibur 0.32.0** (23.12.2025, BSD-2, TS). Для UI [прямо рекомендует HTML/CSS](https://excaliburjs.com/docs/ui/),
  своих виджетов почти нет. Для 145 спрайтовых макетов не подходит.
- **melonJS 20.7.0** (22.09.2026, MIT). Активен, но экосистема крошечная: 1,6 тыс. загрузок в неделю.
  Преимуществ перед PixiJS или Phaser для нашей задачи нет.

## 6. Топ-2: обоснование и главные риски

### 1. PixiJS 8 + TS — 90/100 (оценка)

**Обоснование.**
- Ближайшая к cocos2d-x модель узлов среди code-first движков на TS (`pivot` и `origin`).
- Максимальная свобода, чтобы воспроизвести поведение cocos 2.x: приоритеты касаний, actions,
  таймлайны CCB.
- Лучшая поддержка сжатых текстур (KTX2/Basis) под наш объём графики.
- Маленький рантайм и официальная инфраструктура для ИИ-агентов.

**Риски и меры**

| Риск | Мера |
|---|---|
| Раздувание своего каркаса: сцены, виджеты, actions, звук, камера | Взять @pixi/ui, Howler или @pixi/sound, pixi-viewport. Actions написать свои в стиле cocos (`MoveTo`/`Sequence`/`Ease*`), примерно 300–500 строк: тогда логику, восстановленную из `libinferno.so`, можно переносить один к одному. Каркас фиксировать как библиотеку с тестами |
| Изменения поведения в минорных релизах | Закрепить точную версию и обновляться осознанно. Держать скриншотные регрессионные тесты макетов (Playwright) |
| Модели пишут код под v7 | Подключить skills (`node_modules/pixi.js/skills/`) и llms.txt в CLAUDE.md, в линтере запретить v7-паттерны |
| Видеопамять в iOS Safari (≈4,4 ГБ всех текстур в RGBA8) | KTX2/Basis для крупных атласов, SD-набор на мобильных, загрузка и выгрузка по сценам через Assets bundles и `unload()`, мониторинг памяти |
| Звуковые библиотеки почти не развиваются | Тонкая своя обёртка над WebAudio, чтобы библиотеку можно было заменить |

### 2. Phaser 4 — 82/100 (оценка)

**Обоснование.** Меньше своего кода благодаря встроенным сценам, твинам, звуку и камерам. Тот же
TS/Vite-стек, что и у PixiJS. Официальные skills. Общий движок с Under Control, если UC перейдёт на v4.

**Риски.**
- Контейнеры без origin: для CCNode нужна обёртка из двух контейнеров, у вложенного ввода есть особенности.
- Цветная разметка и скролл-списки зависят от стороннего rexUI.
- v4 молод, а модели склонны писать код под v3.
- Нет Basis: нужны отдельные KTX-файлы под ASTC, ETC2 и BC.
- Custom-фильтры пишутся на новом, менее документированном API.

## 7. Соответствие cocos2d-x 2.x / ccbi → PixiJS 8 / Phaser 4 / Cocos Creator 3.8

| cocos2d-x 2.x / ccbi | PixiJS 8 | Phaser 4 | Cocos Creator 3.8 (для сравнения) |
|---|---|---|---|
| `CCNode`: anchorPoint, contentSize, ось Y вверх | `Container`: `pivot=(ax·w,(1−ay)·h)`, `y=Hродителя−y`, своё поле size | `Container` (origin 0,0) + вложенный контейнер со смещением; `setSize` для ввода | `Node` + `UITransform` — прямое соответствие |
| `ignoreAnchorPointForPosition` | `Container.origin` (экспериментальный) или сдвиг позиции | Сдвиг позиции | Сдвиг позиции |
| `CCSprite` / displayFrame | `Sprite` + `anchor(ax,1−ay)`, кадры из Spritesheet | `Sprite` + `setOrigin` | `Sprite` + `SpriteFrame` |
| `CCSpriteBatchNode` | Обычный `Container`, батчинг автоматический | `Container`/`Layer` | Обычный `Node` |
| `CCLabelTTF` / Localized | `Text` (TTF через Assets/FontFace), цвета через `tagStyles`; `BitmapText` для цифр | `Text`/`BitmapText`; разметка — rexUI BBCodeText | `Label` / `RichText` |
| `CCMenu` + `CCMenuItemImage` (3 состояния) | Свой Button или `@pixi/ui` FancyButton | Свой Button на Image + input | `Button` (normal/pressed/disabled) |
| `CCCheckBox`, `CCNodeSelector` | Свои виджеты (основа — `@pixi/ui` CheckBox/Switcher) | Свои или rexUI | `Toggle` |
| `CCScrollListView`, `CCTableNode`, `CRjScrollListView` | `@pixi/ui` ScrollBox/List + виртуализация | rexUI ScrollablePanel/GridTable | `ScrollView` + свой пул |
| `CCProgressTimer` (полоса/радиальный) | Sprite + маска (дуга Graphics) или `@pixi/ui` ProgressBar | Sprite + crop / маска-фильтр | `Sprite` FILLED (RADIAL) |
| Касания 2.x (`CCTouchDispatcher`, приоритеты, swallow) | `eventMode`, `stopPropagation`, модальный «щит» | `setInteractive`, `input.topOnly` | Система событий + `BlockInputEvents` |
| `CCAction` (`MoveTo`, `Sequence`, `Ease`…) | Свой ActionManager на `Ticker` или GSAP | Tweens, TweenChain, `time.addEvent` | `tween()` |
| `CCBAnimationManager` (таймлайны) | Плеер ключевых кадров на тех же actions | TweenChain | `Animation` |
| `CCDirector` / `CCScene` | Свой SceneManager | `Scene` (встроено) | `director.loadScene` |
| GLSL-шейдеры (`CC_Texture0`) | `Filter` (GlProgram); BlurFilter, ColorMatrixFilter, pixi-filters | Filters v4 (Blur, ColorMatrix, свои) | Effect-файлы (через редактор) |
| Звук (FMOD в оригинале) | @pixi/sound или Howler | Встроенный Sound Manager | `AudioSource` |

## 8. Что сделать независимо от выбора движка

1. **Конвейер ассетов** на Python в `tools/`, в одном стиле с `parse_config.py`:
   - `.pkm.ccz` → декод ETC1, альфа из нижней половины → PNG как мастер. Для доставки — WebP,
     для GPU — KTX2 (Basis UASTC или ETC1S). SD-набор для мобильных.
   - `.atlas` → JSON в формате TexturePacker (`rotated`, `trimmed`, `spriteSourceSize`, `sourceSize`).
   - `.ccbi` → JSON: порт `CCBReader.js` (MIT, версия 5 совпадает). В ccbi тип каждого свойства хранится
     в файле, поэтому **кастомные классы Inferno читаются без их кода**: разбирать нужно только их
     семантику в рантайме. Относительные позиции и размеры (процент, от угла) пересчитываются при сборке
     сцены от contentSize родителя.
   - `visuals/*.xml` → JSON анимаций (fps, направления, состояния, слои).
   - WAV → сжатый формат (m4a/mp3), чтобы уменьшить загрузку.
2. **Архитектура.** Экономику, бой, ИИ и сохранения писать на чистом TS без импорта движка и тестировать
   в Vitest под Node. Рендер держать тонким адаптером. Это снижает цену ошибки в выборе движка и упрощает
   сверку с поведением оригинала.
3. **Инфраструктура для ИИ.** Закрепить версии, положить skills и llms.txt движка, прописать правила в
   CLAUDE.md. Сделать страницу-витрину макетов для скриншотных тестов.

## 9. Спайк для подтверждения (2–3 дня, сначала на PixiJS)

1. Конвертер ccbi→JSON и сборка трёх макетов: `battle/win.ccbi` (простой попап), окно со списком
   `CCScrollListView`, окно с `CCProgressTimer` и разными TTF.
2. Юнит `jelly_alien` в 8 направлениях со всеми состояниями; 100–300 юнитов на изометрической сцене с
   сортировкой; трассеры и эффекты с аддитивным смешиванием.
3. Фон колонии из `maps/` с панорамированием и зумом (мышь и pinch).
4. Размытие под модальным окном (GaussianBlur) и ч/б (Grayscale).
5. Замеры на iPhone (Safari, iOS 26) и слабом Android: FPS, время до первого кадра, пиковая память GPU
   для PNG и для KTX2.

**Условие пересмотра.** Если воспроизведение семантики cocos на PixiJS для этих трёх макетов потребует
заметно больше 1,5 тыс. строк каркаса или вскроются неустранимые проблемы на iOS, повторить спайк на
Phaser 4.

## 10. Источники (проверено 29.09.2026, если не указано иное)

**PixiJS**
- Релизы 8.15–8.21: https://github.com/pixijs/pixijs/releases
- Рендереры (про WebGPU и продакшн): https://pixijs.com/8.x/guides/components/renderers
- Тегированный текст и Canvas-рендерер (04.02.2026): https://pixijs.com/blog/8.16.0
- AI skills и llms.txt (12.06.2026): https://pixijs.com/blog/june-2026, https://github.com/pixijs/pixijs-skills, https://pixijs.com/llms.txt
- Render Layers: https://pixijs.com/8.x/guides/concepts/render-layers
- NineSliceSprite: https://pixijs.com/8.x/guides/components/scene-objects/nine-slice-sprite
- Сжатые текстуры: https://pixijs.com/8.x/guides/components/assets/compressed-textures
- API Container (pivot, origin, tint): https://pixijs.download/release/docs/scene.Container.html
- @pixi/ui: https://github.com/pixijs/ui
- GSAP Standard License (с 30.04.2025): https://gsap.com/standard-license/

**Phaser**
- Релизы 4.0.0–4.2.1 и 3.90.0: https://github.com/phaserjs/phaser/releases
- Последняя версия v3 (23.05.2025): https://phaser.io/news/2025/05/phaser-v390-released
- Рендерер v4 (23.04.2026): https://phaser.io/news/2026/04/phaser-4-renderer-faster-cleaner-and-built-for-modern-games
- Phaser 4.2 (21.07.2026): https://phaser.io/news/2026/07/phaser-4-2-spine-renderer-mesh2d-stencil
- AI skills (28): https://github.com/phaserjs/phaser/tree/master/skills
- llms.txt: https://phaser.io/llms.txt
- Container: https://docs.phaser.io/api-documentation/class/gameobjects-container
- NineSlice: https://docs.phaser.io/api-documentation/class/gameobjects-nineslice
- rexUI для Phaser 4: https://rexrainbow.github.io/phaser3-rex-notes/docs/site/bbcodetext/

**Cocos**
- Релизы Creator (3.8.6–3.8.8): https://github.com/cocos/cocos-engine/releases
- Анонс 3.8.7 и 4.x (22.08.2025): https://forum.cocos.org/t/topic/170142
- Покупка компанией SUD (12.11.2025): https://www.prnewswire.com/news-releases/sud-fully-acquires-cocos-302612392.html
- Открытие Cocos 4 (05.01.2026): https://www.prnewswire.com/apac/news-releases/cocos-4-is-here-fully-open-source-302652633.html
- cocos-cli: https://github.com/cocos/cocos-cli
- Issue #197 (11.07.2026): https://github.com/cocos/cocos4/issues/197
- Жалобы на отсутствие документации (04.2026): https://forum.cocos.org/t/topic/175255
- Сборка из CLI: https://docs.cocos.com/creator/3.8/manual/en/editor/publish/publish-in-command-line.html
- Графические бэкенды: https://docs.cocos.com/creator/3.8/manual/en/graphics-backend/overview.html
- Sprite: https://docs.cocos.com/creator/3.8/manual/en/ui-system/components/editor/sprite.html
- Размер пустой сборки (2021): https://forum.cocosengine.org/t/cocos-creator-3-build-size/53154

**cocos2d-html5 / cocos2d-x**
- Репозиторий: https://github.com/cocos2d/cocos2d-html5
- ccb-reader: https://github.com/cocos2d/cocos2d-html5/tree/develop/extensions/ccb-reader
- Проблемы на iOS: https://github.com/cocos2d/cocos2d-x/issues/20555, https://forum.cocosengine.org/t/cocos-js-3-17-2-ios-16-4-beta-hangs-due-to-glweb-via-metal/58319

**Godot**
- Релиз 4.7.2: https://github.com/godotengine/godot/releases/tag/4.7.2-stable
- Экспорт для Web: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- Размер wasm в 4.3 (15.05.2024): https://godotengine.org/article/progress-report-web-export-in-4-3/
- Командная строка: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html

**Defold**
- Релиз 1.13.1: https://github.com/defold/defold/releases/tag/1.13.1
- Лицензия: https://defold.com/license/
- Размер сборок: https://github.com/defold/build-size
- HTML5: https://defold.com/llms/manuals/html5/
- GUI: https://defold.com/manuals/gui/
- llms.txt: https://defold.com/llms.txt

**Прочее**
- Axmol: https://github.com/axmolengine/axmol, релиз 2.11.5: https://github.com/axmolengine/axmol/releases/tag/v2.11.5
- Excalibur, релиз 0.32.0: https://github.com/excaliburjs/Excalibur/releases/tag/v0.32.0; UI: https://excaliburjs.com/docs/ui/
- WebGPU в браузерах (25.11.2025): https://web.dev/blog/webgpu-supported-major-browsers

**Данные на 29.09.2026**
- npm (версии, даты, лицензии): `npm view <pkg>`
- Загрузки: https://api.npmjs.org/downloads/point/last-week/<pkg>
- Размеры: https://bundlephobia.com (pixi.js@8.21.0, phaser@4.2.1, phaser@3.90.0, excalibur@0.32.0, melonjs@20.7.0)
- Звёзды и статус репозиториев: GitHub REST API
