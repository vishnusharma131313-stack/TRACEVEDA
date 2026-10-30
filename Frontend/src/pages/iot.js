/* Authenticated IoT evidence loader. */
loadIoTEvidence = async function () {
    const input = document.getElementById("iotBatchId");
    const batchId = input?.value.trim();
    if (!batchId) return setIoTMessage("Please enter a batch ID.", "error");

    setIoTMessage("Loading IoT evidence from TraceVeda...");
    try {
        const id = encodeURIComponent(batchId);
        const [readingsData, alertsData] = await Promise.all([
            apiRequest(`/api/iot/readings/${id}`),
            apiRequest(`/api/iot/alerts/${id}`).catch(() => ({ alerts: [] }))
        ]);
        const readings = Array.isArray(readingsData?.readings) ? readingsData.readings : [];
        const alerts = Array.isArray(alertsData?.alerts) ? alertsData.alerts : [];
        renderIoTReadings(readings, alerts);
        setIoTMessage(readings.length ? `Loaded ${readings.length} IoT reading(s) for ${batchId}.` : `No IoT readings found for ${batchId}.`, readings.length ? "success" : "info");
    } catch (error) {
        renderIoTReadings([], []);
        setIoTMessage(`IoT evidence failed to load: ${error.message}`, "error");
    }
};
