# TraceVeda Final IoT Schema

The official physical IoT sensor set is:

1. DHT22 - temperature and humidity
2. BH1750 - light intensity
3. Lever/Limit Switch - opening/tamper event
4. MPU6050 - acceleration, gyroscope, shock and tilt
5. Load Cell + HX711 - weight
6. GPS Module - latitude and longitude

IoT monitoring is used for:
- Lab -> Manufacturer transportation
- Manufacturer storage

The dataset contains synthetic project records for development/testing. They are not presented as real sensor observations.

Important: sensor data may arrive at different sampling rates. The backend should preserve `sensor_id` and `timestamp` rather than assuming all sensor values originate from one simultaneous physical sample.
