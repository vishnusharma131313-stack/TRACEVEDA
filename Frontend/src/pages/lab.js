/* Laboratory certification workflow backed by POST /api/lab/tests. */
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
    table.prepend(row);
}

async function submitLab() {
    const batch = document.getElementById("labBatch")?.value.trim();
    const certificateId = document.getElementById("labCert")?.value.trim();
    const testDate = document.getElementById("labTestDate")?.value;
    const testPhase = document.getElementById("labTestPhase")?.value;
    const result = document.getElementById("labVerdict")?.value;
    const reportInput = document.getElementById("labReport");
    const submitButton = document.querySelector('#lab-workspace button[onclick="submitLab()"]');

    if (!batch || !certificateId || !testDate || !testPhase || !result) {
        alert("Complete the batch ID, certificate ID, test date, test phase and verdict.");
        return;
    }
    if (reportInput?.files?.length) {
        alert("The current backend API does not upload PDF reports yet. Remove the selected PDF and submit the certificate metadata, or retain the file separately for your records.");
        return;
    }
    if (typeof apiRequest !== "function") {
        alert("The API client is unavailable. Refresh the page and sign in again.");
        return;
    }

    const testType = testPhase === "RAW_BATCH_TEST"
        ? "RAW_MATERIAL_QUALITY"
        : "FINAL_PRODUCT_QUALITY";
    const originalButtonHtml = submitButton?.innerHTML;
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting certification…';
    }

    try {
        const data = await apiRequest("/api/lab/tests", {
            method: "POST",
            body: JSON.stringify({
                batch_id: batch,
                test_phase: testPhase,
                test_type: testType,
                test_date: testDate,
                certificate_id: certificateId,
                test_parameters: {},
                result
            })
        });

        if (!data?.lab_test_id || !data?.batch_id) {
            throw new Error("The backend response did not confirm a saved laboratory test.");
        }
        addLabHistoryRow(data);
        alert(`Laboratory certification saved successfully.\nLab Test ID: ${data.lab_test_id}\nBatch: ${data.batch_id}\nCertificate: ${data.certificate_id || certificateId}`);

        document.getElementById("labBatch").value = "";
        document.getElementById("labCert").value = "";
        document.getElementById("labTestDate").value = "";
        document.getElementById("labTestPhase").value = "";
        document.getElementById("labVerdict").value = "PASS";
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
