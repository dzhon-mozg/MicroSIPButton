# CLAUDE.md — инструкция для AI-агентов (OpenCode, Claude, ChatGPT и др.)

## О проекте

MicroSIPButton — оконное приложение на Python 3 + wxPython. Это кнопка-палитра, прикреплённая к окну MicroSIP (SIP-софтфон). Нажатие форматирует номер телефона из буфера обмена (`98` + последние 10 цифр) и вставляет в поле набора MicroSIP через Win32 API.

## Структура проекта

```
MicroSIPButton/
├── main.py              # Точка входа: wx.App, owned-окно, хук, трей, форматирование
├── microsip.py          # Взаимодействие с MicroSIP: поиск окон/exe, WM_PASTE с проверкой
├── build.bat            # Сборка exe (PyInstaller) + установщик (Inno Setup)
├── extract_icon.py      # Извлекает полноразмерную иконку MicroSIP (16–256px) в icon.ico
├── version_info.txt     # Версия/метаданные для exe (PyInstaller --version-file)
├── installer/
│   ├── MicroSIPButton.iss  # Скрипт Inno Setup (per-user, проверка MicroSIP, чекбоксы)
│   └── bundled/            # Портабельный MicroSIP для установки «из комплекта»
├── requirements.txt     # wxPython>=4.2.0
├── .gitignore
├── README.md            # Инструкция для пользователей
└── CLAUDE.md            # Этот файл — инструкция для AI
```

## Ключевая архитектура

### Окно как owned-потомок MicroSIP

Главная фишка: окно кнопки **не topmost** (не поверх всех окон), а привязано к окну MicroSIP через `SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, microsip_hwnd)` — cross-process ownership. Это даёт:

- Кнопка всегда выше MicroSIP в z-order, но не выше других приложений
- Автоматически прячется при минимизации MicroSIP
- `WS_EX_NOACTIVATE` — клик не крадёт фокус у MicroSIP
- `WS_EX_TOOLWINDOW` — не видна в Alt+Tab

### Отслеживание позиции и видимости (событийное, v2)

Главное улучшение: позиция и видимость отслеживаются **событийно**, без опроса таймером. Используется Win32 хук `SetWinEventHook`, покрывающий диапазон событий от `EVENT_SYSTEM_MINIMIZESTART` (0x0016) до `EVENT_OBJECT_LOCATIONCHANGE` (0x800B):

```python
EVENT_OBJECT_SHOW       = 0x8002  # окно показано
EVENT_OBJECT_HIDE       = 0x8003  # окно скрыто
EVENT_OBJECT_LOCATIONCHANGE = 0x800B  # перемещение / редизайн
EVENT_SYSTEM_MINIMIZESTART = 0x0016  # сворачивание
EVENT_SYSTEM_MINIMIZEEND   = 0x0017  # разворачивание
```

Архитектура:
1. **Один хук** на весь диапазон. Фильтрация: только `hwnd == host_hwnd` и `idObject == OBJID_WINDOW`.
2. **Перемещение** — колбэк → `wx.CallAfter(_do_position_scheduled)` с дебаунсом (флаг `_position_scheduled` не даёт копить очередь при быстрых перетаскиваниях).
3. **Видимость** — колбэк → `wx.CallAfter(_sync_visibility)`, проверяет `IsIconic` + `IsWindowVisible`, при расхождении вызывает `ShowWindow`.
4. **Страховочный таймер** (раз в 2 сек): `IsWindow` (жив ли хост) + безусловный `_sync_visibility` (на случай пропуска события).

Привязка по умолчанию: справа от окна MicroSIP (отступ 4px), вертикально по центру, с проверкой границ экрана.

### Перетаскивание кнопки (правый клик)

Кнопку можно перемещать, зажав **правую** кнопку мыши. Позиция сохраняется в `%APPDATA%\MicroSIPButton\config.json` (`{"zone", "offset", "y_offset"}`) и восстанавливается при старте. Старый конфиг (4 зоны, `gap`) мигрируется при загрузке.

2 зоны, считаются от `rect` окна MicroSIP (`S` = размер кнопки, `offset` = смещение левого края кнопки от границы окна):

| Зона | Диапазон offset | Итог |
|---|---|---|
| `left` | `[−3S, +1.5S]` от левой границы | от 3S снаружи до 1.5S внутри |
| `right` | `[−1.5S, +3S]` от правой границы | от 1.5S внутри до 3S снаружи |

- **На границу ставить можно** — кнопка может пересекать ребро окна (offset ∈ (−S, 0) для левой зоны).
- Середина окна запрещена — при попадании курсора туда срабатывает снап к ближайшему краю зоны (`snap_x` → ближайшая точка объединения интервалов).
- Вертикаль: `y ∈ [top, bottom − S]`.
- Кламп к **виртуальному экрану** (`GetSystemMetrics` 76–79: SM_XVIRTUALSCREEN…SM_CYVIRTUALSCREEN), чтобы кнопка работала на любом мониторе, а не только основном. Хелпер — `_virtual_screen()`.

Чистые функции (без GUI, тестируются `--selftest`):
- `snap_ranges(rect)` — 2 интервала разрешённых X
- `zone_rects(rect)` — 2 прямоугольника подсветки
- `snap_x(x, ranges)` — снап X к ближайшему интервалу
- `placement_coords(zone, offset, y_offset, rect, ...)` — экранные координаты из состояния размещения
- `overlay_rgba(w, h, ...)` — пиксельный BGRA-буфер (преумноженная альфа, bottom-up) для подсветки зон

Драг: `EVT_RIGHT_DOWN` → `CaptureMouse`, смещение курсора от кнопки, показ подсветок; `EVT_MOTION` → `snap_x` по зонам + кламп вертикали, `MoveWindow`; `EVT_RIGHT_UP`/`EVT_MOUSE_CAPTURE_LOST` → скрыть подсветки, `_store_placement()` пишет зону/offset/y_offset в конфиг. На время драга хук и таймер игнорируются (флаг `_dragging`), чтобы не бороться с курсором.

Подсветка зон: класс `ZoneOverlay` — 2 окна с попиксельной прозрачностью (layered: `WS_EX_LAYERED` + `UpdateLayeredWindow` с 32-битной DIB), owned-потомки MicroSIP, `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT`, z-order ниже кнопки. Визуал: рамка `OVERLAY_BORDER_PX` px цветом `OVERLAY_BORDER` (почти непрозрачная), от неё внутрь градиент `OVERLAY_GRADIENT_PX` px к полупрозрачной заливке `OVERLAY_FILL`. Создаются лениво при первом драге, позиционируются по `zone_rects` (показ — `UpdateLayeredWindow` + `ShowWindow(SW_SHOWNA)`, скрытие — `ShowWindow(SW_HIDE)`). Важно: после смены ex-style через `SetWindowLongPtrW` нужен `SetWindowPos(SWP_FRAMECHANGED)`, иначе `WS_EX_LAYERED` не применится.

### Запуск MicroSIP и трей-иконка (v3)

При старте `ButtonApp.OnInit` ищет окно MicroSIP (`FindWindowW`). Если не найдено:
1. `find_microsip_exe(explicit)` в `microsip.py` — поиск microsip.exe по порядку: аргумент `--microsip <путь>` → реестр HKCU (uninstall-запись MicroSIP) → `%LOCALAPPDATA%\MicroSIP\MicroSIP.exe` → папка exe (и подпапка `MicroSIP`) → `%ProgramFiles%`/`%ProgramFiles(x86)%`.
2. Найден → `subprocess.Popen([exe])` и ожидание окна до `MICROSIP_WAIT_SECONDS` (20 сек, поллинг 0.2 сек).
3. Не найден → сообщение «Установите MicroSIP…» и выход.

Трей: `TrayIcon(wx.adv.TaskBarIcon)` с меню «Префикс…» и «Выход». «Префикс…» — `wx.TextEntryDialog` → `ButtonApp.set_prefix()`: сохраняет в config.json и обновляет `ButtonFrame._prefix` в рантайме. Иконка берётся из `MicroSIP.exe` в рантайме (`_microsip_icon`: `shell32.ExtractIconExW` → `wx.Icon.CreateFromHICON`, хендл передаётся wx в собственность — `DestroyIcon` для small не вызывать, иначе access violation). Фолбэк — нарисованная `_drawn_tray_icon`. Выход из трея и смерть хоста (таймер) завершают всё приложение через `ExitMainLoop`; очистка — в `ButtonApp.OnExit` (хук, таймер, окно, трей).

Префикс (`_resolve_prefix`): `--prefix` из командной строки → `config.json["prefix"]` → `"98"`. Конфиг хранит `{zone, offset, y_offset, prefix}`; `_save_config(**updates)` мержит с существующим (не затирает).

### Установщик (Inno Setup)

`installer/MicroSIPButton.iss` собирается командой `ISCC.exe /DAppVersion=<версия>` (Inno Setup 6.7, путь по умолчанию `D:\Programs\InnoSetup\ISCC.exe`):
- **Per-user**: `PrivilegesRequired=lowest`, установка в `{localappdata}\Programs\MicroSIPButton`, без UAC.
- **Проверка MicroSIP**: функция `MicroSIPInstalled()` (реестр HKCU + файл). Если найден — задача `installmicrosip` отключена; если нет — чекбокс «Установить MicroSIP (из комплекта)» включён по умолчанию. При снятом чекбоксе `PrepareToInstall` спрашивает подтверждение.
- **Комплект**: `bundled\*` → `{localappdata}\MicroSIP` (только при задаче `installmicrosip`). Флаг `MicroSIPBundled=1` в `HKCU\Software\MicroSIPButton` — деинсталлятор удаляет только файлы комплекта (по имени, список в `BundledMicroSIPFiles`), настройки/контакты MicroSIP не трогает.
- Ярлыки: меню «Пуск» (программа + удаление), рабочий стол по чекбоксу. `[Run]` — запуск после установки.
- Языки: русский (по умолчанию) + английский. Обновление версии комплекта MicroSIP: заменить файлы в `installer/bundled/` и список файлов для удаления в `CurUninstallStepChanged`.

### Вставка в поле набора

`microsip.paste_to_microsip(formatted)`:
1. `FindWindowW("MicroSIP", None)` — поиск окна MicroSIP
2. `EnumChildWindows` — поиск первого видимого Edit-контрола (поле набора)
3. `ShowWindow(SW_RESTORE)` + `SetForegroundWindow` — развернуть MicroSIP из трея
4. `SendMessage(edit, EM_SETSEL, 0, -1)` — выделить всё
5. `SendMessage(edit, WM_PASTE)` — вставка из буфера (номер уже скопирован туда перед вызовом)
6. `SendMessage(edit, WM_GETTEXT)` — проверка, что номер вставился полностью
7. При несовпадении — повтор (до 2 попыток)
8. Фолбэк: `SendMessage(edit, WM_SETTEXT)` — прямая установка текста

### Форматирование телефона

Алгоритм в `_format_phone`:
```python
digits = [c for c in raw if c.isdigit()]
if len(digits) >= 10:
    formatted = "98" + "".join(digits[-10:])
```
Берёт последние 10 цифр из буфера, добавляет префикс (по умолчанию `98`, задаётся через трей или `--prefix`).

## Сборка

```bat
pip install -r requirements.txt    # Установка зависимостей (нужен wxPython)
python main.py                     # Запуск для разработки
build.bat                          # exe (PyInstaller) + установщик (Inno Setup)
```

`build.bat`: PyInstaller (`--onefile --windowed --icon=icon.ico --version-file=version_info.txt`) → `ISCC.exe /DAppVersion=<VERSION>` → результат `installer\Output\MicroSIPButton-Setup-<версия>.exe`. Версия задаётся переменной `VERSION` в начале build.bat. Комплект MicroSIP должен лежать в `installer\bundled\` (портабельный zip с microsip.org).

`extract_icon.py` вытаскивает полноразмерную иконку (16–256px) из `installer\bundled\MicroSIP.exe` в `icon.ico` (парсинг RT_GROUP_ICON/RT_ICON ресурсов PE). Запускается автоматически из `build.bat` при наличии комплекта, чтобы иконка exe/ярлыков не отставала от версии MicroSIP. Важно: у ctypes-вызовов обязательны `argtypes`/`restype` (без них `LoadLibraryExW` обрезает 64-битный хендл до 32 бит), а `EnumResourceNamesW` с колбэком падает в Python 3.14 — вместо него перебор ID через `FindResourceW`.

## Тестирование

Ручное: закрыть MicroSIP, затем `python main.py`:
- Кнопка сама запускает MicroSIP и прикрепляется (ожидание до 20 сек)
- При запущенном MicroSIP — прикрепление без запуска второго экземпляра
- Проверить прикрепление кнопки справа от окна
- Проверить следование при перетаскивании MicroSIP
- Свернуть MicroSIP → кнопка должна спрятаться
- Закрыть MicroSIP в трей (крестик) → кнопка должна спрятаться
- Скопировать номер с 10+ цифрами → нажать кнопку → проверить вставку
- Проверить, что кнопка не видна в Alt+Tab и не забирает фокус
- Трей: правая кнопка → «Префикс…» → ввести префикс → применяется сразу и сохраняется в config.json
- Трей: правая кнопка → «Выход» → приложение полностью завершается

Установщик: `installer\Output\MicroSIPButton-Setup-*.exe` — установить, проверить ярлыки и запуск; удалить через «Удалить MicroSIPButton», проверить, что MicroSIP из комплекта удалён, а настройки остались.

Драг (правая кнопка):
- Перетащить в каждую из 2 зон (слева/справа) — видны 2 зелёные подсветки
- Поставить кнопку на границу окна (наполовину внутри/снаружи) — можно
- Середина окна запрещена — кнопка снапится к ближайшему краю зоны
- Вертикаль ограничена верхом/низом окна MicroSIP
- После перетаскивания: подвигать MicroSIP — кнопка сохраняет зону и отступы
- Перезапустить MicroSIPButton — позиция восстановилась из config.json

Самопроверка логики зон без GUI: `python main.py --selftest`.

Скрипт для проверки `WM_PASTE` отдельно от GUI: см. логику в `microsip.py` — функции самодостаточны и могут вызываться из любого скрипта.

## Распространённые задачи

### Изменить позицию прикрепления

Позиция задаётся перетаскиванием правой кнопкой (см. выше). Геометрия — чистые функции `placement_coords`/`snap_ranges`/`zone_rects` в `main.py`. Размеры зон — `ZONE_INSIDE_PX`/`ZONE_OUTSIDE_PX`, визуал подсветки — `OVERLAY_FILL`/`OVERLAY_BORDER`/`OVERLAY_GRADIENT_PX`/`OVERLAY_BORDER_PX`.

### Изменить алгоритм форматирования

Править метод `_format_phone` в `main.py`.

### Добавить поддержку других SIP-клиентов

1. В `microsip.py` заменить `FindWindowW("MicroSIP", ...)` на имя класса другого клиента
2. Или параметризовать — добавить конфиг/аргумент командной строки

### Поменять внешний вид кнопки

Цвет фона: `panel.SetBackgroundColour(wx.Colour(R, G, B))` в `ButtonFrame.__init__`.
Размер: константа `BUTTON_SIZE_PX`, размер иконки-трубки: `BTN_FONT_PT` в `main.py`.

## Ограничения

- Только Windows (Win32 API: FindWindowW, SendMessage, ownership)
- Только один экземпляр MicroSIP (берет первый найденный по классу окна)
- При закрытии MicroSIP кнопка завершается вместе с ним — запустить MicroSIPButton заново (ownership разрушается вместе с хозяином)
- Не работает без MicroSIP (сам запускает при наличии exe, иначе сообщение и выход)
