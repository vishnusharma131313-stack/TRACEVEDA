/* Manufacturer batch creation, product registration and QR workflows. */
function updateManufacturerBatchFormats() {

    const batchFormat =
        document.getElementById("mfgBatchFormat");

    const sourceFormat =
        document.getElementById("mfgSourceFormat");

    const qrFormat =
        document.getElementById("mfgQrIdFormat");


    if (!batchFormat || !sourceFormat || !qrFormat) {
        return;
    }


    batchFormat.textContent =
        "Format: MED-YYYY-NNN";

    sourceFormat.textContent =
        "Format: CROP-P-YYYY-NNN";

    qrFormat.textContent =
        "Format: QR-Year-NNN";


    batchFormat.style.display = "inline";

    sourceFormat.style.display = "inline";

    qrFormat.style.display = "inline";

}

function addProcessingBatch() {

    const batchList =
        document.getElementById("processingBatchList");

    if (!batchList) {
        return;
    }

    const batchRows =
        batchList.querySelectorAll(".processing-batch-row");

    const nextNumber = batchRows.length + 1;

    const row =
        document.createElement("div");

    row.className = "processing-batch-row";

    row.style.marginTop = "8px";

    row.innerHTML = `
        <input
            class="input mono processing-batch-input"
            id="mfgSource_${nextNumber}"
            placeholder="Enter processing batch ID"
            required
        >
    `;

    batchList.appendChild(row);
}

function removeProcessingBatch() {

    const batchList =
        document.getElementById("processingBatchList");

    if (!batchList) {
        return;
    }

    const rows =
        batchList.querySelectorAll(".processing-batch-row");

    /* Keep at least one batch field */
    if (rows.length <= 1) {
        alert("At least one source processing batch is required.");
        return;
    }

    /* Build list of existing batches */
    let message =
        "Select the processing batch to remove:\n\n";

    rows.forEach((row, index) => {

        const input =
            row.querySelector(".processing-batch-input");

        const value =
            input && input.value.trim()
                ? input.value.trim()
                : "Empty batch field";

        message += `${index + 1}. ${value}\n`;
    });

    /* Ask user which batch to remove */
    const selection =
        prompt(message + "\nEnter the batch number:");

    if (selection === null) {
        return;
    }

    const selectedIndex =
        parseInt(selection, 10) - 1;

    /* Validate selection */
    if (
        Number.isNaN(selectedIndex) ||
        selectedIndex < 0 ||
        selectedIndex >= rows.length
    ) {
        alert("Invalid batch selection.");
        return;
    }

    /* Remove selected row */
    rows[selectedIndex].remove();
}

function submitManufacturer(){

    /*
    ===============================================================================
    BACKEND REQUIREMENT — MANUFACTURER MEDICINE BATCH REGISTRATION
    ===============================================================================

    When the Manufacturer submits the "Formulate & Register Batch" form, the
    backend must handle the submitted data across TWO datasets:

    1. medicine_batches.csv
    2. batch_relationships.csv


    -------------------------------------------------------------------------------
    1. medicine_batches.csv
    -------------------------------------------------------------------------------

    EVERY FIELD FROM THE MANUFACTURER FORM EXCEPT "Source Processing Batch"
    must be appended to medicine_batches.csv.

    Fields to store:

        medicine_batch_id
        product_name
        manufacturer_id
        manufacturing_date
        manufacturing_timestamp
        expiry_date
        qr_id
        batch_status

    The "Source Processing Batch" field MUST NOT be stored in
    medicine_batches.csv because a medicine batch can be created from MULTIPLE
    processing batches.


    -------------------------------------------------------------------------------
    2. batch_relationships.csv
    -------------------------------------------------------------------------------

    All Source Processing Batch IDs entered for the medicine batch must be stored
    as relationships in batch_relationships.csv.

    One medicine batch may have multiple processing batches.

    Example frontend submission:

        medicine_batch_id:
            MED-2026-010

        source_processing_batches:
            [
                "ASH-P-2026-001",
                "TUL-P-2026-003",
                "NIM-P-2026-005"
            ]


    The backend must create ONE PROCESSING_TO_MEDICINE relationship for EACH
    processing batch:

        REL-M-XXXX
        parent_batch_id = ASH-P-2026-001
        child_batch_id  = MED-2026-010
        relationship_type = PROCESSING_TO_MEDICINE

        REL-M-XXXX
        parent_batch_id = TUL-P-2026-003
        child_batch_id  = MED-2026-010
        relationship_type = PROCESSING_TO_MEDICINE

        REL-M-XXXX
        parent_batch_id = NIM-P-2026-005
        child_batch_id  = MED-2026-010
        relationship_type = PROCESSING_TO_MEDICINE


    -------------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------------

    DO NOT store multiple processing batch IDs in a single field such as:

        "ASH-P-2026-001,TUL-P-2026-003,NIM-P-2026-005"

    Instead, create separate rows in batch_relationships.csv.

    Therefore, the relationship is:

        Processing Batch 1 ──┐
        Processing Batch 2 ──┼──> Medicine Batch
        Processing Batch 3 ──┘


    -------------------------------------------------------------------------------
    FRONTEND PAYLOAD
    -------------------------------------------------------------------------------

    The frontend will send all processing batch IDs as an array.

    Expected structure:

    {
        "medicine_batch_id": "MED-2026-010",
        "source_processing_batches": [
            "ASH-P-2026-001",
            "TUL-P-2026-003",
            "NIM-P-2026-005"
        ],
        "product_name": "...",
        "manufacturer_id": "MAN-001",
        "manufacturing_date": "2026-06-15",
        "manufacturing_timestamp": "...",
        "expiry_date": "2028-06-14",
        "qr_id": "QR-2026-010",
        "batch_status": "MONITORED"
    }


    -------------------------------------------------------------------------------
    BACKEND RESPONSIBILITY
    -------------------------------------------------------------------------------

    On successful submission:

        1. Append ONE medicine-batch record to medicine_batches.csv.
        2. Create ONE batch_relationships.csv record for EACH source processing
        batch.
        3. Ensure all relationship rows use:
            relationship_type = PROCESSING_TO_MEDICINE
        4. Generate a unique relationship_id for every relationship row.
        5. Keep the same medicine_batch_id as child_batch_id in every relationship.
        6. The complete operation should be treated as one logical registration
        so that the medicine record and its relationships remain consistent.

    ===============================================================================
    */

    /* ==========================================
       GET FORM VALUES
    ========================================== */

    const batch =
        document.getElementById("mfgBatch").value.trim();

    const sourceBatches =
        Array.from(
            document.querySelectorAll(".processing-batch-input")
        )
        .map(input => input.value.trim())
        .filter(value => value !== "");

    const product =
        document.getElementById("mfgProduct").value.trim();

    const manufacturingDate =
        document.getElementById("mfgManufacturingDate").value;

    const expiryDate =
        document.getElementById("mfgExpiryDate").value;

    const qrId =
        document.getElementById("mfgQrId").value.trim();


    /* ==========================================
       BASIC VALIDATION
    ========================================== */

    if (!batch) {
        alert("Please enter the medicine batch ID.");
        return;
    }

    if (sourceBatches.length === 0) {
        alert("Please enter at least one source processing batch.");
        return;
    }

    if (!product) {
        alert("Please enter the product name.");
        return;
    }

    if (!manufacturingDate) {
        alert("Please select the manufacturing date.");
        return;
    }

    if (!expiryDate) {
        alert("Please select the expiry date.");
        return;
    }

    if (!qrId) {
        alert("Please enter the QR ID.");
        return;
    }


    /* ==========================================
       GET HISTORY TABLE
    ========================================== */

    const table =
        document.getElementById("mfgHistory");

    if (!table) {
        return;
    }


    /* ==========================================
       CREATE NEW ROW
    ========================================== */

    const row =
        document.createElement("tr");


    /* ==========================================
       FORMAT DATES
    ========================================== */

    const formattedManufacturingDate =
        new Date(
            manufacturingDate + "T00:00:00"
        ).toLocaleDateString(
            "en-GB",
            {
                day: "2-digit",
                month: "long",
                year: "numeric"
            }
        );

    const formattedExpiryDate =
        new Date(
            expiryDate + "T00:00:00"
        ).toLocaleDateString(
            "en-GB",
            {
                day: "2-digit",
                month: "long",
                year: "numeric"
            }
        );


    /* ==========================================
       DISPLAY MULTIPLE PROCESSING BATCHES
    ========================================== */

    const sourceBatchDisplay =
        sourceBatches
            .map(batchId => `${batchId}<br>`)
            .join("");


    /* ==========================================
       BUILD TABLE ROW
    ========================================== */

    row.innerHTML = `

        <td class="mono">
            ${batch}
        </td>


        <td class="mono">
            ${sourceBatchDisplay}
        </td>


        <td>
            ${product}
        </td>


        <td>
            ${formattedManufacturingDate}
        </td>


        <td>
            ${formattedExpiryDate}
        </td>


        <td class="mono">
            ${qrId}
        </td>

    `;


    table.appendChild(row);


    /* ==========================================
       SUCCESS MESSAGE
    ========================================== */

    alert(
        "Medicine batch registered successfully."
    );
}

/* =========================================================
   MEDICINE QR ID GENERATION
========================================================= */

async function loadMedicineBatchesForQR(selectedBatchId = "") {
    const select = document.getElementById("qrMedicineBatch");
    if (!select) return;

    select.innerHTML = '<option value="">Loading medicine batches…</option>';

    try {
        const data = await apiRequest("/api/medicine", { method: "GET" });
        const batches = Array.isArray(data) ? data : (data?.batches || data?.medicines || []);

        select.innerHTML = '<option value="">Select registered medicine batch</option>';
        batches.forEach(batch => {
            const batchId = batch.medicine_batch_id || batch.batch_id;
            if (!batchId) return;
            const option = document.createElement("option");
            option.value = batchId;
            option.textContent = `${batchId}${batch.product_name ? ` — ${batch.product_name}` : ""}`;
            select.appendChild(option);
        });

        if (!batches.length) {
            select.innerHTML = '<option value="">No registered medicine batches found</option>';
        }

        if (selectedBatchId) select.value = selectedBatchId;
        select.dataset.loaded = "true";
    } catch (error) {
        console.error("Medicine batch loading failed:", error);
        select.innerHTML = '<option value="">Unable to load medicine batches</option>';
        showMedicineQRMessage("Unable to load registered medicine batches: " + error.message, "error");
    }
}

/* =========================================================
   HANDLE MEDICINE BATCH SELECTION
========================================================= */

async function handleMedicineQRSelection() {
    const batchId = document.getElementById("qrMedicineBatch")?.value;
    const button = document.getElementById("generateMedicineQRButton");
    const result = document.getElementById("medicineQRResult");

    if (result) result.style.display = "none";
    if (!batchId) {
        if (button) button.disabled = true;
        return;
    }

    if (button) button.disabled = false;
    showMedicineQRMessage("Loading the QR code assigned during medicine registration…", "info");

    try {
        const data = await apiRequest(
            `/api/medicine/${encodeURIComponent(batchId)}/qr`,
            { method: "GET" }
        );

        if (!data?.qr_id || !data?.qr_code_data_url) {
            throw new Error("The backend did not return the saved QR ID and image.");
        }
        displayMedicineQR(data);
        showMedicineQRMessage("Saved QR code loaded. Download it and print it on the medicine pack.", "success");
    } catch (error) {
        console.error("QR lookup failed:", error);
        showMedicineQRMessage("Unable to load this batch's QR code: " + error.message, "error");
    }
}


/* =========================================================
   LOAD / REFRESH AN EXISTING MEDICINE QR
========================================================= */

async function generateMedicineQR() {
    // QR IDs are assigned by POST /api/medicine at registration time.
    // This button retrieves that existing ID; it never invents a second one.
    await handleMedicineQRSelection();
}

/* =========================================================
   DISPLAY QR CODE
========================================================= */

function displayMedicineQR(data) {

    const result =
        document.getElementById("medicineQRResult");

    const image =
        document.getElementById("medicineQRCodeImage");

    const batchDisplay =
        document.getElementById("qrMedicineBatchDisplay");

    const qrDisplay =
        document.getElementById("medicineQRIdDisplay");
    const download =
        document.getElementById("medicineQRDownload");

    const imageSource =
        data.qr_code_data_url || data.qr_code_url;

    if (!imageSource) {

        throw new Error(
            "QR ID was returned, but no QR image was provided by the backend."
        );

    }

    image.src = imageSource;
    if (download) {
        download.href = imageSource;
        download.download = `${data.qr_id || "TraceVeda"}.svg`;
        download.style.display = "inline-flex";
    }

    batchDisplay.textContent =
        "Medicine Batch: " +
        (data.medicine_batch_id || "");

    qrDisplay.textContent =
        "QR ID: " + data.qr_id;

    result.style.display = "block";

}


/* =========================================================
   QR STATUS MESSAGE
========================================================= */

function showMedicineQRMessage(message, type = "info") {

    const box =
        document.getElementById("medicineQRMessage");

    if (!box) return;

    box.style.display = "block";
    box.textContent = message;

    if (type === "success") {
        box.style.color = "var(--success)";
    }

    else if (type === "error") {
        box.style.color = "var(--danger)";
    }

    else {
        box.style.color = "var(--muted)";
    }

}



/* Load the latest telemetry for the storage node currently selected. */
async function selectStorageNode() {
    const selector = document.getElementById("storageSelection");
    if (!selector) return;

    const storageId = selector.value;
    const fields = {
        temperature: document.getElementById("storageTemperature"),
        humidity: document.getElementById("storageHumidity"),
        weight: document.getElementById("storageWeight"),
        light: document.getElementById("storageLight"),
        limitSwitch: document.getElementById("storageLimitSwitch")
    };
    const statuses = {
        temperature: document.getElementById("storageTemperatureStatus"),
        humidity: document.getElementById("storageHumidityStatus"),
        weight: document.getElementById("storageWeightStatus"),
        light: document.getElementById("storageLightStatus"),
        limitSwitch: document.getElementById("storageLimitSwitchStatus")
    };

    const setStatus = (element, message, state = "info") => {
        if (!element) return;
        element.textContent = message;
        element.dataset.state = state;
    };
    const setValue = (element, value, suffix = "") => {
        if (!element) return;
        element.textContent = value === null || value === undefined || value === ""
            ? `--${suffix}`
            : `${value}${suffix}`;
    };

    Object.values(fields).forEach(element => setValue(element, null));
    Object.values(statuses).forEach(element => setStatus(element, `Loading ${storageId}…`, "loading"));
    selector.disabled = true;

    try {
        const response = await apiRequest(`/api/storage/readings/${encodeURIComponent(storageId)}`, {
            method: "GET"
        });
        // Support the documented { readings: {...} } response and APIs that
        // return the reading directly or wrap it in a one-element array.
        const payload = response?.readings ?? response?.reading ?? response?.data ?? response;
        const reading = Array.isArray(payload) ? payload[payload.length - 1] : payload;
        if (!reading || typeof reading !== "object") {
            throw new Error(`No telemetry was returned for ${storageId}.`);
        }

        const pick = (...keys) => {
            for (const key of keys) {
                if (reading[key] !== undefined && reading[key] !== null) return reading[key];
            }
            return null;
        };
        const weight = pick("weight", "weight_kg", "load_kg", "hx711_weight");
        const light = pick("light", "light_lux", "light_intensity_lux", "lux", "bh1750_lux");
        const limitSwitch = pick("limit_switch", "switch_status", "seal_status");
        const temperature = pick("temperature", "temperature_c", "temp_c", "dht22_temperature");
        const humidity = pick("humidity", "humidity_percent", "humidity_pct", "dht22_humidity");
        const timestamp = pick("timestamp", "recorded_at", "created_at", "datetime");

        setValue(fields.weight, weight, " kg");
        setValue(fields.light, light, " lx");
        setValue(fields.temperature, temperature, " °C");
        setValue(fields.humidity, humidity, " %");
        setValue(fields.limitSwitch, limitSwitch);

        const updated = timestamp ? `Updated ${timestamp}` : `Latest reading for ${storageId}`;
        setStatus(statuses.weight, weight === null ? "Weight unavailable" : updated, weight === null ? "warning" : "success");
        setStatus(statuses.light, light === null ? "Light reading unavailable" : updated, light === null ? "warning" : "success");
        setStatus(statuses.limitSwitch, limitSwitch === null ? "Seal status unavailable" : updated, limitSwitch === null ? "warning" : "success");
        setStatus(statuses.temperature, temperature === null ? "Temperature not provided by backend" : updated, temperature === null ? "muted" : "success");
        setStatus(statuses.humidity, humidity === null ? "Humidity not provided by backend" : updated, humidity === null ? "muted" : "success");
    } catch (error) {
        console.error(`Failed to load telemetry for ${storageId}:`, error);
        Object.values(statuses).forEach(element => setStatus(element, `Unable to load: ${error.message}`, "error"));
    } finally {
        selector.disabled = false;
    }
}

/* Backend-backed medicine registration. The backend creates the paired QR ID
   and QR image as part of the same medicine registration transaction. */
submitManufacturer = async function () {
    const batch = document.getElementById("mfgBatch")?.value.trim().toUpperCase();
    const source = document.getElementById("mfgSource")?.value.trim();
    const product = document.getElementById("mfgProduct")?.value.trim();
    const manufacturingDate = document.getElementById("mfgManufacturingDate")?.value;
    const expiryDate = document.getElementById("mfgExpiryDate")?.value;

    if (!batch || !source || !product || !manufacturingDate || !expiryDate) {
        return alert("Please complete the batch ID, source processing batch, product name, manufacturing date and expiry date.");
    }

    const sessionUser = (() => {
        try { return JSON.parse(localStorage.getItem("traceveda_user") || "{}"); }
        catch (_) { return {}; }
    })();
    const manufacturerId = sessionUser.organisation_id || sessionUser.username;
    if (!manufacturerId) return alert("Your manufacturer session could not be identified. Sign in again.");

    const submitButton = document.querySelector('#manufacturer-workspace button[onclick="submitManufacturer()"]');
    const originalButtonHtml = submitButton?.innerHTML;
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Registering medicine…';
    }

    try {
        const data = await apiRequest("/api/medicine", {
            method: "POST",
            body: JSON.stringify({
                medicine_batch_id: batch,
                processing_batch_id: source,
                manufacturer_id: manufacturerId,
                product_name: product,
                manufacturing_date: manufacturingDate,
                expiry_date: expiryDate
            })
        });

        if (!data?.medicine_batch_id || !data?.qr_id || !data?.qr_code_data_url) {
            throw new Error("Medicine was registered but the backend did not return its QR label. Refresh the QR panel to retrieve it.");
        }

        const table = document.getElementById("mfgHistory");
        if (table) {
            const row = document.createElement("tr");
            [
                data.medicine_batch_id,
                source,
                product,
                manufacturingDate,
                expiryDate,
                data.qr_id
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                if (String(value).startsWith("MED-") || String(value).startsWith("QR-")) cell.className = "mono";
                row.appendChild(cell);
            });
            table.prepend(row);
        }

        // Populate the retrieval panel with the just-created batch and its QR.
        await loadMedicineBatchesForQR(data.medicine_batch_id);
        if (typeof switchPanel === "function") {
            switchPanel("manufacturer-qr");
        } else {
            displayMedicineQR(data);
        }

        alert(`Medicine registered successfully.\nMedicine Batch: ${data.medicine_batch_id}\nQR ID: ${data.qr_id}\nThe QR label is now ready to download and print.`);
        document.getElementById("mfgBatch")?.value && (document.getElementById("mfgBatch").value = "");
        document.getElementById("mfgSource")?.value && (document.getElementById("mfgSource").value = "");
        document.getElementById("mfgProduct")?.value && (document.getElementById("mfgProduct").value = "");
    } catch (error) {
        console.error("Medicine registration failed:", error);
        alert(`Medicine registration failed: ${error.message}`);
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonHtml || '<i class="fa-solid fa-plus"></i> Formulate & Register Batch';
        }
    }
};
