const WEB3FORMS_ACCESS_KEY = '3524f864-d933-41b9-862c-79f6b1d5b281';  // public Web3Forms key, safe in client code

(function (root) {
  'use strict';
  const MAX_MESSAGE_LENGTH = 300;
  const SUCCESS_MESSAGE = 'ההודעה נשלחה ותענה בהקדם האפשרי לתיבת המייל שציינת לחזרה.';
  const fields = {
    name: {id: 'contact-name', errorId: 'contact-name-error'},
    email: {id: 'contact-email', errorId: 'contact-email-error'},
    message: {id: 'contact-message', errorId: 'contact-message-error'}
  };

  function setFieldError(field, message) {
    const input = document.getElementById(field.id);
    document.getElementById(field.errorId).textContent = message;
    if (message) { input.setAttribute('aria-invalid', 'true'); }
    else { input.removeAttribute('aria-invalid'); }
  }

  function validate() {
    const name = document.getElementById(fields.name.id);
    const email = document.getElementById(fields.email.id);
    const message = document.getElementById(fields.message.id);
    setFieldError(fields.name, name.value.trim() ? '' : 'יש להזין שם מלא.');
    setFieldError(fields.email, !email.value.trim() ? 'יש להזין אימייל לחזרה.' :
      (email.validity.typeMismatch ? 'יש להזין כתובת אימייל תקינה.' : ''));
    setFieldError(fields.message, !message.value.trim() ? 'יש להזין את תוכן ההודעה.' :
      (message.value.length > MAX_MESSAGE_LENGTH ? 'תוכן ההודעה מוגבל ל־300 תווים.' : ''));
    const firstInvalid = [name, email, message].find(function (input) {
      return input.getAttribute('aria-invalid') === 'true';
    });
    if (firstInvalid) { firstInvalid.focus(); return false; }
    return true;
  }

  function updateCount() {
    const length = document.getElementById(fields.message.id).value.length;
    document.getElementById('contact-message-count').textContent = length + '/' + MAX_MESSAGE_LENGTH;
  }

  function setSending(sending) {
    const button = document.getElementById('contact-submit');
    button.disabled = sending;
    button.textContent = sending ? 'שולח…' : 'שלח';
  }

  function showFailure(message) {
    document.getElementById('contact-status').textContent = message;
    setSending(false);
  }

  function submit(event) {
    event.preventDefault();
    document.getElementById('contact-status').textContent = '';
    if (!validate()) { return; }
    if (!WEB3FORMS_ACCESS_KEY) {
      showFailure('הטופס עדיין לא חובר לשירות השליחה — ההודעה לא נשלחה.');
      return;
    }

    setSending(true);
    const form = event.currentTarget;
    const payload = new FormData(form);
    payload.set('access_key', WEB3FORMS_ACCESS_KEY);
    if (root.location.protocol === 'file:') {
      showFailure('לא ניתן היה לשלוח את ההודעה כרגע. התוכן נשמר בטופס ואפשר לנסות שוב.');
      return;
    }
    fetch('https://api.web3forms.com/submit', {method: 'POST', body: payload}).then(function (response) {
      if (!response.ok) { throw new Error('service'); }
      return response.json();
    }).then(function (result) {
      if (result.success !== true) { throw new Error('service'); }
      const area = document.getElementById('contact-form-area');
      area.textContent = '';
      const success = document.createElement('p');
      success.className = 'contact-success';
      success.textContent = SUCCESS_MESSAGE;
      area.appendChild(success);
    }).catch(function () {
      showFailure('לא ניתן היה לשלוח את ההודעה כרגע. התוכן נשמר בטופס ואפשר לנסות שוב.');
    });
  }

  function init() {
    const form = document.getElementById('contact-form');
    const message = document.getElementById(fields.message.id);
    message.addEventListener('input', updateCount);
    form.addEventListener('submit', submit);
    Object.keys(fields).forEach(function (key) {
      document.getElementById(fields[key].id).addEventListener('input', function () {
        if (this.getAttribute('aria-invalid') === 'true') { setFieldError(fields[key], ''); }
      });
    });
    updateCount();
  }

  document.addEventListener('DOMContentLoaded', init);
})(window);
