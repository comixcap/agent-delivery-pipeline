---
description: Системный аудит привязки к ширине и горизонтального переполнения (SwiftUI)
---

## ⚠️ ОБЯЗАТЕЛЬНО ПЕРЕД РАБОТОЙ — прочитай справочники

Это не опция. Правила вынесены из `CLAUDE.md` ради размера, но действуют полностью.
Прочитай эти файлы ДО первой правки кода:

- `$HOME/.claude/rules/layout.md` — вёрстка

---
Проведи глубокий аудит всех View и Sheet проекта и исправь проблемы привязки к ширине экрана. Действуй системно, никаких поверхностных правок.

### 0. Сначала — четыре бага, которые чинятся БЕЗ проверки, по факту обнаружения паттерна

Все четыре компилируются, все четыре выглядят в исходнике безобидно, все четыре ловятся только
чтением кода компонента.

**A. Сетка / доска / поле / календарь, разложенные по `.offset` внутри `ZStack`.**
Симптом на устройстве: раскладка стоит не по центру, а сдвинута вправо-вниз примерно на половину
области; часть ячеек за экраном; соседние подписи оказываются поверх неё; тап попадает НЕ в ту
ячейку, на которую нажали (картинка и хит-тест разъехались).
Причина: `.offset` не участвует в layout. `ZStack`, у которого все дети только смещены оффсетами,
берёт размер самого большого ребёнка (= одна ячейка), и следующий
`.frame(width:height:alignment: .center)` центрирует этот крошечный блок, унося начало координат
на `(область − ячейка)/2` по обеим осям.
Фикс — переписать на настоящий layout:
```swift
ZStack(alignment: .topLeading) {
    Color.clear                                    // держит систему координат = вся область
    VStack(spacing: s) { ForEach(rows) { r in
        HStack(spacing: s) { ForEach(cols) { c in cell(r, c).frame(width: side, height: side) } }
    } }
    .frame(width: geo.size.width, height: geo.size.height)   // центрируется штатно
    if dragging { liftedCell.offset(x: originX + tx, y: originY + ty) }  // оффсет — только для «летящего» элемента
}
```
Стек получает ровно `boardWidth × boardHeight`, его края попадают точно в `insetX/insetY` из
метрик — позиция и попадание больше не расходятся. Пустую ячейку отдавать как
`Color.clear.frame(width: side, height: side)`, иначе ряд схлопывается.
**Компонент доски обычно переиспользуется на 5–10 экранах — баг глобальный, чинится один раз
в компоненте, а не на каждом экране.**

**B. Нечитаемая подпись на плитке / чипе.**
Симптом: под иконкой имя сущности превращается в кашу. `.nano` (9pt) + `lineLimit(1)` +
`minimumScaleFactor(0.7)` на плитке 78pt ужимает «Blood Orange Sorbet» до ~6pt.
Фикс: имя — минимум `.micro` (12pt), **две строки**, `.multilineTextAlignment(.center)`,
`minimumScaleFactor` не ниже 0.85, ширина контента ≥ 96pt. Чтобы ряд не стал рваным при разной
длине имён, под блок имени резервируй фиксированную высоту:
`@ScaledMetric(relativeTo: .caption) private var nameHeight: CGFloat = 32` +
`.frame(width: contentWidth, height: nameHeight, alignment: .top)`, и обязательный
`.denseTypeLimit()` на плитке. Прикидка: 12pt полужирный ≈ 6.5pt на символ → на 96pt влезает
~14 символов в строку, 28 в две (это и есть разумный лимит имени в редакторе).

**C. Безразмерный вью свободным соседом в `ZStack`.**
Симптом на устройстве: элемент интерфейса вдруг занял пол-экрана (чаще всего — таббар); либо
соседние ячейки одного ряда стоят на РАЗНОЙ высоте и «разъехались» — у одной есть декорация,
у остальных нет.
Причина: `LinearGradient`/`RadialGradient`/`AngularGradient`, `Color`, `Shape`/`Rectangle`/
`Capsule` без `.frame` — БЕЗРАЗМЕРНЫЕ вью. Своего размера у них нет, они принимают всё, что им
предложат. Свободным ребёнком `ZStack` такой вью становится самым большим ребёнком и сам задаёт
размер контейнера — по обеим осям. Дальше `HStack` ряда берёт высоту самой высокой ячейки,
остальные центрируются в ней, и ряд визуально разваливается.
Важно: это НЕ про «оверсайз-арт». Чаще всего это мелкая декоративная подсветка внутри кнопки
или ячейки на 48pt — именно поэтому правило про оверсайз-арт её не ловит.
Фикс — декорация никогда не сосед контента, а фон/оверлей НА контенте:
```swift
// было — градиент сам решает, какой высоты будет ячейка
ZStack(alignment: .top) {
    if isSelected { LinearGradient(...).clipShape(Niche()) }   // ← безразмерный сосед
    VStack { icon; label }
}

// стало — фон принимает размер контента и влиять на layout не может
VStack { icon; label }
    .frame(maxWidth: .infinity, minHeight: 48)                 // ← размер задаёт контент
    .background(alignment: .top) { if isSelected { LinearGradient(...).clipShape(Niche()) } }
```
Свободным соседом безразмерный вью допустим ТОЛЬКО когда `ZStack` сразу после этого получает
явный `.frame(width:height:)`.
Метод проверки: греп по `LinearGradient(`, `RadialGradient(`, `Color.`, `Rectangle()` — и на
КАЖДОМ вхождении ответь на один вопрос: кто здесь задаёт размер? Если ответ «этот вью» —
переписывай.
**Прицельно — таббар.** Ячейка обязана иметь явный `.frame(maxWidth: .infinity, minHeight: 48)`
и раскладывать ОДИНАКОВЫЙ контент в обоих состояниях (тот же размер знака, та же одна строка
подписи с `lineLimit(1)`) — меняются только цвет и стиль знака. Подсветка выбранной вкладки —
только через `.background(...)`. Плюс `.denseTypeLimit()` на ряд.

**D. Обводка вылезает за фрейм → соседи наплывают друг на друга.**
Симптом: три кольца в ряду стоят вплотную, между ними нет места; выделенная ячейка сетки съедает
зазор до соседей; кольцо в `HStack` с текстом наезжает на текст.
Причина: `.stroke(lineWidth: w)` рисуется ПО ЦЕНТРУ пути — половина уходит наружу. Фрейм
резервирует `size`, а краска занимает `size + w`. Кольцо `size: 94` даёт `stroke = 9.4`, ink
103.4pt, и при `HStack(spacing: 10)` реальный зазор `10 − 9.4 = 0.6pt`.
Увеличивать `spacing` — лечение симптома. Чинить ink:
```swift
Circle().stroke(track, lineWidth: w).padding(w / 2)          // край краски встаёт ровно на фрейм
Circle().trim(from: 0, to: v).stroke(c, style: .init(lineWidth: w, lineCap: .round))
    .padding(w / 2).rotationEffect(.degrees(-90))            // padding ДО rotationEffect
RoundedRectangle(cornerRadius: r).strokeBorder(c, lineWidth: w)   // для рамок — strokeBorder
```
Порог: `lineWidth ≥ 3` — инсетить обязательно; `lineWidth 1–1.5` (рамки карточек, чипов) можно
оставить, перелив 0.5–0.75pt, это стандартная практика iOS.
Ряд из 2–3 колец раскладывать не «фикс. размер + фикс. spacing», а фикс. размер +
`.frame(maxWidth: .infinity)` на КАЖДОМ — остаток делится поровну. Размер под самый узкий экран:
внутри карточки на 375pt доступно `375 − 32 − 32 = 311pt` → три кольца по 92 + два зазора по 8 =
292pt. Константы — в одно место (`enum RingRow`), иначе экраны разъедутся по размеру колец.

### 1. Найди все источники horizontal overflow
Проверь каждый файл во Features/, Shared/, Views/ на следующие паттерны-источники проблем:
- HStack с fixedSize() элементами рядом с длинным контентом. Самые опасные комбинации:
  - Иконка (40–60pt) + VStack(title + description) + 3+ tag/chip-пилюль + Spacer + checkmark в одном HStack
  - Несколько TagView / SelectableChip / StatusBadge подряд с .fixedSize()
  - Текст без .lineLimit(N) рядом с другими элементами
- ScrollView, чей внутренний VStack не имеет .frame(maxWidth: .infinity, alignment: .leading) — контейнер схлопывается до ширины самого узкого ребёнка вместо ширины экрана
- Sheet-ы (NavigationStack/View внутри sheet) без явного frame(maxWidth: .infinity) на root-VStack
- SectionCard / кастомные card-обёртки, не задающие .frame(maxWidth: .infinity, alignment: .leading) внутри своего background → ширина определяется контентом
- Padding на VStack vs на отдельных карточках — должен быть только один уровень padding (предпочтительно на root VStack, единый: .padding(.horizontal, 16)), иначе появляется двойной отступ
- HStack с Spacer() где Spacer выдавливает контент за пределы при переполнении соседей

### 2. Применяй эти правила-фиксы

A. Top-level ScrollView VStack:
    ScrollView {
        VStack(spacing: 16) {
            // ...content...
        }
        .frame(maxWidth: .infinity, alignment: .leading)  // ← обязательно
        .padding(.horizontal, 16)
        .padding(.bottom, 100)  // ≥ tabbar height
    }

B. Card / SectionCard обёртка:
    content
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)  // ← обязательно
        .background(...)
        .cornerRadius(12)

C. Карточки с иконкой + title + tags + actions — разделяй на две строки:
    // ❌ ПЛОХО: всё в одном HStack
    HStack { IconBadge; VStack { title; desc; HStack { Tag1; Tag2; Tag3 } }; Spacer; Checkmark }

    // ✅ ХОРОШО: VStack из двух рядов, теги получают всю ширину карточки
    VStack(alignment: .leading, spacing: 12) {
        HStack {
            IconBadge
            VStack { title.lineLimit(1); desc.fixedSize(horizontal: false, vertical: true) }
                .frame(maxWidth: .infinity, alignment: .leading)
            if isSelected { Checkmark }
        }
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) { Tag1; Tag2; Tag3 }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

D. Текст внутри HStack с другими элементами:
- Заголовки: .lineLimit(1) или .lineLimit(2).minimumScaleFactor(0.85)
- Многострочные описания: .fixedSize(horizontal: false, vertical: true)
- Длинные имена/коды: .truncationMode(.middle)

E. Tag-ряды на узких экранах:
- Если ≤2 коротких тэга → обычный HStack
- Если ≥3 или есть длинные подписи → ScrollView(.horizontal, showsIndicators: false) { HStack(spacing: 6) { ... } }
- Никогда не комбинируй fixedSize() тэги в HStack с растягивающимся VStack-контентом

F. Кнопки с растяжением:
    PrimaryButton(...).frame(maxWidth: .infinity)
    HStack(spacing: 10) {
        Button(...).frame(maxWidth: .infinity)
        Button(...).frame(maxWidth: .infinity)
    }

G. Sheets (form-sheets):
    NavigationStack {
        ScrollView(showsIndicators: false) {
            VStack(spacing: 20) { /* form fields */ }
                .frame(maxWidth: .infinity, alignment: .leading)  // ← обязательно
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 40)
        }
        .background(BG.ignoresSafeArea())
        .navigationTitle("...")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .navigationBarLeading) { Button("Cancel") { dismiss() } } }
    }
    .presentationDetents([.large])

H. Toolbar/header HStack:
    HStack {
        Button(...)          // leading
        Spacer()
        Text(title)          // centered
        Spacer()
        Text("counter").frame(width: 50)  // ← фикс trailing-ширина, чтобы title по центру
    }
    .padding(.horizontal, 16)

### 3. Проверь все View и Sheet по чек-листу
- [ ] Top-level VStack в ScrollView имеет frame(maxWidth: .infinity, alignment: .leading)
- [ ] Все cards/SectionCard имеют frame(maxWidth: .infinity, alignment: .leading) внутри
- [ ] Нет HStack с >2 fixedSize() элементов рядом с растягивающимся контентом
- [ ] Все длинные тексты имеют lineLimit или truncationMode
- [ ] Tag/chip-ряды либо коротки (≤2), либо обёрнуты в горизонтальный ScrollView
- [ ] Sheet'ы используют единый паттерн (NavigationStack + Cancel toolbar + maxWidth root)
- [ ] padding только на одном уровне (root VStack или каждой карточке, не обоих)
- [ ] EmptyStateView, AlertBanner, headers — все имеют frame(maxWidth: .infinity)
- [ ] Нет hard-coded ширин типа .frame(width: 300) для responsive-контента (только иконки/badge)

### 3b. Вертикаль — арт-зоны и короткие экраны
Всё выше — про ширину. Отдельно проверь два случая, где режет и пустует по ВЫСОТЕ (формулы и
обоснование — в `$HOME/.claude/CLAUDE.md`, раздел «Вёрстка», пункты про интро-арт):

- **Арт в `GeometryReader` фиксированной высоты** (Loader, Onboarding, баннеры) почти всегда
  стоит под `.clipped()`, а высота там маленькая (~200pt) — значит режет сверху/снизу, а не по
  бокам. Координаты элементов обязаны быть заклампены по ОБЕИМ осям с отступом от собственного
  размера элемента (`inset = размер/2 + воздух`), а радиус кольца — `min(w,h)/2 − элемент/2 − воздух`,
  НЕ доля от половины высоты. Проверять арифметикой: координата крайнего элемента ± его половина
  обязана лежать внутри `0…h`. На глаз этот баг не виден, пока не посмотришь на нужный слайд.
- **Короткий экран в top-aligned скролле** прилипает к шапке, а перед нижней закреплённой кнопкой
  остаётся дыра в пол-экрана («всё смещено вверх»). Лечится не отступами, а центрированием:
  `.frame(minHeight: geo.size.height, alignment: .center)` на контенте внутри своего клампованного
  скролла. Общий `ScreenScrollView` при этом НЕ трогать — он скопирован из эталона.

### 4. Переполнение или восприятие?
Иногда «выходит за края» — перцептивная проблема: карточки слишком близко к краю при тонком padding на широких экранах. Стандарт iOS: 16pt по горизонтали (HIG), для воздушного дизайна 20pt, не более 24pt.

### 5. Тестирование
После правок обязательно собери проект:
    DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
      -project *.xcodeproj -scheme YourScheme \
      -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
      build CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD"
Цель: ** BUILD SUCCEEDED **. Если есть симулятор — проверь на iPhone SE (375pt) и iPhone Pro Max (430pt).

### 5b. Swift Charts — ось значений
Если в проекте есть `Chart`, проверь и почини БЕЗ отдельного подтверждения:
- `grep -rn "chartYAxis" --include="*.swift"` — должно быть ровно ОДНО совпадение, внутри общего
  хелпера UI-кита. Каждое лишнее — экран, который пишет ось сам.
- Хелпер: `AxisMarks(position: .leading, values: …)` (НЕ `.automatic` — она уводит подписи на
  trailing, ровно под конец серии) + `AxisValueLabel` с `.lineLimit(1)`, `.minimumScaleFactor(0.6)`
  и ЯВНЫМ `.frame(width:alignment: .trailing)` — явная ширина и резервирует жёлоб оси.
- Столбчатая диаграмма: `x: .value(…, someString)` — band-шкала. `Int`-индекс даёт непрерывную
  шкалу, крайний столбик встаёт на границу plot-области и наезжает на цифры.
- Линия/область: band недопустим, оставляй непрерывный x, но добавь запас
  `.chartXScale(domain: -0.35 ... Double(count-1) + 0.35)`.
- Нулевое значение не должно молча пропадать (столбик нулевой высоты читается как потеря данных).

### 6. Что НЕ нужно делать
- ❌ Не используй .fixedSize() глобально
- ❌ Не задавай .frame(width: ...) для контентных карточек
- ❌ Не используй GeometryReader ради вычисления ширины родителя
- ❌ Не добавляй padding и на VStack, и на каждую карточку
- ❌ Не оставляй комментариями TODO-фиксы — фикси сразу

Найди ВСЕ места — не только то, что выглядит проблемно на конкретном скриншоте. Цель: визуальная консистентность на iPhone SE и iPhone Pro Max одновременно.
