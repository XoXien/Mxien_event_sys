// Fetch a fresh attendance QR image and keep the displayed countdown in sync with Django.
const qrImage = document.getElementById('student-qr');
const qrUrl = qrImage.src;
const countdown = document.getElementById('countdown');
const loading = document.getElementById('qr-loading');
const errorBox = document.getElementById('qr-error');
// Track the QR expiry, retry time, active image URL, and current request.
let expiresAt = 0;
let retryAt = 0;
let currentObjectUrl = null;
let refreshing = false;

// Keep one refresh request active and show the loading state while it runs.
async function refreshQR() {
  if (refreshing) return;
  refreshing = true;
  loading.hidden = false;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  const startedAt = performance.now();

  try {
    // Request a fresh image using the student's signed-in session.
    const response = await fetch(qrUrl, {
      cache: 'no-store',
      credentials: 'same-origin',
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('QR request failed.');
    // Read the expiry header so the browser follows the server's QR validity window.
    const serverExpiry = Number(response.headers.get('X-QR-Expires-At'));
    const serverTime = Number(response.headers.get('X-QR-Server-Time')) || Date.now() / 1000;
    if (!Number.isFinite(serverExpiry) || serverExpiry <= 0) {
      throw new Error('QR expiry information missing.');
    }

    // Turn the image response into a temporary URL and release the previous one.
    const nextObjectUrl = URL.createObjectURL(await response.blob());
    if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = nextObjectUrl;
    qrImage.src = currentObjectUrl;
    qrImage.hidden = false;
    // A phone's wall clock may be wrong. Use the server's remaining validity and a
    // monotonic timer, subtracting the request time so the countdown stays conservative.
    expiresAt = performance.now() + Math.max(0, (serverExpiry - serverTime) * 1000 - (performance.now() - startedAt));
    retryAt = 0;
    errorBox.hidden = true;
  // Hide the unavailable QR and wait a few seconds before retrying.
  } catch {
    retryAt = performance.now() + 4000;
    qrImage.hidden = true;
    errorBox.hidden = false;
  } finally {
    window.clearTimeout(timeout);
    loading.hidden = true;
    refreshing = false;
  }
}

// Show the seconds remaining and refresh when the timer reaches zero.
function updateCountdown() {
  const now = performance.now();
  const remaining = Math.max(0, Math.ceil((expiresAt - now) / 1000));
  countdown.textContent = remaining ? `${remaining}s` : '…';
  if (!remaining && now >= retryAt) refreshQR();
}

// Only the overview preview is hidden on phones. The full My QR page always refreshes.
const isOverview = qrImage.closest('.student-overview-grid') !== null;
const phoneScreen = window.matchMedia('(max-width: 650px)');
let qrTimer;

function updateRefreshState() {
  if (isOverview && phoneScreen.matches) {
    clearInterval(qrTimer);
    qrTimer = undefined;
    return;
  }
  if (qrTimer !== undefined) return;
  refreshQR();
  qrTimer = setInterval(updateCountdown, 250);
}

if (isOverview) phoneScreen.addEventListener('change', updateRefreshState);
updateRefreshState();
function refreshVisibleQR() {
  if (document.hidden) return;
  updateRefreshState();
  if (qrTimer !== undefined) updateCountdown();
}
document.addEventListener('visibilitychange', refreshVisibleQR);
window.addEventListener('online', refreshVisibleQR);
// Release the timer and image when leaving the page. Keep them for browser history restores.
window.addEventListener('pagehide', (event) => {
  if (event.persisted) return;
  clearInterval(qrTimer);
  if (isOverview) phoneScreen.removeEventListener('change', updateRefreshState);
  document.removeEventListener('visibilitychange', refreshVisibleQR);
  window.removeEventListener('online', refreshVisibleQR);
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
});
