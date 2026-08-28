#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <BH1750.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <math.h>
#include <WiFi.h>

// ======================================================
// TRACEVEDA TRUCK NODE
// Integrated Hardware Test
// MPU-6500 + BH1750 + DHT22 + GPS + Switch + LCD
// ======================================================

// ---------------- PIN DEFINITIONS ----------------

#define SDA_PIN 21
#define SCL_PIN 22

#define DHT_PIN 4
#define DHT_TYPE DHT22

#define GPS_RX 16
#define GPS_TX 17

#define LIMIT_SWITCH_PIN 27

#define RED_LED_PIN 25

// HX711 RESERVED FOR LATER
#define HX711_DT 32
#define HX711_SCK 33

// ======================================================
// WI-FI
// ======================================================

const char* ssid = "YOUR_WIFI_NAME ";
const char* password = "YOUR_WIFI_PASSWORD";


// ======================================================
// LCD
// ======================================================

#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 16
#define LCD_ROWS 2

LiquidCrystal_I2C lcd(
  LCD_ADDRESS,
  LCD_COLUMNS,
  LCD_ROWS
);


// ======================================================
// OTHER SENSORS
// ======================================================

DHT dht(DHT_PIN, DHT_TYPE);

BH1750 lightMeter;

HardwareSerial GPS(2);
TinyGPSPlus gps;


// ======================================================
// MPU-6500
// ======================================================

#define MPU_ADDR 0x68

#define PWR_MGMT_1 0x6B
#define WHO_AM_I 0x75
#define ACCEL_XOUT_H 0x3B

// Current readings
float ax = 0.0;
float ay = 0.0;
float az = 0.0;

float gx = 0.0;
float gy = 0.0;
float gz = 0.0;

float mpuTemperature = 0.0;

float tilt = 0.0;


// ======================================================
// MPU CALIBRATION OFFSETS
// ======================================================

float accelOffsetX = 0.0;
float accelOffsetY = 0.0;
float accelOffsetZ = 0.0;

float gyroOffsetX = 0.0;
float gyroOffsetY = 0.0;
float gyroOffsetZ = 0.0;


// ======================================================
// DHT22
// ======================================================

float temperature = NAN;
float humidity = NAN;


// ======================================================
// BH1750
// ======================================================

float lux = 0.0;


// ======================================================
// DOOR
// ======================================================

bool doorClosed = false;


// ======================================================
// TIMERS
// ======================================================

unsigned long lastMPURead = 0;
unsigned long lastDHTRead = 0;
unsigned long lastLightRead = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastLCDScreenChange = 0;
unsigned long lastSerialOutput = 0;

const unsigned long MPU_INTERVAL = 50;
const unsigned long DHT_INTERVAL = 2000;
const unsigned long LIGHT_INTERVAL = 500;
const unsigned long LCD_INTERVAL = 250;
const unsigned long SCREEN_INTERVAL = 2000;
const unsigned long SERIAL_INTERVAL = 1000;


// ======================================================
// LCD SCREENS
// ======================================================

int currentScreen = 0;

const int TOTAL_SCREENS = 8;


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
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30)
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

    Serial.println("Truck Node WiFi test PASSED.");
  }
  else
  {
    Serial.println("WiFi connection FAILED!");
    Serial.println("Truck Node WiFi test FAILED.");
  }

  Serial.println("================================");
}


// ======================================================
// MPU LOW-LEVEL FUNCTIONS
// ======================================================

void writeRegister(byte reg, byte value)
{
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}


byte readRegister(byte reg)
{
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 1);

  if (Wire.available())
  {
    return Wire.read();
  }

  return 0xFF;
}


int16_t read16()
{
  int16_t value =
    Wire.read() << 8 | Wire.read();

  return value;
}


// ======================================================
// MPU INITIALIZATION
// ======================================================

bool initializeMPU()
{
  byte deviceID = readRegister(WHO_AM_I);

  Serial.print("MPU-6500 WHO_AM_I = 0x");
  Serial.println(deviceID, HEX);

  if (deviceID != 0x70)
  {
    Serial.println("MPU-6500 NOT detected!");
    return false;
  }

  Serial.println("MPU-6500 detected successfully!");

  // Wake sensor
  writeRegister(PWR_MGMT_1, 0x00);

  delay(100);

  Serial.println("MPU-6500 initialized.");

  return true;
}


// ======================================================
// READ RAW MPU DATA
// ======================================================

bool readMPURaw(
  int16_t &accelX,
  int16_t &accelY,
  int16_t &accelZ,
  int16_t &temperatureRaw,
  int16_t &gyroX,
  int16_t &gyroY,
  int16_t &gyroZ
)
{
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 14);

  if (Wire.available() != 14)
  {
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


// ======================================================
// MPU CALIBRATION
// ======================================================

void calibrateMPU()
{
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
  Serial.println("Keep the sensor STILL and LEVEL.");
  Serial.println("Calibration starting...");

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");

  lcd.setCursor(0, 1);
  lcd.print("Calibrating MPU");

  delay(1000);

  for (int i = 0; i < samples; i++)
  {
    int16_t accelX;
    int16_t accelY;
    int16_t accelZ;

    int16_t temperatureRaw;

    int16_t gyroX;
    int16_t gyroY;
    int16_t gyroZ;

    if (
      readMPURaw(
        accelX,
        accelY,
        accelZ,
        temperatureRaw,
        gyroX,
        gyroY,
        gyroZ
      )
    )
    {
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

  if (successfulSamples == 0)
  {
    Serial.println("MPU calibration FAILED!");

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("TRACEVEDA TRUCK");

    lcd.setCursor(0, 1);
    lcd.print("MPU CAL ERROR");

    delay(2000);

    return;
  }


  // --------------------------------------------------
  // Calculate average raw values
  // --------------------------------------------------

  float avgAccelX =
    (float)sumAccelX / successfulSamples;

  float avgAccelY =
    (float)sumAccelY / successfulSamples;

  float avgAccelZ =
    (float)sumAccelZ / successfulSamples;

  float avgGyroX =
    (float)sumGyroX / successfulSamples;

  float avgGyroY =
    (float)sumGyroY / successfulSamples;

  float avgGyroZ =
    (float)sumGyroZ / successfulSamples;


  // --------------------------------------------------
  // Expected stationary values
  //
  // X = 0
  // Y = 0
  // Z = +1g = 16384 raw
  //
  // Gyroscope = 0
  // --------------------------------------------------

  accelOffsetX = avgAccelX;

  accelOffsetY = avgAccelY;

  accelOffsetZ =
    avgAccelZ - 16384.0;


  gyroOffsetX = avgGyroX;

  gyroOffsetY = avgGyroY;

  gyroOffsetZ = avgGyroZ;


  Serial.println();
  Serial.println("Calibration complete.");

  Serial.print("Accel offsets: ");
  Serial.print(accelOffsetX, 2);
  Serial.print(", ");
  Serial.print(accelOffsetY, 2);
  Serial.print(", ");
  Serial.println(accelOffsetZ, 2);

  Serial.print("Gyro offsets: ");
  Serial.print(gyroOffsetX, 2);
  Serial.print(", ");
  Serial.print(gyroOffsetY, 2);
  Serial.print(", ");
  Serial.println(gyroOffsetZ, 2);

  Serial.print("Successful samples: ");
  Serial.println(successfulSamples);

  Serial.println();


  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");

  lcd.setCursor(0, 1);
  lcd.print("MPU CALIBRATED");

  delay(1500);
}


// ======================================================
// READ MPU
// ======================================================

void readMPU()
{
  int16_t accelX;
  int16_t accelY;
  int16_t accelZ;

  int16_t temperatureRaw;

  int16_t gyroX;
  int16_t gyroY;
  int16_t gyroZ;


  if (
    !readMPURaw(
      accelX,
      accelY,
      accelZ,
      temperatureRaw,
      gyroX,
      gyroY,
      gyroZ
    )
  )
  {
    return;
  }


  // --------------------------------------------------
  // Apply calibration offsets
  // --------------------------------------------------

  float correctedAccelX =
    accelX - accelOffsetX;

  float correctedAccelY =
    accelY - accelOffsetY;

  float correctedAccelZ =
    accelZ - accelOffsetZ;


  float correctedGyroX =
    gyroX - gyroOffsetX;

  float correctedGyroY =
    gyroY - gyroOffsetY;

  float correctedGyroZ =
    gyroZ - gyroOffsetZ;


  // --------------------------------------------------
  // Convert acceleration
  // --------------------------------------------------

  ax =
    (correctedAccelX / 16384.0)
    * 9.80665;

  ay =
    (correctedAccelY / 16384.0)
    * 9.80665;

  az =
    (correctedAccelZ / 16384.0)
    * 9.80665;


  // --------------------------------------------------
  // Convert gyro
  // --------------------------------------------------

  gx =
    correctedGyroX / 131.0;

  gy =
    correctedGyroY / 131.0;

  gz =
    correctedGyroZ / 131.0;


  // --------------------------------------------------
  // MPU temperature
  // --------------------------------------------------

  mpuTemperature =
    (temperatureRaw / 333.87) + 21.0;


  // --------------------------------------------------
  // Tilt
  //
  // Angle from the vertical gravity vector.
  // --------------------------------------------------

  float horizontalAcceleration =
    sqrt(
      (ax * ax) +
      (ay * ay)
    );

  tilt =
    atan2(
      horizontalAcceleration,
      az
    )
    * 180.0 / PI;
}


// ======================================================
// GPS
// ======================================================

void readGPS()
{
  while (GPS.available())
  {
    gps.encode(GPS.read());
  }
}


// ======================================================
// LCD
// ======================================================

void printLCDLine2(const char* text)
{
  lcd.setCursor(0, 1);

  lcd.print(text);

  int length = strlen(text);

  for (int i = length; i < 16; i++)
  {
    lcd.print(" ");
  }
}


void updateLCD()
{
  // ------------------------------------------
  // LINE 1 — ALWAYS FIXED
  // ------------------------------------------

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");


  char line[17];


  switch (currentScreen)
  {

    // ----------------------------------------
    // 0 — Temperature + Humidity
    // ----------------------------------------

    case 0:

      if (
        isnan(temperature) ||
        isnan(humidity)
      )
      {
        snprintf(
          line,
          sizeof(line),
          "T:ERR H:ERR"
        );
      }
      else
      {
        snprintf(
          line,
          sizeof(line),
          "T:%4.1fC H:%4.1f%%",
          temperature,
          humidity
        );
      }

      break;


    // ----------------------------------------
    // 1 — Light
    // ----------------------------------------

    case 1:

      snprintf(
        line,
        sizeof(line),
        "Light:%5.0f lux",
        lux
      );

      break;


    // ----------------------------------------
    // 2 — Acceleration
    // ----------------------------------------

    case 2:
    {
      float accelerationMagnitude =
        sqrt(
          (ax * ax) +
          (ay * ay) +
          (az * az)
        );

      snprintf(
        line,
        sizeof(line),
        "A:%5.2f m/s2",
        accelerationMagnitude
      );

      break;
    }


    // ----------------------------------------
    // 3 — Tilt
    // ----------------------------------------

    case 3:

      snprintf(
        line,
        sizeof(line),
        "Tilt:%5.1f deg",
        tilt
      );

      break;


    // ----------------------------------------
    // 4 — Latitude
    // ----------------------------------------

    case 4:

      if (gps.location.isValid())
      {
        snprintf(
          line,
          sizeof(line),
          "Lat:%.6f",
          gps.location.lat()
        );
      }
      else
      {
        snprintf(
          line,
          sizeof(line),
          "GPS: NO FIX"
        );
      }

      break;


    // ----------------------------------------
    // 5 — Longitude
    // ----------------------------------------

    case 5:

      if (gps.location.isValid())
      {
        snprintf(
          line,
          sizeof(line),
          "Lon:%.6f",
          gps.location.lng()
        );
      }
      else
      {
        snprintf(
          line,
          sizeof(line),
          "GPS: NO FIX"
        );
      }

      break;


    // ----------------------------------------
    // 6 — GPS status
    // ----------------------------------------

    case 6:

      if (gps.location.isValid())
      {
        if (gps.satellites.isValid())
        {
          snprintf(
            line,
            sizeof(line),
            "GPS:FIX S:%d",
            gps.satellites.value()
          );
        }
        else
        {
          snprintf(
            line,
            sizeof(line),
            "GPS:FIX"
          );
        }
      }
      else
      {
        snprintf(
          line,
          sizeof(line),
          "GPS: NO FIX"
        );
      }

      break;


    // ----------------------------------------
    // 7 — Door
    // ----------------------------------------

    case 7:

      if (doorClosed)
      {
        snprintf(
          line,
          sizeof(line),
          "Door: CLOSED"
        );
      }
      else
      {
        snprintf(
          line,
          sizeof(line),
          "Door: OPEN"
        );
      }

      break;
  }


  printLCDLine2(line);
}


// ======================================================
// SERIAL OUTPUT
// ======================================================

void printSerialData()
{
  Serial.println();
  Serial.println("================================");
  Serial.println("       TRACEVEDA TRUCK");
  Serial.println("================================");


  // DHT22

  if (!isnan(temperature))
  {
    Serial.print("Temperature: ");
    Serial.print(temperature, 2);
    Serial.println(" C");

    Serial.print("Humidity: ");
    Serial.print(humidity, 2);
    Serial.println(" %");
  }
  else
  {
    Serial.println("DHT22: READ ERROR");
  }


  // BH1750

  Serial.print("Light: ");
  Serial.print(lux, 1);
  Serial.println(" lux");


  // MPU6500

  Serial.println();
  Serial.println("MPU-6500:");

  Serial.print("Acceleration (m/s^2): ");

  Serial.print("X=");
  Serial.print(ax, 2);

  Serial.print(" Y=");
  Serial.print(ay, 2);

  Serial.print(" Z=");
  Serial.println(az, 2);


  Serial.print("Gyroscope (deg/s): ");

  Serial.print("X=");
  Serial.print(gx, 2);

  Serial.print(" Y=");
  Serial.print(gy, 2);

  Serial.print(" Z=");
  Serial.println(gz, 2);


  Serial.print("Tilt: ");
  Serial.print(tilt, 2);
  Serial.println(" deg");


  Serial.print("MPU Temperature: ");
  Serial.print(mpuTemperature, 2);
  Serial.println(" C");


  // GPS

  Serial.println();
  Serial.println("GPS:");

  if (gps.location.isValid())
  {
    Serial.println("Fix: VALID");

    Serial.print("Latitude: ");
    Serial.println(
      gps.location.lat(),
      6
    );

    Serial.print("Longitude: ");
    Serial.println(
      gps.location.lng(),
      6
    );
  }
  else
  {
    Serial.println("Fix: INVALID");
  }


  if (gps.satellites.isValid())
  {
    Serial.print("Satellites: ");
    Serial.println(
      gps.satellites.value()
    );
  }


  if (gps.hdop.isValid())
  {
    Serial.print("HDOP: ");
    Serial.println(
      gps.hdop.hdop(),
      2
    );
  }


  if (gps.altitude.isValid())
  {
    Serial.print("Altitude: ");
    Serial.print(
      gps.altitude.meters(),
      2
    );

    Serial.println(" m");
  }


  if (gps.speed.isValid())
  {
    Serial.print("Speed: ");
    Serial.print(
      gps.speed.kmph(),
      2
    );

    Serial.println(" km/h");
  }


  // Door

  Serial.println();

  Serial.print("Door: ");

  if (doorClosed)
  {
    Serial.println("CLOSED");
  }
  else
  {
    Serial.println("OPEN");
  }


  // Wi-Fi

  Serial.println();
  Serial.print("Wi-Fi: ");

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


  Serial.println();
  Serial.println("================================");
  Serial.println("    TRACEVEDA TRUCK NODE");
  Serial.println("================================");


  // ------------------------------------------
  // I2C
  // ------------------------------------------

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );


  // ------------------------------------------
  // LCD
  // ------------------------------------------

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA TRUCK");

  lcd.setCursor(0, 1);
  lcd.print("Starting...");

  delay(1500);


  // ------------------------------------------
  // DHT22
  // ------------------------------------------

  dht.begin();


  // ------------------------------------------
  // Limit Switch
  // ------------------------------------------

  pinMode(
    LIMIT_SWITCH_PIN,
    INPUT_PULLUP
  );


  // ------------------------------------------
  // Red LED
  // ------------------------------------------

  pinMode(
    RED_LED_PIN,
    OUTPUT
  );

  digitalWrite(
    RED_LED_PIN,
    LOW
  );


  // ------------------------------------------
  // BH1750
  // ------------------------------------------

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


  // ------------------------------------------
  // MPU6500
  // ------------------------------------------

  bool mpuOK = initializeMPU();

  if (mpuOK)
  {
    calibrateMPU();
  }


  // ------------------------------------------
  // GPS
  // ------------------------------------------

  GPS.begin(
    9600,
    SERIAL_8N1,
    GPS_RX,
    GPS_TX
  );

  Serial.println("GPS serial initialized.");


  // ------------------------------------------
  // Wi-Fi
  // ------------------------------------------

  connectWiFi();


  // ------------------------------------------
  // Timers
  // ------------------------------------------

  unsigned long now = millis();

  lastMPURead = now;

  lastDHTRead =
    now - DHT_INTERVAL;

  lastLightRead =
    now - LIGHT_INTERVAL;

  lastLCDUpdate =
    now - LCD_INTERVAL;

  lastLCDScreenChange = now;

  lastSerialOutput =
    now - SERIAL_INTERVAL;


  lcd.clear();

  Serial.println();
  Serial.println("Truck Node initialized.");

  digitalWrite(RED_LED_PIN, HIGH);
  delay(1000);
  digitalWrite(RED_LED_PIN, LOW);
}


// ======================================================
// LOOP
// ======================================================

void loop()
{
  unsigned long now = millis();


  // ==================================================
  // GPS
  // ==================================================

  readGPS();


  // ==================================================
  // LIMIT SWITCH
  // ==================================================

  int switchState =
    digitalRead(
      LIMIT_SWITCH_PIN
    );

  doorClosed =
    (switchState == HIGH);


  // ==================================================
  // MPU6500
  // ==================================================

  if (
    now - lastMPURead >= MPU_INTERVAL
  )
  {
    lastMPURead = now;

    readMPU();
  }


  // ==================================================
  // DHT22
  // ==================================================

  if (
    now - lastDHTRead >= DHT_INTERVAL
  )
  {
    lastDHTRead = now;

    temperature =
      dht.readTemperature();

    humidity =
      dht.readHumidity();
  }


  // ==================================================
  // BH1750
  // ==================================================

  if (
    now - lastLightRead >= LIGHT_INTERVAL
  )
  {
    lastLightRead = now;

    lux =
      lightMeter.readLightLevel();
  }


  // ==================================================
  // LCD SCREEN ROTATION
  // ==================================================

  if (
    now - lastLCDScreenChange >= SCREEN_INTERVAL
  )
  {
    lastLCDScreenChange = now;

    currentScreen++;

    if (
      currentScreen >= TOTAL_SCREENS
    )
    {
      currentScreen = 0;
    }
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