/* Shared workspace navigation and role-based shell behaviour. */
function openRole(role, panel = null){

    console.log("Opening role:", role);

    // Validate role
    if(!roleMenus[role]){
        console.error("Invalid role:", role);
        return;
    }


    // Store current role
    currentRole = role;
    document.body.setAttribute("data-role", role);


    /* ==========================================
       SWITCH HEADER TO WORKSPACE MODE
    ========================================== */

    const publicHeaderNav =
        document.getElementById("publicHeaderNav");

    const publicHeaderActions =
        document.getElementById("publicHeaderActions");

    const workspaceHeader =
        document.getElementById("workspaceHeader");

    /* Hide public navigation */
    if (publicHeaderNav) {
        publicHeaderNav.style.display = "none";
    }


    /* Hide Sign In / Request Access */
    if (publicHeaderActions) {
        publicHeaderActions.style.display = "none";
    }


    /* Show and populate the identity control in the actual top header. */
    const rolePresentation = {
        lab: { label: "Laboratory workspace", subtitle: "Quality testing & verification", icon: "fa-flask" },
        manufacturer: { label: "Manufacturer workspace", subtitle: "Production & batch management", icon: "fa-industry" },
        transporter: { label: "Transporter workspace", subtitle: "Transport & logistics", icon: "fa-truck-fast" },
        auditor: { label: "Auditor workspace", subtitle: "Audit & compliance", icon: "fa-shield-halved" },
        admin: { label: "Administrator workspace", subtitle: "Platform administration", icon: "fa-user-gear" },
        consumer: { label: "Consumer experience", subtitle: "Medicine verification", icon: "fa-capsules" }
    };
    const presentation = rolePresentation[role] || rolePresentation.consumer;
    let signedInUser = {};
    try {
        signedInUser = JSON.parse(localStorage.getItem("traceveda_user") || "{}") || {};
    } catch (error) {
        console.warn("Unable to read logged-in user:", error);
    }
    const username = role === "consumer"
        ? "Consumer"
        : (signedInUser.username || signedInUser.full_name || "User");
    const displayName = signedInUser.full_name || signedInUser.username || "TraceVeda User";

    if (workspaceHeader) {
        workspaceHeader.style.setProperty("display", "flex", "important");
        workspaceHeader.removeAttribute("hidden");
    }
    document.body.classList.add("workspace-mode");
    const greetingName = document.getElementById("workspaceGreetingName");
    const roleLabel = document.getElementById("workspaceRoleLabel");
    const greetingSubtitle = document.getElementById("workspaceGreetingSubtitle");
    const roleIcon = document.getElementById("workspaceRoleIcon");
    if (greetingName) greetingName.textContent = username;
    if (roleLabel) roleLabel.textContent = presentation.label;
    if (greetingSubtitle) greetingSubtitle.textContent = presentation.subtitle;
    if (roleIcon) roleIcon.className = `fa-solid ${presentation.icon}`;
    const menuName = document.getElementById("profileMenuName");
    const menuRole = document.getElementById("profileMenuRole");
    const menuAvatar = document.getElementById("profileAvatarLarge");
    if (menuName) menuName.textContent = displayName;
    if (menuRole) menuRole.textContent = presentation.label;
    if (menuAvatar) menuAvatar.textContent = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "TV";

    /* ==========================================
    MANUFACTURER FIELD FORMAT HINTS
    ========================================== */

    if (role === "manufacturer") {
        updateManufacturerBatchFormats();
    }


    // Hide landing page
    const landing =
        document.getElementById("landing");

    if(landing){
        landing.style.display = "none";
    }


    // Show workspace
    const workspace =
        document.getElementById("workspace");

    if(workspace){
        workspace.classList.add("active");
    }


    // Close role dropdown
    const roleMenu =
        document.getElementById("roleMenu");

    if(roleMenu){
        roleMenu.classList.remove("open");
    }


    // Update sidebar heading
    const sidebarRole =
        document.getElementById("sidebarRole");

    if(sidebarRole){

        const roleNames = {

            auditor:
                "Auditor Workspace",

            lab:
                "Laboratory Workspace",

            manufacturer:
                "Manufacturer Workspace",

            transporter:
                "Transporter Workspace",

            admin:
                "Administrator Workspace",

            consumer:
                "Consumer Experience"
        };

        sidebarRole.textContent =
            roleNames[role] ||
            "TraceVeda Workspace";

    }


    // Build the correct sidebar
    buildSidebar(role);


    // Determine which panel to open
    const firstPanel =
        panel ||
        roleMenus[role][0][0];


    console.log(
        "Opening panel:",
        firstPanel
    );


    if (firstPanel === "auditor-reports") {

        loadConsumerReports();

    }

    if (role === "admin" && typeof loadAdminDashboard === "function") {
        loadAdminDashboard();
    }


    // Open role-specific panel
    switchPanel(firstPanel);

}

function buildSidebar(role){

    const menu =
        document.getElementById("sidebarMenu");

    menu.innerHTML="";

    roleMenus[role].forEach(item=>{

        const [id,label,icon] = item;

        const button =
            document.createElement("button");

        button.className="sidebar-item";

        button.dataset.panel=id;

        button.innerHTML=
            `<i class="fa-solid ${icon}"></i>${label}`;

        button.addEventListener("click", function(event) {

            event.preventDefault();
            event.stopPropagation();

            switchPanel(id);

        });

        menu.appendChild(button);

    });

}

function switchPanel(name){

    // Hide every panel first
    document.querySelectorAll(".panel").forEach(panel => {
        panel.classList.remove("active");
    });


    // The panel ID is already provided by roleMenus
    // for role-specific panels.
    const target = document.getElementById(name);


    if(target){

        target.classList.add("active");

        console.log(
            "Active panel after switch:",
            document.querySelector(".panel.active")?.id
        );

    }
    else{
        console.error("Panel not found:", name);
    }

// If IoT Evidence is opened and a batch ID is already entered,
// refresh its live backend data.
if(name === "auditor-iot"){
    const iotInput = document.getElementById("iotBatchId");

    if(iotInput && iotInput.value.trim()){
        loadIoTEvidence();
    }
}


// Load real consumer reports from MongoDB
if(name === "auditor-reports"){
    loadConsumerReports();
}

    // Update active sidebar item
    document.querySelectorAll(".sidebar-item").forEach(item => {

        item.classList.toggle(
            "active",
            item.dataset.panel === name
        );

    });

    // Refresh the medicine selector when its workspace panel is opened.
    if (name === "manufacturer-qr") {
        const select = document.getElementById("qrMedicineBatch");
        if (select && select.dataset.loaded !== "true") {
            loadMedicineBatchesForQR();
        } else if (select && select.value) {
            handleMedicineQRSelection();
        }
    }

    // Refresh the selected storage node's latest telemetry when the panel opens.
    if (name === "manufacturer-storage") {
        selectStorageNode();
    }
}

function showLanding(){

    currentRole = null;
    document.body.removeAttribute("data-role");
    document.body.classList.remove("workspace-mode");

    /* ==========================================
       RESTORE PUBLIC HEADER
    ========================================== */

    const publicHeaderNav =
        document.getElementById("publicHeaderNav");

    const publicHeaderActions =
        document.getElementById("publicHeaderActions");

    const workspaceHeader =
        document.getElementById("workspaceHeader");


    if (publicHeaderNav) {
        publicHeaderNav.style.display = "flex";
    }

    if (publicHeaderActions) {
        publicHeaderActions.style.display = "flex";
    }

    if (workspaceHeader) {
        workspaceHeader.style.display = "none";
    }


    /* ==========================================
       SHOW LANDING PAGE
    ========================================== */

    document
        .getElementById("workspace")
        .classList.remove("active");

    document
        .getElementById("landing")
        .style.display = "block";


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

}

function toggleRoleMenu(){

    document
    .getElementById("roleMenu")
    .classList.toggle("open");


}

// Sidebar is populated only after a role has been authenticated or the public consumer flow is opened.
