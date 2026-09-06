# Порт игр в сторы: mobile / desktop / Steam / itch.io

Статус на 2026-07-06. Пилот: **ru-catfishing** (`~/Desktop/game-designer`).
Решение по формату: **отдельное приложение на каждую игру**, **Android — первым**.
Общий принцип: все игры это SvelteKit + Vite → один статический `build/` кормит ВСЕ платформы.

Игры на диске: `anagram-daily`, `balatrivia`, `battleships`, `game-designer` (catfishing),
`train_tracks`, плюс `games-hub` (лончер).

---

## TL;DR прогресса
- ✅ **Node** поставлен в обход сломанного brew (`~/.local/node`, v24.18.0, прописан в `~/.zshrc`).
- ✅ **catfishing собран и проверен** (`npm run build` → `build/`, пути относительные, смоук-тест 200).
- ✅ **itch.io — ГОТОВО**: `~/Desktop/game-designer/dist/catfishing-itch.zip` можно заливать ($0).
- ⛔ **Android / iOS / Steam / Electron / Tauri — заблокированы на этой корп-машине** (пакетные
  реестры в денилисте прокси Меты). Нужна личная машина или сеть без X2P.

---

## Ограничения этой (рабочей) машины — ПОЧЕМУ всё, кроме itch.io, стоит
Весь внешний трафик идёт через прокси Меты (X2P, `localhost:10054`). Что доступно, что нет:

| Ресурс | Статус | Последствие |
|---|---|---|
| `nodejs.org` | ✅ 200 | Node скачали напрямую |
| `github.com` | ✅ 200 | git-исходники доступны |
| `registry.npmjs.org` | ⛔ 000 | `npm install` новых пакетов падает → **нет Capacitor, нет Electron** |
| `static.crates.io` (CDN крейтов) | ⛔ 403 | `cargo build` не качает зависимости → **Tauri не собрать** |
| `index.crates.io`, `sh.rustup.rs` | ✅ 200 | rustup поставить можно, но толку нет без крейтов |
| `/opt/homebrew` (запись) | ⛔ Operation not permitted | read-only системный том → **brew не работает** (JDK, Android Studio не поставить) |
| `~`, `~/Desktop`, `~/.local`, `~/.cargo` | ✅ пишутся | обычная работа с проектами ок |

Вывод: **на этом ноуте можно делать только itch.io** (не требует новых пакетов, зависимости игры
уже были в `node_modules`). Всё остальное — на личной машине / домашней сети.

---

## Каналы: стоимость, тулинг, статус

| Канал | Обёртка | Деньги | Ревью | Статус здесь |
|---|---|---|---|---|
| **itch.io (HTML5)** | нет, zip из `build/` | **$0** | нет | ✅ готово к заливке |
| **itch.io (десктоп)** | Tauri/Electron | $0 | нет | ⛔ (пакеты закрыты) |
| **Google Play (Android)** | Capacitor | **$25 разово** (аккаунт, на все игры) | почти авто | ⛔ (npm + JDK + Studio) |
| **App Store (iOS)** | Capacitor | **$99/год** (аккаунт) | строгое | ⛔ (npm + Xcode) |
| **Windows/Mac .exe/.dmg** | Tauri (лёгкий) / Electron | $0 без подписи | нет | ⛔ (crates/npm закрыты) |
| **Steam** | Tauri/Electron + Steamworks | **$100 за КАЖДУЮ игру** (возврат после $1000) | есть | ⛔ + Windows-сборка отдельно |

Примечания:
- Мобильные сборы платятся **за аккаунт разработчика** (один раз на все игры). Google $25 разово,
  Apple $99/год.
- Steam — единственный, где платишь **за каждую игру** ($100). Для казуальных daily-головоломок
  спорно: аудитория Steam про "большие" игры, 90% на Windows (с Mac собрать .exe = отдельная боль).
- **Нельзя** публиковать личные игры под корп-аккаунтами Меты и использовать внутренние фреймворки
  Меты для личных проектов (IP-политика). Сборы магазинам платятся из своего кармана в любом случае.

---

## Рекомендованный порядок (когда будем делать)
1. **itch.io (сейчас, $0, здесь)** — залить `catfishing-itch.zip`, получить первую живую версию.
2. **Android (личная машина/сеть)** — Capacitor: `npm i -D @capacitor/cli` + `@capacitor/core`
   `@capacitor/android`, `npx cap init`, `npx cap add android`, `webDir: 'build'`, `npx cap sync`,
   собрать APK/AAB в Android Studio → $25 в Google Play.
3. **Десктоп Win/Mac (личная машина)** — Tauri (лёгкие бинарники), раздача через itch.io/GitHub
   Releases бесплатно.
4. **iOS (опц., личный Mac)** — Capacitor + Xcode → $99/год Apple.
5. **Steam (опц., в последнюю очередь)** — только если решим, что стоит $100/игру и возни с Windows.

---

## Как продолжить (быстрый старт на личной машине)
Node уже умеем ставить без brew:
```
curl -Lo node.tar.gz https://nodejs.org/dist/v24.18.0/node-v24.18.0-darwin-arm64.tar.gz
tar -xzf node.tar.gz -C ~/.local && mv ~/.local/node-v24.18.0-darwin-arm64 ~/.local/node
export PATH="$HOME/.local/node/bin:$PATH"
```
Пересобрать игру:
```
cd ~/Desktop/game-designer/app && npm install && npm run build   # → build/
```
Пересобрать itch.io zip:
```
cd ~/Desktop/game-designer/app/build && zip -qr ../../dist/catfishing-itch.zip . -x '.*'
```

---

## Ключевые пути
- Исходник игры (SvelteKit): `~/Desktop/game-designer/app/`
- Билд (статик, готов для itch.io/Capacitor/Tauri): `~/Desktop/game-designer/app/build/`
- itch.io архив: `~/Desktop/game-designer/dist/catfishing-itch.zip`
- Node: `~/.local/node/bin` (в PATH через `~/.zshrc`)

## Открытые вопросы на потом
- На какой личной машине/сети делаем Android (нужен доступ к npmjs)?
- Нужен ли вообще iOS ($99/год) или хватит Android + itch.io?
- Steam — да/нет? Если да, кто собирает Windows-бинарь (CI типа GitHub Actions)?
- Отдельные приложения на игру vs один хаб — подтверждено "отдельные", но хаб дешевле по ревью.
