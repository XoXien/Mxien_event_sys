// Share sidebar behavior across every signed-in dashboard and account page.
(() => {
  const layout = document.querySelector('[data-dashboard-layout]');
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const mobileToggle = document.querySelector('[data-sidebar-open]');
  const sidebar = document.getElementById('dashboard-sidebar');
  if (!layout || !toggle || !mobileToggle || !sidebar) return;

  const body = document.body;
  const main = document.getElementById('management-content');
  const bottomNavigation = document.getElementById('dashboard-bottom-navigation');
  const backdrop = layout.querySelector('.sidebar-backdrop');
  const accountBar = layout.querySelector('.workspace-topbar, .dashboard-admin-profile');
  const desktop = window.matchMedia('(min-width: 1025px)');
  const preferenceKey = body.dataset.sidebarStorageKey;
  let collapsed = false;
  let drawerOpen = false;

  // Storage can be unavailable in private windows. The controls still work in that case.
  try {
    collapsed = window.localStorage.getItem(preferenceKey) === '1';
  } catch {}

  function syncSidebar() {
    const mobileOpen = !desktop.matches && drawerOpen;
    const expanded = desktop.matches ? !collapsed : mobileOpen;
    const label = desktop.matches
      ? (expanded ? 'Collapse sidebar' : 'Expand sidebar')
      : 'Close navigation';

    body.classList.toggle('sidebar-collapsed', collapsed);
    body.classList.toggle('sidebar-open', mobileOpen);
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
    mobileToggle.setAttribute('aria-expanded', String(mobileOpen));
    mobileToggle.setAttribute('aria-label', mobileOpen ? 'Close navigation' : 'Open navigation');
    mobileToggle.title = mobileOpen ? 'Close navigation' : 'Open navigation';
    sidebar.inert = !desktop.matches && !mobileOpen;
    sidebar.setAttribute('aria-hidden', String(sidebar.inert));
    backdrop.hidden = !mobileOpen;
    main.inert = mobileOpen;
    if (bottomNavigation) bottomNavigation.inert = mobileOpen;
    if (accountBar) accountBar.inert = mobileOpen;

    if (mobileOpen) {
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
    }
  }

  function closeDrawer(restoreFocus = true) {
    if (!drawerOpen) return;
    drawerOpen = false;
    syncSidebar();
    if (restoreFocus) mobileToggle.focus();
  }

  toggle.addEventListener('click', () => {
    if (desktop.matches) {
      collapsed = !collapsed;
      try {
        window.localStorage.setItem(preferenceKey, collapsed ? '1' : '0');
      } catch {}
      syncSidebar();
    } else {
      closeDrawer();
    }
  });

  // Phones need an opener outside the drawer because the closed sidebar is inert.
  mobileToggle.addEventListener('click', () => {
    if (desktop.matches) return;
    if (drawerOpen) {
      closeDrawer();
    } else {
      drawerOpen = true;
      syncSidebar();
      toggle.focus();
    }
  });

  for (const close of layout.querySelectorAll('[data-sidebar-close]')) {
    close.addEventListener('click', () => closeDrawer());
  }
  sidebar.addEventListener('click', (event) => {
    if (event.target.closest('a[href]')) closeDrawer(false);
  });

  // Keep keyboard focus in the open phone menu and return it to the toggle on dismissal.
  document.addEventListener('keydown', (event) => {
    if (desktop.matches || !drawerOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeDrawer();
    } else if (event.key === 'Tab') {
      const links = [...sidebar.querySelectorAll('a[href], button:not([disabled])')].filter(
        element => !element.closest('[hidden]') && window.getComputedStyle(element).display !== 'none',
      );
      const first = links[0];
      const last = links.at(-1);
      const outside = !sidebar.contains(document.activeElement);
      if (first && event.shiftKey && (outside || document.activeElement === first)) {
        event.preventDefault();
        last.focus();
      } else if (first && !event.shiftKey && (outside || document.activeElement === last)) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  desktop.addEventListener('change', () => {
    const focusInside = sidebar.contains(document.activeElement);
    const focusOnMobileControl = document.activeElement === mobileToggle;
    const focusInBottomNavigation = bottomNavigation?.contains(document.activeElement);
    drawerOpen = false;
    syncSidebar();
    if (focusInside && !desktop.matches) mobileToggle.focus();
    else if (desktop.matches && (focusOnMobileControl || focusInBottomNavigation)) toggle.focus();
  });
  window.addEventListener('storage', (event) => {
    if (event.key !== preferenceKey) return;
    collapsed = event.newValue === '1';
    syncSidebar();
  });

  // Keep the existing tab navigation available when JavaScript is disabled.
  body.classList.add('sidebar-ready');
  toggle.hidden = false;
  mobileToggle.hidden = false;
  syncSidebar();
})();
