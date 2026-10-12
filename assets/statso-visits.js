/* Private visit counter (GoatCounter): cookie-free, no visible number.
   Disabled until GOATCOUNTER_CODE is set; never runs from file:// or localhost. */
(function () {
  'use strict';
  var GOATCOUNTER_CODE = '';
  var host = location.hostname;
  if (!GOATCOUNTER_CODE || !/^https?:$/.test(location.protocol)) return;
  if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') return;
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://gc.zgo.at/count.js';
  s.setAttribute('data-goatcounter', 'https://' + GOATCOUNTER_CODE + '.goatcounter.com/count');
  document.head.appendChild(s);
})();
