#include <Wire.h>

#define MPU_ADDR 0x68

// MPU-6500 registers
#define PWR_MGMT_1 0x6B
#define WHO_AM_I 0x75
#define ACCEL_XOUT_H 0x3B
#define GYRO_XOUT_H 0x43

void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

byte readRegister(byte reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 1);

  if (Wire.available())
    return Wire.read();

  return 0xFF;
}

int16_t read16() {
  int16_t value = Wire.read() << 8 | Wire.read();
  return value;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);

  Serial.println("================================");
  Serial.println("       TRACEVEDA MPU-6500 TEST");
  Serial.println("================================");

  // Check device identity
  byte deviceID = readRegister(WHO_AM_I);

  Serial.print("WHO_AM_I = 0x");
  Serial.println(deviceID, HEX);

  if (deviceID != 0x70) {
    Serial.println("MPU-6500 not detected!");
    while (1) {
      delay(10);
    }
  }

  Serial.println("MPU-6500 detected successfully!");

  // Wake sensor from sleep mode
  writeRegister(PWR_MGMT_1, 0x00);

  delay(100);

  Serial.println("Sensor initialized.");
  Serial.println();
}

void loop() {
  // Start reading from ACCEL_XOUT_H
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);

  // 14 bytes:
  // Accel X,Y,Z = 6
  // Temperature = 2
  // Gyro X,Y,Z = 6
  Wire.requestFrom(MPU_ADDR, 14);

  if (Wire.available() == 14) {
    int16_t accelX = read16();
    int16_t accelY = read16();
    int16_t accelZ = read16();

    int16_t temperatureRaw = read16();

    int16_t gyroX = read16();
    int16_t gyroY = read16();
    int16_t gyroZ = read16();

    // Convert acceleration from raw value to m/s²
    float ax = (accelX / 16384.0) * 9.80665;
    float ay = (accelY / 16384.0) * 9.80665;
    float az = (accelZ / 16384.0) * 9.80665;

    // Convert gyroscope from raw value to °/s
    float gx = gyroX / 131.0;
    float gy = gyroY / 131.0;
    float gz = gyroZ / 131.0;

    // Convert temperature to °C
    float temperatureC = (temperatureRaw / 333.87) + 21.0;

    Serial.print("Acceleration (m/s^2): ");
    Serial.print("X=");
    Serial.print(ax, 2);
    Serial.print("  Y=");
    Serial.print(ay, 2);
    Serial.print("  Z=");
    Serial.println(az, 2);

    Serial.print("Gyroscope (deg/s): ");
    Serial.print("X=");
    Serial.print(gx, 2);
    Serial.print("  Y=");
    Serial.print(gy, 2);
    Serial.print("  Z=");
    Serial.println(gz, 2);

    Serial.print("Temperature: ");
    Serial.print(temperatureC, 2);
    Serial.println(" °C");

    Serial.println("----------------------------");

  } else {
    Serial.println("Failed to read sensor data!");
  }

  delay(500);
}