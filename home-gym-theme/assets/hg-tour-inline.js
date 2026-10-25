(() => {
  if (window.hgTourInline) return;
  window.hgTourInline = true;
  // The Google Maps view is only requested after a click, like a two-click embed.
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-tour-start]');
    const embed = link?.closest('[data-tour-embed]');
    if (!embed || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const iframe = document.createElement('iframe');
    iframe.title = embed.dataset.tourTitle || link.textContent.trim();
    iframe.allow = 'fullscreen; accelerometer; gyroscope; magnetometer';
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = 'no-referrer-when-downgrade';
    iframe.src = link.href;
    embed.replaceChildren(iframe);
    embed.dataset.loaded = 'true';
    iframe.focus();
  });
})();
