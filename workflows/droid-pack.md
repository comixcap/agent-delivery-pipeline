---
description: "Сдача Android-игры: clean, чистый zip + APK на стол, STORE_LISTING, переезд в ZMAndroid"
---

# /droid-pack — упаковать игру для заказчика

Проект (по умолчанию — текущая игра на рабочем столе): $ARGUMENTS

**Прочитай раздел «Сдача» в `$HOME/.claude/rules/android-games.md`.**

1. Свежая сборка до BUILD SUCCESSFUL, APK скопировать: `~/Desktop/<Имя>.apk`.
2. `./gradlew clean`, затем zip:
   `cd ~/Desktop && zip -r <Имя>.zip <Папка> -x "<Папка>/app/build/*" -x "<Папка>/build/*" -x "<Папка>/.gradle/*" -x "<Папка>/local.properties" -x "*.DS_Store"`
   (если проект уже в ZMAndroid — cd туда же и zip оттуда, файл класть на стол).
3. Проверить `unzip -l`: врапперы внутри (`gradlew`, `gradlew.bat`, `gradle/wrapper/*`),
   мусора нет.
4. `STORE_LISTING.txt` в корне проекта, если ещё нет: EN, без эмодзи, Short ≤80 символов,
   Long (хук, вопрос, How to Play, Game Features, призыв), 10 keywords, Category.
   Только реальные фичи, без названия игры в тексте.
5. Отправить оператору zip + APK (SendUserFile), подписи: zip — проект заказчику,
   APK — проверить на телефоне за 30 секунд.
6. Если игра закончена и ещё на рабочем столе — предложить переезд в
   `$PIPELINE_ROOT/android/` (или переместить, если оператор уже просил).
