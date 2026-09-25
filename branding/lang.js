/*
 * CMUBS AI Hub: English is the default interface language.
 *
 * LibreChat picks its language from the `lang` cookie, then localStorage `lang`, then the
 * browser language. Choosing a language in Settings sets that cookie, so a visitor without
 * it has never chosen one: give them English. Anyone who later picks a language in
 * Settings keeps it, because the cookie then exists and this script leaves it alone.
 *
 * Loaded as a classic <script> in <head>, so it runs before LibreChat's module bundle.
 */
(function () {
  var DEFAULT_LANG = 'en-US';
  try {
    if (/(?:^|;\s*)lang=/.test(document.cookie)) {
      return;
    }
    localStorage.setItem('lang', JSON.stringify(DEFAULT_LANG));
    document.cookie = 'lang=' + DEFAULT_LANG + '; path=/; max-age=31536000; SameSite=Lax';
    document.documentElement.lang = DEFAULT_LANG;
  } catch (e) {
    /* Storage blocked (private mode, strict settings): LibreChat falls back as usual. */
  }
})();
