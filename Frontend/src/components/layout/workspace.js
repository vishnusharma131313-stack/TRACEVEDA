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


    /* ==========================================
       SWITCH HEADER TO WORKSPACE MODE
    ========================================== */

    const publicHeaderNav =
        document.getElementById("publicHeaderNav");

    const publicHeaderActions =
        document.getElementById("publicHeaderActions");

    const workspaceHeader =
        document.getElementById("workspaceHeader");

    const workspaceWelcome =
        document.getElementById("workspaceWelcome");


    /* Hide public navigation */
    if (publicHeaderNav) {
        publicHeaderNav.style.display = "none";
    }


    /* Hide Sign In / Request Access */
    if (publicHeaderActions) {
        publicHeaderActions.style.display = "none";
    }


    /* Show workspace greeting */
    if (workspaceHeader) {
        workspaceHeader.style.display = "flex";
    }


    /* ==========================================
       WORKSPACE GREETING
    ========================================== */

    /*
     * Consumer verification is a public workflow.
     * It should NOT display the username of a previously
     * logged-in user.
     */ 

    if (role === "consumer") {

        if (workspaceWelcome) {

            workspaceWelcome.textContent =
                "Welcome Consumer!";

        }

    }


    /*
     * All authenticated workspaces display the
     * currently logged-in user's username.
     */

    else {

        let loggedInUsername = "User";

        try {

            const storedUser =
                JSON.parse(
                    localStorage.getItem("traceveda_user")
                );

            if (
                storedUser &&
                storedUser.username
            ) {

                loggedInUsername =
                    storedUser.username;

            }

        } catch (error) {

            console.warn(
                "Unable to read logged-in user:",
                error
            );

        }


        if (workspaceWelcome) {

            workspaceWelcome.textContent =
                `Welcome to the workspace, ${loggedInUsername}`;

        }

    }

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
