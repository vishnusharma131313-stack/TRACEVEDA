/*
 * Page loads always begin on the public landing page.
 * A saved token may remain available for authenticated API calls, but a
 * stale localStorage user must never force the browser into a workspace.
 * Authentication and role selection happen through the sign-in flow.
 */
(function initialisePublicLanding() {
    try {
        const token = localStorage.getItem('traceveda_token');
        if (!token) localStorage.removeItem('traceveda_user');
    } catch (error) {
        console.warn('Unable to inspect the saved TraceVeda session:', error);
    }

    if (typeof showLanding === 'function') showLanding();
})();
