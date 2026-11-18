# Lannacom AI Hub branding

Custom look for a Docker deployment of LibreChat: the Lannacom AI Hub mark (green circle, orange
square), a split-screen login page, a random new-chat greeting and file-download buttons in
chat. Warm neutral surfaces in both themes (off-white in light mode, warm charcoal in dark
mode) with the mark's orange as the accent.
No LibreChat source file or image is modified: everything is layered on at container start
by `docker-compose.override.yml`.

## The login page

| Screen | Layout |
| --- | --- |
| 960px wide and up | Left half: the mark, the headline "Start with a *thought*." and a sample chat that switches to a random example every 6 seconds (slides, a spreadsheet, a memo, a chart, a PDF summary, a reply to an email), written in the interface language. Right half: LibreChat's sign-in form, restyled |
| Narrower | One centred column, as on Linear / ChatGPT: the mark, "Sign in to Lannacom AI Hub" (Thai: "เข้าสู่ระบบ Lannacom AI Hub"), the SSO button, OR, then the email form; buttons look the same as on wide screens |

With `ALLOW_EMAIL_LOGIN=false` the SSO button takes the primary (filled) style. The privacy
and terms links are hidden on the login page. Visitors who ask their system to reduce motion
see one random example and no switching.

Theme and language follow the device until the visitor picks one in Settings: a phone set to
Thai and dark mode gets the Thai interface in dark mode, one set to English and light mode
gets that. The left panel switches with the interface language (Thai for `th`, English for
everything else); the form's own text comes from LibreChat's translations.

## How it works

| Piece | Mechanism |
| --- | --- |
| Mark and icons | `mark.svg` → `build-icons.js` → `icons/`, bind-mounted over the files in `/app/client/dist/assets/` |
| Login form look, fonts, greeting, file buttons | `space.css`, linked into `index.html` by the api container's start command |
| Left panel | `login.js` adds an `<aside>` to `<body>` (outside LibreChat's React tree) and sets `html.aihub-login` while the login screen shows; `space.css` lays it out |
| Scope | CSS `:has(form[aria-label="Login form"])`, or the SSO buttons when there is no form — only the login page changes |
| Theme | `html.dark` → dark tokens, otherwise light tokens (`THEMES` in `build-space-css.js`) |
| Theme and language | LibreChat's own defaults: the device's light/dark setting and language until the visitor picks one; `login.js` follows `<html lang>` |

## Files

| File | Purpose |
| --- | --- |
| `mark.svg` | The mark (source for every icon) |
| `build-icons.js` | Builds `icons/`: `logo.svg`, favicons, app icons, `favicon.ico` |
| `fonts/fraunces*.woff2`, `fonts/plex-thai-*.woff2`, `fonts/OFL-*.txt` | Fraunces (login headings, Latin) and IBM Plex Sans Thai. Text uses LibreChat's own Inter; Plex Thai is added to the Inter family for Thai characters only, so Thai looks the same on every device, on the login page and inside the app. SIL Open Font License |
| `build-space-css.js` | Builds `space.css` and `greeting.js`; colours, sizes and greetings live here |
| `login.js` | The login page's left panel: headline and sample chats in English and Thai (`TEXT`); plainer Thai for LibreChat's own login wording, e.g. "เข้าสู่ระบบ" for "ดำเนินการต่อ" (`THAI_WORDING`) |
| `admin/manifest.json` | Admin panel name and icon |
| `space.css`, `greeting.js`, `icons/` | Generated — do not edit by hand |

## Apply to a deployment

1. Copy `branding/`, `docker-compose.override.yml`, and `librechat.yaml` next to
   `docker-compose.yml`.
2. In that deployment's `.env` (never committed), set `APP_TITLE=Lannacom AI Hub` — the system name
   shown in the browser tab once the app loads.
3. `docker compose up -d --force-recreate api` (a plain `restart` keeps the old `index.html`).
4. Open `/login`.

## Change something

| To change | Do |
| --- | --- |
| Mark | Edit `mark.svg`, run `node branding/build-icons.js`, bump `LOGO_VERSION` in `build-space-css.js`, the `mark.svg?v=` in `login.js` and the favicon `?v=` in the override |
| Headline or sample chats (per language) | `TEXT` in `login.js`; bump `login.js?v=` in the override |
| Colours | `THEMES` in `build-space-css.js` |
| System name | `APP_TITLE` in `.env`, the `<title>` replacement in the override, `PRODUCT_NAME` in `build-space-css.js` and `PRODUCT` in `login.js` |
| New-chat greetings (random per page load, EN/TH) | `GREETINGS` in `build-space-css.js`; `librechat.yaml` `customWelcome` stays `{{user.name}}` |
| SSO-only login | `ALLOW_EMAIL_LOGIN=false` in `.env`. Local accounts can no longer sign in through the UI — give an SSO account the ADMIN role first |
| SSO button text | `OPENID_BUTTON_LABEL` in `.env` (one label for every language). The OpenID glyph is drawn as a padlock; an `OPENID_IMAGE_URL` takes precedence |
| Admin panel name | the `sed` lines under `admin-panel` in the override and `admin/manifest.json`; icon is `icons/favicon.ico` |

Then run `node branding/build-space-css.js`, bump `?v=` in `docker-compose.override.yml`
(browsers cache static files for two days), and recreate the api container.

Both build scripts need Node.js and the repo's `node_modules` (`build-icons.js` uses `sharp`).

## After a LibreChat upgrade

The CSS and `login.js` key off LibreChat's login markup (`form[aria-label="Login form"]`,
`a[href*="/oauth/"]`, `img[src="assets/logo.svg"]`, `[data-testid="login-button"]`,
`[role="contentinfo"]`, `svg#openid`). If an upgrade changes it, the login page falls back to
LibreChat's default look — sign-in keeps working — and the selectors need updating.
