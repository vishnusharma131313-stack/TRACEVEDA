/* Auditor: trace search, evidence display, investigations. */
function runAuditSearch(){

    const id =
        document.getElementById("auditSearch").value;

    if(!id.trim()){

        alert("Please enter a batch ID.");

        return;

    }

    openRole("auditor","trace");

    document.getElementById("traceInput").value=id;

    runTrace();

}

function runTrace(){

    const id =
        document.getElementById("traceInput").value;

    document.getElementById("traceResult")
    .style.display="block";

    document.getElementById("traceBatch")
    .textContent=id;

    document.getElementById("evidence")
    .classList.remove("active");

    document.getElementById("traceResult")
    .scrollIntoView({
        behavior:"smooth",
        block:"start"
    });

}

function showEvidence(stage){

    const evidence =
        document.getElementById("evidence");

    const title =
        document.getElementById("evidenceTitle");

    const body =
        document.getElementById("evidenceBody");

    title.textContent =
        stage+" — Digital Evidence";

    const data = {

        Farm:[
            ["Source","Himalayan Organic Farm"],
            ["Batch","RAW-2026-071"],
            ["Supplied Date","10 Jan 2026"],
            ["Location","Haridwar, Uttarakhand"],
            ["Quantity","753.24 kg"]
        ],

        Processing:[
            ["Process Lot","ASH-P-2026-001"],
            ["Processor ID","PROC-001"],
            ["Processing Date","6 Jun 2026"],
            ["Output Quantity","1016.49 kg"],
            ["Process Status","COMPLETED"]
        ],

        Laboratory:[
            ["Certificate","CERT-PRE-0001"],
            ["Test Date","6 Jun 2026"],
            ["Result","PASS"]
        ],

        Transport:[
            ["Device","IOT-001"],
            ["Weight","4.18 kg"],
            ["Door","OPEN"],
            ["Light","1850 lux"],
            ["Motion","Shock 3.2g"],
            ["Status","ANOMALY DETECTED"]
        ],

        Manufacturing:[
            ["Facility","AyurLabs Facility"],
            ["Batch","MED-2026-043"],
            ["Production Status","Complete"],
            ["Ledger","Verified"]
        ],

        "Final Lab":[
            ["Certificate","CERT-POST-0001"],
            ["Test Date","5 Jun 2026"],
            ["Result","PASS"]
        ],

        Medicine:[
            ["Product","Ashwagandha Extract Tablets"],
            ["Batch","MED-2026-043"],
            ["Blockchain","Verified"],
            ["Consumer Status","Authentic"]
        ]

    };


    body.innerHTML="";

    (data[stage] || []).forEach(row=>{

        body.innerHTML += `

        <tr>

            <td>
                ${row[0]}
            </td>

            <td class="mono">
                ${row[1]}
            </td>

        </tr>

        `;

    });


    evidence.classList.add("active");

    evidence.scrollIntoView({
        behavior:"smooth",
        block:"nearest"
    });

}

function investigateBatch() {

    const batchInput =
        document.getElementById("investigateBatchId");

    const resultBox =
        document.getElementById("batchInvestigationResult");

    const statusBox =
        document.getElementById("batchInvestigationStatus");

    const detailsBox =
        document.getElementById("batchInvestigationDetails");


    if (!batchInput || !resultBox) {
        return;
    }


    const batchId =
        batchInput.value.trim();


    if (!batchId) {

        alert(
            "Please enter a processing batch ID."
        );

        return;
    }


    /*
     * TEMPORARY FRONTEND BEHAVIOUR
     *
     * This will later be replaced with a backend API call.
     */

    resultBox.style.display = "block";


    if (statusBox) {

        statusBox.innerHTML = `
            <span class="badge badge-success">
                No casualty detected
            </span>
        `;

    }


    if (detailsBox) {

        detailsBox.textContent =
            `No transport anomaly or casualty is currently recorded `
            + `for batch ${batchId}.`;

    }

}

/* API-backed trace lookup overrides the local placeholder. */
runTrace = async function () {
    const id = document.getElementById("traceInput")?.value.trim();
    if (!id) return alert("Please enter a medicine batch ID.");

    try {
        const data = await apiRequest(`/api/trace/reverse/${encodeURIComponent(id)}`, { method: "GET" });
        const result = document.getElementById("traceResult");
        const batch = document.getElementById("traceBatch");
        if (batch) batch.textContent = data?.medicine_batch?.medicine_batch_id || data?.medicine_batch?.batch_id || id;
        if (result) {
            result.style.display = "block";
            result.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        window.tracevedaTraceData = data;
    } catch (error) {
        alert(`Trace lookup failed: ${error.message}`);
    }
};
