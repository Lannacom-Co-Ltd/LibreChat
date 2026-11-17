/*
 * Lannacom AI Hub login page: the left-hand panel (mark, headline, and a sample chat that
 * cycles through examples of what the assistant can do), in English or Thai to match the
 * interface language.
 *
 * The panel is a decorative <aside> appended to <body>, outside LibreChat's React tree, so
 * React never re-renders over it. While the login screen is showing, <html> carries the
 * class `aihub-login`; space.css then shows the panel on wide screens and moves the form to
 * the right half. Every other page is left as it is. All text here is fixed in this file.
 *
 * Language: LibreChat sets <html lang> from the visitor's choice in Settings, or else from the
 * device's language; the panel follows it (Thai for `th`, English otherwise) and switches
 * when it changes. Theme needs nothing here: LibreChat follows the device's light/dark
 * setting until the visitor picks one, and space.css follows <html class="dark">.
 *
 * Loaded as a deferred <script> from index.html (docker-compose.override.yml).
 */
(function () {
  var MARK = 'assets/custom/mark.svg?v=4';
  var PRODUCT = 'Lannacom AI Hub';
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

  function points(items) {
    return '<ul class="ah-pts"><li>' + items.join('</li><li>') + '</li></ul>';
  }

  var SIGNUPS = bars([34, 42, 39, 51, 58, 86, 74], 5);

  /* The same six examples in each language; the translation example goes the other way. */
  var TEXT = {
    en: {
      headline: 'Start with<br>a <em>thought</em>.',
      ask: 'Ask anything…',
      scenes: [
        { q: 'Turn this report into slides', a: 'Done — here are the key points as a short deck.', x: file('PPTX', '#f05023', 'Quarterly-summary.pptx', '5 slides · 1.2 MB') },
        { q: 'Compare sales for Q1 to Q3', a: 'Sales grew 18% — Q3 led, driven by online orders.', x: file('XLSX', '#1ab06c', 'Sales-Q1-Q3.xlsx', '3 sheets · with chart') },
        { q: 'Draft a memo about the new leave policy', a: 'Here is a one-page memo, ready to send.', x: file('DOCX', '#3b6fd9', 'Leave-policy-memo.docx', '1 page · A4') },
        { q: 'Chart our monthly sign-ups', a: 'Sign-ups climbed steadily, with a jump in June.', x: SIGNUPS },
        { q: 'Summarise this 40-page PDF', a: 'Three things that matter most:', x: points(['Costs fall 12% after year two', 'Rollout takes six months', 'Main risk is staff training']) },
        { q: 'แปลอีเมลนี้เป็นภาษาไทยให้หน่อย', a: 'ได้เลยครับ นี่คือฉบับภาษาไทย:', x: '<div class="ah-quote">เรียนทุกท่าน ขอแจ้งว่าการประชุมประจำเดือนจะเลื่อนเป็นวันศุกร์นี้ เวลา 10.00 น.</div>' },
      ],
    },
    th: {
      headline: 'ทุกงานเริ่มจาก<br><em>ความคิด</em>',
      ask: 'ถามอะไรก็ได้…',
      scenes: [
        { q: 'ช่วยทำสไลด์จากรายงานนี้หน่อย', a: 'เสร็จแล้วครับ สรุปประเด็นสำคัญเป็นสไลด์ 5 หน้าให้แล้ว', x: file('PPTX', '#f05023', 'Quarterly-summary.pptx', '5 สไลด์ · 1.2 MB') },
        { q: 'เทียบยอดขายไตรมาส 1–3 ให้หน่อย', a: 'ยอดขายโตขึ้น 18% ไตรมาส 3 ดีที่สุด เพราะยอดสั่งซื้อออนไลน์', x: file('XLSX', '#1ab06c', 'Sales-Q1-Q3.xlsx', '3 ชีต · มีกราฟ') },
        { q: 'ช่วยร่างประกาศเรื่องระเบียบการลาใหม่', a: 'ร่างประกาศ 1 หน้าเสร็จแล้ว ส่งต่อได้เลยครับ', x: file('DOCX', '#3b6fd9', 'Leave-policy-memo.docx', '1 หน้า · A4') },
        { q: 'ทำกราฟยอดสมัครสมาชิกแต่ละเดือน', a: 'ยอดสมัครเพิ่มขึ้นเรื่อย ๆ และสูงสุดในเดือนมิถุนายน', x: SIGNUPS },
        { q: 'สรุป PDF 40 หน้านี้ให้หน่อย', a: 'สรุปสั้น ๆ 3 ข้อหลัก:', x: points(['ต้นทุนลดลง 12% ตั้งแต่ปีที่ 3', 'ใช้เวลาวางระบบ 6 เดือน', 'ความเสี่ยงหลักคือการอบรมพนักงาน']) },
        { q: 'แปลอีเมลนี้เป็นภาษาอังกฤษให้หน่อย', a: 'ได้เลยครับ นี่คือฉบับภาษาอังกฤษ:', x: '<div class="ah-quote">Dear all, this month’s meeting has moved to Friday at 10:00.</div>' },
      ],
    },
  };

  /*
   * Plainer wording for LibreChat's own Thai text on the login page, matched exactly. Only text
   * nodes inside the login screen are touched, and in place (nodeValue), so React keeps its
   * reference and any later update it makes is caught and reworded again.
   */
  var THAI_WORDING = {
    'ยินดีต้อนรับกลับ': 'ยินดีต้อนรับกลับมา',
    'อีเมลแอดเดรส': 'อีเมล',
    'ดำเนินการต่อ': 'เข้าสู่ระบบ',
    'จำเป็นต้องระบุอีเมล': 'กรุณากรอกอีเมล',
    'จำเป็นต้องระบุรหัสผ่าน': 'กรุณากรอกรหัสผ่าน',
    'คุณต้องป้อนที่อยู่อีเมลที่ถูกต้อง': 'รูปแบบอีเมลไม่ถูกต้อง',
    'ไม่สามารถเข้าสู่ระบบด้วยข้อมูลที่ให้มา โปรดตรวจสอบข้อมูลประจำตัวของคุณและลองอีกครั้ง':
      'อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง',
    'ลงทะเบียน': 'สมัครใช้งาน',
  };

  function rewordThai() {
    var page = document.querySelector('#root > div');
    if (!page) {
      return;
    }
    var walker = document.createTreeWalker(page, NodeFilter.SHOW_TEXT);
    for (var node = walker.nextNode(); node; node = walker.nextNode()) {
      var plain = THAI_WORDING[node.nodeValue.trim()];
      if (plain) {
        node.nodeValue = plain;
      }
    }
  }

  function langNow() {
    return /^th\b/i.test(document.documentElement.lang || '') ? 'th' : 'en';
  }

  function sceneHtml(s) {
    return (
      '<div class="ah-q">' + s.q + '</div><div class="ah-a"><img src="' + MARK + '" alt=""><div>' +
      s.a + s.x + '</div></div>'
    );
  }

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var panel;
  var thread;
  var lang = null;
  var current = Math.floor(Math.random() * TEXT.en.scenes.length);
  var timer = null;

  function build() {
    panel = document.createElement('aside');
    panel.id = 'aihub-panel';
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML =
      '<div class="ah-brand"><img src="' + MARK + '" alt="">' + PRODUCT + '</div>' +
      '<div class="ah-body"><h2></h2><div class="ah-chat"><div class="ah-thread"></div>' +
      '<div class="ah-ask"><span class="ah-ask-text"></span><span class="ah-send">' + SEND + '</span></div></div></div>';
    document.body.appendChild(panel);
    thread = panel.querySelector('.ah-thread');
  }

  /* Writes the panel's text in the current interface language (only when it changed). */
  function localize() {
    var next = langNow();
    if (next === lang) {
      return;
    }
    lang = next;
    var t = TEXT[lang];
    panel.setAttribute('lang', lang);
    panel.querySelector('h2').innerHTML = t.headline;
    panel.querySelector('.ah-ask-text').textContent = t.ask;
    thread.innerHTML = sceneHtml(t.scenes[current]);
  }

  function next() {
    if (document.hidden) {
      return;
    }
    var scenes = TEXT[lang].scenes;
    var n = Math.floor(Math.random() * (scenes.length - 1));
    current = n >= current ? n + 1 : n;
    thread.classList.add('ah-out');
    setTimeout(function () {
      thread.innerHTML = sceneHtml(TEXT[lang].scenes[current]);
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
    if (on) {
      localize();
      if (lang === 'th') {
        rewordThai();
      }
    }
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
    var pending = false;
    var schedule = function () {
      if (pending) {
        return;
      }
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        update();
      });
    };
    new MutationObserver(schedule).observe(document.getElementById('root') || document.body, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    /* LibreChat updates <html lang> when the language changes. */
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
