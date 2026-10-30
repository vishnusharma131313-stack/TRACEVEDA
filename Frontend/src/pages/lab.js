/* Laboratory certification workflow and dynamic test fields. */
function submitLab(){

    const batch =
        document.getElementById("labBatch").value;

    const cert =
        document.getElementById("labCert").value;

    const verdict =
        document.getElementById("labVerdict").value;


    const table =
        document.getElementById("labHistory");


    const row =
        document.createElement("tr");


    row.innerHTML=`

        <td>
            ${new Date().toLocaleDateString()}
        </td>

        <td class="mono">
            ${batch}
        </td>

        <td>
            ${purity}
        </td>

        <td>
            ${lead}
        </td>

        <td>
            <span class="badge ${
                verdict==="PASS"
                ?"badge-success"
                :"badge-danger"
            }">
                ${verdict}
            </span>
        </td>

        <td class="mono">
            0x${Math.random()
            .toString(16)
            .substring(2,9)
            .toUpperCase()}
        </td>

    `;

    table.prepend(row);

    alert(
        verdict==="PASS"
        ? "✓ Laboratory certification successfully signed and registered."
        : "⚠ Failed certification registered."
    );

}

function updateLabFieldFormats() {

    const testPhase =
        document
            .getElementById("labTestPhase")
            ?.value;


    const batchFormat =
        document.getElementById("labBatchFormat");

    const certFormat =
        document.getElementById("labCertFormat");


    if (!batchFormat || !certFormat) {
        return;
    }


    /* ------------------------------------------
       NO TEST PHASE SELECTED
    ------------------------------------------ */

    if (!testPhase) {

        batchFormat.style.display = "none";
        certFormat.style.display = "none";

        batchFormat.textContent = "";
        certFormat.textContent = "";

        return;

    }


    /* ------------------------------------------
       RAW BATCH TEST
    ------------------------------------------ */

    if (testPhase === "RAW_BATCH_TEST") {

        batchFormat.textContent =
            "Format: CROP-YYYY-NNN";

        certFormat.textContent =
            "Format: CERT-PRE-NNNN";

        batchFormat.style.display = "inline";
        certFormat.style.display = "inline";


        document
            .getElementById("labBatch")
            .placeholder =
            "Example: ASH-2026-001";


        document
            .getElementById("labCert")
            .placeholder =
            "Example: CERT-PRE-0001";

    }


    /* ------------------------------------------
       FINAL PRODUCT QUALITY TEST
    ------------------------------------------ */

    else if (
        testPhase ===
        "FINAL_PRODUCT_QUALITY_TEST"
    ) {

        batchFormat.textContent =
            "Format: MED-YYYY-NNN";

        certFormat.textContent =
            "Format: CERT-POST-NNNN";

        batchFormat.style.display = "inline";
        certFormat.style.display = "inline";


        document
            .getElementById("labBatch")
            .placeholder =
            "Example: MED-2026-001";


        document
            .getElementById("labCert")
            .placeholder =
            "Example: CERT-POST-0001";

    }

}

document
    .getElementById("labTestPhase")
    ?.addEventListener(
        "change",
        updateLabFieldFormats
    );

/* Persist certification through the backend API. */
submitLab = async function () {

    const batch =
        document
            .getElementById("labBatch")
            ?.value
            .trim();


    const cert =
        document
            .getElementById("labCert")
            ?.value
            .trim();


    const testDate =
        document
            .getElementById("labTestDate")
            ?.value;


    const testPhase =
        document
            .getElementById("labTestPhase")
            ?.value;


    const verdict =
        document
            .getElementById("labVerdict")
            ?.value;


    /* ------------------------------------------
       VALIDATION
    ------------------------------------------ */

    if (!batch) {

        return alert(
            "Please enter a batch ID."
        );

    }


    if (!cert) {

        return alert(
            "Please enter a certificate ID."
        );

    }


    if (!testDate) {

        return alert(
            "Please select the test date."
        );

    }


    if (!testPhase) {

        return alert(
            "Please select the test phase."
        );

    }


    /* ------------------------------------------
       TEST PHASE DISPLAY VALUE
    ------------------------------------------ */

    const testPhaseLabel = {

        RAW_BATCH_TEST:
            "Raw batch test",

        FINAL_PRODUCT_QUALITY_TEST:
            "Final Product Quality test"

    };


    const displayedPhase =
        testPhaseLabel[testPhase] ||
        testPhase;

    
         /*
        * ============================================================
        * BACKEND INTEGRATION REQUIRED — LAB TEST CERTIFICATION
        * ============================================================
        *
        * API ENDPOINT:
        * POST /api/lab/tests
        *
        * PURPOSE:
        * When the Laboratory user clicks "Sign Ledger Verification",
        * this request must create a new laboratory test record and
        * append/store it in the lab_tests dataset.
        *
        * IMPORTANT:
        * The frontend MUST NOT generate lab_test_id.
        * lab_test_id must be generated by the backend.
        *
        *
        * ------------------------------------------------------------
        * 1. LAB TEST ID GENERATION
        * ------------------------------------------------------------
        *
        * The ID prefix depends on the selected Test Phase:
        *
        * A) Raw batch test:
        *
        *     LABTEST-PRE-0001
        *     LABTEST-PRE-0002
        *     LABTEST-PRE-0003
        *     ...
        *
        * B) Final Product Quality test:
        *
        *     LABTEST-POST-0001
        *     LABTEST-POST-0002
        *     LABTEST-POST-0003
        *     ...
        *
        * The backend must determine the next number automatically by
        * checking the latest existing ID for the corresponding phase.
        *
        * Example:
        *
        * Last RAW test:
        *     LABTEST-PRE-0001
        *
        * Next RAW test:
        *     LABTEST-PRE-0002
        *
        * Last FINAL PRODUCT test:
        *     LABTEST-POST-0002
        *
        * Next FINAL PRODUCT test:
        *     LABTEST-POST-0003
        *
        * RAW and FINAL PRODUCT sequences must be maintained separately.
        *
        * The frontend should NEVER send lab_test_id.
        *
        *
        * ------------------------------------------------------------
        * 2. DATA RECEIVED FROM FRONTEND
        * ------------------------------------------------------------
        *
        * The frontend will send:
        *
        * {
        *     batch_id: selected batch ID,
        *     lab_id: logged-in laboratory ID,
        *     test_date: selected test date,
        *     test_phase: selected test phase,
        *     test_type: test type if required by backend schema,
        *     result: PASS / FAIL,
        *     certificate_id: certificate ID
        * }
        *
        *
        * test_phase values:
        *
        *     RAW_BATCH_TEST
        *     FINAL_PRODUCT_QUALITY_TEST
        *
        *
        * ------------------------------------------------------------
        * 3. CERTIFICATE ID
        * ------------------------------------------------------------
        *
        * Certificate ID is entered by the Laboratory user.
        *
        * Expected frontend format:
        *
        * Raw batch test:
        *     CERT-PRE-<Batch Number>
        *
        * Final Product Quality test:
        *     CERT-POST-<Batch Number>
        *
        * The backend should validate the submitted certificate ID
        * against the selected test phase where appropriate.
        *
        *
        * ------------------------------------------------------------
        * 4. TEST DATE
        * ------------------------------------------------------------
        *
        * Store the exact Test Date entered by the Laboratory user.
        *
        * Do NOT replace the Test Date with the server submission date.
        *
        * The backend may separately maintain a verification timestamp
        * for the actual submission/ledger registration time.
        *
        *
        * ------------------------------------------------------------
        * 5. RECORD CREATION
        * ------------------------------------------------------------
        *
        * On successful submission:
        *
        *     1. Validate all fields.
        *     2. Determine the correct LABTEST-PRE / LABTEST-POST prefix.
        *     3. Generate the next sequential lab_test_id.
        *     4. Create the laboratory test record.
        *     5. Persist it in the backend datastore.
        *     6. Append/synchronize the record with lab_tests.csv if
        *        CSV is being maintained as the project dataset.
        *     7. Return the newly generated lab_test_id and relevant
        *        record information to the frontend.
        *
        *
        * ------------------------------------------------------------
        * 6. IMPORTANT — SEQUENCE SAFETY
        * ------------------------------------------------------------
        *
        * ID generation must be handled on the backend to prevent
        * duplicate IDs when two laboratory users submit records at
        * nearly the same time.
        *
        * Do NOT rely on:
        *
        *     frontend row count
        *     Math.random()
        *     browser localStorage
        *     hardcoded IDs
        *
        *
        * ------------------------------------------------------------
        * 7. RESPONSE EXPECTATION
        * ------------------------------------------------------------
        *
        * The API should return at least:
        *
        * {
        *     "success": true,
        *     "lab_test_id": "LABTEST-PRE-0002",
        *     "batch_id": "...",
        *     "certificate_id": "...",
        *     "test_date": "...",
        *     "test_phase": "...",
        *     "result": "PASS"
        * }
        *
        * If a blockchain transaction/hash is created, it may also
        * return:
        *
        *     "transaction_id"
        *
        * or
        *
        *     "blockchain_tx"
        *
        * The frontend will display the returned ID and transaction
        * information in Verification History.
        *
        *
        * ============================================================
        * 
        * API to be used: POST /api/lab/tests
        */

    try {

        /* --------------------------------------
           BACKEND API
        -------------------------------------- */

        /*
         * BACKEND INTEGRATION NOTE:
         *
         * The current lab_tests schema contains:
         * batch_id, lab_id, test_date, test_type,
         * test_parameters, result, certificate_id,
         * verification_timestamp.
         *
         * "test_phase" is a frontend workflow field.
         * The backend should map/store the selected phase
         * appropriately when the API contract is finalized.
         *
         * Do not reintroduce removed fields such as:
         * test_stage
         * verified_by
         */


        const data =
            await apiRequest(
                "/api/lab/tests",
                {
                    method: "POST",

                    body: JSON.stringify({

                        batch_id:
                            batch,

                        lab_id:
                            cert || "LAB-001",

                        test_date:
                            testDate,

                        test_type:
                            displayedPhase,

                        result:
                            verdict,

                        certificate_id:
                            cert

                    })

                }
            );


        /* --------------------------------------
           UPDATE HISTORY
        -------------------------------------- */

        const table =
            document.getElementById(
                "labHistory"
            );


        if (table) {

            const row =
                document.createElement("tr");


            row.innerHTML = `

                <td>
                    ${testDate}
                </td>

                <td class="mono">
                    ${data?.batch_id || batch}
                </td>

                <td>
                    ${displayedPhase}
                </td>

                <td>

                    <span class="badge ${
                        String(verdict)
                            .toUpperCase() === "PASS"

                        ? "badge-success"

                        : "badge-danger"
                    }">

                        ${verdict}

                    </span>

                </td>

                <td class="mono">
                    ${
                        data?.certificate_id ||
                        cert ||
                        "—"
                    }
                </td>

                <td class="mono">

                    ${
                        data?.blockchain_tx ||
                        data?.transaction_id ||
                        "—"
                    }

                </td>

            `;


            table.prepend(row);

        }


        alert(
            "✓ Laboratory certification submitted and stored successfully."
        );


        /* --------------------------------------
           CLEAR FORM
        -------------------------------------- */

        document
            .getElementById("labBatch")
            .value = "";


        document
            .getElementById("labCert")
            .value = "";


        document
            .getElementById("labTestDate")
            .value = "";


        document
            .getElementById("labTestPhase")
            .value = "";


        document
            .getElementById("labVerdict")
            .value = "PASS";


    }

    catch (error) {

        console.error(
            "Laboratory certification error:",
            error
        );


        alert(
            `Unable to submit laboratory certification: ${error.message}`
        );

    }

};
