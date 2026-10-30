/* Administrator console: accounts, access requests and safety investigations. */
let adminDashboardLoading = false;

function adminEscape(value) {
    return String(value ?? "—").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
}

function setAdminMessage(id, message, type = "info") {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = message || "";
    element.className = `auth-message ${type}`;
}

function adminDate(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function adminSetCount(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = String(value);
}

function adminSetTable(id, html, colspan, error) {
    const body = document.getElementById(id);
    if (!body) return;
    body.innerHTML = error
        ? `<tr><td colspan="${colspan}">Unable to load: ${adminEscape(error)}</td></tr>`
        : html;
}

function renderAdminUsers(users) {
    adminSetCount("adminTotalUsers", users.length);
    adminSetCount("adminTotalRoles", new Set(users.map(user => user.role).filter(Boolean)).size);
    adminSetCount("adminTotalAdmins", users.filter(user => user.role === "admin").length);
    adminSetTable("adminUsersTableBody", users.length ? users.map(user => `
        <tr>
            <td class="mono">${adminEscape(user.username)}</td>
            <td>${adminEscape(user.full_name)}</td>
            <td>${adminEscape(user.role)}</td>
            <td>${adminEscape(user.organisation_id)}</td>
        </tr>
    `).join("") : '<tr><td colspan="4">No user accounts found.</td></tr>', 4);
}

function renderAdminAccessRequests(requests) {
    const pending = requests.filter(request => request.status === "PENDING").length;
    adminSetCount("adminPendingRequests", pending);
    adminSetTable("adminAccessRequestsBody", requests.length ? requests.map(request => {
        const pendingActions = request.status === "PENDING" ? `
            <div class="admin-action-group">
                <button class="btn btn-primary" type="button" data-admin-action="approve-access" data-id="${adminEscape(request.request_id)}">Approve</button>
                <button class="btn btn-outline" type="button" data-admin-action="reject-access" data-id="${adminEscape(request.request_id)}">Reject</button>
            </div>` : `<span class="status-pill">${adminEscape(request.status)}</span>`;
        return `<tr>
            <td class="mono">${adminEscape(request.request_id)}</td>
            <td>${adminEscape(request.role)}</td>
            <td>${adminEscape(request.organisation_name)}</td>
            <td>${adminEscape(request.location)}</td>
            <td>${adminEscape(request.contact_details)}</td>
            <td>${adminEscape(adminDate(request.submitted_at))}</td>
            <td>${pendingActions}</td>
        </tr>`;
    }).join("") : '<tr><td colspan="7">No access requests have been submitted.</td></tr>', 7);
}

function renderAdminReports(reports) {
    const openCount = reports.filter(report => ["OPEN", "UNDER_INVESTIGATION"].includes(report.report_status)).length;
    adminSetCount("adminOpenReports", openCount);
    const statuses = ["OPEN", "UNDER_INVESTIGATION", "RESOLVED", "DISMISSED", "CLOSED"];
    adminSetTable("adminConsumerReportsBody", reports.length ? reports.map(report => `
        <tr>
            <td class="mono">${adminEscape(report.report_id)}</td>
            <td class="mono">${adminEscape(report.medicine_batch_id)}</td>
            <td>${adminEscape(report.issue_type)}</td>
            <td>${adminEscape(report.description || report.symptoms)}</td>
            <td>
                <select class="input admin-report-status" aria-label="Status for ${adminEscape(report.report_id)}">
                    ${statuses.map(status => `<option value="${status}" ${report.report_status === status ? "selected" : ""}>${status.replaceAll("_", " ")}</option>`).join("")}
                </select>
            </td>
            <td><div class="admin-action-group">
                <button class="btn btn-outline" type="button" data-admin-action="save-report-status" data-id="${adminEscape(report.report_id)}">Save</button>
                ${report.report_status === "OPEN" ? `<button class="btn btn-primary" type="button" data-admin-action="open-investigation" data-id="${adminEscape(report.report_id)}">Investigate</button>` : ""}
            </div></td>
        </tr>
    `).join("") : '<tr><td colspan="6">No consumer safety reports found.</td></tr>', 6);
}

function renderAdminInvestigations(investigations) {
    const active = investigations.filter(item => item.investigation_status !== "CLOSED").length;
    adminSetCount("adminOpenInvestigations", active);
    adminSetTable("adminInvestigationsBody", investigations.length ? investigations.map(item => `
        <tr>
            <td class="mono">${adminEscape(item.investigation_id)}</td>
            <td class="mono">${adminEscape(item.report_id)}</td>
            <td>${adminEscape(item.suspected_stage)}</td>
            <td>${adminEscape(item.investigation_status)}</td>
            <td>${adminEscape(adminDate(item.opened_at))}</td>
            <td>${item.investigation_status !== "CLOSED"
                ? `<button class="btn btn-outline" type="button" data-admin-action="close-investigation" data-id="${adminEscape(item.investigation_id)}">Close Investigation</button>`
                : `<span class="status-pill">Closed</span>`}</td>
        </tr>
    `).join("") : '<tr><td colspan="6">No investigations have been opened.</td></tr>', 6);
}

async function loadAdminDashboard() {
    if (adminDashboardLoading) return;
    adminDashboardLoading = true;
    setAdminMessage("adminUsersMessage", "Refreshing administrator data…", "info");

    const results = await Promise.allSettled([
        apiRequest("/api/auth/users"),
        apiRequest("/api/auth/roles"),
        apiRequest("/api/access-requests?limit=500"),
        apiRequest("/api/consumer/reports?limit=500"),
        apiRequest("/api/investigations?limit=500")
    ]);

    const [usersResult, rolesResult, accessResult, reportsResult, investigationsResult] = results;

    if (usersResult.status === "fulfilled") {
        const users = usersResult.value?.users || [];
        renderAdminUsers(users);
    } else {
        adminSetTable("adminUsersTableBody", "", 4, usersResult.reason.message);
        setAdminMessage("adminUsersMessage", `User management: ${usersResult.reason.message}`, "error");
    }

    if (rolesResult.status === "fulfilled") {
        const roleSelect = document.getElementById("adminRole");
        const roles = rolesResult.value?.roles || [];
        if (roleSelect) {
            roleSelect.innerHTML = '<option value="">Select role</option>' + roles.map(role =>
                `<option value="${adminEscape(role.id)}">${adminEscape(role.label)}</option>`
            ).join("");
        }
    }

    if (accessResult.status === "fulfilled") {
        renderAdminAccessRequests(accessResult.value?.requests || []);
        setAdminMessage("adminAccessRequestsMessage", "Access requests are up to date.", "success");
    } else {
        adminSetTable("adminAccessRequestsBody", "", 7, accessResult.reason.message);
        setAdminMessage("adminAccessRequestsMessage", accessResult.reason.message, "error");
    }

    if (reportsResult.status === "fulfilled") {
        renderAdminReports(reportsResult.value?.reports || []);
    } else {
        adminSetTable("adminConsumerReportsBody", "", 6, reportsResult.reason.message);
    }

    if (investigationsResult.status === "fulfilled") {
        renderAdminInvestigations(investigationsResult.value?.investigations || []);
    } else {
        adminSetTable("adminInvestigationsBody", "", 6, investigationsResult.reason.message);
    }

    if (results.every(result => result.status === "fulfilled")) {
        setAdminMessage("adminUsersMessage", "Dashboard data refreshed successfully.", "success");
    }
    adminDashboardLoading = false;
}

async function createAdminUser(event) {
    event.preventDefault();
    const form = document.getElementById("adminCreateUserForm");
    const button = document.getElementById("adminCreateUserButton");
    const data = new FormData(form);
    const password = String(data.get("password") || "");
    const role = String(data.get("role") || "");

    if (!role || password.length < 8) {
        setAdminMessage("adminDashboardMessage", "Select a role and use a password of at least 8 characters.", "error");
        return;
    }

    const payload = {
        password, role,
        full_name: String(data.get("full_name") || "").trim() || null,
        username: String(data.get("username") || "").trim() || null,
        organisation_id: String(data.get("organisation_id") || "").trim() || null
    };

    button.disabled = true;
    button.textContent = "Creating…";
    try {
        const response = await apiRequest("/api/auth/users", { method: "POST", body: JSON.stringify(payload) });
        setAdminMessage("adminDashboardMessage", `Account created: ${response.user?.username || response.username || "success"}`, "success");
        form.reset();
        await loadAdminDashboard();
    } catch (error) {
        setAdminMessage("adminDashboardMessage", `Could not create account: ${error.message}`, "error");
    } finally {
        button.disabled = false;
        button.innerHTML = '<i class="fa-solid fa-user-plus"></i> Create User';
    }
}

async function decideAdminAccessRequest(requestId, decision) {
    if (decision === "REJECT" && !window.confirm(`Reject access request ${requestId}?`)) return;
    setAdminMessage("adminAccessRequestsMessage", `${decision === "APPROVE" ? "Approving" : "Rejecting"} ${requestId}…`, "info");
    try {
        const result = await apiRequest(`/api/access-requests/${encodeURIComponent(requestId)}/decision`, {
            method: "PATCH", body: JSON.stringify({ decision })
        });
        if (decision === "APPROVE") {
            setAdminMessage(
                "adminAccessDecisionMessage",
                `Approved. New account: ${result.username} | Temporary password: ${result.temporary_password}. Copy it now and share it securely; it will not be shown again.`,
                "success"
            );
        } else {
            setAdminMessage("adminAccessDecisionMessage", `Request ${requestId} rejected.`, "success");
        }
        await loadAdminDashboard();
    } catch (error) {
        setAdminMessage("adminAccessRequestsMessage", `Could not review request: ${error.message}`, "error");
    }
}

async function saveAdminReportStatus(reportId, button) {
    const row = button.closest("tr");
    const select = row?.querySelector(".admin-report-status");
    if (!select) return;
    try {
        await apiRequest(`/api/consumer/reports/${encodeURIComponent(reportId)}/status`, {
            method: "PATCH", body: JSON.stringify({ status: select.value })
        });
        setAdminMessage("adminReportsMessage", `Report ${reportId} updated to ${select.value}.`, "success");
        await loadAdminDashboard();
    } catch (error) {
        setAdminMessage("adminReportsMessage", `Could not update report: ${error.message}`, "error");
    }
}

async function openAdminInvestigation(reportId) {
    if (!window.confirm(`Open an investigation for report ${reportId}?`)) return;
    let username = "admin-001";
    try { username = JSON.parse(localStorage.getItem("traceveda_user") || "{}").username || username; } catch (_) {}
    try {
        await apiRequest("/api/investigations", {
            method: "POST",
            body: JSON.stringify({
                report_id: reportId,
                auditor_id: username,
                suspected_stage: "UNKNOWN",
                evidence_summary: "Investigation opened from the TraceVeda Administrator Dashboard."
            })
        });
        setAdminMessage("adminReportsMessage", `Investigation opened for ${reportId}.`, "success");
        await loadAdminDashboard();
    } catch (error) {
        setAdminMessage("adminReportsMessage", `Could not open investigation: ${error.message}`, "error");
    }
}

async function closeAdminInvestigation(investigationId) {
    const rootCause = window.prompt("Enter the investigation root cause:");
    if (!rootCause?.trim()) return;
    const actionTaken = window.prompt("Enter the corrective action taken:");
    if (!actionTaken?.trim()) return;
    try {
        await apiRequest(`/api/investigations/${encodeURIComponent(investigationId)}/close`, {
            method: "PATCH",
            body: JSON.stringify({ root_cause: rootCause.trim(), action_taken: actionTaken.trim() })
        });
        setAdminMessage("adminInvestigationsMessage", `Investigation ${investigationId} closed and related report resolved.`, "success");
        await loadAdminDashboard();
    } catch (error) {
        setAdminMessage("adminInvestigationsMessage", `Could not close investigation: ${error.message}`, "error");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("adminCreateUserForm");
    if (form) form.addEventListener("submit", createAdminUser);
});

document.addEventListener("click", event => {
    const button = event.target.closest("[data-admin-action]");
    if (!button) return;
    const id = button.dataset.id;
    switch (button.dataset.adminAction) {
        case "approve-access": decideAdminAccessRequest(id, "APPROVE"); break;
        case "reject-access": decideAdminAccessRequest(id, "REJECT"); break;
        case "save-report-status": saveAdminReportStatus(id, button); break;
        case "open-investigation": openAdminInvestigation(id); break;
        case "close-investigation": closeAdminInvestigation(id); break;
        default: break;
    }
});
