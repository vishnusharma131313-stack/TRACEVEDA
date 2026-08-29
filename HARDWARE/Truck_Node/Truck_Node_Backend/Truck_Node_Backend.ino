#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <HX711.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <time.h>
#include <math.h>
#include <string.h>

// ======================================================
// TRACEVEDA TRUCK NODE — FINAL BACKEND INTEGRATION
//
// Existing backend contract is preserved.
// Each physical sensor keeps its own sensor_id.
//
// Sensors:
// DHT22       -> IOT-DHT22-001
// BH1750      -> IOT-BH1750-001
// Limit       -> IOT-LIMIT-001
// MPU-6500    -> IOT-MPU6050-001  (backend-registered ID)
// HX711       -> IOT-HX711-001
// GPS         -> IOT-GPS-001
//
// Data path:
// Sensors -> RAM FIFO -> Backend
//                    \-> LittleFS when offline/failure
//
// No new backend/API fields are introduced.
// ======================================================

// ======================================================
// TRACEVEDA IDs
// ======================================================

// Use IDs that exist in the supplied master dataset/backend.
const char* BATCH_ID = "ASH-2026-001";
const char* TRANSPORT_ID = "TRN-RAW-0001";
const char* DEVICE_ID = "ESP32-001";

// ======================================================
// BACKEND
// ======================================================

const char* BACKEND_URL = "http://YOUR_PC_IP:8000";
const char* IOT_ENDPOINT = "/api/iot/readings";

// ======================================================
// WI-FI
// ======================================================

const char* ssid = "new";
const char* password = "12345678";

// ======================================================
// PINS
// ======================================================

#define SDA_PIN 21
#define SCL_PIN 22

#define DHT_PIN 4
#define DHT_TYPE DHT22

#define GPS_RX 16
#define GPS_TX 17

#define LIMIT_SWITCH_PIN 27
#define RED_LED_PIN 25

#define HX711_DT 32
#define HX711_SCK 33

// ======================================================
// LCD
// ======================================================

#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 16
#define LCD_ROWS 2

LiquidCrystal_I2C lcd(
  LCD_ADDRESS,
  LCD_COLUMNS,
  LCD_ROWS);

// ======================================================
// SENSOR OBJECTS
// ======================================================

DHT dht(DHT_PIN, DHT_TYPE);
BH1750 lightMeter;

HardwareSerial GPS(2);
TinyGPSPlus gps;

HX711 scale;

// ======================================================
// MPU-6500
// ======================================================

#define MPU_ADDR 0x68
#define PWR_MGMT_1 0x6B
#define WHO_AM_I 0x75
#define ACCEL_XOUT_H 0x3B

float ax = 0.0;
float ay = 0.0;
float az = 0.0;

float gx = 0.0;
float gy = 0.0;
float gz = 0.0;

float tilt = 0.0;

float accelOffsetX = 0.0;
float accelOffsetY = 0.0;
float accelOffsetZ = 0.0;

float gyroOffsetX = 0.0;
float gyroOffsetY = 0.0;
float gyroOffsetZ = 0.0;

bool mpuOK = false;

// ======================================================
// DHT / LIGHT / DOOR
// ======================================================

float temperature = NAN;
float humidity = NAN;
float lux = 0.0;

bool doorClosed = false;

// ======================================================
// HX711
// ======================================================

const float HX711_CALIBRATION_FACTOR = 126.4576;

float weightKg = 0.0;
float previousWeightKg = 0.0;
float weightChangeKg = 0.0;
bool weightInitialized = false;
bool hx711OK = false;

// ======================================================
// LOCAL ALERT / RED LED
//
// The physical LED is local. It does not require a new
// backend field. It turns ON whenever a monitored value is
// outside the project's active backend rule limits, or a
// tamper/door/weight/shock condition is detected.
// ======================================================

// Backend-controlled RED LED state
bool redLedState = false;

const float TEMP_MIN = 10.0;
const float TEMP_MAX = 35.0;
const float HUMIDITY_MIN = 20.0;
const float HUMIDITY_MAX = 70.0;
const float LIGHT_MAX = 1000.0;
const float TILT_MAX = 45.0;

// The supplied master examples use 2.0g as the shock reference.
const float SHOCK_THRESHOLD_G = 2.0;

// ======================================================
// TIMERS
// ======================================================

unsigned long lastMPURead = 0;
unsigned long lastDHTRead = 0;
unsigned long lastLightRead = 0;
unsigned long lastWeightRead = 0;
unsigned long lastTelemetry = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastLCDScreenChange = 0;
unsigned long lastSerialOutput = 0;
unsigned long lastWiFiCheck = 0;

const unsigned long MPU_INTERVAL = 50;
const unsigned long DHT_INTERVAL = 2000;
const unsigned long LIGHT_INTERVAL = 500;
const unsigned long WEIGHT_INTERVAL = 1000;

// One complete sensor set every 5 seconds.
const unsigned long TELEMETRY_INTERVAL = 5000;

const unsigned long LCD_INTERVAL = 250;
const unsigned long SCREEN_INTERVAL = 2000;
const unsigned long SERIAL_INTERVAL = 1000;
const unsigned long WIFI_INTERVAL = 5000;

// Process buffered/current readings faster than they are generated.

// ======================================================
// LCD SCREENS
// ======================================================

int currentScreen = 0;
const int TOTAL_SCREENS = 9;

// ======================================================
// RAM FIFO
// ======================================================

const int QUEUE_SIZE = 18;
String payloadQueue[QUEUE_SIZE];

int queueHead = 0;
int queueTail = 0;
int queueCount = 0;

SemaphoreHandle_t queueMutex = nullptr;
SemaphoreHandle_t fsMutex = nullptr;
TaskHandle_t uploadTaskHandle = nullptr;
const unsigned long UPLOAD_TASK_INTERVAL = 500;

// ======================================================
// LITTLEFS
// ======================================================

const char* BUFFER_FILE = "/truck_iot_buffer.txt";
const char* REMAINING_FILE = "/truck_iot_remaining.txt";
const size_t MAX_BUFFER_BYTES = 200 * 1024;

// ======================================================
// FORWARD DECLARATIONS
// ======================================================

bool sendPayload(const String& payload);
void bufferPayload(const String& payload);

// ======================================================
// QUEUE
// ======================================================

bool enqueuePayload(const String& payload)
{
  bool full = false;
  if (queueMutex != nullptr) xSemaphoreTake(queueMutex, portMAX_DELAY);
  if (queueCount >= QUEUE_SIZE) full = true;
  else
  {
    payloadQueue[queueTail] = payload;
    queueTail++;
    if (queueTail >= QUEUE_SIZE) queueTail = 0;
    queueCount++;
  }
  if (queueMutex != nullptr) xSemaphoreGive(queueMutex);
  if (full)
  {
    Serial.println("RAM queue FULL -> LittleFS");
    bufferPayload(payload);
    return false;
  }
  return true;
}

bool peekQueue(String& payload)
{
  bool available = false;
  if (queueMutex != nullptr) xSemaphoreTake(queueMutex, portMAX_DELAY);
  if (queueCount > 0)
  {
    payload = payloadQueue[queueHead];
    available = true;
  }
  if (queueMutex != nullptr) xSemaphoreGive(queueMutex);
  return available;
}

void dequeuePayload()
{
  if (queueMutex != nullptr) xSemaphoreTake(queueMutex, portMAX_DELAY);
  if (queueCount > 0)
  {
    payloadQueue[queueHead] = "";
    queueHead++;
    if (queueHead >= QUEUE_SIZE) queueHead = 0;
    queueCount--;
  }
  if (queueMutex != nullptr) xSemaphoreGive(queueMutex);
}

// ======================================================
// TIMESTAMP
// ======================================================

String getTimestamp() {
  time_t now = time(nullptr);

  struct tm timeinfo;
  localtime_r(&now, &timeinfo);

  char timestamp[32];

  strftime(
    timestamp,
    sizeof(timestamp),
    "%Y-%m-%dT%H:%M:%S",
    &timeinfo);

  return String(timestamp);
}

// ======================================================
// WIFI
// ======================================================

void connectWiFi() {
  Serial.println();
  Serial.println("================================");
  Serial.println("          WI-FI CONNECTION");
  Serial.println("================================");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");

    configTime(
      19800,
      0,
      "pool.ntp.org",
      "time.nist.gov");

    Serial.println("NTP synchronization requested.");
  } else {
    Serial.println("WiFi connection FAILED. Continuing offline.");
  }

  Serial.println("================================");
}

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.disconnect();
  WiFi.begin(ssid, password);
}

// ======================================================
// MPU LOW-LEVEL
// ======================================================

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

  if (Wire.available()) {
    return Wire.read();
  }

  return 0xFF;
}

int16_t read16() {
  return (int16_t)((Wire.read() << 8) | Wire.read());
}

bool readMPURaw(
  int16_t& accelX,
  int16_t& accelY,
  int16_t& accelZ,
  int16_t& temperatureRaw,
  int16_t& gyroX,
  int16_t& gyroY,
  int16_t& gyroZ) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);

  if (Wire.requestFrom(MPU_ADDR, 14) != 14) {
    return false;
  }

  accelX = read16();
  accelY = read16();
  accelZ = read16();
  temperatureRaw = read16();
  gyroX = read16();
  gyroY = read16();
  gyroZ = read16();

  return true;
}

bool initializeMPU() {
  byte deviceID = readRegister(WHO_AM_I);

  Serial.print("MPU-6500 WHO_AM_I = 0x");
  Serial.println(deviceID, HEX);

  if (deviceID != 0x70) {
    Serial.println("MPU-6500 NOT detected!");
    return false;
  }

  writeRegister(PWR_MGMT_1, 0x00);
  delay(100);

  Serial.println("MPU-6500 initialized.");
  return true;
}

void calibrateMPU() {
  const int samples = 300;

  long long sumAccelX = 0;
  long long sumAccelY = 0;
  long long sumAccelZ = 0;

  long long sumGyroX = 0;
  long long sumGyroY = 0;
  long long sumGyroZ = 0;

  int successfulSamples = 0;

  Serial.println();
  Serial.println("================================");
  Serial.println("       MPU-6500 CALIBRATION");
  Serial.println("================================");
  Serial.println("Keep MPU STILL and LEVEL.");

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");
  lcd.setCursor(0, 1);
  lcd.print("Calibrating MPU");

  delay(1000);

  for (int i = 0; i < samples; i++) {
    int16_t accelX, accelY, accelZ;
    int16_t temperatureRaw;
    int16_t gyroX, gyroY, gyroZ;

    if (
      readMPURaw(
        accelX,
        accelY,
        accelZ,
        temperatureRaw,
        gyroX,
        gyroY,
        gyroZ)) {
      sumAccelX += accelX;
      sumAccelY += accelY;
      sumAccelZ += accelZ;

      sumGyroX += gyroX;
      sumGyroY += gyroY;
      sumGyroZ += gyroZ;

      successfulSamples++;
    }

    delay(5);
  }

  if (successfulSamples == 0) {
    Serial.println("MPU calibration FAILED!");
    return;
  }

  float avgAccelX = (float)sumAccelX / successfulSamples;
  float avgAccelY = (float)sumAccelY / successfulSamples;
  float avgAccelZ = (float)sumAccelZ / successfulSamples;

  float avgGyroX = (float)sumGyroX / successfulSamples;
  float avgGyroY = (float)sumGyroY / successfulSamples;
  float avgGyroZ = (float)sumGyroZ / successfulSamples;

  accelOffsetX = avgAccelX;
  accelOffsetY = avgAccelY;
  accelOffsetZ = avgAccelZ - 16384.0;

  gyroOffsetX = avgGyroX;
  gyroOffsetY = avgGyroY;
  gyroOffsetZ = avgGyroZ;

  Serial.println("MPU calibration complete.");

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");
  lcd.setCursor(0, 1);
  lcd.print("MPU CALIBRATED");
  delay(1200);
}

void readMPU() {
  if (!mpuOK) {
    return;
  }

  int16_t accelX, accelY, accelZ;
  int16_t temperatureRaw;
  int16_t gyroX, gyroY, gyroZ;

  if (
    !readMPURaw(
      accelX,
      accelY,
      accelZ,
      temperatureRaw,
      gyroX,
      gyroY,
      gyroZ)) {
    return;
  }

  float correctedAccelX = accelX - accelOffsetX;
  float correctedAccelY = accelY - accelOffsetY;
  float correctedAccelZ = accelZ - accelOffsetZ;

  float correctedGyroX = gyroX - gyroOffsetX;
  float correctedGyroY = gyroY - gyroOffsetY;
  float correctedGyroZ = gyroZ - gyroOffsetZ;

  // Backend expects acceleration in g.
  ax = correctedAccelX / 16384.0;
  ay = correctedAccelY / 16384.0;
  az = correctedAccelZ / 16384.0;

  // Backend expects gyro in degrees/second.
  gx = correctedGyroX / 131.0;
  gy = correctedGyroY / 131.0;
  gz = correctedGyroZ / 131.0;

  float horizontalAcceleration = sqrt(
    (ax * ax) + (ay * ay));

  tilt = atan2(
           horizontalAcceleration,
           az)
         * 180.0 / PI;
}

// ======================================================
// GPS
// ======================================================

void readGPS() {
  while (GPS.available()) {
    gps.encode(GPS.read());
  }
}

// ======================================================
// WEIGHT
// ======================================================

void readWeight() {
  if (!hx711OK || !scale.is_ready()) {
    return;
  }

  float newWeight = scale.get_units(3);

  if (!isfinite(newWeight)) {
    return;
  }

  if (newWeight < 0 && newWeight > -0.05) {
    newWeight = 0;
  }

  weightKg = newWeight;

  if (!weightInitialized) {
    previousWeightKg = weightKg;
    weightChangeKg = 0.0;
    weightInitialized = true;
  } else {
    weightChangeKg = weightKg - previousWeightKg;
    previousWeightKg = weightKg;
  }
}

// ======================================================
// LOCAL RED LED LOGIC
// ======================================================

bool shockDetected() {
  float accelerationMagnitude = sqrt(
    (ax * ax) + (ay * ay) + (az * az));

  return accelerationMagnitude >= SHOCK_THRESHOLD_G;
}

// ======================================================
// JSON HELPERS
// ======================================================

String commonPrefix(const char* sensorID) {
  String json = "{";

  json += "\"batch_id\":\"";
  json += BATCH_ID;
  json += "\",";

  json += "\"transport_id\":\"";
  json += TRANSPORT_ID;
  json += "\",";

  json += "\"sensor_id\":\"";
  json += sensorID;
  json += "\",";

  json += "\"timestamp\":\"";
  json += getTimestamp();
  json += "\",";

  return json;
}

// ======================================================
// DHT PAYLOAD
// ======================================================

String createDHTPayload() {
  String json = commonPrefix("IOT-DHT22-001");

  if (!isnan(temperature)) {
    json += "\"temperature_c\":";
    json += String(temperature, 2);
    json += ",";
  }

  if (!isnan(humidity)) {
    json += "\"humidity_percent\":";
    json += String(humidity, 2);
    json += ",";
  }

  if (json.endsWith(",")) {
    json.remove(json.length() - 1);
  }

  json += "}";
  return json;
}

// ======================================================
// BH1750 PAYLOAD
// ======================================================

String createLightPayload() {
  String json = commonPrefix("IOT-BH1750-001");

  json += "\"light_intensity_lux\":";
  json += String(lux, 2);

  json += "}";
  return json;
}

// ======================================================
// LIMIT SWITCH PAYLOAD
//
// weight_change_kg is included as current cross-sensor
// context so the backend's existing 2FA tamper rule can
// evaluate gate + weight in one incoming reading.
// No new API field is created; this field already exists.
// ======================================================

String createDoorPayload() {
  String json = commonPrefix("IOT-LIMIT-001");

  json += "\"switch_status\":\"";
  json += doorClosed ? "CLOSED" : "OPEN";
  json += "\",";

  json += "\"weight_change_kg\":";
  json += String(weightChangeKg, 2);

  json += "}";
  return json;
}

// ======================================================
// MPU PAYLOAD
// ======================================================

String createMPUPayload() {
  String json = commonPrefix("IOT-MPU6050-001");

  json += "\"accel_x_g\":";
  json += String(ax, 4);
  json += ",";

  json += "\"accel_y_g\":";
  json += String(ay, 4);
  json += ",";

  json += "\"accel_z_g\":";
  json += String(az, 4);
  json += ",";

  json += "\"gyro_x_dps\":";
  json += String(gx, 3);
  json += ",";

  json += "\"gyro_y_dps\":";
  json += String(gy, 3);
  json += ",";

  json += "\"gyro_z_dps\":";
  json += String(gz, 3);
  json += ",";

  json += "\"shock_detected\":";
  json += shockDetected() ? "true" : "false";
  json += ",";

  json += "\"tilt_angle_deg\":";
  json += String(tilt, 2);

  json += "}";
  return json;
}

// ======================================================
// HX711 PAYLOAD
// ======================================================

String createWeightPayload() {
  String json = commonPrefix("IOT-HX711-001");

  json += "\"weight_kg\":";
  json += String(weightKg, 3);
  json += ",";

  json += "\"weight_change_kg\":";
  json += String(weightChangeKg, 3);

  json += "}";
  return json;
}

// ======================================================
// GPS PAYLOAD
// ======================================================

String createGPSPayload() {
  String json = commonPrefix("IOT-GPS-001");

  bool valid = gps.location.isValid();

  json += "\"gps_valid\":";
  json += valid ? "true" : "false";
  json += ",";

  if (valid) {
    json += "\"latitude\":";
    json += String(gps.location.lat(), 6);
    json += ",";

    json += "\"longitude\":";
    json += String(gps.location.lng(), 6);
  } else {
    json += "\"latitude\":null,";
    json += "\"longitude\":null";
  }

  json += "}";
  return json;
}

// ======================================================
// LITTLEFS BUFFER
// ======================================================

bool bufferHasSpace(size_t payloadSize) {
  size_t currentSize = 0;

  if (LittleFS.exists(BUFFER_FILE)) {
    File file = LittleFS.open(BUFFER_FILE, FILE_READ);

    if (file) {
      currentSize = file.size();
      file.close();
    }
  }

  return (
    currentSize + payloadSize + 2 <= MAX_BUFFER_BYTES);
}

void bufferPayload(const String& payload)
{
  if (fsMutex != nullptr) xSemaphoreTake(fsMutex, portMAX_DELAY);
  if (!bufferHasSpace(payload.length()))
  {
    Serial.println("ERROR: LittleFS buffer FULL.");
    if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
    return;
  }
  File file = LittleFS.open(BUFFER_FILE, FILE_APPEND);
  if (!file)
  {
    Serial.println("ERROR: Could not open LittleFS buffer.");
    if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
    return;
  }
  file.println(payload);
  file.close();
  if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
}

// ======================================================
// APPLY BACKEND RED LED RESPONSE
// ======================================================

void applyBackendRedLED(const String& response) {
  // Backend response example:
  // {"status":"success","red_led":true}

  if (response.indexOf("\"red_led\":true") >= 0 ||
      response.indexOf("\"red_led\": true") >= 0) {
    redLedState = true;

    digitalWrite(
      RED_LED_PIN,
      HIGH);

    Serial.println(
      "Backend RED LED = ON");
  } else if (response.indexOf("\"red_led\":false") >= 0 ||
             response.indexOf("\"red_led\": false") >= 0) {
    redLedState = false;

    digitalWrite(
      RED_LED_PIN,
      LOW);

    Serial.println(
      "Backend RED LED = OFF");
  }
}

// ======================================================
// HTTP POST
// ======================================================

bool sendPayload(const String& payload) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;

  String url =
    String(BACKEND_URL) + String(IOT_ENDPOINT);

  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json");

  http.setTimeout(1500);

  int httpCode =
    http.POST(payload);

  bool success =
    (httpCode >= 200 && httpCode < 300);

  Serial.print("HTTP: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    String response =
      http.getString();

    Serial.println(
      "Backend response:");

    Serial.println(response);

    // --------------------------------------------------
    // BACKEND CONTROLS PHYSICAL RED LED
    // --------------------------------------------------

    applyBackendRedLED(response);
  }

  http.end();

  return success;
}

// ======================================================
// UPLOAD ONE LITTLEFS READING
// ======================================================

void uploadBufferedData()
{
  if (WiFi.status() != WL_CONNECTED) return;

  String firstPayload;
  String oldRemaining;

  if (fsMutex != nullptr) xSemaphoreTake(fsMutex, portMAX_DELAY);
  if (!LittleFS.exists(BUFFER_FILE))
  {
    if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
    return;
  }
  File file = LittleFS.open(BUFFER_FILE, FILE_READ);
  if (!file)
  {
    if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
    return;
  }
  if (file.size() == 0)
  {
    file.close();
    LittleFS.remove(BUFFER_FILE);
    if (fsMutex != nullptr) xSemaphoreGive(fsMutex);
    return;
  }
  firstPayload = file.readStringUntil('\n');
  firstPayload.trim();
  while (file.available())
  {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) { oldRemaining += line; oldRemaining += '\n'; }
  }
  file.close();
  if (fsMutex != nullptr) xSemaphoreGive(fsMutex);

  if (firstPayload.length() == 0) return;

  // HTTPClient::POST() blocks, but this function runs only in UploadTask.
  bool uploaded = sendPayload(firstPayload);

  if (fsMutex != nullptr) xSemaphoreTake(fsMutex, portMAX_DELAY);
  String newlyAppended;
  File current = LittleFS.open(BUFFER_FILE, FILE_READ);
  if (current)
  {
    while (current.available())
    {
      String line = current.readStringUntil('\n');
      line.trim();
      if (line.length() > 0) { newlyAppended += line; newlyAppended += '\n'; }
    }
    current.close();
  }
  File remaining = LittleFS.open(REMAINING_FILE, FILE_WRITE);
  if (remaining)
  {
    if (!uploaded) remaining.println(firstPayload);
    remaining.print(oldRemaining);
    remaining.print(newlyAppended);
    remaining.close();
    LittleFS.remove(BUFFER_FILE);
    LittleFS.rename(REMAINING_FILE, BUFFER_FILE);
  }
  if (fsMutex != nullptr) xSemaphoreGive(fsMutex);

  if (uploaded) Serial.println("Oldest buffered reading uploaded.");
  else Serial.println("Buffered reading retained for retry.");
}

// ======================================================
// PROCESS ONE RAM READING
// ======================================================

void processQueue()
{
  String payload;
  if (!peekQueue(payload)) return;
  if (sendPayload(payload)) dequeuePayload();
  else { bufferPayload(payload); dequeuePayload(); }
}

// ======================================================
// QUEUE CURRENT SENSOR DATA
// ======================================================

void queueCurrentSensorData() {
  if (!isnan(temperature) && !isnan(humidity)) {
    enqueuePayload(createDHTPayload());
  }

  enqueuePayload(createLightPayload());
  enqueuePayload(createDoorPayload());

  if (mpuOK) {
    enqueuePayload(createMPUPayload());
  }

  if (hx711OK) {
    enqueuePayload(createWeightPayload());
  }

  enqueuePayload(createGPSPayload());
}

// ======================================================
// LCD
// ======================================================

void printLCDLine2(const char* text) {
  lcd.setCursor(0, 1);
  lcd.print(text);

  int length = strlen(text);

  for (int i = length; i < 16; i++) {
    lcd.print(" ");
  }
}

void updateLCD() {
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");

  char line[17];

  switch (currentScreen) {
    case 0:
      if (isnan(temperature) || isnan(humidity)) {
        snprintf(line, sizeof(line), "T:ERR H:ERR");
      } else {
        snprintf(
          line,
          sizeof(line),
          "T:%4.1fC H:%4.1f%%",
          temperature,
          humidity);
      }
      break;

    case 1:
      snprintf(line, sizeof(line), "Light:%5.0f lux", lux);
      break;

    case 2:
      {
        float magnitude = sqrt(
          (ax * ax) + (ay * ay) + (az * az));

        snprintf(
          line,
          sizeof(line),
          "A:%5.2fg",
          magnitude);
        break;
      }

    case 3:
      snprintf(line, sizeof(line), "Tilt:%5.1f deg", tilt);
      break;

    case 4:
      if (gps.location.isValid()) {
        snprintf(
          line,
          sizeof(line),
          "Lat:%.6f",
          gps.location.lat());
      } else {
        snprintf(line, sizeof(line), "GPS: NO FIX");
      }
      break;

    case 5:
      if (gps.location.isValid()) {
        snprintf(
          line,
          sizeof(line),
          "Lon:%.6f",
          gps.location.lng());
      } else {
        snprintf(line, sizeof(line), "GPS: NO FIX");
      }
      break;

    case 6:
      if (gps.location.isValid()) {
        if (gps.satellites.isValid()) {
          snprintf(
            line,
            sizeof(line),
            "GPS FIX S:%d",
            gps.satellites.value());
        } else {
          snprintf(line, sizeof(line), "GPS: FIX");
        }
      } else {
        snprintf(line, sizeof(line), "GPS: NO FIX");
      }
      break;

    case 7:
      snprintf(
        line,
        sizeof(line),
        "W:%5.2fkg",
        weightKg);
      break;

    case 8:
      if (doorClosed) {
        snprintf(line, sizeof(line), "Door: CLOSED");
      } else {
        snprintf(line, sizeof(line), "Door: OPEN");
      }
      break;
  }

  printLCDLine2(line);
}

// ======================================================
// SERIAL
// ======================================================

void printSerialData() {
  Serial.println();
  Serial.println("================================");
  Serial.println("       TRACEVEDA TRUCK");
  Serial.println("================================");

  if (!isnan(temperature) && !isnan(humidity)) {
    Serial.print("Temperature: ");
    Serial.print(temperature, 2);
    Serial.println(" C");

    Serial.print("Humidity: ");
    Serial.print(humidity, 2);
    Serial.println(" %");
  } else {
    Serial.println("DHT22: READ ERROR");
  }

  Serial.print("Light: ");
  Serial.print(lux, 1);
  Serial.println(" lux");

  Serial.println();
  Serial.println("MPU-6500:");

  Serial.print("Accel g: X=");
  Serial.print(ax, 3);
  Serial.print(" Y=");
  Serial.print(ay, 3);
  Serial.print(" Z=");
  Serial.println(az, 3);

  Serial.print("Gyro dps: X=");
  Serial.print(gx, 2);
  Serial.print(" Y=");
  Serial.print(gy, 2);
  Serial.print(" Z=");
  Serial.println(gz, 2);

  Serial.print("Tilt: ");
  Serial.print(tilt, 2);
  Serial.println(" deg");

  Serial.print("Shock: ");
  Serial.println(shockDetected() ? "YES" : "NO");

  Serial.println();
  Serial.println("HX711:");

  Serial.print("Weight: ");
  Serial.print(weightKg, 3);
  Serial.println(" kg");

  Serial.print("Weight change: ");
  Serial.print(weightChangeKg, 3);
  Serial.println(" kg");

  Serial.println();
  Serial.println("GPS:");

  if (gps.location.isValid()) {
    Serial.println("Fix: VALID");
    Serial.print("Latitude: ");
    Serial.println(gps.location.lat(), 6);
    Serial.print("Longitude: ");
    Serial.println(gps.location.lng(), 6);
  } else {
    Serial.println("Fix: INVALID");
  }

  Serial.print("Door: ");
  Serial.println(doorClosed ? "CLOSED" : "OPEN");

  Serial.print("Red LED: ");
  Serial.println(redLedState ? "ON" : "OFF");

  Serial.print("RAM queue: ");
  Serial.println(queueCount);

  if (LittleFS.exists(BUFFER_FILE)) {
    File file = LittleFS.open(BUFFER_FILE, FILE_READ);

    if (file) {
      Serial.print("LittleFS bytes: ");
      Serial.println(file.size());
      file.close();
    }
  } else {
    Serial.println("LittleFS: EMPTY");
  }

  Serial.print("WiFi: ");

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("CONNECTED, IP=");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("DISCONNECTED");
  }

  Serial.println("================================");
}

// ======================================================
void uploadTask(void* parameter)
{
  (void)parameter;
  for (;;)
  {
    uploadBufferedData();
    processQueue();
    vTaskDelay(pdMS_TO_TICKS(UPLOAD_TASK_INTERVAL));
  }
}

// SETUP
// ======================================================

void setup() {
  Serial.begin(115200);

  queueMutex = xSemaphoreCreateMutex();
  fsMutex = xSemaphoreCreateMutex();
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("    TRACEVEDA TRUCK NODE FINAL");
  Serial.println("================================");

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(1200);

  // DHT22
  dht.begin();

  // Limit switch
  pinMode(LIMIT_SWITCH_PIN, INPUT_PULLUP);

  // Red LED
  pinMode(RED_LED_PIN, OUTPUT);
  digitalWrite(RED_LED_PIN, LOW);

  // BH1750
  if (
    lightMeter.begin(
      BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("BH1750 detected.");
  } else {
    Serial.println("BH1750 NOT detected.");
  }

  // MPU
  mpuOK = initializeMPU();

  if (mpuOK) {
    calibrateMPU();
  }

  // GPS
  GPS.begin(
    9600,
    SERIAL_8N1,
    GPS_RX,
    GPS_TX);

  Serial.println("GPS serial initialized.");

  // HX711
  scale.begin(HX711_DT, HX711_SCK);
  scale.set_scale(HX711_CALIBRATION_FACTOR);

  if (scale.is_ready()) {
    Serial.println("HX711 detected. Taring...");
    scale.tare(20);
    hx711OK = true;
    Serial.println("HX711 tare complete.");
  } else {
    Serial.println("HX711 NOT detected.");
  }

  // LittleFS
  if (LittleFS.begin(true)) {
    Serial.println("LittleFS initialized.");
  } else {
    Serial.println("LittleFS initialization FAILED.");
  }

  // Wi-Fi + NTP
  connectWiFi();


  // Initial values
  readMPU();
  readGPS();

  temperature = dht.readTemperature();
  humidity = dht.readHumidity();

  float initialLux = lightMeter.readLightLevel();
  if (initialLux >= 0) {
    lux = initialLux;
  }

  doorClosed = (digitalRead(LIMIT_SWITCH_PIN) == HIGH);

  readWeight();

  digitalWrite(
    RED_LED_PIN,
    LOW);

  redLedState = false;

  updateLCD();

  unsigned long now = millis();

  lastMPURead = now;
  lastDHTRead = now - DHT_INTERVAL;
  lastLightRead = now - LIGHT_INTERVAL;
  lastWeightRead = now - WEIGHT_INTERVAL;
  lastTelemetry = now - TELEMETRY_INTERVAL;
  lastLCDUpdate = now - LCD_INTERVAL;
  lastLCDScreenChange = now;
  lastSerialOutput = now - SERIAL_INTERVAL;
  lastWiFiCheck = now;


  xTaskCreatePinnedToCore(
    uploadTask,
    "UploadTask",
    8192,
    nullptr,
    1,
    &uploadTaskHandle,
    0
  );

  Serial.println("Truck Node initialized.");
}

// ======================================================
// LOOP
// ======================================================

void loop() {
  unsigned long now = millis();

  // GPS is read continuously.
  readGPS();

  // Door state is read continuously.
  doorClosed = (digitalRead(LIMIT_SWITCH_PIN) == HIGH);

  // MPU
  if (now - lastMPURead >= MPU_INTERVAL) {
    lastMPURead = now;
    readMPU();
  }

  // DHT22
  if (now - lastDHTRead >= DHT_INTERVAL) {
    lastDHTRead = now;

    float newTemperature = dht.readTemperature();
    float newHumidity = dht.readHumidity();

    if (!isnan(newTemperature)) {
      temperature = newTemperature;
    }

    if (!isnan(newHumidity)) {
      humidity = newHumidity;
    }
  }

  // BH1750
  if (now - lastLightRead >= LIGHT_INTERVAL) {
    lastLightRead = now;

    float newLux = lightMeter.readLightLevel();

    if (newLux >= 0) {
      lux = newLux;
    }
  }

  // HX711
  if (now - lastWeightRead >= WEIGHT_INTERVAL) {
    lastWeightRead = now;
    readWeight();
  }

  // Create one reading per registered sensor at the telemetry interval.
  if (now - lastTelemetry >= TELEMETRY_INTERVAL) {
    lastTelemetry = now;
    queueCurrentSensorData();

    Serial.println();
    Serial.println("Sensor set queued for backend.");
  }

  // LCD rotation
  if (now - lastLCDScreenChange >= SCREEN_INTERVAL) {
    lastLCDScreenChange = now;

    currentScreen++;

    if (currentScreen >= TOTAL_SCREENS) {
      currentScreen = 0;
    }
  }

  // LCD
  if (now - lastLCDUpdate >= LCD_INTERVAL) {
    lastLCDUpdate = now;
    updateLCD();
  }

  // Wi-Fi
  if (now - lastWiFiCheck >= WIFI_INTERVAL) {
    lastWiFiCheck = now;
    checkWiFi();
  }

  // Serial
  if (now - lastSerialOutput >= SERIAL_INTERVAL) {
    lastSerialOutput = now;
    printSerialData();
  }
}
