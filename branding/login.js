/*
 * AI Hub login page: the left-hand panel (mark, headline, and a sample chat that cycles
 * through examples of what the assistant can do).
 *
 * The panel is a decorative <aside> appended to <body>, outside LibreChat's React tree, so
 * React never re-renders over it. While the login screen is showing, <html> carries the
 * class `aihub-login`; space.css then shows the panel on wide screens and moves the form to
 * the right half. Every other page is left as it is. All text here is fixed in this file.
 *
 * Loaded as a deferred <script> from index.html (docker-compose.override.yml).
 */
(function () {
  var MARK = 'assets/custom/mark.svg?v=4';
  var PRODUCT = 'AI Hub';
  var HEADLINE = 'Start with<br>a <em>thought</em>.';
  var INTERVAL_MS = 6000;
  var FADE_MS = 450;

  var DOWNLOAD =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>';
  var SEND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg>';

  function file(type, colour, name, meta) {
    return (
      '<div class="ah-file"><b style="background:' + colour + '">' + type + '</b><div>' + name +
      '<small>' + meta + '</small></div><i>' + DOWNLOAD + '</i></div>'
    );
  }

  function bars(heights, highlight) {
    return (
      '<div class="ah-bars">' +
      heights
        .map(function (h, i) {
          return '<i style="height:' + h + '%"' + (i === highlight ? ' class="ah-hi"' : '') + '></i>';
        })
        .join('') +
      '</div>'
    );
  }

  var SCENES = [
    {
      q: 'Turn this report into slides',
      a: 'Done — here are the key points as a short deck.',
      x: file('PPTX', '#f05023', 'Quarterly-summary.pptx', '5 slides · 1.2 MB'),
    },
    {
      q: 'Compare sales for Q1 to Q3',
      a: 'Sales grew 18% — Q3 led, driven by online orders.',
      x: file('XLSX', '#1ab06c', 'Sales-Q1-Q3.xlsx', '3 sheets · with chart'),
    },
    {
      q: 'Draft a memo about the new leave policy',
      a: 'Here is a one-page memo, ready to send.',
      x: file('DOCX', '#3b6fd9', 'Leave-policy-memo.docx', '1 page · A4'),
    },
    {
      q: 'Chart our monthly sign-ups',
      a: 'Sign-ups climbed steadily, with a jump in June.',
      x: bars([34, 42, 39, 51, 58, 86, 74], 5),
    },
    {
      q: 'Summarise this 40-page PDF',
      a: 'Three things that matter most:',
      x: '<ul class="ah-pts"><li>Costs fall 12% after year two</li><li>Rollout takes six months</li><li>Main risk is staff training</li></ul>',
    },
    {
      q: 'แปลอีเมลนี้เป็นภาษาไทยให้หน่อย',
      a: 'ได้เลยครับ นี่คือฉบับภาษาไทย:',
      x: '<div class="ah-quote">เรียนทุกท่าน ขอแจ้งว่าการประชุมประจำเดือนจะเลื่อนเป็นวันศุกร์นี้ เวลา 10.00 น.</div>',
    },
  ];

  function sceneHtml(s) {
    return (
      '<div class="ah-q">' + s.q + '</div><div class="ah-a"><img src="' + MARK + '" alt=""><div>' +
      s.a + s.x + '</div></div>'
    );
  }

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var panel;
  var thread;
  var current = Math.floor(Math.random() * SCENES.length);
  var timer = null;

  function build() {
    panel = document.createElement('aside');
    panel.id = 'aihub-panel';
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML =
      '<div class="ah-brand"><img src="' + MARK + '" alt="">' + PRODUCT + '</div>' +
      '<div class="ah-body"><h2>' + HEADLINE + '</h2><div class="ah-chat"><div class="ah-thread"></div>' +
      '<div class="ah-ask">Reply to ' + PRODUCT + '…<span class="ah-send">' + SEND + '</span></div></div></div>';
    document.body.appendChild(panel);
    thread = panel.querySelector('.ah-thread');
    thread.innerHTML = sceneHtml(SCENES[current]);
  }

  function next() {
    if (document.hidden) {
      return;
    }
    var n = Math.floor(Math.random() * (SCENES.length - 1));
    current = n >= current ? n + 1 : n;
    thread.classList.add('ah-out');
    setTimeout(function () {
      thread.innerHTML = sceneHtml(SCENES[current]);
      thread.classList.remove('ah-out');
    }, FADE_MS);
  }

  /* Same test as space.css: the login form, or SSO buttons with no other form. */
  function isLoginScreen() {
    if (document.querySelector('form[aria-label="Login form"]')) {
      return true;
    }
    var main = document.querySelector('#root main');
    return !!(main && main.querySelector('a[href*="/oauth/"]') && !main.querySelector('form'));
  }

  function update() {
    var on = isLoginScreen();
    document.documentElement.classList.toggle('aihub-login', on);
    if (on && !timer && !reduceMotion) {
      timer = setInterval(next, INTERVAL_MS);
    } else if (!on && timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function start() {
    build();
    update();
    var root = document.getElementById('root') || document.body;
    var pending = false;
    new MutationObserver(function () {
      if (pending) {
        return;
      }
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        update();
      });
    }).observe(root, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
