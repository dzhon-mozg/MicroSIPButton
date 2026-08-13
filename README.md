# MicroSIPButton — кнопка-палитра для MicroSIP

Копируете номер телефона (Ctrl+C) → нажимаете кнопку → номер отформатирован и вставлен в поле набора MicroSIP за одно нажатие.

## Что делает

В MicroSIP нет встроенного форматирования номеров перед звонком. Приходится вручную стирать лишние цифры, добавлять префикс. MicroSIPButton делает это автоматически:

1. Берёт номер из буфера обмена
2. Оставляет последние 10 цифр
3. Добавляет префикс (по умолчанию `98` — для SIP-провайдеров)
4. Вставляет готовый номер в поле набора MicroSIP

**Одно нажатие.** Не надо переключаться между окнами, выделять текст, редактировать вручную.

## Быстрый старт

1. Скачать [`MicroSIPButton.exe`](../../releases/latest) из Releases
2. Скопировать `launch.bat` в ту же папку
3. Запустить MicroSIP, затем MicroSIPButton.exe

Дальше: копируете номер → жмёте синюю кнопку 📞.

### Свой префикс

```
MicroSIPButton.exe --prefix "+7"
```

## Особенности интерфейса

- Кнопка прикреплена к окну MicroSIP (справа, по центру) и следует за ним при перемещении/редизайне
- Прячется при сворачивании MicroSIP и при уходе в трей
- Не перекрывает другие приложения (выше MicroSIP, но ниже остальных окон)
- Не видна в Alt+Tab и не забирает фокус при клике
- **Перетаскивание**: зажмите правую кнопку мыши и двигайте кнопку. Две зоны — слева и справа от окна MicroSIP: от 1.5 размеров кнопки внутри окна до 3 размеров снаружи. Кнопку можно ставить прямо на границу окна. По вертикали — в пределах окна MicroSIP. Во время перетаскивания зоны подсвечиваются зелёным с яркими границами. Позиция запоминается и восстанавливается при следующем запуске.

## Требования

- Windows 10/11
- [MicroSIP](https://www.microsip.org/)

## Сборка

```bat
pip install -r requirements.txt
python main.py
```

Сборка в exe:

```bat
pyinstaller --onefile --windowed --icon=icon.ico --name MicroSIPButton main.py
```

---

## MicroSIPButton — palette button for MicroSIP

Copy a phone number (Ctrl+C) → click the button → number is formatted and pasted into MicroSIP's dial field. **One click.**

### What it does

MicroSIP has no built-in number formatting. MicroSIPButton automates it: extracts last 10 digits from clipboard, prepends a prefix (default `98` for SIP providers), and injects the result into the dial field.

### Quick start

1. Download [`MicroSIPButton.exe`](../../releases/latest) from Releases
2. Copy `launch.bat` to the same folder
3. Launch MicroSIP, then MicroSIPButton.exe

Copy a number → click the blue 📞 button.

### Custom prefix

```
MicroSIPButton.exe --prefix "+44"
```

### UI features

- Docks to the right of MicroSIP, follows movement/resizing instantly
- Hides with MicroSIP (minimize and tray)
- Stays above MicroSIP but below other apps
- Invisible in Alt+Tab, does not steal focus
- **Dragging**: hold the right mouse button to move the button. Two zones — left and right of the MicroSIP window: from 1.5 button sizes inside to 3 button sizes outside. The button may sit right on the window border. Vertical movement is limited to MicroSIP's height. The zones are highlighted in green with bright borders while dragging. The position is saved and restored on next launch.

### Requirements

- Windows 10/11
- [MicroSIP](https://www.microsip.org/)

### Build

```bat
pip install -r requirements.txt
pyinstaller --onefile --windowed --icon=icon.ico --name MicroSIPButton main.py
```
