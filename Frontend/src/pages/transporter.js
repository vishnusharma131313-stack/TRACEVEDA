/* Transporter mode switching, geotagged photo and ledger evidence. */

/* =========================================================
   RAW BATCH ID GENERATION
========================================================= */
let rawBatchGeneration = 0;

async function generateRawBatchId() {
    const cropSelect = document.getElementById("rawCrop");
    const output = document.getElementById("rawBatchId");
    const cropCode = cropSelect?.value?.trim();
    if (!output) return;
    if (!cropCode) {
        output.value = "";
        return;
    }

    const generation = ++rawBatchGeneration;
    output.value = "Generating…";
    const year = new Date().getFullYear();
    const storageKey = `traceveda_raw_batch_sequence_${year}`;
    let highest = Number(localStorage.getItem(storageKey) || (year === 2026 ? 71 : 0));

    // Prefer the backend's current batch list so a newly generated ID follows
    // existing RAW-YYYY-NNN records. Fall back to a browser-local sequence if
    // that optional collection endpoint is unavailable.
    try {
        const data = await apiRequest("/api/batches/raw", { method: "GET" });
        const batches = Array.isArray(data)
            ? data
            : (data?.batches || data?.raw_batches || data?.raw || []);
        for (const batch of batches) {
            const id = batch?.raw_batch_id || batch?.batch_id || batch?.id || "";
            const match = String(id).match(new RegExp("^RAW-" + year + "-(\\d+)$", "i"));
            if (match) highest = Math.max(highest, Number(match[1]));
        }
    } catch (_) {
        // The transport form can still prepare an ID when the collection read
        // is not available; the backend remains the final uniqueness authority.
    }

    if (generation !== rawBatchGeneration) return;
    const next = highest + 1;
    localStorage.setItem(storageKey, String(next));
    output.value = `RAW-${year}-${String(next).padStart(3, "0")}`;
    output.dataset.crop = cropCode;
}


function handleTransporterType() {

    const type =
        document.getElementById("transporterType")?.value;

    const rawForm =
        document.getElementById("rawToProcessorForm");

    const labManufacturerForm =
        document.getElementById("labToManufacturerForm");


    if (rawForm) {

        rawForm.style.display =
            type === "raw-to-processor"
                ? "block"
                : "none";

    }


    if (labManufacturerForm) {

        labManufacturerForm.style.display =
            type === "lab-to-manufacturer"
                ? "block"
                : "none";

    }

}

window.geoCameraStream = null;

window.geoCapturedImageBlob = null;

window.geoCoordinates = null;

window.geoCapturedAt = null;

async function startGeoCapture() {

    console.log("Open Camera clicked");
    setGeoGPSStatus("Opening camera and requesting GPS location…");

    /* -----------------------------------------
       CAMERA SUPPORT CHECK
    ----------------------------------------- */

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {
        alert(
            "Camera access is not supported by this browser."
        );
        return;
    }

    try {

        /* -----------------------------------------
           OPEN CAMERA FIRST
        ----------------------------------------- */

        window.geoCameraStream =
            await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: {
                        ideal: "environment"
                    }
                },
                audio: false
            });

        console.log("Camera stream acquired.");


        /* -----------------------------------------
           CAMERA PREVIEW
        ----------------------------------------- */

        const video =
            document.getElementById("geoCamera");

        if (!video) {
            stopGeoCamera();
            alert(
                "Camera preview element not found."
            );
            return;
        }

        video.srcObject =
            window.geoCameraStream;

        await video.play();


        document
            .getElementById("cameraStartArea")
            .style.display = "none";

        document
            .getElementById("cameraContainer")
            .style.display = "block";

        document
            .getElementById("cameraControls")
            .style.display = "block";


        /* -----------------------------------------
           GET GPS AFTER CAMERA IS OPEN
        ----------------------------------------- */

        if (navigator.geolocation) {

            navigator.geolocation.getCurrentPosition(

                function(position) {

                    geoCoordinates = {
                        latitude:
                            position.coords.latitude,

                        longitude:
                            position.coords.longitude,

                        accuracy:
                            position.coords.accuracy
                    };


                    const latitude =
                        document.getElementById(
                            "geoLatitude"
                        );

                    const longitude =
                        document.getElementById(
                            "geoLongitude"
                        );

                    const accuracy =
                        document.getElementById(
                            "geoAccuracy"
                        );


                    if (latitude) {
                        latitude.textContent =
                            geoCoordinates.latitude.toFixed(6);
                    }

                    if (longitude) {
                        longitude.textContent =
                            geoCoordinates.longitude.toFixed(6);
                    }

                    if (accuracy) {
                        accuracy.textContent =
                            `±${Math.round(
                                geoCoordinates.accuracy
                            )} m`;
                    }


                    setGeoGPSStatus(
                        "Location acquired successfully. You can now capture the image.",
                        true
                    );

                    console.log(
                        "GPS location acquired:",
                        geoCoordinates
                    );

                },

                function(error) {

                    console.error(
                        "Geolocation error:",
                        error
                    );

                    setGeoGPSStatus(
                        "Location could not be obtained. Enable location permission or retry GPS."
                    );
                    alert(
                        "Camera opened, but location could not be obtained. Please enable location permission."
                    );

                },

                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                }
            );

        } else {

            alert(
                "Geolocation is not supported by this browser."
            );

        }

    }

    catch (error) {

        console.error(
            "Camera error:",
            error
        );

        if (error.name === "NotAllowedError") {

            alert(
                "Camera permission was denied. Please allow camera access in your browser."
            );

        }

        else if (error.name === "NotFoundError") {

            alert(
                "No camera was found on this device."
            );

        }

        else if (error.name === "NotReadableError") {

            alert(
                "The camera is already being used by another application."
            );

        }

        else if (error.name === "SecurityError") {

            alert(
                "Camera access was blocked by the browser. Make sure TraceVeda is running on HTTPS or localhost."
            );

        }

        else {

            alert(
                `Unable to open camera: ${error.message}`
            );

        }

    }
}

function setGeoGPSStatus(message, success = false) {

    const status = document.getElementById("geoGpsStatus");
    const captureButton = document.getElementById("captureGeoButton");

    if (status) {
        status.textContent = message;
        status.style.color = success
            ? "var(--success)"
            : "var(--muted)";
    }

    if (captureButton) {
        captureButton.disabled = !success;
        captureButton.style.opacity = success ? "1" : ".5";
        captureButton.style.cursor = success ? "pointer" : "not-allowed";
    }
}

function requestGeoGPS() {

    window.geoCoordinates = null;

    setGeoGPSStatus("Requesting location permission...");

    if (!navigator.geolocation) {
        setGeoGPSStatus("Geolocation is not supported by this browser.");
        return;
    }

    navigator.geolocation.getCurrentPosition(

        function(position) {

            window.geoCoordinates = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy
            };

            const latitude = document.getElementById("geoLatitude");
            const longitude = document.getElementById("geoLongitude");
            const accuracy = document.getElementById("geoAccuracy");

            if (latitude) {
                latitude.textContent =
                    window.geoCoordinates.latitude.toFixed(6);
            }

            if (longitude) {
                longitude.textContent =
                    window.geoCoordinates.longitude.toFixed(6);
            }

            if (accuracy) {
                accuracy.textContent =
                    `±${Math.round(window.geoCoordinates.accuracy)} m`;
            }

            setGeoGPSStatus(
                "Location acquired successfully. You can now capture the image.",
                true
            );

            console.log("GPS coordinates:", window.geoCoordinates);

        },

        function(error) {

            console.error("GPS error:", error.code, error.message);

            if (error.code === 1) {
                setGeoGPSStatus(
                    "Location permission denied. Allow location access in browser site settings."
                );
            }

            else if (error.code === 2) {
                setGeoGPSStatus(
                    "Location unavailable. Check your device location services."
                );
            }

            else if (error.code === 3) {
                setGeoGPSStatus(
                    "Location request timed out. Click Retry GPS."
                );
            }

            else {
                setGeoGPSStatus(
                    `Unable to obtain location: ${error.message}`
                );
            }

        },

        {
            enableHighAccuracy: true,
            timeout: 30000,
            maximumAge: 0
        }
    );
}

function retryGeoGPS() {
    requestGeoGPS();
}

function captureGeoImage() {

    const video =
        document.getElementById("geoCamera");

    if (
        !video ||
        !video.videoWidth ||
        !video.videoHeight
    ) {
        alert(
            "Camera is not ready yet."
        );

        return;
    }


    const canvas =
        document.createElement("canvas");

    canvas.width =
        video.videoWidth;

    canvas.height =
        video.videoHeight;


    const context =
        canvas.getContext("2d");

    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );


    canvas.toBlob(
        function(blob) {

            if (!blob) {
                alert("The image could not be captured. Please try again.");
                return;
            }

            geoCapturedImageBlob =
                blob;

            geoCapturedAt =
                new Date();


            if (window.geoImageObjectUrl) {
                URL.revokeObjectURL(window.geoImageObjectUrl);
            }
            window.geoImageObjectUrl = URL.createObjectURL(blob);

            document
                .getElementById("capturedGeoImage")
                .src = window.geoImageObjectUrl;


            document
                .getElementById("cameraContainer")
                .style.display = "none";


            document
                .getElementById("cameraControls")
                .style.display = "none";


            document
                .getElementById("capturedImageContainer")
                .style.display = "block";


            document
                .getElementById("geoLocationDetails")
                .style.display = "block";


            if (geoCapturedAt) {

                document
                    .getElementById("geoCapturedAt")
                    .textContent =
                    geoCapturedAt.toLocaleString(
                        "en-IN",
                        {
                            dateStyle: "medium",
                            timeStyle: "medium"
                        }
                    );

            }


            /* -----------------------------------------
               STOP CAMERA
            ----------------------------------------- */

            stopGeoCamera();

        },
        "image/jpeg",
        0.90
    );
}

function retakeGeoImage() {
    if (window.geoImageObjectUrl) {
        URL.revokeObjectURL(window.geoImageObjectUrl);
        window.geoImageObjectUrl = null;
    }

    window.geoCapturedImageBlob = null;
    window.geoCapturedAt = null;
    window.geoCoordinates = null;

    const image = document.getElementById("capturedGeoImage");
    if (image) image.removeAttribute("src");

    const captured = document.getElementById("capturedImageContainer");
    const details = document.getElementById("geoLocationDetails");
    const start = document.getElementById("cameraStartArea");
    if (captured) captured.style.display = "none";
    if (details) details.style.display = "none";
    if (start) start.style.display = "block";

    ["geoLatitude", "geoLongitude", "geoAccuracy", "geoCapturedAt"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.textContent = "—";
    });

    setGeoGPSStatus("Preparing camera and requesting location…");
    startGeoCapture();
}

function stopGeoCamera() {

    if (window.geoCameraStream) {

        window.geoCameraStream
            .getTracks()
            .forEach(
                track => track.stop()
            );

        window.geoCameraStream = null;
    }

}

async function signInGeoEvidence() {

    if (!geoCapturedImageBlob) {

        alert(
            "Please capture an image first."
        );

        return;
    }


    if (!geoCoordinates) {

        alert(
            "Location data is not available."
        );

        return;
    }


    try {

        const formData =
            new FormData();


        /* -----------------------------------------
           IMAGE
        ----------------------------------------- */

        formData.append(
            "image",
            geoCapturedImageBlob,
            `geo-${Date.now()}.jpg`
        );


        /* -----------------------------------------
           LOCATION
        ----------------------------------------- */

        formData.append(
            "latitude",
            geoCoordinates.latitude
        );

        formData.append(
            "longitude",
            geoCoordinates.longitude
        );

        formData.append(
            "gps_accuracy_m",
            geoCoordinates.accuracy
        );


        /* -----------------------------------------
           CAPTURE TIME
        ----------------------------------------- */

        formData.append(
            "captured_at",
            geoCapturedAt
                ? geoCapturedAt.toISOString()
                : new Date().toISOString()
        );


        /* -----------------------------------------
           TRANSPORTER
        ----------------------------------------- */

        const sessionUser =
            JSON.parse(
                localStorage.getItem(
                    "traceveda_user"
                ) || "{}"
            );


        formData.append(
            "transporter_id",
            sessionUser.username || ""
        );


        /* -----------------------------------------
           BACKEND REQUEST
           IMPORTANT:
           FormData must NOT use JSON headers.
        ----------------------------------------- */

        const token =
            getTraceVedaToken();


        const headers = {};

        if (token) {
            headers.Authorization =
                `Bearer ${token}`;
        }


        const response =
            await fetch(
                `${TRACEVEDA_API}/api/transport/geotag`,
                {
                    method: "POST",
                    headers,
                    body: formData
                }
            );


        let data = null;

        try {
            data = await response.json();
        }
        catch (_) {
            data = null;
        }


        if (!response.ok) {

            throw new Error(
                data?.detail ||
                data?.message ||
                `HTTP ${response.status}`
            );

        }


        console.log(
            "Geo tagged evidence stored:",
            data
        );


        alert(
            "✓ Geo tagged image signed in ledger successfully."
        );


    }
    catch (error) {

        console.error(
            "Geo tagged evidence error:",
            error
        );


        alert(
            `Unable to sign geo tagged evidence: ${error.message}`
        );

    }

}

async function signInTransportLedger(type) {

    let payload = {};

    /* -----------------------------------------
       RAW BATCH → PROCESSOR
    ----------------------------------------- */

    if (type === "raw") {

        const crop = document
            .getElementById("rawCrop")
            ?.value
            .trim();

        const batchId = document
            .getElementById("rawBatchId")
            ?.value
            .trim();

        const farmName = document
            .getElementById("rawFarmName")
            ?.value
            .trim();

        const quantity = document
            .getElementById("rawQuantity")
            ?.value
            .trim();

        const destination = document
            .getElementById("rawDestination")
            ?.value
            .trim();

        const transportDate = document
            .getElementById("rawTransportDate")
            ?.value;

        if (
            !crop ||
            !batchId ||
            !farmName ||
            !quantity ||
            !destination ||
            !transportDate
        ) {
            alert("Please complete all transport fields.");
            return;
        }

        payload = {
            transport_stage: "RAW_BATCH_TO_PROCESSOR",
            crop_name: crop,
            batch_id: batchId,
            farm_name: farmName,
            quantity: quantity,
            destination: destination,
            date_of_transport: transportDate
        };
    }

    /* -----------------------------------------
       LAB → MANUFACTURER
    ----------------------------------------- */

    else if (type === "lab") {

        const processedBatchId = document
            .getElementById("processedBatchId")
            ?.value
            .trim();

        const manufacturer = document
            .getElementById("manufacturerOrganization")
            ?.value
            .trim();

        const quantity = document
            .getElementById("labManufacturerQuantity")
            ?.value
            .trim();

        const transportDate = document
            .getElementById("transportDate")
            ?.value;

        if (
            !processedBatchId ||
            !manufacturer ||
            !quantity ||
            !transportDate
        ) {
            alert("Please complete all transport fields.");
            return;
        }

        payload = {
            transport_stage: "LAB_TO_MANUFACTURER",
            batch_id: processedBatchId,
            manufacturer_organization: manufacturer,
            quantity: quantity,
            date_of_transport: transportDate
        };
    }

    try {

        const data = await apiRequest("/api/transport", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        console.log("Transport ledger record created:", data);

        alert("✓ Transport record signed in ledger successfully.");

    } catch (error) {

        console.error(
            "Transport ledger submission error:",
            error
        );

        alert(
            `Unable to sign transport record in ledger: ${error.message}`
        );
    }
}
