---
description: Сборка без симулятора (xcodebuild) → устранить ошибки до BUILD SUCCEEDED
---
Собери проект БЕЗ запуска симулятора, чтобы проверить ошибки компиляции, и устрани их.

1. Найди `.xcodeproj` (или `.xcworkspace`) и определи имя схемы автоматически:
   `xcodebuild -list -project *.xcodeproj`
2. Запусти сборку под iOS Simulator без подписи:
   ```
   DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
     -project *.xcodeproj -scheme "<SCHEME>" \
     -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
     build CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD"
   ```
3. Если есть ошибки компиляции — открой указанные файлы, исправь настоящую причину (не подавляй ошибку), пересобери.
4. Повторяй, пока не получишь `** BUILD SUCCEEDED **`.
5. Не запускай симулятор. Не меняй логику ради «зелёного» билда — чини корневую причину.

В конце выведи финальный статус сборки.
