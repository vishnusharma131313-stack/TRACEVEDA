/* TraceVeda role catalogue and shared role state. */
const roleMenus = {

    auditor: [
        ["auditor-overview","Overview","fa-house"],
        ["auditor-trace","Trace Journey","fa-route"],
        ["auditor-batches","Batch Records","fa-box"],
        ["auditor-iot","IoT Evidence","fa-wifi"],
        ["auditor-investigations","Investigations","fa-shield-halved"],
        ["auditor-reports","Consumer Reports","fa-file-lines"]
    ],

    lab: [

        ["lab-workspace","Log Certification","fa-signature"],

        ["lab-history","Verification History","fa-clock-rotate-left"]

    ],

    manufacturer: [

        ["manufacturer-workspace","Formulate Batch","fa-industry"],
        ["manufacturer-batches","Medicine Batches","fa-boxes-stacked"],
        ["manufacturer-qr","QR ID Generation","fa-qrcode"],
        ["manufacturer-transport","Transport Monitoring","fa-truck"],
        ["manufacturer-storage","Storage Monitoring","fa-temperature-half"]

    ],

    transporter: [
        ["transporter-overview","Overview","fa-house"],
        ["transporter-geotag","Geo Tagged Image","fa-location-dot"]
    ],

    admin: [
        ["admin-overview","Administrator Dashboard","fa-shield-halved"]
    ],

    consumer: [

        ["consumer-qr","Verify Medicine","fa-qrcode"],

        ["consumer-report","Report Medicine","fa-flag"]

    ]

};

const API_BASE_URL = window.TRACEVEDA_CONFIG.API_BASE_URL;

let currentRole = null;
