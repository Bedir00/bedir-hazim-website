(() => {
  const instances = new WeakMap();
  const init = (scope = document) => scope.querySelectorAll('[data-portrait]').forEach(root => {
    const video = root.querySelector('[data-portrait-video]');
    if (!video || instances.has(root)) return;
    const controller = new AbortController();
    const signal = controller.signal;
    const sound = root.querySelector('[data-portrait-sound]');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    let visible = true;
    const play = () => video.play()?.catch(() => { video.controls = true; });
    const sync = () => {
      if (reducedMotion.matches) { video.pause(); video.controls = true; return; }
      if (visible && !document.hidden) play(); else video.pause();
    };
    video.muted = true;
    video.defaultMuted = true;
    sound?.addEventListener('click', () => {
      video.muted = !video.muted;
      if (!video.muted) play();
      sound.setAttribute('aria-pressed', String(!video.muted));
      sound.setAttribute('aria-label', video.muted ? sound.dataset.labelUnmute : sound.dataset.labelMute);
    }, { signal });
    // Only play while the video is on screen.
    const observer = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); }, { threshold: .25 }) : null;
    observer?.observe(root);
    document.addEventListener('visibilitychange', sync, { signal });
    reducedMotion.addEventListener('change', sync, { signal });
    sync();
    instances.set(root, () => { controller.abort(); observer?.disconnect(); video.pause(); });
  });
  init();
  document.addEventListener('shopify:section:load', event => init(event.target));
  document.addEventListener('shopify:section:unload', event => event.target.querySelectorAll('[data-portrait]').forEach(root => { instances.get(root)?.(); instances.delete(root); }));
})();
