/* Shared IoT rendering helpers and first-pass loader. */
function setIoTMessage(message, type = "info") {
    const box = document.getElementById("iotMessage");
    if (!box) return;

    box.textContent = message;
    box.style.display = message ? "block" : "none";

    if (type === "error") {
        box.style.color = "var(--danger)";
    } else if (type === "success") {
        box.style.color = "var(--success)";
    } else {
        box.style.color = "var(--text)";
    }
}

function iotValue(value, suffix = "") {
    if (value === null || value === undefined || value === "") return "—";
    return `${value}${suffix}`;
}

function latestIoTReading(readings, field) {
    for (let i = readings.length - 1; i >= 0; i--) {
        const value = readings[i]?.[field];
        if (value !== null && value !== undefined && value !== "") {
            return readings[i];
        }
    }
    return null;
}

function formatIoTTimestamp(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
}

function getMotionText(reading) {
    if (!reading) return "—";

    if (reading.shock_detected === true) {
        const parts = ["Shock"];
        if (reading.accel_x_g !== null && reading.accel_x_g !== undefined) {
            parts.push(`${reading.accel_x_g}g`);
        }
        return parts.join(" ");
    }

    if (reading.tilt_angle_deg !== null && reading.tilt_angle_deg !== undefined) {
        return `Tilt ${reading.tilt_angle_deg}°`;
    }

    const accel = [
        reading.accel_x_g,
        reading.accel_y_g,
        reading.accel_z_g
    ].filter(v => v !== null && v !== undefined);

    return accel.length ? `Accel ${accel.join(", ")}g` : "Normal";
}

function renderIoTReadings(readings, alerts) {
    const latest = readings.length ? readings[readings.length - 1] : null;

    const weightReading = latestIoTReading(readings, "weight_kg");
    const doorReading = latestIoTReading(readings, "switch_status");
    const lightReading = latestIoTReading(readings, "light_intensity_lux");
    const motionReading = readings.length ? readings[readings.length - 1] : null;

    document.getElementById("iotWeightValue").textContent =
        weightReading ? iotValue(weightReading.weight_kg, " kg") : "—";
    document.getElementById("iotWeightStatus").textContent =
        weightReading ? `Latest reading • ${formatIoTTimestamp(weightReading.timestamp)}` : "No weight reading";

    document.getElementById("iotDoorValue").textContent =
        doorReading ? String(doorReading.switch_status).toUpperCase() : "—";
    document.getElementById("iotDoorStatus").textContent =
        doorReading ? `Latest switch reading • ${formatIoTTimestamp(doorReading.timestamp)}` : "No switch reading";

    document.getElementById("iotLightValue").textContent =
        lightReading ? iotValue(lightReading.light_intensity_lux, " lx") : "—";
    document.getElementById("iotLightStatus").textContent =
        lightReading ? `Latest light reading • ${formatIoTTimestamp(lightReading.timestamp)}` : "No light reading";

    document.getElementById("iotMotionValue").textContent =
        getMotionText(motionReading);
    document.getElementById("iotMotionStatus").textContent =
        motionReading ? `Latest motion data • ${formatIoTTimestamp(motionReading.timestamp)}` : "No motion reading";

    const body = document.getElementById("iotReadingsBody");
    body.innerHTML = "";

    if (!readings.length) {
        body.innerHTML = `
            <tr>
                <td colspan="7" style="text-align:center;">
                    No IoT readings were found for this batch.
                </td>
            </tr>`;
        return;
    }

    const sortedReadings = [...readings].sort((a, b) =>
        new Date(b.timestamp) - new Date(a.timestamp)
    );

    sortedReadings.forEach(reading => {
        const matchingAlerts = alerts.filter(alert => {
            const alertSensor = alert.sensor_id;
            const sameSensor = !alertSensor || alertSensor === reading.sensor_id;
            return sameSensor;
        });

        const hasCritical = matchingAlerts.some(alert =>
            String(alert.severity || "").toUpperCase() === "CRITICAL"
        );

        const integrity = reading.alert_status ||
            (hasCritical ? "BREACH" :
            (matchingAlerts.length ? "ALERT" : "NORMAL"));

        const badgeClass =
            ["BREACH", "CRITICAL", "ALERT"].includes(String(integrity).toUpperCase())
                ? "badge-danger"
                : "badge-success";

        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${formatIoTTimestamp(reading.timestamp)}</td>
            <td class="mono">${reading.sensor_id || "—"}</td>
            <td>${iotValue(reading.weight_kg, " kg")}</td>
            <td>${reading.switch_status ? String(reading.switch_status).toUpperCase() : "—"}</td>
            <td>${iotValue(reading.light_intensity_lux, " lux")}</td>
            <td>${getMotionText(reading)}</td>
            <td><span class="badge ${badgeClass}">${integrity}</span></td>
        `;

        body.appendChild(tr);
    });
}

async function loadIoTEvidence() {
    const input = document.getElementById("iotBatchId");
    const batchId = input ? input.value.trim() : "";

    if (!batchId) {
        setIoTMessage("Please enter a batch ID.", "error");
        return;
    }

    setIoTMessage("Loading IoT evidence from MongoDB...");

    try {
        const encodedBatchId = encodeURIComponent(batchId);

        const [readingsResponse, alertsResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/api/iot/readings/${encodedBatchId}`),
            fetch(`${API_BASE_URL}/api/iot/alerts/${encodedBatchId}`)
        ]);

        const readingsData = await readingsResponse.json();

        let alertsData = { alerts: [] };
        try {
            alertsData = await alertsResponse.json();
        } catch (_) {}

        if (!readingsResponse.ok) {
            throw new Error(readingsData.detail || "Unable to load IoT readings.");
        }

        const readings = Array.isArray(readingsData.readings)
            ? readingsData.readings
            : [];

        const alerts = Array.isArray(alertsData.alerts)
            ? alertsData.alerts
            : [];

        renderIoTReadings(readings, alerts);

        if (readings.length) {
            setIoTMessage(
                `Loaded ${readings.length} IoT reading(s) for ${batchId}.`,
                "success"
            );
        } else {
            setIoTMessage(
                `No IoT readings are currently stored in MongoDB for ${batchId}.`,
                "info"
            );
        }

    } catch (error) {
        console.error("IoT loading error:", error);
        renderIoTReadings([], []);
        setIoTMessage(`IoT evidence failed to load: ${error.message}`, "error");
    }
}
