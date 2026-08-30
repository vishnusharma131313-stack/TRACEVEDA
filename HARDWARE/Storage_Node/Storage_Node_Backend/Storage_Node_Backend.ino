#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <time.h>
#include <WiFiClientSecure.h>

// ======================================================
// TRACEVEDA STORAGE NODE
// Final Hardware + Backend Integration
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
// RED LED:
// Backend response contains:
// "red_led": true / false
//
// ESP32 reads that response and controls GPIO 25.
// ======================================================


// ======================================================
// TRACEVEDA IDs
// ======================================================

const char* BATCH_ID   = "ASH-2026-001";
const char* STORAGE_ID = "STR-0001";


// ======================================================
// BACKEND
// ======================================================
//
// Replace YOUR_PC_IP with the backend PC's LAN IP.
//
// Example:
// http://192.168.1.105:8000
//
// DO NOT use:
// localhost
// 127.0.0.1
//
// Uvicorn must listen on:
// 0.0.0.0
//
// ======================================================

const char* BACKEND_URL =
  "https://traceveda.onrender.com";

const char* IOT_ENDPOINT =
  "/api/iot/readings";

// ======================================================
// DEVICE AUTHENTICATION
// ======================================================
//
// POST /api/iot/readings now requires this node to identify
// itself. Send it as the X-Device-Key header.
//
// The value must match TRACEVEDA_DEVICE_API_KEY in
// BACKEND/.env. If that variable is unset the backend logs a
// warning and accepts the development key below, so an
// unconfigured demo still works - but set both for anything
// reachable from outside your LAN.
//
// ======================================================

const char* DEVICE_API_KEY = "traceveda-dev-device-key";



// ======================================================
// WI-FI
// ======================================================
//
// Keep real credentials OUT of GitHub.
//
// For local testing, enter them here temporarily.
// Before pushing to GitHub, replace with placeholders
// or move credentials into a separate private file.
//
// ======================================================

const char* ssid = "YOUR_WIFI_SSID";
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
  LCD_ROWS
);


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
//
// This state is controlled by the backend response.
//
// true  -> RED LED ON
// false -> RED LED OFF
//
// If a response does not contain red_led, the previous
// state is retained.
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

const char* REMAINING_FILE =
  "/iot_remaining.txt";


// Maximum allowed LittleFS buffer size.
// Prevents unlimited flash growth.

const size_t MAX_BUFFER_BYTES = 200 * 1024;


// ======================================================
// RAM FIFO QUEUE
// ======================================================

const int QUEUE_SIZE = 12;

String payloadQueue[QUEUE_SIZE];

int queueHead = 0;
int queueTail = 0;
int queueCount = 0;

SemaphoreHandle_t queueMutex = nullptr;
SemaphoreHandle_t fsMutex = nullptr;
TaskHandle_t uploadTaskHandle = nullptr;
const unsigned long UPLOAD_TASK_INTERVAL = 500;


// ======================================================
// FORWARD DECLARATIONS
// ======================================================

void bufferPayload(const String& payload);
bool sendPayload(const String& payload);


// ======================================================
// QUEUE — ENQUEUE
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


// ======================================================
// QUEUE — PEEK
// ======================================================

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


// ======================================================
// QUEUE — DEQUEUE
// ======================================================

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

String getTimestamp()
{
  time_t now = time(nullptr);

  struct tm timeinfo;

  localtime_r(
    &now,
    &timeinfo
  );

  char timestamp[32];

  strftime(
    timestamp,
    sizeof(timestamp),
    "%Y-%m-%dT%H:%M:%S",
    &timeinfo
  );

  return String(timestamp);
}


// ======================================================
// WI-FI CONNECTION
// ======================================================

void connectWiFi()
{
  Serial.println();
  Serial.println("================================");
  Serial.println("          WI-FI CONNECTION");
  Serial.println("================================");

  WiFi.mode(WIFI_STA);

  WiFi.begin(
    ssid,
    password
  );

  Serial.print("Connecting");

  int attempts = 0;

  while (
    WiFi.status() != WL_CONNECTED &&
    attempts < 30
  )
  {
    delay(500);

    Serial.print(".");

    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("WiFi connected!");

    Serial.print("SSID: ");
    Serial.println(WiFi.SSID());

    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");

    Serial.println(
      "Storage Node WiFi test PASSED."
    );

    // --------------------------------------------------
    // NTP
    // --------------------------------------------------

    configTime(
      19800,
      0,
      "pool.ntp.org",
      "time.nist.gov"
    );

    Serial.println(
      "NTP time synchronization requested."
    );
  }
  else
  {
    Serial.println(
      "WiFi connection FAILED!"
    );

    Serial.println(
      "Storage Node will continue offline."
    );
  }

  Serial.println(
    "================================"
  );
}


// ======================================================
// WI-FI RECONNECT
// ======================================================

void checkWiFi()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    return;
  }

  Serial.println(
    "WiFi disconnected. Attempting reconnect..."
  );

  WiFi.disconnect();

  WiFi.begin(
    ssid,
    password
  );
}


// ======================================================
// READ SENSORS
// ======================================================

void readSensors()
{
  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  float newTemperature =
    dht.readTemperature();

  float newHumidity =
    dht.readHumidity();

  if (
    !isnan(newTemperature) &&
    !isnan(newHumidity)
  )
  {
    temperature = newTemperature;
    humidity = newHumidity;
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  float newLux =
    lightMeter.readLightLevel();

  if (newLux >= 0)
  {
    lux = newLux;
  }


  // --------------------------------------------------
  // LIMIT SWITCH
  // --------------------------------------------------

  int switchState =
    digitalRead(
      LIMIT_SWITCH_PIN
    );

  doorClosed =
    (switchState == HIGH);
}


// ======================================================
// CREATE JSON — DHT22
// ======================================================

String createDHTPayload()
{
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

  if (!isnan(temperature))
  {
    json += "\"temperature_c\":";
    json += String(
      temperature,
      2
    );
    json += ",";
  }

  if (!isnan(humidity))
  {
    json += "\"humidity_percent\":";
    json += String(
      humidity,
      2
    );
    json += ",";
  }

  if (json.endsWith(","))
  {
    json.remove(
      json.length() - 1
    );
  }

  json += "}";

  return json;
}


// ======================================================
// CREATE JSON — BH1750
// ======================================================

String createLightPayload()
{
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
    2
  );

  json += "}";

  return json;
}


// ======================================================
// CREATE JSON — LIMIT SWITCH
// ======================================================

String createDoorPayload()
{
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

  if (doorClosed)
  {
    json += "CLOSED";
  }
  else
  {
    json += "OPEN";
  }

  json += "\"";

  json += "}";

  return json;
}


// ======================================================
// APPLY BACKEND RED LED RESPONSE
// ======================================================
//
// Expected backend response:
//
// {
//   ...,
//   "red_led": true
// }
//
// or:
//
// {
//   ...,
//   "red_led": false
// }
//
// We intentionally do not create a new request field.
// red_led is read ONLY from the backend response.
// ======================================================

void processBackendLEDResponse(
  const String& response
)
{
  if (
    response.indexOf("\"red_led\":true") >= 0 ||
    response.indexOf("\"red_led\": true") >= 0
  )
  {
    redLedState = true;

    digitalWrite(
      RED_LED_PIN,
      HIGH
    );

    Serial.println(
      "Backend RED LED command: ON"
    );

    return;
  }

  if (
    response.indexOf("\"red_led\":false") >= 0 ||
    response.indexOf("\"red_led\": false") >= 0
  )
  {
    redLedState = false;

    digitalWrite(
      RED_LED_PIN,
      LOW
    );

    Serial.println(
      "Backend RED LED command: OFF"
    );

    return;
  }

  Serial.println(
    "Backend response contains no red_led command."
  );
}


// ======================================================
// SEND HTTP POST
// ======================================================

bool sendPayload(
  const String& payload
)
{
  if (
    WiFi.status() != WL_CONNECTED
  )
  {
    return false;
  }
  WiFiClientSecure client;
client.setInsecure();

  HTTPClient http;

  String url =
    String(BACKEND_URL) +
    String(IOT_ENDPOINT);

 http.begin(client, url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  // Identifies this node to the backend. Without it the
  // request is rejected with 401.
  http.addHeader(
    "X-Device-Key",
    DEVICE_API_KEY
  );

  http.setTimeout(15000);

Serial.println("================================");
Serial.println("SENDING TO BACKEND");
Serial.println(url);
Serial.println("PAYLOAD:");
Serial.println(payload);
Serial.println("================================");

int httpCode = http.POST(payload);

  bool success = false;

  Serial.println();
  Serial.println(
    "Backend upload attempt"
  );

  Serial.print("HTTP Code: ");
  Serial.println(httpCode);

  if (
    httpCode >= 200 &&
    httpCode < 300
  )
  {
    success = true;

    String response =
      http.getString();

    Serial.println(
      "Backend response:"
    );

    Serial.println(response);

    // --------------------------------------------------
    // BACKEND RED LED COMMAND
    // --------------------------------------------------

    processBackendLEDResponse(response);
  }
  else
  {
    Serial.println(
      "Backend upload failed."
    );

    if (httpCode > 0)
    {
      Serial.println(
        http.getString()
      );
    }
  }

  http.end();

  return success;
}


// ======================================================
// CHECK LITTLEFS BUFFER SIZE
// ======================================================

bool bufferHasSpace(
  size_t payloadSize
)
{
  size_t currentSize = 0;

  if (
    LittleFS.exists(BUFFER_FILE)
  )
  {
    File file =
      LittleFS.open(
        BUFFER_FILE,
        FILE_READ
      );

    if (file)
    {
      currentSize = file.size();
      file.close();
    }
  }

  if (
    currentSize +
    payloadSize +
    2 >
    MAX_BUFFER_BYTES
  )
  {
    return false;
  }

  return true;
}


// ======================================================
// APPEND PAYLOAD TO LITTLEFS
// ======================================================

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
// UPLOAD ONE BUFFERED READING
// ======================================================
//
// Only one buffered payload is processed per call.
// This prevents long blocking operations.
//
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
// QUEUE CURRENT SENSOR DATA
// ======================================================

void sendCurrentData()
{
  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  if (
    !isnan(temperature) &&
    !isnan(humidity)
  )
  {
    String payload =
      createDHTPayload();

    enqueuePayload(payload);
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  {
    String payload =
      createLightPayload();

    enqueuePayload(payload);
  }


  // --------------------------------------------------
  // LIMIT SWITCH
  // --------------------------------------------------

  {
    String payload =
      createDoorPayload();

    enqueuePayload(payload);
  }
}


// ======================================================
// PROCESS ONE RAM QUEUED READING
// ======================================================

void processQueue()
{
  String payload;
  if (!peekQueue(payload)) return;
  if (sendPayload(payload)) dequeuePayload();
  else { bufferPayload(payload); dequeuePayload(); }
}


// ======================================================
// UPDATE LCD
// ======================================================
//
// IMPORTANT:
// Layout intentionally unchanged from tested version.
//
// ======================================================

void updateLCD()
{
  // ==================================================
  // LINE 1
  // ==================================================

  lcd.setCursor(0, 0);

  lcd.print(
    "TRACEVEDA STORAGE   "
  );


  // ==================================================
  // LINE 2
  // ==================================================

  lcd.setCursor(0, 1);

  if (
    isnan(temperature) ||
    isnan(humidity)
  )
  {
    lcd.print(
      "T:ERROR H:ERROR     "
    );
  }
  else
  {
    lcd.print("T:");

    lcd.print(
      temperature,
      1
    );

    lcd.print((char)223);

    lcd.print("C H:");

    lcd.print(
      humidity,
      1
    );

    lcd.print("%   ");
  }


  // ==================================================
  // LINE 3
  // ==================================================

  lcd.setCursor(0, 2);

  lcd.print("Light: ");

  lcd.print(
    lux,
    0
  );

  lcd.print(
    " lux      "
  );


  // ==================================================
  // LINE 4
  // ==================================================

  lcd.setCursor(0, 3);

  lcd.print("Door: ");

  if (doorClosed)
  {
    lcd.print("CLOSED");
  }
  else
  {
    lcd.print("OPEN  ");
  }

  lcd.print("        ");
}


// ======================================================
// SERIAL OUTPUT
// ======================================================

void printSerialData()
{
  Serial.println();
  Serial.println(
    "================================"
  );

  Serial.println(
    "      STORAGE NODE DATA"
  );

  Serial.println(
    "================================"
  );


  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  if (
    isnan(temperature) ||
    isnan(humidity)
  )
  {
    Serial.println(
      "DHT22: READ ERROR"
    );
  }
  else
  {
    Serial.print(
      "Temperature: "
    );

    Serial.print(
      temperature,
      1
    );

    Serial.println(" C");

    Serial.print(
      "Humidity: "
    );

    Serial.print(
      humidity,
      1
    );

    Serial.println(" %");
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  Serial.print(
    "Light: "
  );

  Serial.print(
    lux,
    1
  );

  Serial.println(" lux");


  // --------------------------------------------------
  // Door
  // --------------------------------------------------

  Serial.print(
    "Door: "
  );

  if (doorClosed)
  {
    Serial.println("CLOSED");
  }
  else
  {
    Serial.println("OPEN");
  }


  // --------------------------------------------------
  // RED LED
  // --------------------------------------------------

  Serial.print(
    "Red LED: "
  );

  if (redLedState)
  {
    Serial.println("ON");
  }
  else
  {
    Serial.println("OFF");
  }


  // --------------------------------------------------
  // Wi-Fi
  // --------------------------------------------------

  Serial.print(
    "WiFi: "
  );

  if (
    WiFi.status() == WL_CONNECTED
  )
  {
    Serial.println(
      "CONNECTED"
    );

    Serial.print(
      "IP: "
    );

    Serial.println(
      WiFi.localIP()
    );
  }
  else
  {
    Serial.println(
      "DISCONNECTED"
    );
  }


  // --------------------------------------------------
  // LittleFS buffer
  // --------------------------------------------------

  if (
    LittleFS.exists(BUFFER_FILE)
  )
  {
    File file =
      LittleFS.open(
        BUFFER_FILE,
        FILE_READ
      );

    if (file)
    {
      Serial.print(
        "Buffered bytes: "
      );

      Serial.println(
        file.size()
      );

      file.close();
    }
  }
  else
  {
    Serial.println(
      "Buffered data: NONE"
    );
  }


  // --------------------------------------------------
  // RAM queue
  // --------------------------------------------------

  Serial.print(
    "RAM queue items: "
  );

  Serial.println(
    queueCount
  );


  Serial.println(
    "================================"
  );
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

void setup()
{
  Serial.begin(115200);

  queueMutex = xSemaphoreCreateMutex();
  fsMutex = xSemaphoreCreateMutex();

  delay(1000);


  // ==================================================
  // I2C
  // ==================================================

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );


  // ==================================================
  // LCD
  // ==================================================

  lcd.init();

  lcd.backlight();

  lcd.setCursor(0, 0);

  lcd.print(
    "TRACEVEDA STORAGE"
  );

  lcd.setCursor(0, 1);

  lcd.print(
    "Node Starting..."
  );

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
    INPUT_PULLUP
  );


  // ==================================================
  // RED LED
  // ==================================================

  pinMode(
    RED_LED_PIN,
    OUTPUT
  );

  digitalWrite(
    RED_LED_PIN,
    LOW
  );


  // ==================================================
  // BH1750
  // ==================================================

  if (
    lightMeter.begin(
      BH1750::CONTINUOUS_HIGH_RES_MODE
    )
  )
  {
    Serial.println(
      "BH1750 detected!"
    );
  }
  else
  {
    Serial.println(
      "BH1750 NOT detected!"
    );
  }


  // ==================================================
  // LITTLEFS
  // ==================================================

  if (
    LittleFS.begin(true)
  )
  {
    Serial.println(
      "LittleFS initialized."
    );
  }
  else
  {
    Serial.println(
      "LittleFS initialization FAILED!"
    );
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

  lastSensorRead = now;
  lastLCDUpdate = now;
  lastWiFiCheck = now;
  lastSerialOutput = now;


  Serial.println();

  xTaskCreatePinnedToCore(
    uploadTask,
    "UploadTask",
    8192,
    nullptr,
    1,
    &uploadTaskHandle,
    0
  );

  Serial.println(
    "Storage Node initialized."
  );
}


// ======================================================
// LOOP
// ======================================================

void loop()
{
  unsigned long now =
    millis();


  // ==================================================
  // LIMIT SWITCH
  // ==================================================

  int switchState =
    digitalRead(
      LIMIT_SWITCH_PIN
    );

  bool newDoorClosed =
    (switchState == HIGH);

  if (
    newDoorClosed != doorClosed
  )
  {
    doorClosed =
      newDoorClosed;

    // Immediate LCD response
    updateLCD();
  }


  // ==================================================
  // SENSOR READ
  // ==================================================

  if (
    now - lastSensorRead >=
    SENSOR_INTERVAL
  )
  {
    lastSensorRead = now;

    readSensors();

    // Queue fresh sensor readings
    sendCurrentData();
  }


  // ==================================================
  // LCD UPDATE
  // ==================================================

  if (
    now - lastLCDUpdate >=
    LCD_INTERVAL
  )
  {
    lastLCDUpdate = now;

    updateLCD();
  }


  // ==================================================
  // WI-FI CHECK
  // ==================================================

  if (
    now - lastWiFiCheck >=
    WIFI_INTERVAL
  )
  {
    lastWiFiCheck = now;

    checkWiFi();
  }


  // ==================================================


  // ==================================================
  // SERIAL
  // ==================================================

  if (
    now - lastSerialOutput >=
    SERIAL_INTERVAL
  )
  {
    lastSerialOutput = now;

    printSerialData();
  }
}