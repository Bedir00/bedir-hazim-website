(() => {
  const instances = new WeakMap();
  const init = (scope = document) => scope.querySelectorAll('[data-home-gym]').forEach(root => {
    const dialog = root.querySelector('[data-tour-dialog]');
    if (!dialog || instances.has(root) || typeof dialog.showModal !== 'function') return;
    const controller = new AbortController();
    const signal = controller.signal;
    const frame = dialog.querySelector('[data-tour-frame]');
    const title = dialog.querySelector('[data-tour-heading]');
    const heroVideo = root.querySelector('[data-hero-native]');
    let resumeVideo = false;
    // The Google Maps view is only requested after a click, like a two-click embed.
    root.addEventListener('click', event => {
      const link = event.target.closest('[data-tour-open]');
      if (!link || !root.contains(link) || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      title.textContent = link.dataset.tourTitle || link.textContent.trim();
      const iframe = document.createElement('iframe');
      iframe.title = title.textContent;
      iframe.allow = 'fullscreen; accelerometer; gyroscope; magnetometer';
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = 'no-referrer-when-downgrade';
      iframe.src = link.href;
      frame.replaceChildren(iframe);
      resumeVideo = Boolean(heroVideo && !heroVideo.paused);
      heroVideo?.pause();
      dialog.showModal();
    }, { signal });
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); }, { signal });
    dialog.querySelector('[data-tour-close]')?.addEventListener('click', () => dialog.close(), { signal });
    dialog.addEventListener('close', () => {
      frame.replaceChildren();
      if (resumeVideo && !matchMedia('(prefers-reduced-motion: reduce)').matches) heroVideo.play()?.catch(() => {});
      resumeVideo = false;
    }, { signal });
    instances.set(root, () => { if (dialog.open) dialog.close(); controller.abort(); });
  });
  init();
  document.addEventListener('shopify:section:load', event => init(event.target));
  document.addEventListener('shopify:section:unload', event => event.target.querySelectorAll('[data-home-gym]').forEach(root => { instances.get(root)?.(); instances.delete(root); }));
})();
