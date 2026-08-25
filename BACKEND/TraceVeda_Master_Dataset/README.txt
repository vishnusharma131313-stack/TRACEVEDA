TraceVeda Master Dataset Package

Reference sources processed:
- BSI: 1,915 medicinal-plant records across 20 CSV parts.
- NMPB: 960 numbered medicinal-plant records extracted from the supplied 62-page PDF.
- GS1 EPCIS 2.0: used as an event-schema reference, not merged as transactional data.
- IoT reference: 2,313,682 source rows; 2,219,803 complete rows; 93,879 partial/quarantined rows preserved in iot_reference_quarantine.csv.

Plant master:
- 2,300 conservative union records.
- 562 exact genus+species matches between BSI and NMPB.
- Source provenance is preserved.

Project synthetic data:
- 70 raw batches, 45 processing batches, 42 medicine batches, 157 transport events, 87 lab tests, 11,128 project IoT readings, 42 storage periods, 20 consumer reports, 20 investigations, and 375 blockchain anchors.
- Synthetic supply-chain records are clearly marked.
- IoT monitoring is intentionally limited to LAB_TO_MANUFACTURER transport and manufacturer storage.
- Handling thresholds are project configuration for demonstration and are not presented as universal scientific limits.

Validation:
- Foreign-key checks: True
- Raw-to-processing temporal violations: 0
- Shipment temporal violations: 0
- Lab/manufacturing temporal violations: 0
- Reverse trace tests: 10/10
- Forward trace tests: 20/20
- Many-to-one processing relationships: 17
- One-to-many processing relationships: 14

Important: public source data is not used to fabricate farms, transport history, lab outcomes, manufacturer storage, consumer incidents or blockchain transactions. Those project records are synthetic demonstration data.
