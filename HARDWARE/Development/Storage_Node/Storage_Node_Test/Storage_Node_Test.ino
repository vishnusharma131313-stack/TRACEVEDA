#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <WiFi.h>

// ================================
// TRACEVEDA STORAGE NODE
// Hardware + Wi-Fi Integration Test
// ================================

// ---------- Wi-Fi ----------
// Enter your current hotspot details here for testing.
// DO NOT push real credentials to GitHub.

const char* ssid = "new";
const char* password = "YOUR_WIFI_PASSWORD";

// ---------- DHT22 ----------
#define DHT_PIN 4
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);

// ---------- Limit Switch ----------
#define LIMIT_SWITCH_PIN 27

// ---------- Red LED ----------
#define RED_LED_PIN 25

// ---------- I2C ----------
#define SDA_PIN 21
#define SCL_PIN 22

// ---------- LCD ----------
#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 20
#define LCD_ROWS 4

LiquidCrystal_I2C lcd(
  LCD_ADDRESS,
  LCD_COLUMNS,
  LCD_ROWS);

// ---------- BH1750 ----------
BH1750 lightMeter;


// ================================
// SETUP
// ================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // LCD
  lcd.init();
  lcd.backlight();

  // DHT22
  dht.begin();

  // Limit switch
  pinMode(LIMIT_SWITCH_PIN, INPUT_PULLUP);

  // Red LED
  pinMode(RED_LED_PIN, OUTPUT);
  digitalWrite(RED_LED_PIN, LOW);

  // BH1750
  if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("BH1750 detected!");
  } else {
    Serial.println("BH1750 NOT detected!");
  }

  // Startup screen
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA STORAGE");

  lcd.setCursor(0, 1);
  lcd.print("Node Starting...");

  delay(1500);

  // ---------- Wi-Fi ----------
  Serial.println();
  Serial.println("Connecting to WiFi...");

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

    Serial.print("SSID: ");
    Serial.println(WiFi.SSID());

    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("WiFi connection FAILED!");
  }

  Serial.println();

  // Clear LCD once after startup
  lcd.clear();
}


// ================================
// LOOP
// ================================

void loop() {
  // ---------- Read DHT22 ----------

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();


  // ---------- Read BH1750 ----------

  float lux = lightMeter.readLightLevel();


  // ---------- Read Limit Switch ----------

  int switchState = digitalRead(LIMIT_SWITCH_PIN);

  // Same interpretation as our
  // previously tested switch setup
  bool doorClosed = (switchState == HIGH);


  // ================================
  // SERIAL MONITOR
  // ================================

  Serial.println();
  Serial.println("================================");
  Serial.println("      STORAGE NODE DATA");
  Serial.println("================================");

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT22: READ ERROR");
  } else {
    Serial.print("Temperature: ");
    Serial.print(temperature, 1);
    Serial.println(" C");

    Serial.print("Humidity: ");
    Serial.print(humidity, 1);
    Serial.println(" %");
  }

  Serial.print("Light: ");
  Serial.print(lux, 1);
  Serial.println(" lux");

  Serial.print("Door: ");

  if (doorClosed) {
    Serial.println("CLOSED");
  } else {
    Serial.println("OPEN");
  }


  // ================================
  // WIFI STATUS
  // ================================

  Serial.print("WiFi: ");

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("CONNECTED | IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("DISCONNECTED");
  }


  // ================================
  // LCD
  // ================================

  // Line 1
  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA STORAGE   ");


  // Line 2
  lcd.setCursor(0, 1);

  if (isnan(temperature) || isnan(humidity)) {
    lcd.print("T:ERROR H:ERROR     ");
  } else {
    lcd.print("T:");
    lcd.print(temperature, 1);
    lcd.print((char)223);
    lcd.print("C H:");
    lcd.print(humidity, 1);
    lcd.print("%   ");
  }


  // Line 3
  lcd.setCursor(0, 2);

  lcd.print("Light: ");
  lcd.print(lux, 0);
  lcd.print(" lux      ");


  // Line 4
  lcd.setCursor(0, 3);

  lcd.print("Door: ");

  if (doorClosed) {
    lcd.print("CLOSED");
  } else {
    lcd.print("OPEN  ");
  }

  lcd.print("        ");


  // ================================
  // RED LED HARDWARE TEST
  // ================================
  //
  // NO crop-specific thresholds.
  // Backend will eventually control this.
  //

  static bool ledState = false;

  ledState = !ledState;
  digitalWrite(RED_LED_PIN, ledState);


  // Approximately 2-second update
  delay(2000);
}