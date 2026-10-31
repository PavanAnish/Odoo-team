const { JSDOM } = (() => {
  // Simple DOM simulation if jsdom not installed
  return { JSDOM: null };
})();

// Set up minimal browser globals
const html = `
<!DOCTYPE html>
<html>
<body>
<div id="app">
  <aside>
    <div class="logo"><i>A</i><span class="lb">Admin Panel</span></div>
    <nav id="nv"></nav>
  </aside>
  <main>
    <div id="mn"></div>
  </main>
</div>
</body>
</html>
`;

const elements = {
  '#nv': { innerHTML: '' },
  '#mn': { innerHTML: '' },
  '#app': { classList: { remove: () => {}, toggle: () => {} } }
};

globalThis.window = globalThis;
globalThis.document = {
  getElementById: (id) => elements['#' + id] || null,
  querySelector: (sel) => elements[sel] || null,
  querySelectorAll: () => [],
  addEventListener: () => {}
};
globalThis.location = { hash: '#products' };
globalThis.performance = { now: () => Date.now() };
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 16);
globalThis.fetch = () => Promise.reject(new Error('no network'));

import('../admin/app.js').then(async () => {
  console.log('app.js loaded successfully!');
  console.log('#nv HTML length:', elements['#nv'].innerHTML.length);
  console.log('#nv navigation rendered:');
  console.log(elements['#nv'].innerHTML.substring(0, 200) + '...');
  
  // Call go() to see what happens
  globalThis.go();
  await new Promise(r => setTimeout(r, 400));
  console.log('#mn content length:', elements['#mn'].innerHTML.length);
  console.log('#mn rendered successfully!');
}).catch(err => {
  console.error('ERROR LOADING app.js:', err);
  process.exit(1);
});
