# CMUBS AI Hub branding

Custom look for a Docker deployment of LibreChat — CMUBS logo and tagline, login title, and a
campus skyline backdrop on the login page (white line art on navy in dark mode, teal on light
grey in light mode).
No LibreChat source file or image is modified: everything is layered on at container start
by `docker-compose.override.yml`.

## How it works

| Piece | Mechanism |
| --- | --- |
| Logo and icons | Bind-mounted over the files in `/app/client/dist/assets/` |
| Login backdrop, title, card, button | `space.css`, linked into `index.html` by the api container's start command |
| Scope | CSS `:has(form[aria-label="Login form"])`, or the SSO buttons when there is no form — only the login page changes |
| Theme | `html.dark` → `backdrops/dark.jpg`, otherwise → `backdrops/light.jpg` |
| Language | `lang.js` makes English the default for anyone who hasn't picked one in Settings; the login form follows the chosen language |

## Files

| File | Purpose |
| --- | --- |
| `cmubs-logo.png` | Source logo (a 1024px+ PNG or an SVG gives sharper results) |
| `cmu-logo.webp` | Source for the SSO button icon (the CMU wordmark, white letters and an orange 1) |
| `build-icons.js` | Builds `icons/`: light and dark logos, and round favicons / app icons from the dot mark |
| `backdrops/dark.jpg`, `backdrops/light.jpg` | Login backdrops (2000×1125; plain sky on top, skyline along the bottom) |
| `build-space-css.js` | Builds `space.css`; login title, colours, and backdrop placement live here |
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
| SSO-only login (no email/password form) | `ALLOW_EMAIL_LOGIN=false` in `.env`; the SSO button then takes the primary purple style. Local accounts can no longer sign in through the UI — give an SSO account the ADMIN role first |
| SSO button text | `OPENID_BUTTON_LABEL=Continue with CMU IT Account` in `.env` (one label for every language) |
| SSO button icon | The CMU wordmark: replace `cmu-logo.webp`, run `node branding/build-icons.js` (writes `icons/sso-dark.png` and `icons/sso-light.png`) and bump `LOGO_VERSION`. It replaces the default OpenID glyph via `space.css`; an `OPENID_IMAGE_URL` in `.env` takes precedence |
| Admin panel name | the `sed` lines under `admin-panel` in `docker-compose.override.yml`; icon is `icons/favicon.ico` |
| Backdrop | Replace the image in `backdrops/`, update its `sky` colour in `BACKDROPS` in `build-space-css.js` if it changed, and bump `BACKDROP_VERSION` |

Then run `node branding/build-space-css.js`, bump `?v=` in `docker-compose.override.yml`
(browsers cache static files for two days), and recreate the api container.

Both build scripts need Node.js and the repo's `node_modules` (`build-icons.js` uses `sharp`).

## After a LibreChat upgrade

The CSS keys off LibreChat's login markup (`form[aria-label="Login form"]`,
`a[href*="/oauth/"]`, `img[src="assets/logo.svg"]`, `[data-testid="login-button"]`,
`[role="contentinfo"]`). If an
upgrade changes it, the login page falls back to LibreChat's default look — sign-in keeps
working — and the selectors in `build-space-css.js` need updating.
