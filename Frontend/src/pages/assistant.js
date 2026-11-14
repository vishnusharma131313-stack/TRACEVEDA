/* Public TraceVeda Assistant: anonymous website help + no-email access requests. */
(function () {
    "use strict";

    const API_BASE = (window.TRACEVEDA_CONFIG?.API_BASE_URL || "").replace(/\/+$/, "");
    const SESSION_KEY = "traceveda_assistant_session";
    const root = document.getElementById("traceVedaAssistantRoot");
    if (!root) return;

    const launcher = document.getElementById("tvAssistantLauncher");
    const panel = document.getElementById("tvAssistantPanel");
    const closeButton = document.getElementById("tvAssistantClose");
    const newChatButton = document.getElementById("tvAssistantNewChat");
    const messagesNode = document.getElementById("tvAssistantMessages");
    const quickActionsNode = document.getElementById("tvAssistantQuickActions");
    const form = document.getElementById("tvAssistantForm");
    const input = document.getElementById("tvAssistantInput");
    const sendButton = document.getElementById("tvAssistantSend");

    let sessionId = null;
    let sessionReady = null;
    let application = null;
    let busy = false;
    let lastRecoveryCode = null;
    let activationContext = null;

    const roleOptions = [
        { value: "lab", label: "Laboratory" },
        { value: "manufacturer", label: "Manufacturer" },
        { value: "transporter", label: "Transporter" },
        { value: "auditor", label: "Auditor" },
        { value: "farmer", label: "Farmer" },
        { value: "processor", label: "Processor" },
    ];

    async function api(path, options = {}) {
        let response;
        try {
            response = await fetch(`${API_BASE}${path}`, {
                ...options,
                headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            });
        } catch (_) {
            throw new Error("Unable to reach TraceVeda right now. Please check the connection and try again.");
        }
        const text = await response.text();
        let data = {};
        try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text }; }
        if (!response.ok) {
            const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg || String(item)).join(" · ") : data.detail;
            throw new Error(detail || data.message || `Request failed (${response.status})`);
        }
        return data;
    }

    function addMessage(role, text, options = {}) {
        const bubble = document.createElement("div");
        bubble.className = `tv-assistant-message ${role}${options.pending ? " pending" : ""}`;
        bubble.textContent = String(text ?? "");
        if (options.id) bubble.id = options.id;
        messagesNode.appendChild(bubble);
        messagesNode.scrollTop = messagesNode.scrollHeight;
        return bubble;
    }

    function setQuickActions(items) {
        quickActionsNode.replaceChildren();
        (items || []).forEach(item => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = item.label;
            button.addEventListener("click", item.onClick);
            quickActionsNode.appendChild(button);
        });
    }

    function welcomeActions() {
        setQuickActions([
            { label: "What can you help with?", onClick: () => sendText("What can you help me with on TraceVeda?") },
            { label: "Request an account", onClick: startApplication },
            { label: "Track / activate application", onClick: () => openActivationModal() },
        ]);
    }

    async function ensureSession(forceNew = false) {
        if (sessionReady && !forceNew) return sessionReady;
        sessionReady = (async () => {
            if (!forceNew) {
                try {
                    const saved = localStorage.getItem(SESSION_KEY);
                    if (saved) {
                        const existing = await api(`/api/assistant/session/${encodeURIComponent(saved)}`);
                        sessionId = existing.session_id;
                        messagesNode.replaceChildren();
                        (existing.messages || []).forEach(message => addMessage(message.role, message.content));
                        if (!existing.messages?.length) addMessage("assistant", "Welcome to TraceVeda! I can explain website features or help you request an account. / TraceVeda mein aapka swagat hai!");
                        welcomeActions();
                        return sessionId;
                    }
                } catch (_) {
                    localStorage.removeItem(SESSION_KEY);
                }
            }
            const created = await api("/api/assistant/session", { method: "POST", body: "{}" });
            sessionId = created.session_id;
            localStorage.setItem(SESSION_KEY, sessionId);
            messagesNode.replaceChildren();
            addMessage("assistant", "Welcome to TraceVeda! I can explain website features or help you request an account. / TraceVeda mein aapka swagat hai!");
            welcomeActions();
            return sessionId;
        })();
        try { return await sessionReady; }
        finally { sessionReady = null; }
    }

    function setBusy(value) {
        busy = value;
        sendButton.disabled = value;
        input.disabled = value;
    }

    async function sendText(text) {
        const message = String(text || "").trim();
        if (!message || busy || application) return;
        input.value = "";
        setQuickActions([]);
        setBusy(true);
        let pending = null;
        try {
            await ensureSession();
            addMessage("user", message);
            pending = addMessage("assistant", "Thinking…", { pending: true, id: "tvAssistantPending" });
            const result = await api("/api/assistant/chat", {
                method: "POST",
                body: JSON.stringify({ session_id: sessionId, message }),
            });
            pending.remove();
            addMessage("assistant", result.reply || "I couldn't prepare a reply. Please try again.");
            welcomeActions();
        } catch (error) {
            pending?.remove();
            addMessage("assistant", error.message);
            welcomeActions();
        } finally {
            setBusy(false);
            input.focus();
        }
    }

    function startApplication() {
        application = { role: null, step: 0, data: {} };
        addMessage("assistant", "I can guide you through an account application. Admin accounts are created internally and cannot be requested here. We will collect your email and phone for administrator contact only; no OTP or email will be sent. Which role do you need? / Aapko kis role ka account chahiye?");
        setQuickActions(roleOptions.map(role => ({
            label: role.label,
            onClick: () => selectApplicationRole(role),
        })).concat([{ label: "Cancel", onClick: cancelApplication }]));
        input.placeholder = "Choose a role above…";
        input.disabled = true;
        sendButton.disabled = true;
    }

    function selectApplicationRole(role) {
        application.role = role.value;
        addMessage("user", role.label);
        setQuickActions([]);
        input.disabled = false;
        sendButton.disabled = false;
        input.placeholder = "Type your answer…";
        application.fields = [
            { key: "full_name", label: "Full name", prompt: "What is your full name? / Aapka poora naam?" },
            { key: "email", label: "Email address", prompt: "What email address should the administrator use to contact you? We do not send OTPs or automated emails. / Admin contact ke liye apna email address batayein." },
            { key: "phone", label: "Phone number", prompt: "What phone number should the organisation use to contact you? / Contact number batayein." },
            { key: "organisation_name", label: "Organisation", prompt: "What is your organisation, company, laboratory or farm name? / Organisation ya company ka naam?" },
            { key: "location", label: "Location", prompt: "Where are you based? Please enter city and state. / City aur state batayein." },
            { key: "designation", label: "Designation", prompt: "What is your designation or responsibility? / Aapki designation ya zimmedari?" },
            { key: "role_details", label: "Role-specific details", prompt: roleDetailsPrompt(role.value) },
            { key: "reason", label: "Reason for access", prompt: "Briefly explain why your organisation needs TraceVeda access. / TraceVeda access kyun chahiye?" },
        ];
        application.step = 0;
        askApplicationQuestion();
    }

    function roleDetailsPrompt(role) {
        const prompts = {
            lab: "Please share your laboratory registration/accreditation details (or write ‘Not available’). / Lab registration ya accreditation details batayein.",
            manufacturer: "Please share your manufacturing licence or registration details (or write ‘Not available’). / Manufacturing licence details batayein.",
            transporter: "Please share your fleet, vehicle or transport registration details (or write ‘Not available’). / Vehicle ya fleet details batayein.",
            auditor: "Please share your audit credentials, affiliation or authorisation details (or write ‘Not available’). / Audit credentials batayein.",
            farmer: "Please share your farm, supplier or cultivation registration details (or write ‘Not available’). / Farm ya supplier details batayein.",
            processor: "Please share your processing facility or registration details (or write ‘Not available’). / Processing facility details batayein.",
        };
        return prompts[role] || "Share relevant organisation details.";
    }

    function askApplicationQuestion() {
        const field = application?.fields?.[application.step];
        if (!field) return showApplicationSummary();
        addMessage("assistant", field.prompt);
        input.placeholder = `Enter ${field.label.toLowerCase()}…`;
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
    }

    function validAnswer(key, value) {
        if (key === "email") return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        if (key === "phone") return value.replace(/\D/g, "").length >= 7 && value.replace(/\D/g, "").length <= 15;
        if (key === "reason") return value.length >= 5;
        return value.length >= 2;
    }

    function handleApplicationAnswer(value) {
        const field = application?.fields?.[application.step];
        if (!field) return showApplicationSummary();
        if (!validAnswer(field.key, value)) {
            addMessage("assistant", field.key === "email" ? "That email doesn't look valid. Please check it and try again." : field.key === "phone" ? "Please enter a valid phone number." : "Please provide a little more detail.");
            return;
        }
        application.data[field.key] = value;
        addMessage("user", value);
        application.step += 1;
        if (application.step < application.fields.length) askApplicationQuestion();
        else showApplicationSummary();
    }

    function showApplicationSummary() {
        const d = application.data;
        const role = roleOptions.find(item => item.value === application.role)?.label || application.role;
        const summary = [
            `Role: ${role}`,
            `Name: ${d.full_name}`,
            `Organisation: ${d.organisation_name}`,
            `Email: ${d.email}`,
            `Phone: ${d.phone}`,
            `Location: ${d.location}`,
            `Designation: ${d.designation}`,
            `Role details: ${d.role_details}`,
            `Reason: ${d.reason}`,
        ].join("\n");
        addMessage("assistant", `Please review your application. Your email and phone are collected for administrator contact only; they are not verified and no email/SMS will be sent.\n\n${summary}\n\nSubmit only if everything is correct.`);
        input.disabled = true;
        sendButton.disabled = true;
        input.placeholder = "Review the details above…";
        setQuickActions([
            { label: "Submit application", onClick: submitApplication },
            { label: "Start again", onClick: restartApplication },
            { label: "Cancel", onClick: cancelApplication },
        ]);
    }

    async function submitApplication() {
        if (!application || busy) return;
        setQuickActions([]);
        setBusy(true);
        addMessage("user", "Submit my account application.");
        const pending = addMessage("assistant", "Submitting your application…", { pending: true });
        try {
            const result = await api("/api/access-requests", {
                method: "POST",
                body: JSON.stringify({ role: application.role, ...application.data }),
            });
            pending.remove();
            lastRecoveryCode = result.recovery_code;
            const receipt = [
                "Your application has been submitted successfully.",
                "",
                `Request ID: ${result.request_id}`,
                `Recovery code: ${result.recovery_code}`,
                "Status: PENDING",
                "",
                "IMPORTANT: Save both the Request ID and recovery code now. The recovery code is shown only once and is not emailed or stored in chat history. You will need it to track the request and activate your account after administrator approval.",
                "",
                "An administrator will review your details and may contact you using the email address or phone number you provided. Approval is not automatic.",
                "Email and phone are not verified by this no-email workflow. / Dhanyavaad!",
            ].join("\n");
            addMessage("assistant", receipt);
            application = null;
            input.value = "";
            input.maxLength = 1200;
            input.disabled = false;
            sendButton.disabled = false;
            input.placeholder = "Ask about TraceVeda…";
            setQuickActions([
                {
                    label: "Copy full application receipt",
                    onClick: async () => {
                        const receiptText = `TraceVeda application\nRequest ID: ${result.request_id}\nRecovery code: ${result.recovery_code}\nStatus: PENDING`;
                        try {
                            await navigator.clipboard.writeText(receiptText);
                            addMessage("assistant", "Application receipt copied. Save it somewhere private and safe.");
                        } catch (_) {
                            window.prompt("Copy and save this application receipt:", receiptText);
                        }
                    },
                },
                {
                    label: "Copy recovery code only",
                    onClick: async () => {
                        try {
                            await navigator.clipboard.writeText(lastRecoveryCode || result.recovery_code);
                            addMessage("assistant", "Recovery code copied. Store it somewhere safe.");
                        } catch (_) {
                            window.prompt("Copy and save this recovery code:", lastRecoveryCode || result.recovery_code);
                        }
                    },
                },
                {
                    label: "Track / activate application",
                    onClick: () => openActivationModal({ request_id: result.request_id, recovery_code: result.recovery_code }),
                },
                { label: "Ask another question", onClick: () => welcomeActions() },
            ]);
        } catch (error) {
            pending.remove();
            addMessage("assistant", `I couldn't submit the application: ${error.message}`);
            setQuickActions([
                { label: "Try again", onClick: submitApplication },
                { label: "Start again", onClick: restartApplication },
                { label: "Cancel", onClick: cancelApplication },
            ]);
        } finally {
            setBusy(false);
            if (application && application.step >= application.fields.length) {
                input.disabled = true;
                sendButton.disabled = true;
            }
        }
    }

    function restartApplication() {
        application = null;
        input.maxLength = 1200;
        addMessage("assistant", "Let's start the application again. / Chaliye dobara shuru karte hain.");
        startApplication();
    }

    function cancelApplication() {
        application = null;
        input.disabled = false;
        sendButton.disabled = false;
        input.maxLength = 1200;
        input.placeholder = "Ask about TraceVeda…";
        addMessage("assistant", "Your account application was cancelled. No request was submitted.");
        welcomeActions();
    }

    function openPanel(mode) {
        panel.hidden = false;
        launcher.setAttribute("aria-expanded", "true");
        ensureSession().then(() => {
            if (mode === "account" && !application) startApplication();
            input.focus();
        }).catch(error => addMessage("assistant", error.message));
    }

    window.openTraceVedaAssistant = function (mode) { openPanel(mode || "general"); };

    launcher.addEventListener("click", () => panel.hidden ? openPanel("general") : closePanel());
    closeButton.addEventListener("click", closePanel);
    function closePanel() {
        panel.hidden = true;
        launcher.setAttribute("aria-expanded", "false");
    }
    newChatButton.addEventListener("click", async () => {
        if (application) {
            if (!window.confirm("Start a new chat and discard this unfinished application?")) return;
        }
        const previousSession = sessionId;
        application = null;
        input.disabled = false;
        sendButton.disabled = false;
        input.maxLength = 1200;
        localStorage.removeItem(SESSION_KEY);
        sessionId = null;
        sessionReady = null;
        if (previousSession) {
            try { await api(`/api/assistant/session/${encodeURIComponent(previousSession)}`, { method: "DELETE" }); }
            catch (_) { /* The 30-day TTL still removes an unreachable old session. */ }
        }
        lastRecoveryCode = null;
        await ensureSession(true);
    });

    form.addEventListener("submit", event => {
        event.preventDefault();
        const value = input.value.trim();
        if (!value || busy) return;
        input.value = "";
        if (application) handleApplicationAnswer(value);
        else sendText(value);
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !panel.hidden) closePanel();
    });

    // No-email applicant workflow: the visitor proves possession of the
    // one-time recovery code saved when the application was submitted.
    const activationModal = document.getElementById("tvActivationModal");
    const lookupForm = document.getElementById("tvActivationLookupForm");
    const passwordForm = document.getElementById("tvActivationForm");
    const activationMessage = document.getElementById("tvActivationMessage");
    const approvalPanel = document.getElementById("tvActivationApprovalPanel");

    function openActivationModal(prefill = null) {
        if (!activationModal) return;
        activationContext = null;
        if (approvalPanel) approvalPanel.hidden = true;
        if (lookupForm) {
            lookupForm.hidden = false;
            lookupForm.reset();
        }
        if (passwordForm) {
            passwordForm.hidden = true;
            passwordForm.reset();
            passwordForm.querySelectorAll("input,button").forEach(node => { node.disabled = false; });
        }
        if (activationMessage) {
            activationMessage.className = "tv-activation-message";
            activationMessage.textContent = "Enter the Request ID and recovery code you saved when you submitted your application.";
        }
        if (prefill) {
            document.getElementById("tvActivationRequestId").value = prefill.request_id || "";
            document.getElementById("tvActivationRecoveryCode").value = prefill.recovery_code || "";
        }
        activationModal.hidden = false;
        document.getElementById("tvActivationRequestId")?.focus();
    }

    function closeActivationModal() {
        if (activationModal) activationModal.hidden = true;
        activationContext = null;
    }

    document.getElementById("tvActivationClose")?.addEventListener("click", closeActivationModal);
    activationModal?.addEventListener("click", event => {
        if (event.target === activationModal) closeActivationModal();
    });

    lookupForm?.addEventListener("submit", async event => {
        event.preventDefault();
        const requestId = document.getElementById("tvActivationRequestId")?.value.trim() || "";
        const recoveryCode = document.getElementById("tvActivationRecoveryCode")?.value.trim() || "";
        const button = document.getElementById("tvActivationLookupSubmit");
        if (!requestId || !recoveryCode) {
            activationMessage.textContent = "Enter both the Request ID and recovery code.";
            return;
        }
        button.disabled = true;
        button.textContent = "Checking…";
        activationMessage.className = "tv-activation-message";
        activationMessage.textContent = "Checking your application status…";
        try {
            const result = await api("/api/access-requests/status", {
                method: "POST",
                body: JSON.stringify({ request_id: requestId, recovery_code: recoveryCode }),
            });
            activationContext = { request_id: requestId, recovery_code: recoveryCode, username: result.username || null };
            if (result.status === "PENDING") {
                activationMessage.textContent = "Your application is still pending administrator approval. Please check again later.";
                return;
            }
            if (result.status === "REJECTED") {
                activationMessage.textContent = `Your application was not approved.${result.admin_notes ? ` Admin note: ${result.admin_notes}` : " Please contact the TraceVeda administrator for details."}`;
                return;
            }
            if (result.status === "ACTIVATED") {
                activationMessage.className = "tv-activation-message success";
                activationMessage.textContent = `Your account (${result.username || "TraceVeda ID"}) is already active. You can sign in now.`;
                return;
            }
            if (result.status === "APPROVED") {
                if (approvalPanel) approvalPanel.hidden = false;
                if (lookupForm) lookupForm.hidden = true;
                document.getElementById("tvActivationApprovedText").textContent = `Your application is approved. Your TraceVeda login ID is ${result.username}. Create a password below to activate the account.`;
                if (passwordForm) passwordForm.hidden = false;
                activationMessage.className = "tv-activation-message success";
                activationMessage.textContent = "Application approved.";
                document.getElementById("tvActivationPassword")?.focus();
                return;
            }
            activationMessage.textContent = result.message || "The application status could not be determined.";
        } catch (error) {
            activationMessage.textContent = error.message;
        } finally {
            button.disabled = false;
            button.textContent = "Check status";
        }
    });

    passwordForm?.addEventListener("submit", async event => {
        event.preventDefault();
        const password = document.getElementById("tvActivationPassword")?.value || "";
        const confirmPassword = document.getElementById("tvActivationConfirm")?.value || "";
        const button = document.getElementById("tvActivationSubmit");
        if (!activationContext?.request_id || !activationContext?.recovery_code) {
            activationMessage.textContent = "Check your application status first.";
            return;
        }
        if (password.length < 8 || password.length > 128) {
            activationMessage.textContent = "Use a password between 8 and 128 characters.";
            return;
        }
        if (password !== confirmPassword) {
            activationMessage.textContent = "The passwords do not match.";
            return;
        }
        button.disabled = true;
        button.textContent = "Activating…";
        let activatedSuccessfully = false;
        try {
            const result = await api("/api/auth/activate", {
                method: "POST",
                body: JSON.stringify({
                    request_id: activationContext.request_id,
                    recovery_code: activationContext.recovery_code,
                    password,
                }),
            });
            activationMessage.className = "tv-activation-message success";
            activationMessage.textContent = `Account ${result.username} is now active. You can sign in using this TraceVeda ID and your new password.`;
            passwordForm.reset();
            passwordForm.querySelectorAll("input,button").forEach(node => { node.disabled = true; });
            activationContext = null;
            activatedSuccessfully = true;
        } catch (error) {
            activationMessage.textContent = error.message;
        } finally {
            button.disabled = activatedSuccessfully;
            button.textContent = activatedSuccessfully ? "Account activated" : "Activate account";
        }
    });

    // Create/restore the anonymous session only when the visitor opens the
    // assistant. Merely visiting the website must not create chat records.
})();
