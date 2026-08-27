#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

HardwareSerial GPS(2);
TinyGPSPlus gps;

#define GPS_RX 16
#define GPS_TX 17

void setup()
{
  Serial.begin(115200);

  GPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  Serial.println("================================");
  Serial.println("        TRACEVEDA GPS TEST");
  Serial.println("================================");
  Serial.println("Waiting for GPS fix...");
}

void loop()
{
  // Read all incoming GPS characters
  while (GPS.available())
  {
    gps.encode(GPS.read());
  }

  // Print a new position when one is received
  if (gps.location.isUpdated())
  {
    Serial.println();
    Serial.println("========== GPS DATA ==========");

    if (gps.location.isValid())
    {
      Serial.println("Fix: VALID");

      Serial.print("Latitude:  ");
      Serial.println(gps.location.lat(), 6);

      Serial.print("Longitude: ");
      Serial.println(gps.location.lng(), 6);
    }
    else
    {
      Serial.println("Fix: INVALID");
    }

    if (gps.satellites.isValid())
    {
      Serial.print("Satellites: ");
      Serial.println(gps.satellites.value());
    }

    if (gps.hdop.isValid())
    {
      Serial.print("HDOP: ");
      Serial.println(gps.hdop.hdop(), 2);
    }

    if (gps.altitude.isValid())
    {
      Serial.print("Altitude: ");
      Serial.print(gps.altitude.meters(), 2);
      Serial.println(" m");
    }

    if (gps.speed.isValid())
    {
      Serial.print("Speed: ");
      Serial.print(gps.speed.kmph(), 2);
      Serial.println(" km/h");
    }

    Serial.println("==============================");
  }

  // Diagnostic message if GPS isn't producing data
  static unsigned long lastCheck = 0;

  if (millis() - lastCheck > 5000)
  {
    lastCheck = millis();

    if (gps.charsProcessed() < 10)
    {
      Serial.println("WARNING: No GPS data received!");
    }
  }
}