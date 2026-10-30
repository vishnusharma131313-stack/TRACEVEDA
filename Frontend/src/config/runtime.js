/*
 * Runtime configuration for the TraceVeda frontend.
 * Vite replaces %VITE_API_URL% from .env files during dev/build.
 * An unreplaced placeholder falls back to the hosted API. An explicitly
 * empty value uses same-origin /api requests through the Vite dev proxy.
 */
(() => {
    const meta = document.querySelector('meta[name="traceveda-api-url"]');
    const configured = meta ? (meta.content || '').trim() : '%VITE_API_URL%';
    const isUnreplacedPlaceholder = configured.startsWith('%') && configured.endsWith('%');
    const fallback = 'https://traceveda.onrender.com';
    const apiBaseUrl = (isUnreplacedPlaceholder ? fallback : configured).replace(/\/+$/, '');

    window.TRACEVEDA_CONFIG = Object.freeze({ API_BASE_URL: apiBaseUrl });
})();
