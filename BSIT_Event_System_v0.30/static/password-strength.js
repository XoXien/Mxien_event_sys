// Estimate password strength locally. Django applies the same policy before saving.
(() => {
  function initializePasswords() {
    const labels = ['Very weak', 'Weak', 'Fair', 'Strong', 'Very strong'];

    function addVisibilityControl(input) {
      let toggle = [...document.querySelectorAll('[data-password-toggle]')].find(
        button => button.getAttribute('aria-controls') === input.id,
      );
      if (!toggle) {
        const control = document.createElement('div');
        control.className = 'password-control';
        input.before(control);
        control.append(input);
        toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-visibility';
        toggle.dataset.passwordToggle = '';
        toggle.setAttribute('aria-controls', input.id);
        toggle.textContent = 'Show';
        control.append(toggle);
      }
      if (toggle.dataset.passwordReady) return;
      toggle.dataset.passwordReady = 'true';
      toggle.setAttribute('aria-pressed', 'false');
      toggle.setAttribute('aria-label', 'Show password');
      toggle.addEventListener('click', () => {
        const visible = input.type === 'password';
        input.type = visible ? 'text' : 'password';
        toggle.textContent = visible ? 'Hide' : 'Show';
        toggle.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
        toggle.setAttribute('aria-pressed', String(visible));
      });
    }

    for (const input of document.querySelectorAll('[data-password-strength]')) {
      if (input.dataset.passwordReady) continue;
      input.dataset.passwordReady = 'true';
      const form = input.form;
      // Validate after reading autofilled values as well as ordinary input events.
      form.noValidate = true;
      const confirmation = form.elements.namedItem(input.dataset.passwordConfirmField);
      const usablePassword = form.elements.namedItem('usable_password');
      const policy = JSON.parse(input.dataset.passwordPolicy);
      addVisibilityControl(input);
      if (confirmation) addVisibilityControl(confirmation);

      const panel = document.createElement('div');
      panel.className = 'password-strength';
      panel.id = input.id + '_strength';
      const heading = document.createElement('div');
      heading.className = 'password-strength-heading';
      const title = document.createElement('span');
      title.textContent = 'Password strength';
      const status = document.createElement('strong');
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      heading.append(title, status);
      const meter = document.createElement('meter');
      meter.min = 0;
      meter.max = 4;
      meter.low = 2;
      meter.high = 3;
      meter.optimum = 4;
      meter.setAttribute('aria-label', 'Password strength estimate');
      const checklist = document.createElement('ul');
      const lengthRule = document.createElement('li');
      lengthRule.textContent = `${policy.minLength}–${policy.maxLength} characters`;
      const strengthRule = document.createElement('li');
      strengthRule.textContent = `Rated ${labels[policy.minScore]} or better`;
      checklist.append(lengthRule, strengthRule);
      const advice = document.createElement('p');
      advice.textContent = 'Use a unique mix of letters, numbers and symbols. Avoid names, School IDs and repeated patterns.';
      panel.append(heading, meter, checklist, advice);
      const adminRow = input.closest('.form-row');
      const control = adminRow?.querySelector('.flex-container')
        || input.closest('.password-control, .registration-control') || input;
      if (adminRow) panel.classList.add('help');
      control.after(panel);
      const describedBy = input.getAttribute('aria-describedby') || '';
      input.setAttribute('aria-describedby', `${describedBy} ${panel.id}`.trim());

      let match;
      if (confirmation) {
        match = document.createElement('p');
        match.className = 'password-match';
        match.id = confirmation.id + '_match';
        match.setAttribute('role', 'status');
        match.setAttribute('aria-live', 'polite');
        match.hidden = true;
        const confirmRow = confirmation.closest('.form-row');
        const confirmControl = confirmRow?.querySelector('.flex-container')
          || confirmation.closest('.password-control, .registration-control') || confirmation;
        if (confirmRow) match.classList.add('help');
        confirmControl.after(match);
        const description = confirmation.getAttribute('aria-describedby') || '';
        confirmation.setAttribute('aria-describedby', `${description} ${match.id}`.trim());
      }

      function updateMatch() {
        if (!confirmation) return;
        if (usablePassword?.value === 'false') {
          match.hidden = true;
          confirmation.setCustomValidity('');
          return;
        }
        const entered = confirmation.value.length > 0;
        const matches = input.value === confirmation.value;
        match.hidden = !entered;
        match.textContent = matches ? 'Passwords match.' : 'Passwords do not match.';
        match.dataset.state = matches ? 'met' : 'missing';
        confirmation.setCustomValidity(entered && !matches ? 'The passwords do not match.' : '');
      }

      function updateStrength() {
        const enabled = usablePassword?.value !== 'false';
        if (usablePassword) {
          input.disabled = !enabled;
          if (confirmation) confirmation.disabled = !enabled;
        }
        panel.hidden = !enabled;
        if (!enabled) {
          input.setCustomValidity('');
          updateMatch();
          return;
        }
        const password = input.value;
        const length = [...password].length;
        let error = '';
        const validLength = length >= policy.minLength && length <= policy.maxLength;
        let score = 0;
        let available = typeof window.zxcvbn === 'function';
        if (password && length <= policy.maxLength && available) {
          const words = [...policy.userInputs];
          for (const name of ['username', 'student_id', 'first_name', 'last_name', 'email']) {
            const value = form.elements.namedItem(name)?.value;
            if (value) words.push(value, ...value.split(/[\W_]+/).filter(part => part.length >= 3));
          }
          try {
            score = window.zxcvbn(password, words).score;
          } catch {
            available = false;
          }
        }
        if (!password) status.textContent = 'Enter a password';
        else if (!validLength) status.textContent = length < policy.minLength ? 'Too short' : 'Too long';
        else status.textContent = available ? labels[score] : 'Check when saving';
        meter.value = validLength ? score : Math.min(score, 1);
        meter.setAttribute('aria-valuetext', status.textContent);
        panel.dataset.score = String(validLength ? score : 0);
        lengthRule.dataset.state = password ? (validLength ? 'met' : 'missing') : 'pending';
        strengthRule.dataset.state = password && available
          ? (validLength && score >= policy.minScore ? 'met' : 'missing') : 'pending';

        if (password && !validLength) error = `Use ${policy.minLength}–${policy.maxLength} characters.`;
        else if (password && available && score < policy.minScore) {
          error = `Choose a less predictable password rated ${labels[policy.minScore]} or better.`;
        }
        const oldPassword = form.elements.namedItem('old_password');
        if (password && oldPassword?.value === password) error = 'Choose a different password from your current one.';
        input.setCustomValidity(error);
        updateMatch();
      }

      // Recheck on submit too, including passwords filled by a password manager.
      input.addEventListener('input', updateStrength);
      input.addEventListener('change', updateStrength);
      confirmation?.addEventListener('input', updateMatch);
      confirmation?.addEventListener('change', updateMatch);
      for (const field of form.elements) {
        if (['username', 'student_id', 'first_name', 'last_name', 'email', 'old_password', 'usable_password'].includes(field.name)) {
          field.addEventListener('input', updateStrength);
          field.addEventListener('change', updateStrength);
        }
      }
      form.addEventListener('submit', (event) => {
        updateStrength();
        if (!form.reportValidity()) {
          event.preventDefault();
        }
      });
      updateStrength();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePasswords, {once: true});
  } else {
    initializePasswords();
  }
})();
