/* Browser QR scanner. html5-qrcode supports Windows desktop browsers as well
   as mobile cameras. It is loaded only when a consumer chooses to scan. */
let traceVedaQrScanner = null;
let traceVedaQrScanInProgress = false;
let traceVedaQrHandledResult = false;

function setConsumerScannerMessage(message, isError = false) {
    const node = document.getElementById("consumerScannerMessage");
    if (!node) return;
    node.textContent = message || "";
    node.style.color = isError ? "var(--danger, #b42318)" : "var(--muted)";
}

function loadHtml5QrCodeLibrary() {
    if (window.Html5Qrcode) return Promise.resolve();
    if (window.__tracevedaQrLibraryPromise) return window.__tracevedaQrLibraryPromise;

    const sources = [
        "https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js",
        "https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8/html5-qrcode.min.js",
        "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"
    ];

    const loadPromise = (async () => {
        let lastError;
        for (const src of sources) {
            try {
                await new Promise((resolve, reject) => {
                    const script = document.createElement("script");
                    script.src = src;
                    script.async = true;
                    script.onload = () => window.Html5Qrcode ? resolve() : reject(new Error("QR scanner library did not initialise."));
                    script.onerror = () => {
                        script.remove();
                        reject(new Error(`Could not load ${src}`));
                    };
                    document.head.appendChild(script);
                });
                return;
            } catch (error) {
                lastError = error;
            }
        }
        throw new Error(`QR scanner could not be loaded. Check your internet connection and try again. ${lastError?.message || ""}`);
    })();

    window.__tracevedaQrLibraryPromise = loadPromise.catch(error => {
        window.__tracevedaQrLibraryPromise = null;
        throw error;
    });
    return window.__tracevedaQrLibraryPromise;
}

function extractTraceVedaQrId(decodedValue) {
    const raw = String(decodedValue || "").trim();
    if (!raw) return "";

    // Also accept future QR labels that encode a URL containing qr_id or
    // finish with /verify/QR-....; the current manufacturer label encodes QR-....
    try {
        const parsed = new URL(raw);
        const fromQuery = parsed.searchParams.get("qr_id") || parsed.searchParams.get("qrId");
        if (fromQuery) return fromQuery.trim();
        const pathMatch = parsed.pathname.match(/(?:verify|medicine)\/(QR-[A-Z0-9-]+)/i);
        if (pathMatch) return pathMatch[1].toUpperCase();
    } catch (_) { /* The QR value is a plain ID, not a URL. */ }

    const match = raw.match(/\bQR-[A-Z0-9]+(?:-[A-Z0-9]+)*\b/i);
    return match ? match[0].toUpperCase() : raw;
}

async function acceptScannedMedicineQr(decodedValue) {
    const qrId = extractTraceVedaQrId(decodedValue);
    if (!qrId) {
        setConsumerScannerMessage("No QR ID was detected. Try positioning the code inside the camera frame.", true);
        return;
    }

    const input = document.getElementById("consumerBatch");
    if (input) input.value = qrId;
    setConsumerScannerMessage(`QR detected: ${qrId}. Verifying medicine…`);
    await stopConsumerQrScanner();
    await verifyMedicine();
}

async function startConsumerQrScanner() {
    if (traceVedaQrScanInProgress) return;
    const reader = document.getElementById("consumerQrReader");
    const startButton = document.getElementById("consumerStartScanButton");
    const stopButton = document.getElementById("consumerStopScanButton");

    if (!reader) return;
    if (!window.isSecureContext) {
        setConsumerScannerMessage("Camera access requires HTTPS or localhost. Open TraceVeda at http://localhost:5173 or use HTTPS.", true);
        return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
        setConsumerScannerMessage("This browser does not provide camera access. Enter the QR ID manually or upload a QR image.", true);
        return;
    }

    traceVedaQrScanInProgress = true;
    if (startButton) startButton.disabled = true;
    setConsumerScannerMessage("Loading QR scanner and requesting camera permission…");
    reader.style.display = "block";

    try {
        await loadHtml5QrCodeLibrary();
        traceVedaQrHandledResult = false;
        const cameras = await Html5Qrcode.getCameras();
        const preferredCamera = cameras.find(camera => /back|rear|environment/i.test(camera.label || "")) || cameras[0];
        traceVedaQrScanner = new Html5Qrcode("consumerQrReader", { verbose: false });
        await traceVedaQrScanner.start(
            preferredCamera?.id || { facingMode: "environment" },
            {
                fps: 10,
                qrbox: (viewWidth, viewHeight) => {
                    const size = Math.max(180, Math.min(280, Math.floor(Math.min(viewWidth, viewHeight) * 0.72)));
                    return { width: size, height: size };
                },
                aspectRatio: 1
            },
            decodedText => {
                if (traceVedaQrHandledResult) return;
                traceVedaQrHandledResult = true;
                acceptScannedMedicineQr(decodedText);
            },
            () => { /* Per-frame decode misses are expected; keep scanning. */ }
        );
        if (stopButton) stopButton.style.display = "inline-flex";
        setConsumerScannerMessage("Camera active. Hold the medicine QR code steady inside the square.");
    } catch (error) {
        console.error("Unable to start QR scanner:", error);
        if (reader) reader.style.display = "none";
        if (traceVedaQrScanner) {
            try { await traceVedaQrScanner.clear(); } catch (_) { /* no-op */ }
            traceVedaQrScanner = null;
        }
        setConsumerScannerMessage(`Could not start the camera: ${error.message}. Check browser camera permission or upload a QR image instead.`, true);
    } finally {
        traceVedaQrScanInProgress = false;
        if (startButton && !traceVedaQrScanner?.isScanning) startButton.disabled = false;
    }
}

async function stopConsumerQrScanner() {
    const reader = document.getElementById("consumerQrReader");
    const stopButton = document.getElementById("consumerStopScanButton");
    const startButton = document.getElementById("consumerStartScanButton");
    if (traceVedaQrScanner) {
        try {
            if (traceVedaQrScanner.isScanning) await traceVedaQrScanner.stop();
        } catch (error) {
            console.warn("QR scanner stop warning:", error);
        }
        try { await traceVedaQrScanner.clear(); } catch (_) { /* no-op */ }
        traceVedaQrScanner = null;
    }
    if (reader) {
        reader.style.display = "none";
        reader.innerHTML = "";
    }
    if (stopButton) stopButton.style.display = "none";
    if (startButton) startButton.disabled = false;
}

async function scanConsumerQrImage(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    setConsumerScannerMessage("Reading QR code from the selected image…");

    try {
        await loadHtml5QrCodeLibrary();
        const reader = document.getElementById("consumerQrReader");
        reader.style.display = "none";
        const imageScanner = new Html5Qrcode("consumerQrReader", { verbose: false });
        const decodedText = await imageScanner.scanFile(file, true);
        try { await imageScanner.clear(); } catch (_) { /* no-op */ }
        await acceptScannedMedicineQr(decodedText);
    } catch (error) {
        console.error("QR image scan failed:", error);
        setConsumerScannerMessage(`Could not read a QR code from that image: ${error.message}`, true);
    } finally {
        event.target.value = "";
    }
}

/* Public medicine verification and consumer issue reporting. */
async function verifyMedicine() {
    const input = document.getElementById("consumerBatch");
    const button = document.getElementById("consumerVerifyButton");
    const result = document.getElementById("consumerResult");
    const qrId = input?.value?.trim();

    const setText = (id, value) => {
        const node = document.getElementById(id);
        if (node) node.textContent = value ?? "—";
    };

    const showResult = () => {
        if (result) {
            result.style.display = "block";
            result.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    };

    if (!qrId) {
        alert("Enter the QR ID printed on the medicine pack.");
        input?.focus();
        return;
    }

    if (result) result.style.display = "none";
    sessionStorage.removeItem("traceveda_qr_id");
    localStorage.removeItem("traceveda_qr_id");

    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking…';
    }

    try {
        // This endpoint is public by design: consumers do not need an account.
        const data = await apiRequest(`/api/verify/${encodeURIComponent(qrId)}`, {
            method: "GET"
        });

        const verified = data?.verified === true || data?.verified === 1 || data?.verified === "true";
        const medicineBatchId = data?.medicine_batch_id || data?.batch_id || data?.medicine_batch?.batch_id || "—";
        const productName = data?.product_name || data?.medicine_name || data?.medicine_batch?.product_name || "Not available in verification response";
        const batchStatus = data?.batch_status || data?.medicine_batch?.batch_status || "Not provided";

        const icon = document.getElementById("consumerVerdictIcon");
        if (icon) {
            icon.style.background = verified ? "var(--success-bg)" : "var(--danger-bg, #fde8e8)";
            icon.style.color = verified ? "var(--success)" : "var(--danger, #b42318)";
            icon.innerHTML = verified
                ? '<i class="fa-solid fa-check"></i>'
                : '<i class="fa-solid fa-xmark"></i>';
        }

        setText("consumerVerdictTitle", verified ? "Medicine Verified" : "Medicine Not Verified");
        setText("consumerVerdictMessage", verified
            ? (data?.message || "This QR ID matches a medicine record in TraceVeda.")
            : (data?.message || "This QR ID could not be matched to a verified medicine record. Do not rely on this product until it has been checked by a pharmacist."));
        setText("consumerVerifiedQr", data?.qr_id || qrId);
        setText("verifiedBatch", medicineBatchId);
        setText("consumerProductName", verified ? productName : "—");
        setText("consumerBatchStatus", verified ? batchStatus : "Not verified");
        setText("consumerVerificationStatus", verified ? "Verified" : "Not verified");
        setText("consumerBlockchainStatus", data?.blockchain_status || data?.blockchain_verification || "Not provided by verification response");

        const errorBox = document.getElementById("consumerVerifyError");
        if (errorBox) {
            errorBox.style.display = "none";
            errorBox.textContent = "";
        }

        if (verified) {
            sessionStorage.setItem("traceveda_qr_id", data?.qr_id || qrId);
            if (medicineBatchId !== "—") {
                const reportBatch = document.getElementById("consumerReportBatch");
                if (reportBatch) reportBatch.value = medicineBatchId;
            }
        }

        showResult();
    } catch (error) {
        const icon = document.getElementById("consumerVerdictIcon");
        if (icon) {
            icon.style.background = "var(--danger-bg, #fde8e8)";
            icon.style.color = "var(--danger, #b42318)";
            icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
        }
        setText("consumerVerdictTitle", "Verification service unavailable");
        setText("consumerVerdictMessage", "TraceVeda could not complete this verification. Check that the backend is running, then try again.");
        setText("consumerVerifiedQr", qrId);
        setText("verifiedBatch", "—");
        setText("consumerProductName", "—");
        setText("consumerBatchStatus", "—");
        setText("consumerVerificationStatus", "Unavailable");
        setText("consumerBlockchainStatus", "Not checked");

        const errorBox = document.getElementById("consumerVerifyError");
        if (errorBox) {
            errorBox.style.display = "block";
            errorBox.textContent = `Verification error: ${error.message}`;
        }
        showResult();
        console.error("Medicine verification failed:", error);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = "Verify";
        }
    }
}

async function submitConsumerReport(event) {
    event?.preventDefault();

    const batch = document
        .getElementById("consumerReportBatch")
        ?.value
        .trim();

    const description = document
        .getElementById("consumerReportDescription")
        ?.value
        .trim();

    const issueType = document
        .getElementById("consumerIssueType")
        ?.value
        .trim();

    const symptoms = document
        .getElementById("consumerSymptoms")
        ?.value
        .trim();

    const message = document.getElementById("consumerReportMessage");

    /*
     * QR ID must belong to the medicine batch.
     *
     * First try sessionStorage, then localStorage.
     * The QR verification code should save the scanned QR ID here.
     */
    const qrId =
        sessionStorage.getItem("traceveda_qr_id") ||
        localStorage.getItem("traceveda_qr_id");

    if (!batch || !issueType || !symptoms || !description) {
        if (message) {
            message.className = "auth-message error";
            message.textContent = "Please complete all fields.";
        }
        return;
    }

    if (!qrId) {
        if (message) {
            message.className = "auth-message error";
            message.textContent =
                "Please verify the medicine QR code before submitting a report.";
        }
        return;
    }

    try {
        await apiRequest("/api/consumer/reports", {
            method: "POST",

            body: JSON.stringify({
                medicine_batch_id: batch,
                qr_id: qrId,
                reported_at: new Date().toISOString(),
                issue_type: issueType,
                symptoms: symptoms,
                description: description,
                is_synthetic: false
            })
        });

        if (message) {
            message.className = "auth-message success";
            message.textContent =
                "Your medicine report has been submitted successfully.";
        }

        document.getElementById("consumerReportForm")?.reset();

    } catch (error) {

        if (message) {
            message.className = "auth-message error";
            message.textContent =
                `Report submission failed: ${error.message}`;
        }

    }
}
