---
description: SwiftUI — профилактика пустых вью/sheet/fullScreenCover и гонок презентации
---

## ⚠️ ОБЯЗАТЕЛЬНО ПЕРЕД РАБОТОЙ — прочитай справочники

Это не опция. Правила вынесены из `CLAUDE.md` ради размера, но действуют полностью.
Прочитай эти файлы ДО первой правки кода:

- `$HOME/.claude/rules/layout.md` — вёрстка

---
Проведи полный аудит проекта на iOS 16+ SwiftUI и устрани все классические причины «пустого белого экрана при первом открытии» и гонок презентации. Применяй изменения железно во всех файлах, не выборочно.

1. NavigationView → NavigationStack
- Найди все NavigationView → замени на NavigationStack. NavigationView deprecated в iOS 16, в fullScreenCover/sheet может рендериться пустым контейнером при первом показе.
- Удали все .navigationViewStyle(StackNavigationViewStyle()) — не нужны в NavigationStack.

2. Убери NavigationStack из модалов с кастомным header'ом
Если вью имеет свой header (HStack с xmark-кнопкой + заголовком) и использует .navigationBarHidden(true) — NavigationStack не нужен и ломает первый рендер. Замени NavigationStack { на Group { и удали .navigationBarHidden(true).
NavigationStack оставляй только:
- на корневых таб-экранах
- где реально используются navigationTitle, navigationBarItems, или toolbar с placement .navigationBar*

3. Sheet с if let / опциональным state → .sheet(item:)
Антипаттерн (race-condition, пустой sheet на первый тап):

    @State var selectedId: UUID? = nil
    @State var showDetail = false

    .sheet(isPresented: $showDetail) {
        if let id = selectedId { DetailView(id: id) }
    }

Переделывай на:

    @State var selectedItem: Item? = nil

    .sheet(item: $selectedItem) { item in
        DetailView(item: item)
    }

Презентация и закрытие триггерятся атомарно вместе с данными. Действие кнопки: selectedItem = item, закрытие: selectedItem = nil.

4. Явная инжекция @EnvironmentObject в каждую презентацию
SwiftUI в ряде edge-case'ов (особенно при первом показе) теряет environment object в .fullScreenCover / .sheet. Добавь .environmentObject(...) явно на контент каждого модала:

    .fullScreenCover(isPresented: $showX) {
        SomeView().environmentObject(dataManager)
    }

5. Keyboard toolbar не требует NavigationStack
ToolbarItemGroup(placement: .keyboard) работает через UIKit input accessory view. Его можно оставлять на любой View без NavigationStack.

6. Гарантируй ширину у всех блоков
Любой кастомный контейнер/строку/кнопку, которая должна растягиваться — явно помечай .frame(maxWidth: .infinity). Проверь все: SectionCard, cards, rows, quick-actions, buttons, banners, toast. Это устраняет «гуляющую» ширину на iPhone Pro Max и компактных моделях.

7. .background(...) клади на правильный уровень
Background на ScrollView / VStack внутри модала — да; внутри NavigationStack без background — нет (NavigationStack по умолчанию белый). Всегда:

    .background(BackgroundColor.ignoresSafeArea())

на контенте, не на NavigationStack.

8. App.swift должен быть чистым
Только:

    @main
    struct MyApp: App {
        var body: some Scene {
            WindowGroup { ContentView() }
        }
    }

Никаких init(), @StateObject, onReceive, preferredColorScheme — всё в ContentView или сервисный слой.

9. Все поля ввода имеют keyboard-Done toolbar

    @FocusState private var focused: Bool
    TextField(...).focused($focused)
    .toolbar {
        ToolbarItemGroup(placement: .keyboard) {
            Spacer()
            Button("Done") { focused = false }
        }
    }

Обязательно для App Store review.

10. Каждый sheet/fullScreenCover имеет видимую кнопку закрытия
xmark в кастомном header'е или Cancel в toolbar. Никогда не полагайся только на swipe-down.

11. «Тихие» кнопки → toast / haptic feedback
Любая кнопка, меняющая state, но не открывающая экран и не меняющая что-то видимое сразу — должна давать обратную связь: toast overlay + UINotificationFeedbackGenerator().notificationOccurred(.success).

12. Destructive действия — за .alert
Delete / Reset / Clear — всегда подтверждение через .alert, не прямой вызов.

13. Анимированные transitions на условные вью
Условные блоки (success screen, loader, onboarding) оборачивай в .transition(.opacity) + withAnimation { ... } — иначе мгновенная смена выглядит как баг.

14. @State инициализация в onAppear, не в init
Значения из EnvironmentObject читай в .onAppear { if !initialized { ... } } с флагом. В init вью environment ещё не доступен.

15. Персистентность — Codable + UserDefaults, все методы save/load public или internal
saveX() методы должны вызываться из view при каждой мутации. Тестируй: изменил → убил приложение → запустил → данные на месте.

Команда на выполнение
Проверь каждый .swift файл в Features/ и Views/. По каждому пункту из списка выдай: «ок» или «исправил». В конце — финальный build-check (xcodebuild ... build) и подтверждение BUILD SUCCEEDED.
Не пропускай файлы, не делай выборочно — железно во всём проекте.
