(() => {
  const root = document.documentElement;
  const key = 'ahb-color-theme';
  let saved;
  try { saved = localStorage.getItem(key); } catch (_) {}
  if (saved === 'dark' || saved === 'light') root.dataset.theme = saved;
  document.querySelector('.theme-button')?.addEventListener('click', () => {
    const dark = root.dataset.theme === 'dark' || (root.dataset.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem(key, root.dataset.theme); } catch (_) {}
  });
  if ('IntersectionObserver' in window) {
    const nav = [...document.querySelectorAll('nav a[href^="#"]')];
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        nav.forEach(a => a.toggleAttribute('data-active', a.hash === '#' + entry.target.id));
      }
    }, {rootMargin: '-12% 0px -65% 0px'});
    document.querySelectorAll('main section[id]').forEach(section => observer.observe(section));
  }
})();
