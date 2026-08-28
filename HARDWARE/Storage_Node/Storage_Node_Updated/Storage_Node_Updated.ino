#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <WiFi.h>

// ======================================================
// TRACEVEDA STORAGE NODE
// Non-Blocking Hardware + Wi-Fi Integration Test
//
// DHT22 + BH1750 + Limit Switch + LCD + Red LED + Wi-Fi
// ======================================================


// ======================================================
// WI-FI
// ======================================================

const char* ssid = "new";
const char* password = "12345678";


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
// TIMERS
// ======================================================

unsigned long lastSensorRead = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastWiFiCheck = 0;
unsigned long lastLEDUpdate = 0;
unsigned long lastSerialOutput = 0;


// ======================================================
// INTERVALS
// ======================================================

const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long LCD_INTERVAL = 250;
const unsigned long WIFI_INTERVAL = 5000;
const unsigned long LED_INTERVAL = 2000;
const unsigned long SERIAL_INTERVAL = 1000;


// ======================================================
// LED TEST STATE
// ======================================================

bool ledState = false;


// ======================================================
// READ SENSORS
// ======================================================

void readSensors()
{
  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  float newTemperature = dht.readTemperature();
  float newHumidity = dht.readHumidity();

  // Only replace stored values if the reading is valid.
  if (!isnan(newTemperature) && !isnan(newHumidity))
  {
    temperature = newTemperature;
    humidity = newHumidity;
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  float newLux = lightMeter.readLightLevel();

  if (newLux >= 0)
  {
    lux = newLux;
  }


  // --------------------------------------------------
  // LIMIT SWITCH
  // --------------------------------------------------

  int switchState =
    digitalRead(LIMIT_SWITCH_PIN);

  doorClosed =
    (switchState == HIGH);
}


// ======================================================
// UPDATE LCD
// ======================================================

void updateLCD()
{
  // ==================================================
  // LINE 1
  // ==================================================

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA STORAGE   ");


  // ==================================================
  // LINE 2
  // ==================================================

  lcd.setCursor(0, 1);

  if (
    isnan(temperature) ||
    isnan(humidity)
  )
  {
    lcd.print("T:ERROR H:ERROR     ");
  }
  else
  {
    lcd.print("T:");
    lcd.print(temperature, 1);
    lcd.print((char)223);
    lcd.print("C H:");
    lcd.print(humidity, 1);
    lcd.print("%   ");
  }


  // ==================================================
  // LINE 3
  // ==================================================

  lcd.setCursor(0, 2);

  lcd.print("Light: ");
  lcd.print(lux, 0);
  lcd.print(" lux      ");


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
// WIFI STATUS CHECK
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
  WiFi.begin(ssid, password);
}


// ======================================================
// SERIAL OUTPUT
// ======================================================

void printSerialData()
{
  Serial.println();
  Serial.println("================================");
  Serial.println("      STORAGE NODE DATA");
  Serial.println("================================");


  // --------------------------------------------------
  // DHT22
  // --------------------------------------------------

  if (
    isnan(temperature) ||
    isnan(humidity)
  )
  {
    Serial.println("DHT22: READ ERROR");
  }
  else
  {
    Serial.print("Temperature: ");
    Serial.print(temperature, 1);
    Serial.println(" C");

    Serial.print("Humidity: ");
    Serial.print(humidity, 1);
    Serial.println(" %");
  }


  // --------------------------------------------------
  // BH1750
  // --------------------------------------------------

  Serial.print("Light: ");
  Serial.print(lux, 1);
  Serial.println(" lux");


  // --------------------------------------------------
  // LIMIT SWITCH
  // --------------------------------------------------

  Serial.print("Door: ");

  if (doorClosed)
  {
    Serial.println("CLOSED");
  }
  else
  {
    Serial.println("OPEN");
  }


  // --------------------------------------------------
  // WI-FI
  // --------------------------------------------------

  Serial.print("WiFi: ");

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("CONNECTED");

    Serial.print("IP: ");
    Serial.println(WiFi.localIP());

    Serial.print("RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  }
  else
  {
    Serial.println("DISCONNECTED");
  }


  Serial.println("================================");
}


// ======================================================
// SETUP
// ======================================================

void setup()
{
  Serial.begin(115200);

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
  lcd.print("TRACEVEDA STORAGE");

  lcd.setCursor(0, 1);
  lcd.print("Node Starting...");

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
    Serial.println("BH1750 detected!");
  }
  else
  {
    Serial.println("BH1750 NOT detected!");
  }


  // ==================================================
  // WI-FI
  // ==================================================

  Serial.println();
  Serial.println("Connecting to WiFi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

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
  }
  else
  {
    Serial.println("WiFi connection FAILED!");

    Serial.println(
      "Storage Node WiFi test FAILED."
    );
  }


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
  // INITIAL TIMER VALUES
  // ==================================================

  unsigned long now = millis();

  lastSensorRead = now;
  lastLCDUpdate = now;
  lastWiFiCheck = now;
  lastLEDUpdate = now;
  lastSerialOutput = now;


  Serial.println();
  Serial.println(
    "Storage Node initialized."
  );
}


// ======================================================
// LOOP
// ======================================================

void loop()
{
  unsigned long now = millis();


  // ==================================================
  // LIMIT SWITCH
  // ==================================================

  int switchState =
    digitalRead(LIMIT_SWITCH_PIN);

  bool newDoorClosed =
    (switchState == HIGH);

  // Update immediately when door changes.
  if (newDoorClosed != doorClosed)
  {
    doorClosed = newDoorClosed;

    updateLCD();
    lastLCDUpdate = now;
  }


  // ==================================================
  // SENSOR READ
  // ==================================================

  if (
    now - lastSensorRead >= SENSOR_INTERVAL
  )
  {
    lastSensorRead = now;

    readSensors();
  }


  // ==================================================
  // LCD UPDATE
  // ==================================================

  if (
    now - lastLCDUpdate >= LCD_INTERVAL
  )
  {
    lastLCDUpdate = now;

    updateLCD();
  }


  // ==================================================
  // WI-FI CHECK
  // ==================================================

  if (
    now - lastWiFiCheck >= WIFI_INTERVAL
  )
  {
    lastWiFiCheck = now;

    checkWiFi();
  }


  // ==================================================
  // RED LED HARDWARE TEST
  // ==================================================
  //
  // Temporary hardware test only.
  // Backend will eventually determine this.
  //
  // ==================================================

  if (
    now - lastLEDUpdate >= LED_INTERVAL
  )
  {
    lastLEDUpdate = now;

    ledState = !ledState;

    digitalWrite(
      RED_LED_PIN,
      ledState
    );
  }


  // ==================================================
  // SERIAL OUTPUT
  // ==================================================

  if (
    now - lastSerialOutput >= SERIAL_INTERVAL
  )
  {
    lastSerialOutput = now;

    printSerialData();
  }
}