# Макеты интерфейса: JSON из .ccbi

Интерфейс игры свёрстан в CocosBuilder: макеты лежат в файлах `.ccbi` (формат CCBI v5 в варианте
движка Inferno). `tools/ccbi_to_json.py` переводит их в JSON для загрузчика UI в `web/`. Разбор
без потерь: `tools/ccbi_write.py` собирает из JSON исходный `.ccbi` байт в байт. Устройство самого
формата и статистика макетов — в [исследовании](../research/ccbi.md).

```bash
python3 tools/ccbi_to_json.py            # raw/ → assets/ui/ (177 макетов)
python3 tools/ccbi_to_json.py --check    # 306 файлов всех слоёв: разбор, обратная сборка, сверка с отчётом
python3 tools/ccbi_write.py макет.json макет.ccbi
```

- **Вход:** `raw/{apk,obb_main,obb_patch}/assets/interface/**/*.ccbi`. Один путь бывает в
  нескольких слоях, берётся старший: patch, затем main, затем apk.
- **Выход:** `assets/ui/<путь внутри interface/ без .ccbi>.json`, например
  `assets/ui/1024x768/city/popups/yes_no_popup.json`. Dev-сервер клиента отдаёт его по адресу
  `/assets/ui/1024x768/city/popups/yes_no_popup.json`.
- JSON в UTF-8 с отступом 1. Повторный запуск даёт те же байты.

Числа — как в файле. float32 записан кратчайшей десятичной строкой, которая даёт те же 4 байта
(`505.21606`, а не `505.216064453125`), целые значения — целыми.

## Версия

`formatVersion: 1`. Если поле меняет имя или смысл, версия растёт. Новое необязательное поле
версию не меняет.

## Документ

| Поле | Значение |
|---|---|
| `formatVersion` | `1` |
| `source` | `{layer, path}`: слой, из которого взят файл (`apk`, `obb_main`, `obb_patch`), и путь внутри `assets/interface/` |
| `resolution` | `{name, width, height}` по первой папке пути (`1024x768` → 1024 × 768) или `null`. Это экран, под который свёрстан макет, — размер корня по умолчанию. `interface.xml` объявляет только `1024x768`; `2048x1536` — старая копия части макетов |
| `sequences` | таймлайны в порядке файла |
| `autoPlaySequenceId` | таймлайн, который запускается сразу после загрузки; `-1` — никакой |
| `root` | корневой узел |
| `ccbi` | `{version: 5, jsControlled: false, stringCache}` — служебное, загрузчику не нужно. Кэш строк хранит порядок оригинала и строки, на которые файл не ссылается: без него файл не собрать байт в байт |

## Таймлайн

`{sequenceId, name, duration, chainedSequenceId, callbacks, sounds}`

- `sequenceId` — номер, на который ссылаются `autoPlaySequenceId`, `chainedSequenceId` и ключи
  `animatedProperties` у узлов.
- `name` — имя, по которому код запускает таймлайн: `timelineShow`, `Social timer` и т. п.
- `duration` — длина в секундах. Когда она истекает, запускается `chainedSequenceId`; `-1` —
  ничего не запускается. Таймлайн, который ссылается сам на себя, крутится по кругу.
- `callbacks: [{time, selector, target}]` и `sounds: [{time, file, pitch, pan, gain}]` — каналы
  колбэков и звуков. Во всех 306 файлах оба пустые.

## Узел

| Поле | Значение |
|---|---|
| `baseClass` | плагин CocosBuilder: задаёт набор свойств |
| `customClass` | класс игры поверх плагина или `null`. В `.ccbi` записано одно имя, `customClass ?? baseClass`, и по нему движок выбирает загрузчик |
| `memberVarAssignment` | `{target, name}` или `null` — outlet: движок передаёт узел владельцу (`Owner` — диалог на C++, `DocumentRoot` — корень макета) под именем `name`. Пустое `name` встречается, такой узел никуда не передаётся |
| `jsController` | есть только у документов с `ccbi.jsControlled = true`; в игре таких нет |
| `properties` | обычные свойства, `{имя: свойство}` |
| `customProperties` | «Custom properties» CocosBuilder, `{имя: свойство}`; бывают только у узлов с `customClass` |
| `animatedProperties` | `{"sequenceId": {имя: {type, keyframes}}}` — дорожки узла в таймлайнах |
| `children` | дети; их порядок — порядок отрисовки (`zOrder` и `tag` в файлах игры не задаются) |

Порядок в `properties`, `customProperties`, `animatedProperties` и `children` — как в файле.
Для `properties` он важен: движок применяет свойства по очереди. Например, у `CCMenuItemImage`
`normalSpriteFrame` идёт после `contentSize` и перезаписывает его размером кадра.

### baseClass и customClass

Четыре класса — `customClass` поверх стандартного плагина. Свойства у них в точности от
плагина. Писатель CocosBuilder кладёт в кэш строк оба имени, а в файл пишет одно
([CCBXCocos2diPhoneWriter.m][wr-cache], [выбор имени][wr-class]), поэтому имя плагина
остаётся в кэше без ссылок. Custom-свойства писатель сохраняет только при заданном
`customClass` ([там же][wr-custom]).

| В файле | baseClass | customClass | Чем подтверждено |
|---|---|---|---|
| CCSpriteBatchNode | CCNode | CCSpriteBatchNode | свойства CCNode и custom-свойства `texture`, `textures`, `isAbsolute` |
| CCLabelTTFLocalized | CCLabelTTF | CCLabelTTFLocalized | в 11 файлах `CCLabelTTF` лежит в кэше без ссылок |
| CRjScrollListView | CCScrollView | CRjScrollListView | в 3 файлах в кэше без ссылок `CCScrollView`; `scale` типа Float, как у этого плагина |
| MainMenuScene | CCLayer | MainMenuScene | `CCLayer` в кэше без ссылок |

Остальные классы — плагины, у них `customClass: null`. Плагины CocosBuilder и классы движка за
ними не всегда совпадают по имени. Базы классов и загрузчиков ниже взяты из typeinfo в
`libinferno.so`; какой загрузчик зарегистрирован под каким именем — из
[исследования](../research/ccbi.md#32-классы-нод-п).

| Класс в файле | Узел в движке | Загрузчик |
|---|---|---|
| CCNode, CCSprite, CCMenu, CCMenuItemImage, CCLayer, CCLayerColor | штатные cocos2d-x | штатные |
| CCLabelTTF | CCLabelTTFSize : CCLabelTTF | CCLabelTTFSizeLoader : CCLabelTTFLoader |
| CCLabelTTFLocalized | CCLabelTTFSize; строку переводит `CRjInterface::GetLocalizedString` | CCLabelTTFLocalizedLoader : CCLabelTTFSizeLoader |
| CCTextButton | CCTextButton : CCMenuItemImage | CCTextButtonLoader : CCMenuItemImageLoader |
| CCCheckBox | CCCheckBox : CCMenuItemToggle | CCCheckBoxLoader : CCMenuItemLoader |
| CCNodeSelector | CCNodeSelector : CCLayer | CCNodeSelectorLoader : CCNodeLoader |
| CCTextLayout | CCTextLayout : CCLayer | CCTextLayoutLoader : CCNodeLoader |
| CCTableNode | CCTableNode : CCNode | CCTableNodeLoader : CCNodeLoader |
| CCScrollListView | CRjScrollListView : CCScrollView | CRjScrollListViewLoader : CCScrollViewLoader |
| CCProgressTimer | CCProgressTimer (есть и CCPointsProgressTimer : CCProgressTimer) | CCProgressTimerLoader : CCNodeLoader |
| CCSpriteBatchNode | CCSpriteBatchNode | CCSpriteBatchNodeLoader : CCNodeLoader |

`CCTextButton` и `CCCheckBox` — пункты меню, касания они получают от родительского `CCMenu`.
`CCNodeSelector` — самостоятельная невидимая зона касания.

## Свойство

`{type, value}`. У типов с единицами измерения рядом с `value` лежит `positionType`, `sizeType`
или `scaleType`. У платформенных свойств есть `platform`.

| id | type | value | Где встречается в игре |
|---:|---|---|---|
| 0 | Position | `{x, y}` + `positionType` | `position` |
| 1 | Size | `{width, height}` + `sizeType` | `contentSize`, `dimensions` у меток, `preferedSize` |
| 2 | Point | `{x, y}` | `anchorPoint`, `midpoint`, `barChangeRate`, `offset`, `normalOffset` и др. |
| 3 | PointLock | `{x, y}` | — |
| 4 | ScaleLock | `{x, y}` + `scaleType` | `scale` |
| 5 | Degrees | число, градусы по часовой стрелке | `rotation` |
| 6 | Integer | целое | `group`, `colcount`, `_count` |
| 7 | Float | число | `percentage`, `scale` у CCScrollView |
| 8 | FloatVar | `{base, variance}` | — |
| 9 | Check | bool | `visible`, `ignoreAnchorPointForPosition`, `isEnabled`, `selected`, `touchEnabled` и др. |
| 10 | SpriteFrame | `{sheet, frame}` | `displayFrame`, `normalSpriteFrame`, `normalImage` и др. |
| 11 | Texture | строка | — |
| 12 | Byte | 0…255 | `opacity` |
| 13 | Color3 | `[r, g, b]` | `color`, `normalColor` |
| 14 | Color4FVar | `{base: [r, g, b, a], variance: [r, g, b, a]}` | — |
| 15 | Flip | `{x, y}` из bool | — |
| 16 | Blendmode | `{src, dst}` — GLenum: 1 ONE, 770 SRC_ALPHA, 771 ONE_MINUS_SRC_ALPHA | `blendFunc` (везде 770/771) |
| 17 | FntFile | строка | — |
| 18 | Text | строка | `string`, `_template` |
| 19 | FontTTF | строка: путь к TTF или имя системного шрифта | `fontName`, `normalFontName` и др. |
| 20 | IntegerLabeled | целое — номер варианта из списка | выравнивания, `state`, `type` |
| 21 | Block | `{selector, target, soundFile, soundEnabled}` | `block` |
| 22 | Animation | `{file, animation}` | — |
| 23 | CCBFile | строка | `container` (пустой, в мёртвых файлах) |
| 24 | String | строка | custom `texture`, `template`; `title\|1` |
| 25 | BlockCCControl | `{selector, target, controlEvents}` — битовая маска CCControlEvent | `ccControl` |
| 26 | FloatScale | число + `scaleType` | `fontSize`, `normalFontSize` и др. |
| 27 | FloatXY | `{x, y}` | — |
| 28 | NoValue28 | `null` | `makeCopy` у CCTextButton, 20 раз |

«—» — типа нет ни в одном из 306 файлов; конвертер и тесты его всё равно поддерживают.

**Отличия варианта Inferno** (дизассемблер `libinferno.so`, см. [исследование, §1.4](../research/ccbi.md#14-диалект-inferno-расширения-rj-games-п)):

- `Block`: после `selector` и `target` записаны `soundFile` (строка) и `soundEnabled` (bool).
  Движок передаёт их в `CCMenuItem::setSoundFile` и `setSoundEnabled`. Звук задан один раз —
  `champion_close_attack.wav` в мёртвом `mainmenu/MainMenuScene`; у остальных 1 251 колбэка
  `soundFile` пустой, `soundEnabled` — `false`.
- Тип 28 не несёт значения: в движке это пустой `case`. По смыслу — кнопка инспектора
  редактора «make copy», в игре ни на что не влияет (гипотеза).

`platform`: `iOS` или `Mac`; если поля нет — свойство для всех платформ. cocos2d-x 2.2 применяет
свойства `iOS` на всех платформах, а `Mac` — нигде ([CCNodeLoader.cpp][nl-platform]). В игре так
помечены только `touchEnabled` (iOS) и `mouseEnabled` (Mac) у наследников CCLayer: CCMenu,
CCLayer, CCLayerColor, CCTextLayout. Штатный `CCLayerLoader` ждёт имя `isTouchEnabled`
([CCLayerLoader.cpp][layer-loader]), и в строках `libinferno.so` другого имени нет. Поэтому
`touchEnabled` попадает в custom-свойства узла и на касания не влияет. CCMenu включает касания
сам ([CCMenu::initWithArray][menu-init]).

## Ключ анимации

`{time, easing, [easingOpt], value}`

- `time` — секунды от начала таймлайна.
- `easing` — переход от этого ключа к следующему. `easingOpt` есть только у `CubicIn`,
  `CubicOut`, `CubicInOut` (степень) и `ElasticIn`, `ElasticOut`, `ElasticInOut` (период).
- `value` — того же вида, что `value` у свойства: `{x, y}`, число, bool, `[r, g, b]` или
  `{sheet, frame}`. `positionType` и `scaleType` у ключей нет: движок берёт их из свойства узла.

Анимируются 8 типов: Check, Byte, Color3, Degrees, ScaleLock, Position, FloatXY, SpriteFrame.
В игре — только `opacity`, `scale` и `position`, и везде `Linear`.

```json
"animatedProperties": {
 "1": {"opacity": {"type": "Byte", "keyframes": [
   {"time": 0, "easing": "Linear", "value": 255},
   {"time": 0.16666667, "easing": "Linear", "value": 0}]}},
 "2": {"opacity": {"type": "Byte", "keyframes": [
   {"time": 0, "easing": "Linear", "value": 0},
   {"time": 0.2, "easing": "Linear", "value": 255}]}}
}
```

## Перечисления

Значения — строки, в скобках индекс в `.ccbi`. Имена совпадают с константами `PositionType`,
`SizeType` и `ScaleType` в `web/src/engine/cocos.ts`.

| Поле | Значения |
|---|---|
| `positionType` | RelativeBottomLeft (0), RelativeTopLeft (1), RelativeTopRight (2), RelativeBottomRight (3), Percent (4), MultiplyResolution (5) |
| `sizeType` | Absolute (0), Percent (1), RelativeContainer (2), HorizontalPercent (3), VerticalPercent (4), MultiplyResolution (5) |
| `scaleType` | Absolute (0), MultiplyResolution (1) |
| `target` | None (0), DocumentRoot (1), Owner (2) |
| `platform` | нет поля (0 — все), iOS (1), Mac (2) |
| `easing` | Instant (0), Linear (1), CubicIn (2), CubicOut (3), CubicInOut (4), ElasticIn (5), ElasticOut (6), ElasticInOut (7), BounceIn (8), BounceOut (9), BounceInOut (10), BackIn (11), BackOut (12), BackInOut (13) |

## Как движок считает геометрию

Движок Inferno — cocos2d-x 2.2.0 ([native.md](../research/native.md)). Ссылки ведут на тег
[`cocos2d-x-2.2`](https://github.com/cocos2d/cocos2d-x/tree/cocos2d-x-2.2).

1. **Порядок.** [`CCBReader::readNodeGraph`][rd-graph]: класс, outlet, дорожки анимации, затем
   свойства по очереди ([`CCNodeLoader::parseProperties`][nl-parse]), затем дети. Когда читаются
   дети, свойства родителя уже применены.
2. **Контейнер** относительных позиций и размеров — `contentSize` родителя. Для корня это
   `parentSize`, по умолчанию `winSize` ([`getContainerSize`][am-container],
   [`readNodeGraphFromData`][rd-data]).
3. **Позиция** — [`parsePropTypePosition`][nl-position] → [`getAbsolutePosition`][rp-position].
   W и H — размер контейнера:

   | positionType | x | y |
   |---|---|---|
   | RelativeBottomLeft | x | y |
   | RelativeTopLeft | x | H − y |
   | RelativeTopRight | W − x | H − y |
   | RelativeBottomRight | W − x | y |
   | Percent | (int)(W · x / 100) | (int)(H · y / 100) |
   | MultiplyResolution | x · resolutionScale | y · resolutionScale |

   `(int)` отбрасывает дробную часть (`Math.trunc`).
4. **Размер** — [`parsePropTypeSize`][nl-size]: Absolute — как есть; Percent — (int)(W · w / 100)
   и (int)(H · h / 100); RelativeContainer — W − w и H − h; HorizontalPercent и VerticalPercent —
   процент только по своей оси; MultiplyResolution — ×resolutionScale. Так считаются и
   `contentSize` ([`onHandlePropTypeSize`][nl-onsize]), и `dimensions` у меток.
5. **Масштаб** — [`parsePropTypeScaleLock`][nl-scale] и [`setRelativeScale`][rp-scale]:
   MultiplyResolution умножает на resolutionScale. Размер шрифта (`FloatScale`) — так же
   ([`parsePropTypeFloatScale`][nl-floatscale]).
6. **resolutionScale** в cocos2d-x — одно статическое число, по умолчанию 1
   ([CCBReader.cpp][rd-resscale]). Inferno задаёт его по осям отдельно: 2 для SD-атласов (`*_sd`),
   иначе 1 ([исследование, §1.4](../research/ccbi.md#14-диалект-inferno-расширения-rj-games-п)).
   С HD-атласами `textures_etc/interface/1024x768` он равен 1, и MultiplyResolution читается как
   Absolute.
7. **Трансформация** — [`CCNode::nodeToParentTransform`][node-transform]. Перевод в Container
   PixiJS — `toPixiTransform` в `web/src/engine/cocos.ts`. `ignoreAnchorPointForPosition = true`
   сдвигает позицию на anchor в точках, но поворот и масштаб всё равно идут вокруг anchor.

### Если свойства нет в файле

CocosBuilder не пишет свойство, если оно равно значению по умолчанию плагина и не анимируется
([CCBWriterInternal.m][wr-default]). Ридер такое свойство не трогает, и у узла остаётся значение
из конструктора класса. Из общих свойств узла всегда записаны только `anchorPoint`, `scale` и
`ignoreAnchorPointForPosition`; свойства плагинов без значения по умолчанию (шрифт, текст, кадры
кнопок, колбэки) тоже пишутся всегда.

| Свойство | Когда его нет в файле | Что остаётся у узла |
|---|---|---|
| `position` | (0, 0), RelativeBottomLeft | (0, 0) |
| `visible` | `true` | `true` |
| `rotation` | 0 | 0 |
| `tag` | −1 | −1 |
| `opacity`, `color` | 255, белый | 255, белый |
| `blendFunc` у CCSprite | {1, 771} | от текстуры: для непремультиплицированной — {770, 771} ([`updateBlendFunc`][sprite-blend]); в PixiJS оба случая — обычный режим `normal` |
| `contentSize` | 0 × 0, Absolute | зависит от класса, см. ниже |

`contentSize` по классам:

- **CCNode** и классы без своего размера (CCSpriteBatchNode, CCTableNode) — 0 × 0. Дети с
  позицией Percent или Relative* внутри такого узла получают 0 по оси с нулевым размером.
  Пример: у `CCNode «topLeft»` в CityScene размера нет, поэтому его ребёнок с позицией
  (47.07 %, 69.76 %) оказывается в (0, 0).
- **CCMenu** — `winSize`, `ignoreAnchorPointForPosition = true`, anchor (0.5, 0.5)
  ([`CCMenu::initWithArray`][menu-init]). Размер записан только у 57 из 400 меню набора 1024x768,
  у остальных он равен экрану. Поэтому меню с масштабом ≠ 1 масштабируются вокруг центра экрана.
- **CCLayer** — `winSize` и `ignoreAnchorPointForPosition = true` ([`CCLayer`][layer-init]). У
  CCLayer в файлах размер записан всегда. CCNodeSelector и CCTextLayout — наследники CCLayer;
  вероятно, без `contentSize` они тоже размером с экран (гипотеза; такой случай один —
  CCNodeSelector в наборе 1024x768).
- **CCSprite** — исходный (нетримленный) размер кадра ([`CCSprite::setTextureRect`][sprite-rect]).
  Своего `contentSize` у спрайтов в файлах нет.
- **CCMenuItemImage** — размер кадра `normalSpriteFrame`. Он перезаписывает и явный `contentSize`
  ([`CCMenuItemSprite::setNormalImage`][item-normal]). Обычно они совпадают, но не всегда: у
  `info.png` в `construction_menu_template` записано 123 × 126, а кадр в атласе — 122 × 125.
- **CCLabelTTF** — по тексту. `dimensions` 0 × 0 — авторазмер, иначе бокс с выравниванием
  `horizontalAlignment` (0 — влево, 1 — по центру, 2 — вправо) и `verticalAlignment`
  (0 — сверху, 1 — по центру, 2 — снизу).

### Таймлайны

- Запуск — [`runAnimationsForSequenceIdTweenDuration`][am-run]. У каждого узла с дорожками в этом
  таймлайне свойство сразу получает значение первого ключа, затем идёт цепочка: пауза до первого
  ключа, потом переходы между ключами. Свойства, которые анимируются только в других таймлайнах,
  возвращаются к базовому значению — тому, что записано в `properties`.
- Переход от ключа i к ключу i + 1 длится `time[i+1] − time[i]`, easing берётся у ключа i
  ([`runAction`][am-action], [`getEaseAction`][am-ease]).
- Ключи `position` и `scale` хранят только числа, тип берётся из свойства узла
  ([`getAction`][am-getaction]).
- Через `duration` запускается `chainedSequenceId` ([`sequenceCompleted`][am-completed]).
  Сразу после загрузки играется `autoPlaySequenceId` ([CCBReader.cpp][rd-autoplay]).

## Пример

Крестик закрытия из `1024x768/city/popups/yes_no_popup.json` (без `selectedSpriteFrame` и
`disabledSpriteFrame`):

```json
{
 "baseClass": "CCMenuItemImage",
 "customClass": null,
 "memberVarAssignment": {"target": "Owner", "name": ""},
 "properties": {
  "position": {"type": "Position", "value": {"x": -2.334898, "y": -2.3255103},
               "positionType": "RelativeBottomLeft"},
  "anchorPoint": {"type": "Point", "value": {"x": 0.5, "y": 0.5}},
  "scale": {"type": "ScaleLock", "value": {"x": 0.5, "y": 0.5}, "scaleType": "MultiplyResolution"},
  "ignoreAnchorPointForPosition": {"type": "Check", "value": false},
  "block": {"type": "Block", "value": {"selector": "close", "target": "Owner",
                                        "soundFile": "", "soundEnabled": false}},
  "isEnabled": {"type": "Check", "value": true},
  "normalSpriteFrame": {"type": "SpriteFrame", "value": {"sheet": "", "frame": "popup_cross.png"}}
 },
 "customProperties": {},
 "animatedProperties": {},
 "children": []
}
```

Кадры ищутся по имени (`frame`) в общем кэше атласов, `sheet` во всех файлах пустой.

[wr-cache]: https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/CocosBuilder/Cocos2D%20iPhone/CCBXCocos2diPhoneWriter.m#L451-L457
[wr-class]: https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/CocosBuilder/Cocos2D%20iPhone/CCBXCocos2diPhoneWriter.m#L828-L840
[wr-custom]: https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/CocosBuilder/Cocos2D%20iPhone/CCBXCocos2diPhoneWriter.m#L944-L952
[wr-default]: https://github.com/cocos2d/CocosBuilder/blob/v3.5.0/CocosBuilder/ccBuilder/CCBWriterInternal.m#L419-L423
[nl-platform]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L45-L66
[nl-parse]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L35-L354
[nl-position]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L356-L377
[nl-size]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L394-L447
[nl-scale]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L462-L490
[nl-floatscale]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L507-L519
[nl-onsize]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNodeLoader.cpp#L967-L973
[rp-position]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNode+CCBRelativePositioning.cpp#L8-L44
[rp-scale]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCNode+CCBRelativePositioning.cpp#L46-L60
[rd-graph]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBReader.cpp#L536-L745
[rd-data]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBReader.cpp#L257-L277
[rd-autoplay]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBReader.cpp#L273-L277
[rd-resscale]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBReader.cpp#L1063-L1073
[am-container]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L207-L217
[am-getaction]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L349-L385
[am-ease]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L523-L591
[am-action]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L695-L731
[am-run]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L748-L824
[am-completed]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCBAnimationManager.cpp#L861-L886
[layer-loader]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/extensions/CCBReader/CCLayerLoader.cpp#L13-L28
[menu-init]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/menu_nodes/CCMenu.cpp#L121-L137
[item-normal]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/menu_nodes/CCMenuItem.cpp#L415-L434
[layer-init]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/layers_scenes_transitions_nodes/CCLayer.cpp#L45-L80
[sprite-rect]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/sprite_nodes/CCSprite.cpp#L315-L319
[sprite-blend]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/sprite_nodes/CCSprite.cpp#L1052-L1069
[node-transform]: https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-2.2/cocos2dx/base_nodes/CCNode.cpp#L1132-L1205
