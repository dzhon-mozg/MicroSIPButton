# MicroSIPButton — кнопка-палитра для MicroSIP

Копируете номер телефона (Ctrl+C) → нажимаете кнопку → номер отформатирован и вставлен в поле набора MicroSIP за одно нажатие.

## Что делает

В MicroSIP нет встроенного форматирования номеров перед звонком. Приходится вручную стирать лишние цифры, добавлять префикс. MicroSIPButton делает это автоматически:

1. Берёт номер из буфера обмена
2. Оставляет последние 10 цифр
3. Добавляет префикс (по умолчанию `98` — для SIP-провайдеров)
4. Вставляет готовый номер в поле набора MicroSIP

**Одно нажатие.** Не надо переключаться между окнами, выделять текст, редактировать вручную.

## Установка

1. Скачать [`MicroSIPButton-Setup-1.6.exe`](../../releases/latest) из Releases
2. Запустить установщик. Если MicroSIP ещё не установлен — отметить «Установить MicroSIP (из комплекта)»
3. По желанию: ярлык на рабочем столе, запуск сразу после установки

Установка без прав администратора, в `%LOCALAPPDATA%\Programs\MicroSIPButton`.

## Использование

- Запустите MicroSIPButton (ярлык в меню «Пуск»). Если MicroSIP не запущен — кнопка сама его запустит
- Копируете номер → жмёте синюю кнопку 📞
- Значок в трее: правая кнопка → «Префикс…» или «Выход»
- **Перетаскивание кнопки**: зажать правую кнопку мыши. Две зоны — слева и справа от окна MicroSIP, позиция запоминается

### Свой префикс

Правой кнопкой по значку в трее → **«Префикс…»** → ввести префикс (например `+7`). Применяется сразу и сохраняется. По умолчанию — `98`.

Продвинутый способ — аргумент командной строки (перекрывает сохранённый префикс):

```
MicroSIPButton.exe --prefix "+7"
```

## Удаление

«Пуск» → «Удалить MicroSIPButton» (или «Параметры» → «Приложения»). Если MicroSIP был установлен из комплекта — он будет удалён, ваши настройки и контакты MicroSIP сохраняются.

## Особенности интерфейса

- Кнопка прикреплена к окну MicroSIP (справа, по центру) и следует за ним при перемещении/редизайне
- Прячется при сворачивании MicroSIP и при уходе в трей
- Не перекрывает другие приложения (выше MicroSIP, но ниже остальных окон)
- Не видна в Alt+Tab и не забирает фокус при клике

## Требования

- Windows 10/11
- MicroSIP (устанавливается из комплекта либо с [microsip.org](https://www.microsip.org/))

## Ограничения

- Только один экземпляр MicroSIP
- При закрытии MicroSIP кнопка тоже закрывается — запустите MicroSIPButton снова

## Сборка

```bat
pip install -r requirements.txt
python main.py            # запуск для разработки
python main.py --selftest # проверка логики без GUI
build.bat                 # exe + установщик (нужен Inno Setup 6)
```

Результат: `installer\Output\MicroSIPButton-Setup-<версия>.exe`.

---

## MicroSIPButton — palette button for MicroSIP (EN)

Copy a phone number (Ctrl+C) → click the button → number is formatted and pasted into MicroSIP's dial field. **One click.**

### Install

1. Download [`MicroSIPButton-Setup-1.6.exe`](../../releases/latest) from Releases
2. Run the installer. If MicroSIP is not installed, check "Install MicroSIP (bundled)"
3. Optional: desktop shortcut, launch after install

No admin rights required; installs to `%LOCALAPPDATA%\Programs\MicroSIPButton`.

### Usage

- Launch MicroSIPButton (Start Menu shortcut). It starts MicroSIP automatically if not running
- Copy a number → click the blue 📞 button
- Tray icon: right-click → "Prefix…" or "Exit"
- **Drag the button**: hold the right mouse button. Two zones — left and right of the MicroSIP window; position is saved

### Custom prefix

Right-click the tray icon → **"Prefix…"** → enter a prefix (e.g. `+44`). Applied immediately and saved. Default is `98`.

Advanced: command-line argument (overrides the saved prefix):

```
MicroSIPButton.exe --prefix "+44"
```

### Uninstall

Start Menu → "Uninstall MicroSIPButton" (or Settings → Apps). MicroSIP is removed only if it was installed from the bundle; its settings and contacts are kept.

### Requirements / Limitations

- Windows 10/11
- Single MicroSIP instance; the button exits when MicroSIP closes — just relaunch it

### Build

```bat
pip install -r requirements.txt
build.bat   # builds exe + installer (requires Inno Setup 6)
```
