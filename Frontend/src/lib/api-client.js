/* Single shared fetch client. All feature pages use this same base URL and token. */
const API_URL = window.TRACEVEDA_CONFIG.API_BASE_URL;

const TRACEVEDA_API = API_URL;

function getTraceVedaToken() {
    return localStorage.getItem("traceveda_token");
}

async function apiRequest(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

    // Do not force JSON headers on multipart requests; the browser must set
    // the boundary itself. JSON remains the default for the existing API.
    if (!isFormData && options.body !== undefined && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    const token = getTraceVedaToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
        response = await fetch(`${TRACEVEDA_API}${path}`, {
            ...options,
            headers
        });
    } catch (error) {
        throw new Error(`Unable to reach TraceVeda API at ${TRACEVEDA_API}. Check your internet connection or backend status.`);
    }

    let data = null;
    const responseText = await response.text();
    if (responseText) {
        try { data = JSON.parse(responseText); }
        catch (_) { data = { detail: responseText }; }
    }

    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem('traceveda_token');
            localStorage.removeItem('traceveda_user');
        }
        const detail = Array.isArray(data?.detail)
            ? data.detail.map(x => x?.msg || String(x)).join(' · ')
            : data?.detail;
        throw new Error(detail || data?.message || `Request failed (${response.status})`);
    }

    return data;
}

async function loadConsumerReports() {
    const tbody = document.querySelector("#auditor-reports tbody");

    if (!tbody) {
        console.error("Consumer reports table body not found");
        return;
    }

    tbody.innerHTML = `
        <tr>
            <td colspan="5">Loading reports...</td>
        </tr>
    `;

    try {
        console.log("Fetching consumer reports...");

        const data = await apiRequest("/api/consumer/reports?limit=200", {
            method: "GET"
        });

        console.log("Consumer reports received:", data);

        const reports = data.reports || [];

        if (reports.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5">No consumer reports found.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = reports.map(report => `
            <tr>
                <td class="mono">${report.report_id || "-"}</td>
                <td class="mono">${report.medicine_batch_id || "-"}</td>
                <td>${report.issue_type || "-"}</td>
                <td>${report.description || report.symptoms || "-"}</td>
                <td>${report.reported_at || "-"}</td>
            </tr>
        `).join("");

    } catch (error) {

        console.error("Failed to load consumer reports:", error);

        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    Failed to load reports: ${error.message}
                </td>
            </tr>
        `;
    }
}

window.TraceVedaAPI = {
    auth: {
        me: () => apiRequest('/api/auth/me'),
        roles: () => apiRequest('/api/auth/roles')
    },
    batches: {
        raw: () => apiRequest('/api/batches/raw'),
        processing: () => apiRequest('/api/batches/processing')
    },
    blockchain: {
        events: () => apiRequest('/api/blockchain/events'),
        verifyChain: () => apiRequest('/api/blockchain/verify-chain')
    },
    trace: {
        reverse: id => apiRequest(`/api/trace/reverse/${encodeURIComponent(id)}`),
        forward: id => apiRequest(`/api/trace/forward/${encodeURIComponent(id)}`),
        impact: id => apiRequest(`/api/trace/impact/${encodeURIComponent(id)}`)
    },
    transport: { get: id => apiRequest(`/api/transport/${encodeURIComponent(id)}`) },
    storage: { get: id => apiRequest(`/api/storage/${encodeURIComponent(id)}`) }
};
