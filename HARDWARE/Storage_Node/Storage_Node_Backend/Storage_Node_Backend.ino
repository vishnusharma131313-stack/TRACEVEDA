#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <time.h>

// ======================================================
// TRACEVEDA STORAGE NODE
// Reliable Hardware + Backend Integration
//
// Hardware:
// DHT22 + BH1750 + Limit Switch + LCD + Red LED
//
// Backend:
// POST /api/iot/readings
//
// Data flow:
//
// Sensors
//    ↓
// RAM FIFO Queue
//    ↓
// Backend
//
// If backend unavailable:
// RAM FIFO → LittleFS
//
// When backend returns:
// LittleFS → Backend
//
// Priority:
// Fresh RAM readings are uploaded first.
// LittleFS backlog is uploaded when RAM queue is empty.
//
// RED LED:
// Backend response contains:
// "red_led": true / false
//
// ESP32 reads that response and controls GPIO 25.
// ======================================================


// ======================================================
// TRACEVEDA IDs
// ======================================================

const char* BATCH_ID = "ASH-2026-001";
const char* STORAGE_ID = "STR-0001";


// ======================================================
// BACKEND
// ======================================================

const char* BACKEND_URL =
  "";

const char* IOT_ENDPOINT =
  "/api/iot/readings";


// ======================================================
// WI-FI
// ======================================================

const char* ssid = "";
const char* password = "YOUR_WIFI_PASSWORD";


// ======================================================
// DHT22
// ======================================================

#define DHT_PIN 4
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);


// ======================================================
// LIMIT SWITCH
// ======================================================

#define LIMIT_SWITCH_PIN 27


// ======================================================
// RED LED
// ======================================================

#define RED_LED_PIN 25


// ======================================================
// I2C
// ======================================================

#define SDA_PIN 21
#define SCL_PIN 22


// ======================================================
// LCD
// ======================================================

#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 20
#define LCD_ROWS 4

LiquidCrystal_I2C lcd(
  LCD_ADDRESS,
  LCD_COLUMNS,
  LCD_ROWS);


// ======================================================
// BH1750
// ======================================================

BH1750 lightMeter;


// ======================================================
// SENSOR VALUES
// ======================================================

float temperature = NAN;
float humidity = NAN;
float lux = 0.0;

bool doorClosed = false;


// ======================================================
// BACKEND RED LED STATE
// ======================================================

bool redLedState = false;


// ======================================================
// TIMERS
// ======================================================

unsigned long lastSensorRead = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastWiFiCheck = 0;
unsigned long lastSerialOutput = 0;


// ======================================================
// INTERVALS
// ======================================================

const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long LCD_INTERVAL = 250;
const unsigned long WIFI_INTERVAL = 5000;
const unsigned long SERIAL_INTERVAL = 1000;


// ======================================================
// LITTLEFS BUFFER
// ======================================================

const char* BUFFER_FILE =
  "/iot_buffer.txt";

const char* TEMP_FILE =
  "/iot_buffer.tmp";


// Maximum logical buffer size.
//
// This is intentionally below the actual filesystem
// capacity so the application cannot grow indefinitely.
//

const size_t MAX_BUFFER_BYTES = 200 * 1024;


// ======================================================
// HTTP
// ======================================================
//
// 15 seconds is retained because Render can occasionally
// take several seconds to respond, especially after idle.
//
// The important fix is NOT simply increasing this timeout.
// The queue/upload architecture has been corrected.
//

const uint32_t HTTP_TIMEOUT = 15000;


// ======================================================
// RAM FIFO QUEUE
// ======================================================

const int QUEUE_SIZE = 12;

String payloadQueue[QUEUE_SIZE];

int queueHead = 0;
int queueTail = 0;
int queueCount = 0;


// ======================================================
// FREERTOS
// ======================================================

SemaphoreHandle_t queueMutex = nullptr;
SemaphoreHandle_t fsMutex = nullptr;

TaskHandle_t uploadTaskHandle = nullptr;


// Upload task wakes periodically.
//
// It can process more than one fast request per wake-up,
// but will never start another request while one is active.
//

const unsigned long UPLOAD_TASK_INTERVAL = 250;


// Maximum number of HTTP operations per task cycle.
//
// This allows fast backends to drain the queue quickly,
// while avoiding an uncontrolled upload loop.
//

const int MAX_UPLOADS_PER_CYCLE = 2;


// ======================================================
// FORWARD DECLARATIONS
// ======================================================

void bufferPayload(const String& payload);
bool sendPayload(const String& payload);

bool enqueuePayload(const String& payload);
bool peekQueue(String& payload);
bool dequeueQueue(String& payload);

bool uploadBufferedData();


// ======================================================
// QUEUE COUNT — THREAD SAFE
// ======================================================

int getQueueCount() {
  int count = 0;

  if (queueMutex != nullptr) {
    xSemaphoreTake(queueMutex, portMAX_DELAY);
  }

  count = queueCount;

  if (queueMutex != nullptr) {
    xSemaphoreGive(queueMutex);
  }

  return count;
}


// ======================================================
// QUEUE — ENQUEUE
// ======================================================

bool enqueuePayload(const String& payload) {
  bool storedInRAM = false;

  if (queueMutex != nullptr) {
    xSemaphoreTake(queueMutex, portMAX_DELAY);
  }

  if (queueCount < QUEUE_SIZE) {
    payloadQueue[queueTail] = payload;

    queueTail++;

    if (queueTail >= QUEUE_SIZE) {
      queueTail = 0;
    }

    queueCount++;

    storedInRAM = true;
  }

  if (queueMutex != nullptr) {
    xSemaphoreGive(queueMutex);
  }


  // ----------------------------------------------------
  // RAM FULL
  // ----------------------------------------------------

  if (!storedInRAM) {
    Serial.println(
      "RAM queue FULL -> LittleFS");

    bufferPayload(payload);

    return false;
  }

  return true;
}


// ======================================================
// QUEUE — PEEK
// ======================================================

bool peekQueue(String& payload) {
  bool available = false;

  if (queueMutex != nullptr) {
    xSemaphoreTake(queueMutex, portMAX_DELAY);
  }

  if (queueCount > 0) {
    payload = payloadQueue[queueHead];
    available = true;
  }

  if (queueMutex != nullptr) {
    xSemaphoreGive(queueMutex);
  }

  return available;
}


// ======================================================
// QUEUE — DEQUEUE
// ======================================================

bool dequeueQueue(String& payload) {
  bool available = false;

  if (queueMutex != nullptr) {
    xSemaphoreTake(queueMutex, portMAX_DELAY);
  }

  if (queueCount > 0) {
    payload = payloadQueue[queueHead];

    payloadQueue[queueHead] = "";

    queueHead++;

    if (queueHead >= QUEUE_SIZE) {
      queueHead = 0;
    }

    queueCount--;

    available = true;
  }

  if (queueMutex != nullptr) {
    xSemaphoreGive(queueMutex);
  }

  return available;
}


// ======================================================
// TIMESTAMP
// ======================================================

String getTimestamp() {
  time_t now = time(nullptr);

  struct tm timeinfo;

  localtime_r(
    &now,
    &timeinfo);

  char timestamp[32];

  strftime(
    timestamp,
    sizeof(timestamp),
    "%Y-%m-%dT%H:%M:%S",
    &timeinfo);

  return String(timestamp);
}


// ======================================================
// NTP SYNCHRONIZATION
// ======================================================

void synchronizeTime() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  configTime(
    19800,
    0,
    "pool.ntp.org",
    "time.nist.gov");

  Serial.println(
    "NTP time synchronization requested.");


  // ----------------------------------------------------
  // Wait briefly for valid time.
  //
  // Do not wait forever.
  // ----------------------------------------------------

  const unsigned long start = millis();

  while (
    time(nullptr) < 1700000000 && millis() - start < 5000) {
    delay(100);
  }

  if (time(nullptr) >= 1700000000) {
    Serial.println(
      "NTP synchronization PASSED.");
  } else {
    Serial.println(
      "NTP synchronization pending.");
  }
}


// ======================================================
// WI-FI CONNECTION
// ======================================================

void connectWiFi() {
  Serial.println();
  Serial.println(
    "================================");

  Serial.println(
    "          WI-FI CONNECTION");

  Serial.println(
    "================================");


  WiFi.mode(WIFI_STA);

  WiFi.setAutoReconnect(true);

  WiFi.persistent(false);

  WiFi.begin(
    ssid,
    password);


  Serial.print("Connecting");

  int attempts = 0;

  while (
    WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);

    Serial.print(".");

    attempts++;
  }

  Serial.println();


  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(
      "WiFi connected!");

    Serial.print(
      "SSID: ");

    Serial.println(
      WiFi.SSID());


    Serial.print(
      "IP Address: ");

    Serial.println(
      WiFi.localIP());


    Serial.print(
      "Signal Strength: ");

    Serial.print(
      WiFi.RSSI());

    Serial.println(
      " dBm");


    Serial.println(
      "Storage Node WiFi test PASSED.");


    synchronizeTime();
  } else {
    Serial.println(
      "WiFi connection FAILED!");

    Serial.println(
      "Storage Node will continue offline.");
  }


  Serial.println(
    "================================");
}


// ======================================================
// WI-FI RECONNECT
// ======================================================

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }


  Serial.println(
    "WiFi disconnected. Attempting reconnect...");


  // IMPORTANT:
  //
  // Do NOT call WiFi.disconnect() every 5 seconds.
  //
  // That can make recovery less stable.
  //

  WiFi.reconnect();

  // If reconnect does not start properly,
  // WiFi.begin() will be attempted.

  delay(50);

  if (WiFi.status() == WL_NO_SSID_AVAIL || WiFi.status() == WL_CONNECT_FAILED) {
    WiFi.begin(
      ssid,
      password);
  }
}


// ======================================================
// READ SENSORS
// ======================================================

void readSensors() {
  // ----------------------------------------------------
  // DHT22
  // ----------------------------------------------------

  float newTemperature =
    dht.readTemperature();

  float newHumidity =
    dht.readHumidity();


  if (
    !isnan(newTemperature) && !isnan(newHumidity)) {
    temperature = newTemperature;

    humidity = newHumidity;
  }


  // ----------------------------------------------------
  // BH1750
  // ----------------------------------------------------

  float newLux =
    lightMeter.readLightLevel();


  if (newLux >= 0) {
    lux = newLux;
  }


  // ----------------------------------------------------
  // LIMIT SWITCH
  // ----------------------------------------------------

  int switchState =
    digitalRead(
      LIMIT_SWITCH_PIN);


  doorClosed =
    (switchState == HIGH);
}


// ======================================================
// CREATE JSON — DHT22
// ======================================================

String createDHTPayload() {
  String json = "{";

  json += "\"batch_id\":\"";
  json += BATCH_ID;
  json += "\",";

  json += "\"storage_id\":\"";
  json += STORAGE_ID;
  json += "\",";

  json += "\"sensor_id\":\"IOT-DHT22-001\",";

  json += "\"timestamp\":\"";
  json += getTimestamp();
  json += "\",";


  if (!isnan(temperature)) {
    json += "\"temperature_c\":";
    json += String(
      temperature,
      2);
    json += ",";
  }


  if (!isnan(humidity)) {
    json += "\"humidity_percent\":";
    json += String(
      humidity,
      2);
    json += ",";
  }


  if (json.endsWith(",")) {
    json.remove(
      json.length() - 1);
  }


  json += "}";

  return json;
}


// ======================================================
// CREATE JSON — BH1750
// ======================================================

String createLightPayload() {
  String json = "{";

  json += "\"batch_id\":\"";
  json += BATCH_ID;
  json += "\",";

  json += "\"storage_id\":\"";
  json += STORAGE_ID;
  json += "\",";

  json += "\"sensor_id\":\"IOT-BH1750-001\",";

  json += "\"timestamp\":\"";
  json += getTimestamp();
  json += "\",";

  json += "\"light_intensity_lux\":";

  json += String(
    lux,
    2);

  json += "}";

  return json;
}


// ======================================================
// CREATE JSON — LIMIT SWITCH
// ======================================================

String createDoorPayload() {
  String json = "{";

  json += "\"batch_id\":\"";
  json += BATCH_ID;
  json += "\",";

  json += "\"storage_id\":\"";
  json += STORAGE_ID;
  json += "\",";

  json += "\"sensor_id\":\"IOT-LIMIT-001\",";

  json += "\"timestamp\":\"";
  json += getTimestamp();
  json += "\",";

  json += "\"switch_status\":\"";


  if (doorClosed) {
    json += "CLOSED";
  } else {
    json += "OPEN";
  }


  json += "\"";

  json += "}";

  return json;
}


// ======================================================
// APPLY BACKEND RED LED RESPONSE
// ======================================================

void processBackendLEDResponse(
  const String& response) {
  if (
    response.indexOf(
      "\"red_led\":true")
      >= 0
    || response.indexOf(
         "\"red_led\": true")
         >= 0) {
    redLedState = true;

    digitalWrite(
      RED_LED_PIN,
      HIGH);

    Serial.println(
      "Backend RED LED command: ON");

    return;
  }


  if (
    response.indexOf(
      "\"red_led\":false")
      >= 0
    || response.indexOf(
         "\"red_led\": false")
         >= 0) {
    redLedState = false;

    digitalWrite(
      RED_LED_PIN,
      LOW);

    Serial.println(
      "Backend RED LED command: OFF");

    return;
  }


  Serial.println(
    "Backend response contains no red_led command.");
}


// ======================================================
// SEND HTTP POST
// ======================================================

bool sendPayload(
  const String& payload) {
  if (
    WiFi.status() != WL_CONNECTED) {
    return false;
  }


  HTTPClient http;

  String url =
    String(BACKEND_URL) + String(IOT_ENDPOINT);


  Serial.println();
  Serial.println(
    "Backend upload attempt");


  // ----------------------------------------------------
  // Start HTTP
  // ----------------------------------------------------

  if (!http.begin(url)) {
    Serial.println(
      "HTTP begin FAILED.");

    return false;
  }


  http.addHeader(
    "Content-Type",
    "application/json");


  http.setTimeout(
    HTTP_TIMEOUT);


  // ----------------------------------------------------
  // POST
  // ----------------------------------------------------

  int httpCode =
    http.POST(payload);


  bool success = false;


  Serial.print(
    "HTTP Code: ");

  Serial.println(
    httpCode);


  // ----------------------------------------------------
  // SUCCESS
  // ----------------------------------------------------

  if (
    httpCode >= 200 && httpCode < 300) {
    success = true;


    String response =
      http.getString();


    Serial.println(
      "Backend response:");

    Serial.println(
      response);


    // --------------------------------------------------
    // BACKEND RED LED COMMAND
    // --------------------------------------------------

    processBackendLEDResponse(
      response);
  }


  // ----------------------------------------------------
  // FAILURE
  // ----------------------------------------------------

  else {
    Serial.println(
      "Backend upload failed.");


    if (httpCode > 0) {
      String errorResponse =
        http.getString();

      if (errorResponse.length() > 0) {
        Serial.println(
          "Backend error response:");

        Serial.println(
          errorResponse);
      }
    }
  }


  // ----------------------------------------------------
  // ALWAYS CLOSE CONNECTION
  // ----------------------------------------------------

  http.end();


  return success;
}


// ======================================================
// GET LITTLEFS BUFFER SIZE
// ======================================================
//
// Must be called while fsMutex is held.
//

size_t getBufferSizeLocked() {
  if (
    !LittleFS.exists(
      BUFFER_FILE)) {
    return 0;
  }


  File file =
    LittleFS.open(
      BUFFER_FILE,
      FILE_READ);


  if (!file) {
    return 0;
  }


  size_t size =
    file.size();


  file.close();


  return size;
}


// ======================================================
// CHECK LITTLEFS BUFFER SPACE
// ======================================================

bool bufferHasSpace(
  size_t payloadSize) {
  size_t currentSize =
    getBufferSizeLocked();


  // +1 for newline
  // +1 safety byte

  if (
    currentSize + payloadSize + 2 > MAX_BUFFER_BYTES) {
    return false;
  }


  return true;
}


// ======================================================
// APPEND PAYLOAD TO LITTLEFS
// ======================================================

void bufferPayload(
  const String& payload) {
  if (payload.length() == 0) {
    return;
  }


  if (fsMutex != nullptr) {
    xSemaphoreTake(
      fsMutex,
      portMAX_DELAY);
  }


  if (
    !bufferHasSpace(
      payload.length())) {
    Serial.println(
      "ERROR: LittleFS buffer FULL.");

    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return;
  }


  File file =
    LittleFS.open(
      BUFFER_FILE,
      FILE_APPEND);


  if (!file) {
    Serial.println(
      "ERROR: Could not open LittleFS buffer.");

    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return;
  }


  file.println(
    payload);

  file.close();


  if (fsMutex != nullptr) {
    xSemaphoreGive(fsMutex);
  }
}


// ======================================================
// READ FIRST BUFFERED READING
// ======================================================
//
// This function reads ONLY the first line.
//
// It does NOT load the entire LittleFS file into RAM.
//
// Returns:
//
// true  = reading found
// false = no valid reading
//
// firstLineEnd is the byte offset immediately after
// the first line. This is later used to remove exactly
// that reading from the file.
//
// ======================================================

bool getFirstBufferedPayload(
  String& payload,
  size_t& firstLineEnd) {
  payload = "";
  firstLineEnd = 0;


  if (fsMutex != nullptr) {
    xSemaphoreTake(
      fsMutex,
      portMAX_DELAY);
  }


  if (
    !LittleFS.exists(
      BUFFER_FILE)) {
    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return false;
  }


  File file =
    LittleFS.open(
      BUFFER_FILE,
      FILE_READ);


  if (!file) {
    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return false;
  }


  // ----------------------------------------------------
  // Skip empty lines if any.
  // ----------------------------------------------------

  while (file.available()) {
    String line =
      file.readStringUntil('\n');


    firstLineEnd =
      file.position();


    line.trim();


    if (line.length() > 0) {
      payload = line;

      file.close();


      if (fsMutex != nullptr) {
        xSemaphoreGive(fsMutex);
      }

      return true;
    }
  }


  // File contains no valid data.
  file.close();


  LittleFS.remove(
    BUFFER_FILE);


  if (fsMutex != nullptr) {
    xSemaphoreGive(fsMutex);
  }


  return false;
}


// ======================================================
// REBUILD LITTLEFS AFTER BUFFERED UPLOAD
// ======================================================
//
// CRITICAL FIX:
//
// The old code read the entire file before upload,
// then read the entire file AGAIN after upload,
// and appended the already-existing data again.
//
// That caused duplication and explosive buffer growth.
//
// This version:
//
// 1. Records the end of the first line.
// 2. Releases FS mutex while HTTP happens.
// 3. New readings may safely append to the file.
// 4. After HTTP completes, it copies ONLY the bytes
//    after the original first line.
//
// Therefore:
//
// SUCCESS:
//     remove first reading
//
// FAILURE:
//     retain first reading
//
// New readings appended during HTTP are preserved.
//
// ======================================================

bool removeFirstBufferedPayload(
  size_t firstLineEnd,
  bool uploaded,
  const String& firstPayload) {
  if (fsMutex != nullptr) {
    xSemaphoreTake(
      fsMutex,
      portMAX_DELAY);
  }


  File source =
    LittleFS.open(
      BUFFER_FILE,
      FILE_READ);


  if (!source) {
    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return false;
  }


  size_t currentSize =
    source.size();


  // ----------------------------------------------------
  // Sanity check.
  //
  // The file should never shrink while HTTP is running.
  // It can only grow because new readings are appended.
  // ----------------------------------------------------

  if (
    currentSize < firstLineEnd) {
    source.close();

    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    Serial.println(
      "ERROR: LittleFS buffer changed unexpectedly.");

    return false;
  }


  // ----------------------------------------------------
  // Create temporary file.
  // ----------------------------------------------------

  LittleFS.remove(
    TEMP_FILE);


  File temp =
    LittleFS.open(
      TEMP_FILE,
      FILE_WRITE);


  if (!temp) {
    source.close();

    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    Serial.println(
      "ERROR: Could not create LittleFS temp file.");

    return false;
  }


  // ----------------------------------------------------
  // If upload failed, preserve the first payload.
  // ----------------------------------------------------

  if (!uploaded) {
    temp.println(
      firstPayload);
  }


  // ----------------------------------------------------
  // Skip the first payload from the old file.
  // ----------------------------------------------------

  source.seek(
    firstLineEnd);


  // ----------------------------------------------------
  // Copy remaining data in chunks.
  //
  // This avoids creating a huge String.
  // ----------------------------------------------------

  uint8_t buffer[256];


  while (source.available()) {
    size_t available =
      source.available();


    size_t toRead =
      available;


    if (toRead > sizeof(buffer)) {
      toRead = sizeof(buffer);
    }


    size_t bytesRead =
      source.read(
        buffer,
        toRead);


    if (bytesRead == 0) {
      break;
    }


    size_t written =
      temp.write(
        buffer,
        bytesRead);


    if (written != bytesRead) {
      Serial.println(
        "ERROR: LittleFS temp write failed.");

      source.close();
      temp.close();

      LittleFS.remove(
        TEMP_FILE);

      if (fsMutex != nullptr) {
        xSemaphoreGive(fsMutex);
      }

      return false;
    }
  }


  source.close();
  temp.close();


  // ----------------------------------------------------
  // Replace original file.
  // ----------------------------------------------------

  LittleFS.remove(
    BUFFER_FILE);


  if (
    !LittleFS.rename(
      TEMP_FILE,
      BUFFER_FILE)) {
    Serial.println(
      "ERROR: LittleFS rename failed.");

    LittleFS.remove(
      TEMP_FILE);

    if (fsMutex != nullptr) {
      xSemaphoreGive(fsMutex);
    }

    return false;
  }


  if (fsMutex != nullptr) {
    xSemaphoreGive(fsMutex);
  }


  return true;
}


// ======================================================
// UPLOAD ONE BUFFERED READING
// ======================================================

bool uploadBufferedData() {
  if (
    WiFi.status() != WL_CONNECTED) {
    return false;
  }


  String firstPayload;

  size_t firstLineEnd = 0;


  // ----------------------------------------------------
  // Get oldest reading.
  // ----------------------------------------------------

  if (
    !getFirstBufferedPayload(
      firstPayload,
      firstLineEnd)) {
    return false;
  }


  if (firstPayload.length() == 0) {
    return false;
  }


  // ----------------------------------------------------
  // HTTP happens WITHOUT fsMutex.
  //
  // This is extremely important.
  //
  // New sensor readings can still be written to
  // LittleFS while this HTTP request is waiting.
  // ----------------------------------------------------

  bool uploaded =
    sendPayload(
      firstPayload);


  // ----------------------------------------------------
  // Remove exactly one reading.
  // ----------------------------------------------------

  bool rebuilt =
    removeFirstBufferedPayload(
      firstLineEnd,
      uploaded,
      firstPayload);


  if (!rebuilt) {
    Serial.println(
      "WARNING: Could not update LittleFS buffer.");

    return false;
  }


  if (uploaded) {
    Serial.println(
      "Oldest buffered reading uploaded.");
  } else {
    Serial.println(
      "Buffered reading retained for retry.");
  }


  return uploaded;
}


// ======================================================
// QUEUE CURRENT SENSOR DATA
// ======================================================

void sendCurrentData() {
  // ----------------------------------------------------
  // DHT22
  // ----------------------------------------------------

  if (
    !isnan(temperature) && !isnan(humidity)) {
    String payload =
      createDHTPayload();

    enqueuePayload(
      payload);
  }


  // ----------------------------------------------------
  // BH1750
  // ----------------------------------------------------

  {
    String payload =
      createLightPayload();

    enqueuePayload(
      payload);
  }


  // ----------------------------------------------------
  // LIMIT SWITCH
  // ----------------------------------------------------

  {
    String payload =
      createDoorPayload();

    enqueuePayload(
      payload);
  }
}


// ======================================================
// PROCESS ONE RAM QUEUED READING
// ======================================================
//
// IMPORTANT:
//
// We remove the item from RAM ONLY after a successful
// backend upload.
//
// If upload fails, the item is moved to LittleFS.
//
// ======================================================

bool processOneRAMReading() {
  String payload;


  if (
    !peekQueue(payload)) {
    return false;
  }


  // ----------------------------------------------------
  // Try upload.
  // ----------------------------------------------------

  if (
    sendPayload(payload)) {
    // Successful upload.
    // NOW remove from RAM.

    String discarded;

    dequeueQueue(
      discarded);

    return true;
  }


  // ----------------------------------------------------
  // Backend unavailable.
  //
  // Move this exact reading to LittleFS.
  // ----------------------------------------------------

  bufferPayload(
    payload);


  String discarded;

  dequeueQueue(
    discarded);


  Serial.println(
    "RAM reading moved to LittleFS.");


  return false;
}


// ======================================================
// UPLOAD TASK
// ======================================================
//
// Priority:
//
// 1. RAM queue
// 2. LittleFS backlog
//
// This prevents an old flash backlog from starving
// freshly generated readings.
//
// ======================================================

void uploadTask(void* parameter) {
  (void)parameter;


  for (;;) {
    int uploadsThisCycle = 0;


    // --------------------------------------------------
    // FIRST PRIORITY: RAM QUEUE
    // --------------------------------------------------

    while (
      uploadsThisCycle < MAX_UPLOADS_PER_CYCLE) {
      if (
        getQueueCount() == 0) {
        break;
      }


      bool success =
        processOneRAMReading();


      uploadsThisCycle++;


      // ------------------------------------------------
      // If upload failed, do NOT immediately hammer
      // the backend again.
      // ------------------------------------------------

      if (!success) {
        break;
      }
    }


    // --------------------------------------------------
    // SECOND PRIORITY: LITTLEFS
    //
    // Only touch old flash data when RAM is empty.
    // --------------------------------------------------

    if (
      getQueueCount() == 0 && uploadsThisCycle < MAX_UPLOADS_PER_CYCLE) {
      uploadBufferedData();
    }


    vTaskDelay(
      pdMS_TO_TICKS(
        UPLOAD_TASK_INTERVAL));
  }
}


// ======================================================
// UPDATE LCD
// ======================================================

void updateLCD() {
  // ==================================================
  // LINE 1
  // ==================================================

  lcd.setCursor(
    0,
    0);

  lcd.print(
    "TRACEVEDA STORAGE   ");


  // ==================================================
  // LINE 2
  // ==================================================

  lcd.setCursor(
    0,
    1);


  if (
    isnan(temperature) || isnan(humidity)) {
    lcd.print(
      "T:ERROR H:ERROR     ");
  } else {
    lcd.print(
      "T:");

    lcd.print(
      temperature,
      1);

    lcd.print(
      (char)223);

    lcd.print(
      "C H:");

    lcd.print(
      humidity,
      1);

    lcd.print(
      "%   ");
  }


  // ==================================================
  // LINE 3
  // ==================================================

  lcd.setCursor(
    0,
    2);

  lcd.print(
    "Light: ");

  lcd.print(
    lux,
    0);

  lcd.print(
    " lux      ");


  // ==================================================
  // LINE 4
  // ==================================================

  lcd.setCursor(
    0,
    3);

  lcd.print(
    "Door: ");


  if (doorClosed) {
    lcd.print(
      "CLOSED");
  } else {
    lcd.print(
      "OPEN  ");
  }


  lcd.print(
    "        ");
}


// ======================================================
// SERIAL OUTPUT
// ======================================================

void printSerialData() {
  Serial.println();

  Serial.println(
    "================================");

  Serial.println(
    "      STORAGE NODE DATA");

  Serial.println(
    "================================");


  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  if (
    isnan(temperature) || isnan(humidity)) {
    Serial.println(
      "DHT22: READ ERROR");
  } else {
    Serial.print(
      "Temperature: ");

    Serial.print(
      temperature,
      1);

    Serial.println(
      " C");


    Serial.print(
      "Humidity: ");

    Serial.print(
      humidity,
      1);

    Serial.println(
      " %");
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  Serial.print(
    "Light: ");

  Serial.print(
    lux,
    1);

  Serial.println(
    " lux");


  // --------------------------------------------------
  // Door
  // --------------------------------------------------

  Serial.print(
    "Door: ");


  if (doorClosed) {
    Serial.println(
      "CLOSED");
  } else {
    Serial.println(
      "OPEN");
  }


  // --------------------------------------------------
  // RED LED
  // --------------------------------------------------

  Serial.print(
    "Red LED: ");


  if (redLedState) {
    Serial.println(
      "ON");
  } else {
    Serial.println(
      "OFF");
  }


  // --------------------------------------------------
  // Wi-Fi
  // --------------------------------------------------

  Serial.print(
    "WiFi: ");


  if (
    WiFi.status() == WL_CONNECTED) {
    Serial.println(
      "CONNECTED");


    Serial.print(
      "IP: ");

    Serial.println(
      WiFi.localIP());
  } else {
    Serial.println(
      "DISCONNECTED");
  }


  // --------------------------------------------------
  // LittleFS buffer
  // --------------------------------------------------

  size_t bufferedBytes = 0;


  if (fsMutex != nullptr) {
    xSemaphoreTake(
      fsMutex,
      portMAX_DELAY);
  }


  bufferedBytes =
    getBufferSizeLocked();


  if (fsMutex != nullptr) {
    xSemaphoreGive(fsMutex);
  }


  if (bufferedBytes > 0) {
    Serial.print(
      "Buffered bytes: ");

    Serial.println(
      bufferedBytes);
  } else {
    Serial.println(
      "Buffered data: NONE");
  }


  // --------------------------------------------------
  // RAM queue
  // --------------------------------------------------

  Serial.print(
    "RAM queue items: ");

  Serial.println(
    getQueueCount());


  Serial.println(
    "================================");
}


// ======================================================
// SETUP
// ======================================================

void setup() {
  Serial.begin(
    115200);


  // ==================================================
  // FREERTOS MUTEXES
  // ==================================================

  queueMutex =
    xSemaphoreCreateMutex();

  fsMutex =
    xSemaphoreCreateMutex();


  delay(1000);


  // ==================================================
  // I2C
  // ==================================================

  Wire.begin(
    SDA_PIN,
    SCL_PIN);


  // ==================================================
  // LCD
  // ==================================================

  lcd.init();

  lcd.backlight();


  lcd.setCursor(
    0,
    0);

  lcd.print(
    "TRACEVEDA STORAGE");


  lcd.setCursor(
    0,
    1);

  lcd.print(
    "Node Starting...");


  delay(1500);


  // ==================================================
  // DHT22
  // ==================================================

  dht.begin();


  // ==================================================
  // LIMIT SWITCH
  // ==================================================

  pinMode(
    LIMIT_SWITCH_PIN,
    INPUT_PULLUP);


  // ==================================================
  // RED LED
  // ==================================================

  pinMode(
    RED_LED_PIN,
    OUTPUT);


  digitalWrite(
    RED_LED_PIN,
    LOW);


  // ==================================================
  // BH1750
  // ==================================================

  if (
    lightMeter.begin(
      BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println(
      "BH1750 detected!");
  } else {
    Serial.println(
      "BH1750 NOT detected!");
  }


  // ==================================================
  // LITTLEFS
  // ==================================================
  //
  // IMPORTANT:
  //
  // false means:
  // DO NOT FORMAT automatically if mount fails.
  //
  // This protects persisted sensor data.
  //

  if (
    LittleFS.begin(false)) {
    Serial.println(
      "LittleFS initialized.");
  } else {
    Serial.println(
      "LittleFS initialization FAILED!");

    Serial.println(
      "WARNING: Persistent buffering unavailable.");
  }


  // ==================================================
  // WI-FI
  // ==================================================

  connectWiFi();


  // ==================================================
  // INITIAL SENSOR READ
  // ==================================================

  readSensors();


  // ==================================================
  // INITIAL LCD
  // ==================================================

  lcd.clear();

  updateLCD();


  // ==================================================
  // TIMERS
  // ==================================================

  unsigned long now =
    millis();


  lastSensorRead =
    now;

  lastLCDUpdate =
    now;

  lastWiFiCheck =
    now;

  lastSerialOutput =
    now;


  Serial.println();


  // ==================================================
  // UPLOAD TASK
  // ==================================================

  xTaskCreatePinnedToCore(
    uploadTask,
    "UploadTask",
    8192,
    nullptr,
    1,
    &uploadTaskHandle,
    0);


  Serial.println(
    "Storage Node initialized.");
}


// ======================================================
// LOOP
// ======================================================

void loop() {
  unsigned long now =
    millis();


  // ==================================================
  // LIMIT SWITCH
  // ==================================================

  int switchState =
    digitalRead(
      LIMIT_SWITCH_PIN);


  bool newDoorClosed =
    (switchState == HIGH);


  if (
    newDoorClosed != doorClosed) {
    doorClosed =
      newDoorClosed;


    // Immediate LCD response
    updateLCD();
  }


  // ==================================================
  // SENSOR READ
  // ==================================================

  if (
    now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead =
      now;


    readSensors();


    // Queue fresh sensor readings
    sendCurrentData();
  }


  // ==================================================
  // LCD UPDATE
  // ==================================================

  if (
    now - lastLCDUpdate >= LCD_INTERVAL) {
    lastLCDUpdate =
      now;


    updateLCD();
  }


  // ==================================================
  // WI-FI CHECK
  // ==================================================

  if (
    now - lastWiFiCheck >= WIFI_INTERVAL) {
    lastWiFiCheck =
      now;


    checkWiFi();
  }


  // ==================================================
  // SERIAL
  // ==================================================

  if (
    now - lastSerialOutput >= SERIAL_INTERVAL) {
    lastSerialOutput =
      now;


    printSerialData();
  }
}