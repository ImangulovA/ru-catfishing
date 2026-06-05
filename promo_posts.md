# ru-catfishing — promo posts

Live: https://imangulova.github.io/ru-catfishing/

---

## 1. LinkedIn (English, architecture-heavy)

**I built a daily web game over a weekend, and I'm unreasonably proud of how it's engineered.**

It's called **ru-catfishing**: every day you get 10 Wikipedia articles stripped down to just their category lists, and you have one shot to name each one. Wordle's daily-ritual loop, but for people who think knowing things is a personality trait.

🔗 https://imangulova.github.io/ru-catfishing/

The fun part is the engineering. A trivia game has one obvious failure mode: **the answers leak to anyone who opens DevTools.** So the whole thing is built around *never shipping a plaintext answer to the browser.*

Architecture, for the nerds:

🧩 **SvelteKit + adapter-static**, deployed to GitHub Pages via GitHub Actions. Zero servers for the core game. The entire thing is a static bundle.

🔒 **Privacy-by-construction answer checking.** Each puzzle ships only three things: the category list, an array of `sha256` hashes of accepted answers, and a `base64`-encoded title that's decoded *only* after you solve or give up. Your guess is hashed client-side and compared against the hash set. No answer text exists in the build. I verified it: grep the bundle, find nothing.

✍️ **A normalization function that has to be byte-identical in two languages.** Author-side it's Python (build time), runtime it's JavaScript. If they ever diverge, real gameplay silently breaks. So `norm()` does the same dance on both sides: lowercase, fold ё/й, drop parentheticals, strip punctuation, collapse doubled letters, sort words. Result: "Dennis Bergkamp" == "Бергкамп Деннис" == "бергкамп". I diff the Python and JS outputs on every change to keep them honest.

🌍 **Cross-language acceptance** via Wikipedia langlinks, so foreign topics answer in English *or* Russian. Ada Lovelace, Pulp Fiction, Mona Lisa: all accepted both ways.

📊 **Global stats on a Cloudflare Worker + D1.** Personal stats live in localStorage (static site, no login). Cross-player aggregates ("you solved this, most players didn't") run on a tiny serverless endpoint with idempotent writes via `sendBeacon`. Static frontend, serverless backend, no monolith.

🎉 Plus confetti on a good day, streak tracking, a calendar archive, and full mobile support. Because shipping is a feature.

The constraint *"a static site can't keep a secret"* turned out to be the most interesting design problem I've solved in months. Obfuscation isn't encryption, and I'm honest about that ceiling, but for a free daily game it's exactly the right amount of paranoia.

Go break my streak. 🐈

#SvelteKit #WebDev #GameDev #Cloudflare #BuildInPublic

---

## 2. Instagram (short)

Сделал игру 🐈

Каждый день 10 статей из Википедии, от которых остались только категории. Угадай статью с одной попытки. Делись результатом, ломай стрики.

Ссылка в шапке 👆
🔗 imangulova.github.io/ru-catfishing

#wikipedia #dailygame #trivia #sveltekit #indiedev

---

## 3. Workplace (LinkedIn copy)

**I built a daily web game over a weekend, and I'm unreasonably proud of how it's engineered.**

It's called **ru-catfishing**: every day you get 10 Wikipedia articles stripped down to just their category lists, and you have one shot to name each one. Wordle's daily-ritual loop, but for people who think knowing things is a personality trait.

🔗 https://imangulova.github.io/ru-catfishing/

The fun part is the engineering. A trivia game has one obvious failure mode: **the answers leak to anyone who opens DevTools.** So the whole thing is built around *never shipping a plaintext answer to the browser.*

Architecture, for the nerds:

🧩 **SvelteKit + adapter-static**, deployed to GitHub Pages via GitHub Actions. Zero servers for the core game.

🔒 **Privacy-by-construction answer checking.** Each puzzle ships only the category list, an array of `sha256` hashes of accepted answers, and a `base64` title decoded only after you solve or give up. Your guess is hashed client-side and compared against the hash set. No answer text exists in the build.

✍️ **A `norm()` that's byte-identical in Python (build) and JS (runtime):** lowercase, fold ё/й, drop parentheticals, strip punctuation, collapse doubled letters, sort words. So "Dennis Bergkamp" == "Бергкамп Деннис". I diff both outputs on every change.

🌍 **Cross-language acceptance** via Wikipedia langlinks: foreign topics answer in EN or RU.

📊 **Global stats on a Cloudflare Worker + D1.** Personal stats in localStorage, cross-player aggregates on a tiny serverless endpoint with idempotent `sendBeacon` writes.

🎉 Plus confetti, streaks, a calendar archive, full mobile support.

The constraint *"a static site can't keep a secret"* was the most interesting design problem I've solved in months. Go break my streak. 🐈

#buildinpublic #webdev #sidequest

---

## 4. Meta community (Russian, short)

Народ, смотрите чо нахуярил за выходные 🐈

**ru-catfishing**: каждый день 10 статей из Википедии, от которых остались одни категории. Угадай с одной попытки, делись результатом, страдай.

Внутри куча красивого инженерства: SvelteKit статикой на GitHub Pages, ответы НИКОГДА не уезжают в браузер открытым текстом (только sha256-хэши + base64), нормализация ответов байт-в-байт одинаковая на питоне и на джаве, кросс-язык через вики-langlinks, и глобальная статистика на Cloudflare Worker + D1.

🔗 https://imangulova.github.io/ru-catfishing/

Залетайте ломать мне стрик.
