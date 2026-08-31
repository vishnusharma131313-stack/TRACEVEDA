from database import db

readings = db.iot_readings.find(
    {},
    {"_id": 0, "batch_id": 1}
).limit(50)

for reading in readings:
    print(reading)