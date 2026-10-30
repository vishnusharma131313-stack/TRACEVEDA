/* TraceVeda role header + profile menu. Presentation-only; no API or business logic. */
(function () {
    const ROLE_LABELS = {
        lab: "Laboratory",
        manufacturer: "Manufacturer",
        transporter: "Transporter",
        auditor: "Auditor",
        admin: "Administrator",
        consumer: "Consumer"
    };

    const ROLE_ICONS = {
        lab: "fa-flask",
        manufacturer: "fa-industry",
        transporter: "fa-truck-fast",
        auditor: "fa-shield-halved",
        admin: "fa-user-gear",
        consumer: "fa-capsules"
    };

    const ROLE_SUBTITLES = {
        lab: "Laboratory workspace",
        manufacturer: "Manufacturing workspace",
        transporter: "Transport & logistics workspace",
        auditor: "Audit & compliance workspace",
        admin: "Platform administration workspace",
        consumer: "Medicine verification experience"
    };

    function normalizeRole(value) {
        const role = String(value || "").trim().toLowerCase();
        if (role === "regulator") return "auditor";
        if (role === "logistics") return "transporter";
        return ROLE_LABELS[role] ? role : "";
    }

    function initials(name) {
        const parts = String(name || "TraceVeda User").trim().split(/\s+/).filter(Boolean);
        return parts.length ? parts.slice(0, 2).map(part => part[0]).join("").toUpperCase() : "TV";
    }

    function getUser() {
        try {
            return JSON.parse(localStorage.getItem("traceveda_user") || "null") || {};
        } catch (error) {
            console.warn("Could not read TraceVeda profile details.", error);
            return {};
        }
    }

    function setDisplay(element, value) {
        if (!element) return;
        element.style.setProperty("display", value, "important");
    }

    function syncWorkspacePresentation() {
        const workspace = document.getElementById("workspace");
        const header = document.getElementById("workspaceHeader");
        const publicNav = document.getElementById("publicHeaderNav");
        const publicActions = document.getElementById("publicHeaderActions");
        const menu = document.getElementById("profileMenu");
        const trigger = document.getElementById("profileTrigger");
        const isActive = Boolean(workspace && workspace.classList.contains("active"));

        if (!isActive) {
            document.body.removeAttribute("data-role");
            document.body.classList.remove("workspace-mode");
            setDisplay(header, "none");
            if (menu) menu.classList.remove("open");
            if (trigger) trigger.setAttribute("aria-expanded", "false");
            return;
        }

        let role = "";
        try {
            if (typeof currentRole !== "undefined") role = normalizeRole(currentRole);
        } catch (_) {
            role = "";
        }

        const user = getUser();
        role = role || normalizeRole(user.role) || "consumer";
        document.body.setAttribute("data-role", role);
        document.body.classList.add("workspace-mode");

        // Explicitly switch the same top header row into signed-in mode.
        setDisplay(header, "flex");
        setDisplay(publicNav, "none");
        setDisplay(publicActions, "none");

        const displayName = user.full_name || user.username || (role === "consumer" ? "Consumer" : "TraceVeda User");
        const welcomeName = role === "consumer" ? "Consumer" : (user.username || user.full_name || "User");
        const roleLabel = ROLE_LABELS[role] || "Workspace";
        const iconClass = ROLE_ICONS[role] || "fa-user";

        const greetingName = document.getElementById("workspaceGreetingName");
        const greetingSubtitle = document.getElementById("workspaceGreetingSubtitle");
        const roleLabelElement = document.getElementById("workspaceRoleLabel");
        const roleIcon = document.getElementById("workspaceRoleIcon");
        if (greetingName) greetingName.textContent = welcomeName;
        if (greetingSubtitle) greetingSubtitle.textContent = ROLE_SUBTITLES[role] || "Your TraceVeda workspace";
        if (roleLabelElement) roleLabelElement.textContent = `${roleLabel} workspace`;
        if (roleIcon) roleIcon.className = `fa-solid ${iconClass}`;

        ["profileName", "profileMenuName"].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.textContent = displayName;
        });
        ["profileRole", "profileMenuRole"].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.textContent = roleLabel;
        });
        ["profileAvatar", "profileAvatarLarge"].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.textContent = initials(displayName);
        });
    }

    window.toggleProfileMenu = function () {
        const menu = document.getElementById("profileMenu");
        const trigger = document.getElementById("profileTrigger");
        if (!menu || !trigger) return;
        const willOpen = !menu.classList.contains("open");
        menu.classList.toggle("open", willOpen);
        trigger.setAttribute("aria-expanded", String(willOpen));
    };

    document.addEventListener("click", function (event) {
        const control = document.querySelector(".profile-control");
        const menu = document.getElementById("profileMenu");
        const trigger = document.getElementById("profileTrigger");
        if (control && menu && !control.contains(event.target)) {
            menu.classList.remove("open");
            if (trigger) trigger.setAttribute("aria-expanded", "false");
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            const menu = document.getElementById("profileMenu");
            const trigger = document.getElementById("profileTrigger");
            if (menu) menu.classList.remove("open");
            if (trigger) trigger.setAttribute("aria-expanded", "false");
        }
    });

    const workspace = document.getElementById("workspace");
    if (workspace && "MutationObserver" in window) {
        new MutationObserver(syncWorkspacePresentation).observe(workspace, {
            attributes: true,
            attributeFilter: ["class"]
        });
    }

    document.addEventListener("DOMContentLoaded", syncWorkspacePresentation);
    window.addEventListener("storage", syncWorkspacePresentation);
    syncWorkspacePresentation();
})();
