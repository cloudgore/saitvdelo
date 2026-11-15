(function () {
  'use strict';
  const cfg = window.SVD_ANALYTICS || {};
  const version = '2026-11-07-v2';
  const key = 'svd_analytics_choice_v1';
  const noticeKey = 'svd_cookie_notice_v2';
  const maxAge = 180 * 24 * 60 * 60 * 1000;
  const counter = Number(cfg.metrikaId);
  const available = cfg.enabled === true && Number.isSafeInteger(counter) && counter > 0;
  let running = false;
  let busy = false;
  let focusedBefore = null;
  let choice = readChoice();

  function readChoice() {
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      if (saved && saved.version === version && ['granted', 'denied'].includes(saved.status) && Number.isFinite(saved.time) && saved.time <= Date.now() && Date.now() - saved.time < maxAge) return saved;
    } catch (_) {}
    return null;
  }

  function noticeSeen() {
    try {
      const time = Number(localStorage.getItem(noticeKey));
      return time > 0 && time <= Date.now() && Date.now() - time < maxAge;
    } catch (_) {
      return false;
    }
  }

  function storeChoice(value) {
    choice = value;
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
  }

  function clearMetricaStorage() {
    for (const storageName of ['localStorage', 'sessionStorage']) {
      try {
        const storage = window[storageName];
        for (const name of Object.keys(storage)) if (/^_ym/.test(name)) storage.removeItem(name);
      } catch (_) {}
    }
    const names = document.cookie.split(';').map(item => item.split('=')[0].trim()).filter(name => /^_ym/.test(name));
    const parts = location.hostname.split('.');
    const domains = ['', location.hostname, '.' + location.hostname];
    if (parts.length > 2) domains.push('.' + parts.slice(-2).join('.'));
    for (const name of names) for (const domain of domains) {
      document.cookie = name + '=; Max-Age=0; Path=/; SameSite=Lax' + (domain ? '; Domain=' + domain : '') + (location.protocol === 'https:' ? '; Secure' : '');
    }
  }

  function start() {
    if (!available || running || !choice || choice.status !== 'granted' || !/^[a-f0-9]{64}$/.test(choice.receipt || '')) return;
    running = true;
    if (typeof window.ym !== 'function') {
      window.ym = function () { (window.ym.a = window.ym.a || []).push(arguments); };
      window.ym.l = Date.now();
    }
    const script = document.createElement('script');
    script.async = true;
    script.dataset.svdMetrica = 'true';
    script.src = 'https://mc.yandex.ru/metrika/tag.js?id=' + counter;
    document.head.appendChild(script);
    // No Session Replay, clickmap, advertising matching or user-provided contacts.
    window.ym(counter, 'init', {
      webvisor: false, clickmap: false, trackLinks: false, accurateTrackBounce: true,
      url: location.origin + location.pathname, referrer: '',
      params: { consent_version: version }
    });
  }

  function stop() {
    running = false;
    // Removing the executing document stops queued and future tag activity.
    document.querySelectorAll('script[data-svd-metrica]').forEach(script => script.remove());
    if (window.ym && window.ym.a) window.ym.a.length = 0;
    clearMetricaStorage();
  }

  async function receipt(action) {
    const response = await fetch('/analytics-consent.php', {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', keepalive: true,
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ version: version, action: action, receipt: choice && choice.receipt || null })
    });
    const data = await response.json();
    if (!response.ok || !data.ok || !/^[a-f0-9]{64}$/.test(data.receipt || '')) throw new Error('receipt unavailable');
    return data.receipt;
  }

  const panel = document.createElement('section');
  panel.className = 'analytics-choice';
  panel.setAttribute('role', 'region');
  panel.setAttribute('aria-labelledby', 'analytics-choice-title');
  panel.innerHTML = '<div class="analytics-choice-copy"><h2 id="analytics-choice-title">Куки и Яндекс Метрика</h2><p>Сайт запоминает ваш выбор в браузере. Яндекс Метрика использует куки для статистики посещений и загружается только после разрешения.</p><p><a href="/analytics-consent/">Отдельное согласие на аналитику</a> · <a href="/privacy/">Политика обработки данных</a></p><p class="analytics-choice-status" role="status" aria-live="polite"></p></div><div class="analytics-choice-actions"><button type="button" data-analytics-accept>Разрешить аналитику</button><button type="button" data-analytics-deny>Отказаться</button><button type="button" data-analytics-close hidden>Закрыть настройки</button></div>';
  document.body.appendChild(panel);
  const accept = panel.querySelector('[data-analytics-accept]');
  const deny = panel.querySelector('[data-analytics-deny]');
  const close = panel.querySelector('[data-analytics-close]');
  const status = panel.querySelector('.analytics-choice-status');

  function hide() {
    panel.hidden = true;
    document.body.classList.remove('analytics-choice-open');
    if (focusedBefore && typeof focusedBefore.focus === 'function') focusedBefore.focus();
  }
  function show(fromSettings) {
    focusedBefore = fromSettings ? document.activeElement : null;
    panel.hidden = false;
    close.hidden = !fromSettings;
    deny.textContent = choice && choice.status === 'granted' ? 'Отозвать согласие' : 'Отказаться';
    accept.hidden = !available;
    accept.disabled = !available;
    if (!available && (!choice || choice.status !== 'granted')) deny.textContent = 'Понятно';
    status.textContent = available ? '' : 'Аналитика сейчас отключена владельцем сайта. Передача данных в Метрику не выполняется.';
    document.body.classList.add('analytics-choice-open');
    if (fromSettings) (available ? accept : deny).focus();
  }

  accept.addEventListener('click', async function () {
    if (busy || !available) return;
    busy = true; accept.disabled = true; deny.disabled = true;
    status.textContent = 'Сохраняем ваш выбор…';
    try {
      const id = await receipt('granted');
      storeChoice({ status: 'granted', version: version, time: Date.now(), receipt: id });
      start(); hide();
    } catch (_) {
      status.textContent = 'Не удалось сохранить согласие. Аналитика не включена. Можно продолжить без неё.';
    } finally { busy = false; accept.disabled = !available; deny.disabled = false; }
  });

  deny.addEventListener('click', async function () {
    if (busy) return;
    if (!available && (!choice || choice.status !== 'granted')) {
      try { localStorage.setItem(noticeKey, String(Date.now())); } catch (_) {}
      hide();
      return;
    }
    const wasRunning = running;
    const prior = choice;
    stop();
    storeChoice({ status: 'denied', version: version, time: Date.now(), receipt: prior && prior.receipt || null });
    hide();
    const withdrawal = prior && prior.receipt ? receipt('withdrawn').catch(function () {}) : Promise.resolve();
    if (wasRunning) location.reload();
    else await withdrawal;
  });
  close.addEventListener('click', hide);
  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-analytics-settings]')) show(true);
  });
  window.addEventListener('storage', function (event) {
    if (event.key !== key) return;
    const wasRunning = running;
    choice = readChoice();
    if (!choice || choice.status !== 'granted') {
      stop();
      if (wasRunning) location.reload();
    }
    // Granting in another tab takes effect on this tab after navigation/reload.
  });
  window.addEventListener('svd:portfolio-open', function (event) {
    if (!running || !choice || choice.status !== 'granted') return;
    const project = event.detail && event.detail.project;
    if (typeof project === 'string' && /^[a-z0-9-]{1,60}$/.test(project)) window.ym(counter, 'reachGoal', 'portfolio_open', { project: project });
  });
  document.addEventListener('click', function (event) {
    if (!running || !choice || choice.status !== 'granted') return;
    const a = event.target.closest('a');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (href === 'https://t.me/saitvdelo') window.ym(counter, 'reachGoal', 'telegram_click');
  });

  if (!choice || choice.status !== 'granted' || !available) clearMetricaStorage();
  if (available ? !choice : !noticeSeen()) show(false);
  else { panel.hidden = true; start(); }
})();
