/* Guided demo carousel. */
let demoStep=1;

const demoTexts=[

    "Landing Page",

    "Auditor Workspace",

    "Trace Journey",

    "Laboratory Evidence",

    "IoT Monitoring",

    "Investigation"

];

function updateDemo(){

    document.getElementById("demoText")
    .textContent=
    `Step ${demoStep} of 12: ${demoTexts[demoStep-1] || "TraceVeda Workspace"}`;

    document.querySelectorAll(".demo-dot")
    .forEach((dot,i)=>{

        dot.classList.toggle(
            "active",
            i===demoStep-1
        );

    });

}

function nextDemo(){

    demoStep++;

    if(demoStep>6)
        demoStep=1;

    updateDemo();

}

function prevDemo(){

    demoStep--;

    if(demoStep<1)
        demoStep=6;

    updateDemo();

}
