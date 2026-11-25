// Read one rotating QR, review its owner, then save only after an explicit confirmation.
(() => {
  const panel = document.querySelector('[data-attendance-scanner]');
  if (!panel) return;
  const modes = {
    IN: {button: document.getElementById('inBtn'), flag: 'time_in_allowed', label: 'Time In'},
    OUT: {button: document.getElementById('outBtn'), flag: 'time_out_allowed', label: 'Time Out'},
    EXCUSED_OUT: {button: document.getElementById('excusedOutBtn'), flag: 'excused_time_out_allowed', label: 'Excused Time Out'},
  };
  const dialog = document.getElementById('scan-identity-review');
  const confirmButton = dialog.querySelector('[data-review-confirm]');
  const rejectButton = dialog.querySelector('[data-review-reject]');
  const cancelButton = dialog.querySelector('[data-review-cancel]');
  const reviewError = dialog.querySelector('[data-review-error]');
  const expiryLabel = dialog.querySelector('[data-review-expiry]');
  const photo = dialog.querySelector('[data-review-photo]');
  const initials = dialog.querySelector('[data-review-initials]');
  const photoNote = dialog.querySelector('[data-review-photo-note]');
  const timingMessage = document.getElementById('scan-timing-message');
  const result = document.getElementById('result');
  const reminder = panel.querySelector('[data-end-reminder]');
  const endLabel = reminder.querySelector('[data-scheduled-end]');
  const csrfToken = panel.querySelector('[name=csrfmiddlewaretoken]').value;
  const attendanceChannel = typeof BroadcastChannel === 'function'
    ? new BroadcastChannel('attendance-' + panel.dataset.attendanceScanner) : null;
  let timing = JSON.parse(document.getElementById('scanner-timing').textContent);
  let scanType = timing.time_in_allowed ? 'IN' : 'OUT';
  let busy = false;
  let pending;
  let nextScanAt = 0;
  let reviewTimer;
  let timingTimer;
  let timingVersion = 0;
  let camera;
  let cameraRunning = false;
  let cameraPaused = false;
  const recentDecodes = new Map();

  function setResult(message, kind = '') {
    result.textContent = message;
    result.className = 'scan-result ' + kind;
    if (kind) document.dispatchEvent(new CustomEvent('bsit:feedback', {detail: {message, level: kind}}));
  }

  function setScanType(type) {
    scanType = type;
    for (const [mode, {button}] of Object.entries(modes)) button.setAttribute('aria-pressed', String(mode === type));
    if (type) setResult(`Ready for ${modes[type].label}.`);
  }

  function updateButtons() {
    for (const {button, flag} of Object.values(modes)) button.disabled = busy || !!pending || !timing[flag];
    modes.EXCUSED_OUT.button.hidden = !timing.excused_time_out_allowed;
    confirmButton.disabled = busy || !pending || pending.expired || pending.invalidated;
    rejectButton.disabled = cancelButton.disabled = busy;
  }

  function stopCamera() {
    if (!cameraRunning) return;
    cameraRunning = cameraPaused = false;
    camera.stop().catch(() => {});
  }

  function pauseCamera() {
    if (!cameraRunning || cameraPaused || typeof camera.pause !== 'function') return;
    try { camera.pause(false); cameraPaused = true; } catch {}
  }

  function resumeCamera() {
    if (!timing.scanning_open) { stopCamera(); return; }
    if (!cameraRunning || !cameraPaused) return;
    try { camera.resume(); cameraPaused = false; } catch {
      setResult('The camera could not resume. Reload the scanner.', 'error');
    }
  }

  function showReviewError(message) {
    reviewError.textContent = message;
    reviewError.hidden = !message;
  }

  function applyTiming(updated) {
    timingVersion += 1;
    timing = updated;
    timingMessage.textContent = timing.message;
    endLabel.textContent = timing.end_label;
    reminder.hidden = !timing.show_end_reminder;
    if (pending) {
      // A review can finish after the QR rotates or the session ends. Cancellation or
      // revoked scanner access still invalidates it immediately.
      if (timing.state === 'closed' || timing.access_revoked) {
        pending.invalidated = true;
        showReviewError('This event or scanner is no longer available. Cancel this scan.');
        stopCamera();
      }
      updateButtons();
      return;
    }
    if (!timing.scanning_open) {
      setScanType(null);
      setResult(timing.message);
      stopCamera();
    } else if (!timing.time_in_allowed && scanType !== 'OUT') {
      setScanType('OUT');
    } else if (scanType && !timing[modes[scanType].flag]) {
      setScanType(null);
      setResult('Choose an available scan mode.');
    }
    updateButtons();
  }

  function scheduleTimingRefresh(delay) {
    window.clearTimeout(timingTimer);
    if (timing.scanning_open || pending) timingTimer = window.setTimeout(refreshTiming, delay);
  }

  async function refreshTiming() {
    const version = timingVersion;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    let delay = 3000;
    try {
      const response = await fetch(panel.dataset.timingUrl, {cache: 'no-store', signal: controller.signal});
      if (version !== timingVersion) return;
      if (response.redirected || [401, 403, 404].includes(response.status)) {
        applyTiming({scanning_open: false, time_in_allowed: false, time_out_allowed: false,
          excused_time_out_allowed: false, show_end_reminder: false, access_revoked: true,
          end_label: timing.end_label, message: 'This scanner is no longer available.'});
      } else if (response.ok) {
        const updated = await response.json();
        if (version !== timingVersion) return;
        applyTiming(updated);
        delay = timing.refresh_after_ms;
      }
    } catch {
      if (version !== timingVersion) return;
    } finally { window.clearTimeout(timeout); }
    scheduleTimingRefresh(delay);
  }

  function rememberDecode(key, duration) {
    recentDecodes.delete(key);
    recentDecodes.set(key, performance.now() + duration);
    if (recentDecodes.size > 128) recentDecodes.delete(recentDecodes.keys().next().value);
  }

  async function post(url, values) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        body: new URLSearchParams({...values, csrfmiddlewaretoken: csrfToken}),
      });
      if (response.redirected || response.status === 401) throw new Error('Sign in again to use the scanner.');
      return {response, data: await response.json()};
    } finally { window.clearTimeout(timeout); }
  }

  function reviewCountdown() {
    if (!pending) return;
    const remaining = Math.max(0, Math.ceil((pending.deadline - performance.now()) / 1000));
    pending.expired = remaining === 0;
    const label = remaining
      ? `Confirm within ${remaining}s. The student's QR may keep changing while you review.`
      : 'This confirmation expired. Close it and scan the latest QR again.';
    if (expiryLabel.textContent !== label) expiryLabel.textContent = label;
    if (pending.expired || pending.invalidated) rejectButton.textContent = 'Scan again';
    updateButtons();
  }

  function openReview(data, scan, startedAt) {
    pending = {...data, scan, deadline: performance.now() + Math.max(0,
      data.review_seconds * 1000 - (performance.now() - startedAt)), expired: false, invalidated: false};
    dialog.querySelector('[data-review-name]').textContent = data.student.name;
    dialog.querySelector('[data-review-school-id]').textContent = data.student.school_id;
    dialog.querySelector('[data-review-course]').textContent = [data.student.program, data.student.year_section].filter(Boolean).join(' · ');
    dialog.querySelector('[data-review-mode]').textContent = data.scan_label;
    dialog.querySelector('[data-review-event]').textContent = data.event;
    dialog.querySelector('[data-review-day]').textContent = data.day;
    dialog.querySelector('[data-review-scanned]').textContent = data.scanned_label;
    const hasPhoto = !!data.student.photo_url;
    photo.hidden = !hasPhoto;
    initials.hidden = hasPhoto;
    photoNote.hidden = hasPhoto;
    initials.textContent = data.student.name.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase();
    photo.onerror = () => { photo.hidden = true; initials.hidden = false; photoNote.hidden = false; };
    if (hasPhoto) photo.src = data.student.photo_url;
    else photo.removeAttribute('src');
    confirmButton.textContent = 'Confirm ' + data.scan_label;
    rejectButton.textContent = 'Not the same person';
    showReviewError('');
    pauseCamera();
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    reviewCountdown();
    reviewTimer = window.setInterval(reviewCountdown, 250);
    rejectButton.focus();
  }

  function closeReview() {
    window.clearInterval(reviewTimer);
    pending = undefined;
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
    applyTiming(timing);
    resumeCamera();
    if (scanType) modes[scanType].button.focus();
  }

  function rejectReview() {
    if (busy || !pending) return;
    const review = pending;
    nextScanAt = performance.now() + 750;
    rememberDecode(review.scan.key, 1500);
    closeReview();
    setResult('Scan cancelled. No attendance was recorded.');
    // A delayed cancellation is bound to this receipt, so it cannot discard a newer scan.
    post(panel.dataset.reviewUrl, {action: 'reject', confirmation: review.confirmation}).catch(() => {});
  }

  async function requestReview(scan) {
    busy = true;
    rememberDecode(scan.key, Infinity);
    updateButtons();
    const startedAt = performance.now();
    try {
      const {data} = await post(panel.dataset.reviewUrl, {
        token: scan.token, day: scan.day, scan_type: scan.type,
      });
      if (data.ok && data.requires_confirmation) openReview(data, scan, startedAt);
      else {
        rememberDecode(scan.key, data.already_recorded ? Infinity : 1000);
        setResult(data.message || 'This QR could not be reviewed.', 'error');
      }
    } catch (error) {
      rememberDecode(scan.key, 1000);
      setResult(error.message === 'Sign in again to use the scanner.' ? error.message : 'Could not contact the server. Try scanning again.', 'error');
    } finally {
      busy = false;
      applyTiming(timing);
    }
  }

  async function confirmReview() {
    if (busy || !pending || pending.expired || pending.invalidated) return;
    const review = pending;
    busy = true;
    updateButtons();
    showReviewError('');
    try {
      const {response, data} = await post(panel.dataset.scanUrl, {
        confirmation: review.confirmation, identity_confirmed: '1',
        day: review.day, scan_type: review.scan_type,
      });
      if (data.ok) {
        attendanceChannel?.postMessage('attendance-updated');
        rememberDecode(review.scan.key, Infinity);
        busy = false;
        if (data.timing) timing = data.timing;
        closeReview();
        if (data.scan_type === 'EXCUSED_OUT' && scanType === 'EXCUSED_OUT') setScanType(null);
        setResult(data.message || 'Attendance recorded.', 'success');
        scheduleTimingRefresh(timing.refresh_after_ms);
      } else {
        if ([400, 403, 404, 409].includes(response.status)) review.invalidated = true;
        showReviewError(data.message || 'Attendance was not saved. Try again.');
      }
    } catch {
      showReviewError('Could not confirm the scan. Check your connection and try again.');
    } finally {
      busy = false;
      if (pending) reviewCountdown();
      else updateButtons();
    }
  }

  function scanDetected(token) {
    if (busy || pending || !scanType || !timing[modes[scanType].flag] || performance.now() < nextScanAt) return;
    const key = timing.day + ':' + scanType + ':' + token;
    if ((recentDecodes.get(key) ?? 0) > performance.now()) return;
    requestReview({token, day: timing.day, type: scanType, key});
  }

  confirmButton.addEventListener('click', confirmReview);
  rejectButton.addEventListener('click', rejectReview);
  cancelButton.addEventListener('click', rejectReview);
  dialog.addEventListener('cancel', event => { event.preventDefault(); rejectReview(); });
  dialog.addEventListener('close', () => { if (pending && !busy) rejectReview(); });
  for (const [mode, {button}] of Object.entries(modes)) button.addEventListener('click', () => {
    if (!busy && !pending && timing[modes[mode].flag]) setScanType(mode);
  });
  applyTiming(timing);
  scheduleTimingRefresh(timing.refresh_after_ms);

  if (typeof Html5Qrcode === 'undefined') {
    setResult('The camera scanner could not load. Refresh the page to try again.', 'error');
    return;
  }
  camera = new Html5Qrcode('reader');
  const qrSize = Math.min(260, Math.max(160, Math.floor(window.innerWidth * 0.72)));
  camera.start({facingMode: 'environment'}, {fps: 15, qrbox: {width: qrSize, height: qrSize}}, scanDetected, () => {})
    .then(() => {
      cameraRunning = true;
      if (pending) pauseCamera();
      else if (!timing.scanning_open) stopCamera();
    }).catch(() => {
      if (timing.scanning_open) setResult('Camera could not start. Allow camera permission and use HTTPS/localhost.', 'error');
    });
  window.addEventListener('pagehide', () => {
    window.clearTimeout(timingTimer);
    window.clearInterval(reviewTimer);
    attendanceChannel?.close();
    stopCamera();
  });
})();
