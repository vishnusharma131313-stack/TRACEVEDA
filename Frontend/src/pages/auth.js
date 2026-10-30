/* Sign-in, access request and role selection. */
let selectedAuthRole = null;

let selectedRequestRole = null;

let currentAuthMode = "signin";

function getBackendRole(frontendRole) {

    const roleMap = {

        lab: "lab",

        manufacturer: "manufacturer",

        auditor: "regulator",

        transporter: "logistics",

        farmer: "farmer",

        processor: "processor",

        logistics: "logistics",

        admin: "admin"

    };

    return roleMap[frontendRole] || null;

}

function openAuthModal(mode) {

    currentAuthMode = mode;

    const modal =
        document.getElementById("authModal");

    const title =
        document.getElementById("authTitle");

    const subtitle =
        document.getElementById("authSubtitle");

    const signinForm =
        document.getElementById("signinForm");

    const requestAccessForm =
        document.getElementById("requestAccessForm");

    const signinRoleSection =
        document.getElementById("signinRoleSection");

    const requestRoleSection =
        document.getElementById("requestRoleSection");

    const message =
        document.getElementById("authMessage");


    modal.classList.add("active");

    selectedAuthRole = null;
    selectedRequestRole = null;


    document.querySelectorAll(".auth-role").forEach(role => {
        role.classList.remove("selected");
    });


    if (message) {
        message.className = "auth-message";
        message.textContent = "";
    }


    if (signinForm) {
        signinForm.style.display = "none";
        signinForm.reset();
    }


    if (requestAccessForm) {
        requestAccessForm.style.display = "none";
        requestAccessForm.reset();
    }


    /* SIGN IN */

    if (currentAuthMode === "signin") {

        title.textContent = "Sign In";

        subtitle.textContent =
            "Use the TraceVeda ID and password issued to you after verification.";

        if (signinRoleSection) {
            signinRoleSection.style.display = "";
        }

        if (requestRoleSection) {
            requestRoleSection.style.display = "none";
        }

    }


    /* ADMINISTRATOR LOGIN */

    else if (currentAuthMode === "admin") {

        title.textContent = "Administrator Login";
        subtitle.textContent = "Demo administrator account: admin-001. Enter the configured password to continue.";
        selectedAuthRole = "admin";

        if (signinRoleSection) signinRoleSection.style.display = "none";
        if (requestRoleSection) requestRoleSection.style.display = "none";
        if (signinForm) signinForm.style.display = "flex";
        const usernameInput = document.getElementById("signinUsername");
        if (usernameInput) usernameInput.value = "admin-001";

    }

    /* REQUEST ACCESS */

    else {

        title.textContent = "Request Access";

        subtitle.textContent =
            "Submit your organisation details for administrator review.";

        if (signinRoleSection) {
            signinRoleSection.style.display = "none";
        }

        if (requestRoleSection) {
            requestRoleSection.style.display = "";
        }

    }

}

function selectAuthRole(button) {

    /* Remove previous selection */
    document
        .querySelectorAll("#signinRoleSection .auth-role")
        .forEach(role => {
            role.classList.remove("selected");
        });

    /* Select clicked role */
    button.classList.add("selected");

    /* Store selected role */
    selectedAuthRole =
        button.dataset.role;

    /* Hide role selection */
    const signinRoleSection =
        document.getElementById("signinRoleSection");

    /* Show username/password form */
    const signinForm =
        document.getElementById("signinForm");

    if (signinRoleSection) {
        signinRoleSection.style.display = "none";
    }

    if (signinForm) {
        signinForm.style.display = "flex";
    }

}

function closeAuthModal() {

    document
        .getElementById("authModal")
        .classList.remove("active");

}

document
    .getElementById("signinForm")
    .addEventListener("submit", async function(event) {
        event.preventDefault();

        const username = document.getElementById("signinUsername").value.trim().toLowerCase();
        const password = document.getElementById("signinPassword").value;

        if (!selectedAuthRole) {
            showAuthMessage("Please select your role first.", "error");
            return;
        }
        if (!username || !password) {
            showAuthMessage("Please enter your ID and password.", "error");
            return;
        }

        const submitButton = document.querySelector("#signinForm .auth-submit");
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Signing in…";
        }
        showAuthMessage("Signing in…", "info");

        try {
            const response = await fetch(`${API_URL}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const detail = Array.isArray(data?.detail)
                    ? data.detail.map(item => item?.msg || String(item)).join(" · ")
                    : data?.detail;
                showAuthMessage(detail || data?.message || "Invalid username or password.", "error");
                return;
            }

            const user = data.user || data;
            const backendRole = user.role || data.role;
            const accessToken = data.access_token || data.token;

            if (!accessToken || !backendRole) {
                showAuthMessage("The server login response did not include an access token and role. Check the backend /api/auth/login response.", "error");
                return;
            }

            if (currentAuthMode === "admin" && backendRole !== "admin") {
                showAuthMessage("Access denied. This login requires an Administrator account.", "error");
                return;
            }

            const canonicalRole = String(backendRole).trim().toLowerCase();
            const roleAliases = {
                auditor: "regulator",
                transporter: "logistics"
            };
            const normalizedBackendRole = roleAliases[canonicalRole] || canonicalRole;

            if (currentAuthMode !== "admin") {
                const expectedRole = getBackendRole(selectedAuthRole);
                if (normalizedBackendRole !== expectedRole) {
                    showAuthMessage(`This account belongs to the ${backendRole} role. Choose the matching login option.`, "error");
                    return;
                }
            }

            const uiRole = normalizedBackendRole === "regulator" ? "auditor"
                : normalizedBackendRole === "logistics" ? "transporter"
                : normalizedBackendRole;

            if (!roleMenus[uiRole]) {
                showAuthMessage(`The backend role “${backendRole}” does not have a frontend workspace configured yet.`, "error");
                return;
            }

            const sessionUser = {
                username: user.username || data.username || username,
                role: backendRole,
                full_name: user.full_name || data.full_name || "",
                organisation_id: user.organisation_id || data.organisation_id || null
            };

            localStorage.setItem("traceveda_token", accessToken);
            localStorage.setItem("traceveda_user", JSON.stringify(sessionUser));

            showAuthMessage("Sign in successful.", "success");
            setTimeout(() => {
                closeAuthModal();
                openRole(uiRole);
            }, 250);

        } catch (error) {
            console.error("Login error:", error);
            showAuthMessage(`Unable to connect to the server: ${error.message}`, "error");
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = 'Sign In <i class="fa-solid fa-arrow-right"></i>';
            }
        }
    });

function selectRequestRole(button) {

    document
        .querySelectorAll("#requestRoleSection .auth-role")
        .forEach(role => {
            role.classList.remove("selected");
        });

    button.classList.add("selected");

    selectedRequestRole =
        button.dataset.role;

    const requestRoleSection =
        document.getElementById("requestRoleSection");

    const requestAccessForm =
        document.getElementById("requestAccessForm");


    if (requestRoleSection) {
        requestRoleSection.style.display = "none";
    }


    if (requestAccessForm) {
        requestAccessForm.style.display = "flex";
    }

}

document
    .getElementById("requestAccessForm")
    .addEventListener("submit", async function(event) {
        event.preventDefault();

        if (!selectedRequestRole) {
            showAuthMessage("Please select your role first.", "error");
            return;
        }

        const organisationName = document.getElementById("requestOrganisationName").value.trim();
        const location = document.getElementById("requestLocation").value.trim();
        const contactDetails = document.getElementById("requestContactDetails").value.trim();
        if (!organisationName || !location || !contactDetails) {
            showAuthMessage("Please complete all required fields.", "error");
            return;
        }

        const submitButton = document.querySelector("#requestAccessForm button[type='submit']");
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Submitting…";
        }

        try {
            const result = await apiRequest("/api/access-requests", {
                method: "POST",
                body: JSON.stringify({
                    role: selectedRequestRole,
                    organisation_name: organisationName,
                    location,
                    contact_details: contactDetails
                })
            });
            showAuthMessage(`Request submitted successfully. Your request ID is ${result.request_id}. An administrator will review it.`, "success");
            document.getElementById("requestAccessForm").reset();
            selectedRequestRole = null;
        } catch (error) {
            showAuthMessage(`Could not submit access request: ${error.message}`, "error");
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = 'Submit Access Request <i class="fa-solid fa-arrow-right"></i>';
            }
        }
    });

const signupForm =
    document.getElementById("signupForm");

if (signupForm) {

    signupForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();


            /* ------------------------------------------
               CHECK ROLE
            ------------------------------------------ */

            if (!selectedAuthRole) {

                showAuthMessage(
                    "Please select your role first.",
                    "error"
                );

                return;
            }


            /* ------------------------------------------
               CONVERT FRONTEND ROLE
               TO BACKEND ROLE
            ------------------------------------------ */

            const backendRole =
                getBackendRole(selectedAuthRole);


            /* ------------------------------------------
               CONSUMER DOES NOT REQUIRE ACCOUNT
            ------------------------------------------ */

            if (
                selectedAuthRole === "consumer"
            ) {

                showAuthMessage(
                    "Consumer access does not require an account.",
                    "error"
                );

                return;
            }


            if (!backendRole) {

                showAuthMessage(
                    "This role cannot create an account.",
                    "error"
                );

                return;
            }


            /* ------------------------------------------
               GET PASSWORD
            ------------------------------------------ */

            const password =
                document
                    .getElementById("signupPassword")
                    .value;

            const confirmPassword =
                document
                    .getElementById("signupConfirmPassword")
                    .value;


            /* ------------------------------------------
               PASSWORD MATCH
            ------------------------------------------ */

            if (password !== confirmPassword) {

                showAuthMessage(
                    "Passwords do not match.",
                    "error"
                );

                return;
            }


            /* ------------------------------------------
               PASSWORD LENGTH
            ------------------------------------------ */

            if (password.length < 8) {

                showAuthMessage(
                    "Password must contain at least 8 characters.",
                    "error"
                );

                return;
            }


            /* ------------------------------------------
               LOADING
            ------------------------------------------ */

            showAuthMessage(
                "Creating your TraceVeda account...",
                "success"
            );


            try {

                /* ------------------------------------------
                   BACKEND SIGNUP REQUEST
                ------------------------------------------ */

                const response =
                    await fetch(
                        `${API_URL}/api/auth/signup`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                password: password,
                                role: backendRole
                            })
                        }
                    );


                const data =
                    await response.json();


                /* ------------------------------------------
                   SIGNUP FAILED
                ------------------------------------------ */

                if (!response.ok) {

                    showAuthMessage(
                        data.detail ||
                        "Unable to create account.",
                        "error"
                    );

                    return;
                }


                /* ------------------------------------------
                   SUCCESS
                ------------------------------------------ */

                const generatedID =
                    data.user.username;


                showAuthMessage(
                    `Account created successfully! Your TraceVeda ID is: ${generatedID}`,
                    "success"
                );


                console.log(
                    "Account created:",
                    data
                );


                /* ------------------------------------------
                   SAVE USER DATA
                ------------------------------------------ */

                localStorage.setItem(
                    "traceveda_user",
                    JSON.stringify(data.user)
                );


                /* ------------------------------------------
                   AUTO-FILL SIGN IN
                ------------------------------------------ */

                setTimeout(function() {

                    alert(
                        "Account Created Successfully!\n\n" +
                        "Your TraceVeda ID is:\n" +
                        generatedID +
                        "\n\nPlease remember this ID."
                    );


                    /* Close signup modal */

                    closeAuthModal();


                    /* Open signin modal */

                    openAuthModal("signin");


                    /* Select same role */

                    document
                        .querySelectorAll(".auth-role")
                        .forEach(role => {

                            if (
                                role.dataset.role ===
                                selectedAuthRole
                            ) {

                                selectAuthRole(role);

                            }

                        });


                    /* Fill generated ID */

                    const signinUsername =
                        document.getElementById(
                            "signinUsername"
                        );


                    if (signinUsername) {

                        signinUsername.value =
                            generatedID;

                    }

                }, 1000);


            }
            catch (error) {

                console.error(
                    "Signup error:",
                    error
                );


                showAuthMessage(
                    "Unable to connect to the server.",
                    "error"
                );

            }

        }
    );

}


function logoutTraceVeda() {
    localStorage.removeItem("traceveda_token");
    localStorage.removeItem("traceveda_user");
    sessionStorage.removeItem("traceveda_qr_id");
    currentRole = null;
    showLanding();
}

function showAuthMessage(message, type) {


    const element =
        document.getElementById("authMessage");


    if (!element) {

        return;

    }


    element.textContent =
        message;


    element.className =
        "auth-message " + type;

}

document.addEventListener(

    "keydown",

    function(event) {

        if (event.key === "Escape") {

            closeAuthModal();

        }

    }

);
