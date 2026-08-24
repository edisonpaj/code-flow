(() => {
  const IDLE_LIMIT_MS = 5 * 60 * 1000;
  const ACTIVITY_KEY = 'expert-code-flow:last-activity';
  let lastActivity = Date.now();
  let lastRecorded = 0;
  let redirecting = false;

  function recordActivity() {
    const now = Date.now();
    lastActivity = now;
    if (now - lastRecorded > 1000) {
      lastRecorded = now;
      try { localStorage.setItem(ACTIVITY_KEY, String(now)); } catch {}
    }
  }

  async function expireSession() {
    if (redirecting) return;
    redirecting = true;
    try { await fetch('/api/auth/logout', {method: 'POST', keepalive: true}); } catch {}
    location.replace('/login?reason=inactive');
  }

  ['pointerdown', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach(type =>
    addEventListener(type, recordActivity, {passive: true})
  );
  addEventListener('codeflow:activity', recordActivity);
  addEventListener('storage', event => {
    if (event.key === ACTIVITY_KEY && event.newValue) {
      const shared = Number(event.newValue);
      if (Number.isFinite(shared)) lastActivity = Math.max(lastActivity, shared);
    }
  });

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    recordActivity();
    const response = await originalFetch(...args);
    if (response.status === 401 && !location.pathname.startsWith('/login')) expireSession();
    return response;
  };

  recordActivity();
  setInterval(() => {
    let shared = 0;
    try { shared = Number(localStorage.getItem(ACTIVITY_KEY) || 0); } catch {}
    const mostRecent = Math.max(lastActivity, Number.isFinite(shared) ? shared : 0);
    if (Date.now() - mostRecent >= IDLE_LIMIT_MS) expireSession();
  }, 1000);
})();
