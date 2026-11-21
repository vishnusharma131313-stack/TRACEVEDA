/* Laboratory certification workflow backed by POST /api/lab/tests.
 * Optional PDF reports are submitted in the same multipart request and stored
 * by the backend in MongoDB GridFS.
 */
const MAX_LAB_REPORT_BYTES = 10 * 1024 * 1024;

function updateLabFieldFormats() {
    const phase = document.getElementById("labTestPhase")?.value;
    const batchFormat = document.getElementById("labBatchFormat");
    const certFormat = document.getElementById("labCertFormat");
    const batchInput = document.getElementById("labBatch");
    const certInput = document.getElementById("labCert");
    if (!batchFormat || !certFormat || !batchInput || !certInput) return;

    const formats = {
        RAW_BATCH_TEST: {
            batch: "Format: CROP-YYYY-NNN",
            certificate: "Format: CERT-PRE-NNNN",
            batchPlaceholder: "Example: ASH-2026-001",
            certificatePlaceholder: "Example: CERT-PRE-0001"
        },
        FINAL_PRODUCT_QUALITY_TEST: {
            batch: "Format: MED-YYYY-NNN",
            certificate: "Format: CERT-POST-NNNN",
            batchPlaceholder: "Example: MED-2026-001",
            certificatePlaceholder: "Example: CERT-POST-0001"
        }
    };
    const selected = formats[phase];
    [batchFormat, certFormat].forEach(element => {
        element.style.display = selected ? "inline" : "none";
    });
    batchFormat.textContent = selected?.batch || "";
    certFormat.textContent = selected?.certificate || "";
    batchInput.placeholder = selected?.batchPlaceholder || "Select a test phase first";
    certInput.placeholder = selected?.certificatePlaceholder || "Enter certificate ID";
}

function updateLabReportFileName() {
    const reportInput = document.getElementById("labReport");
    const display = document.getElementById("labReportFileName");
    if (!reportInput || !display) return;

    const file = reportInput.files?.[0];
    if (!file) {
        display.textContent = "Optional PDF. Reports are stored securely in TraceVeda and can be downloaded from verification history. Maximum size: 10 MB.";
        return;
    }

    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
    display.textContent = `${file.name} · ${sizeMb} MB selected`;
}

async function downloadLabReport(labTestId, filename) {
    const baseUrl = window.TRACEVEDA_CONFIG?.API_BASE_URL;
    const token = localStorage.getItem("traceveda_token");
    if (!baseUrl || !token) {
        alert("Your TraceVeda session is missing. Sign in again and retry.");
        return;
    }

    const button = document.querySelector(`[data-lab-report-id="${CSS.escape(labTestId)}"]`);
    const originalText = button?.textContent;
    if (button) {
        button.disabled = true;
        button.textContent = "Downloading…";
    }

    try {
        const response = await fetch(
            `${baseUrl.replace(/\/$/, "")}/api/lab/tests/${encodeURIComponent(labTestId)}/report`,
            { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok) {
            let detail = `Report download failed (${response.status})`;
            try {
                const body = await response.json();
                detail = body.detail || detail;
            } catch (_) { /* response was not JSON */ }
            if (response.status === 401) {
                localStorage.removeItem("traceveda_token");
                localStorage.removeItem("traceveda_user");
            }
            throw new Error(detail);
        }

        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = filename || "lab-report.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) {
        console.error("Laboratory report download failed:", error);
        alert(`Unable to download laboratory report: ${error.message}`);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = originalText || "Download PDF";
        }
    }
}

function addLabHistoryRow(record) {
    const table = document.getElementById("labHistory");
    if (!table) return;
    const row = document.createElement("tr");
    const phaseLabels = {
        RAW_BATCH_TEST: "Raw batch test",
        FINAL_PRODUCT_QUALITY_TEST: "Final product quality test"
    };
    const values = [
        record.test_date || "—",
        record.batch_id || "—",
        phaseLabels[record.test_phase] || record.test_stage || record.test_phase || "—",
        record.result || "—",
        record.certificate_id || "—",
        record.blockchain_tx || "—"
    ];
    values.forEach((value, index) => {
        const cell = document.createElement("td");
        if (index === 1 || index === 4 || index === 5) cell.className = "mono";
        if (index === 3) {
            const badge = document.createElement("span");
            badge.className = `badge ${String(value).toUpperCase() === "PASS" ? "badge-success" : "badge-danger"}`;
            badge.textContent = value;
            cell.appendChild(badge);
        } else {
            cell.textContent = value;
        }
        row.appendChild(cell);
    });

    const reportCell = document.createElement("td");
    if (record.report?.download_url && record.lab_test_id) {
        const downloadButton = document.createElement("button");
        downloadButton.type = "button";
        downloadButton.className = "btn btn-primary";
        downloadButton.textContent = "Download PDF";
        downloadButton.dataset.labReportId = record.lab_test_id;
        downloadButton.addEventListener("click", () => {
            downloadLabReport(record.lab_test_id, record.report.filename);
        });
        reportCell.appendChild(downloadButton);
    } else {
        reportCell.textContent = "—";
    }
    row.appendChild(reportCell);
    table.prepend(row);
}

async function loadLabHistory() {
    const table = document.getElementById("labHistory");
    if (!table || !localStorage.getItem("traceveda_token")) return;

    table.innerHTML = '<tr><td colspan="7">Loading laboratory history…</td></tr>';
    try {
        const data = await apiRequest("/api/lab/tests?limit=200", { method: "GET" });
        table.innerHTML = "";
        const tests = Array.isArray(data?.tests) ? data.tests : [];
        if (!tests.length) {
            table.innerHTML = '<tr><td colspan="7">No laboratory certifications found.</td></tr>';
            return;
        }
        // addLabHistoryRow prepends, so insert oldest first to display newest first.
        tests.slice().reverse().forEach(addLabHistoryRow);
    } catch (error) {
        console.error("Could not load laboratory history:", error);
        table.innerHTML = `<tr><td colspan="7">Unable to load laboratory history: ${error.message}</td></tr>`;
    }
}

async function submitLab() {
    const batch = document.getElementById("labBatch")?.value.trim();
    const certificateId = document.getElementById("labCert")?.value.trim();
    const testDate = document.getElementById("labTestDate")?.value;
    const testPhase = document.getElementById("labTestPhase")?.value;
    const result = document.getElementById("labVerdict")?.value;
    const reportInput = document.getElementById("labReport");
    const reportFile = reportInput?.files?.[0] || null;
    const submitButton = document.querySelector('#lab-workspace button[onclick="submitLab()"]');

    if (!batch || !certificateId || !testDate || !testPhase || !result) {
        alert("Complete the batch ID, certificate ID, test date, test phase and verdict.");
        return;
    }
    if (reportFile) {
        if (!reportFile.name.toLowerCase().endsWith(".pdf")) {
            alert("Please select a PDF report.");
            return;
        }
        if (reportFile.size > MAX_LAB_REPORT_BYTES) {
            alert("The PDF report must be 10 MB or smaller.");
            return;
        }
    }
    if (typeof apiRequest !== "function") {
        alert("The API client is unavailable. Refresh the page and sign in again.");
        return;
    }

    const testType = testPhase === "RAW_BATCH_TEST"
        ? "RAW_MATERIAL_QUALITY"
        : "FINAL_PRODUCT_QUALITY";
    const payload = {
        batch_id: batch,
        test_phase: testPhase,
        test_type: testType,
        test_date: testDate,
        certificate_id: certificateId,
        test_parameters: {},
        result
    };
    let body = JSON.stringify(payload);
    if (reportFile) {
        const formData = new FormData();
        formData.append("payload", JSON.stringify(payload));
        formData.append("report", reportFile, reportFile.name);
        body = formData;
    }

    const originalButtonHtml = submitButton?.innerHTML;
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting certification…';
    }

    try {
        const data = await apiRequest("/api/lab/tests", {
            method: "POST",
            body
        });

        if (!data?.lab_test_id || !data?.batch_id) {
            throw new Error("The backend response did not confirm a saved laboratory test.");
        }
        if (reportFile && !data.report?.download_url) {
            throw new Error("The test was accepted but the backend did not confirm PDF storage. Contact the administrator before retrying this test.");
        }

        addLabHistoryRow(data);
        const reportStatus = reportFile ? `\nPDF report stored: ${data.report.filename}` : "\nNo PDF report attached.";
        alert(`Laboratory certification saved successfully.\nLab Test ID: ${data.lab_test_id}\nBatch: ${data.batch_id}\nCertificate: ${data.certificate_id || certificateId}${reportStatus}`);

        document.getElementById("labBatch").value = "";
        document.getElementById("labCert").value = "";
        document.getElementById("labTestDate").value = "";
        document.getElementById("labTestPhase").value = "";
        document.getElementById("labVerdict").value = "PASS";
        if (reportInput) reportInput.value = "";
        updateLabReportFileName();
        updateLabFieldFormats();
    } catch (error) {
        console.error("Laboratory certification submission failed:", error);
        alert(`Unable to submit laboratory certification: ${error.message}`);
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonHtml || '<i class="fa fa-signature"></i> Sign Ledger Verification';
        }
    }
}

document.getElementById("labTestPhase")?.addEventListener("change", updateLabFieldFormats);
document.getElementById("labReport")?.addEventListener("change", updateLabReportFileName);
