# CMUBS AI Hub branding

Custom look for a Docker deployment of LibreChat — CMUBS logo and tagline, login title, and an
animated login backdrop (deep space in dark mode, a sky above the clouds in light mode).
No LibreChat source file or image is modified: everything is layered on at container start
by `docker-compose.override.yml`.

## How it works

| Piece | Mechanism |
| --- | --- |
| Logo and icons | Bind-mounted over the files in `/app/client/dist/assets/` |
| Login backdrop, title, card, button | `space.css`, linked into `index.html` by the api container's start command |
| Scope | CSS `:has(form[aria-label="Login form"])` — only the login page changes |
| Theme | `html.dark` → space, otherwise → sky |
| Language | `lang.js` makes English the default for anyone who hasn't picked one in Settings; the login form follows the chosen language |

## Files

| File | Purpose |
| --- | --- |
| `cmubs-logo.png` | Source logo (a 1024px+ PNG or an SVG gives sharper results) |
| `build-icons.js` | Builds `icons/`: light and dark logos, and round favicons / app icons from the dot mark |
| `build-space-css.js` | Builds `space.css`; login title, colours, and animation live here |
| `space.css`, `icons/` | Generated — do not edit by hand |

## Apply to a deployment

1. Copy `branding/`, `docker-compose.override.yml`, and `librechat.yaml` next to
   `docker-compose.yml`.
2. In that deployment's `.env` (never committed), set `APP_TITLE=CMUBS AI Hub` — the
   system name shown in the browser tab once the app loads.
3. `docker compose up -d --force-recreate api`
4. Open `/login`.

## Change something

| To change | Do |
| --- | --- |
| Logo | Replace `cmubs-logo.png`, run `node branding/build-icons.js`, bump `LOGO_VERSION` in `build-space-css.js` and the favicon `?v=` in the override |
| Login heading and tagline (per language) | `LOGIN_TITLES`, `LOGIN_TAGLINES` in `build-space-css.js` |
| System name | `APP_TITLE` in `.env`, and the `<title>` replacement in `docker-compose.override.yml` |
| New-chat greetings (random per page load, EN/TH) | `GREETINGS` in `build-space-css.js`; `librechat.yaml` `customWelcome` stays `{{user.name}}` |
| Admin panel name | the `sed` lines under `admin-panel` in `docker-compose.override.yml`; icon is `icons/favicon.ico` |
| Backdrop | Edit `build-space-css.js` |

Then run `node branding/build-space-css.js`, bump `?v=` in `docker-compose.override.yml`
(browsers cache static files for two days), and recreate the api container.

Both build scripts need Node.js and the repo's `node_modules` (`build-icons.js` uses `sharp`).

## After a LibreChat upgrade

The CSS keys off LibreChat's login markup (`form[aria-label="Login form"]`,
`img[src="assets/logo.svg"]`, `[data-testid="login-button"]`, `[role="contentinfo"]`). If an
upgrade changes it, the login page falls back to LibreChat's default look — sign-in keeps
working — and the selectors in `build-space-css.js` need updating.
