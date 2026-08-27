#include <Wire.h>

void setup()
{
  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);

  Serial.println("================================");
  Serial.println(" TRACEVEDA STORAGE I2C SCANNER");
  Serial.println("================================");
}

void loop()
{
  byte devices = 0;

  Serial.println("Scanning...");

  for (byte address = 1; address < 127; address++)
  {
    Wire.beginTransmission(address);

    if (Wire.endTransmission() == 0)
    {
      Serial.print("I2C device found at 0x");

      if (address < 16)
        Serial.print("0");

      Serial.println(address, HEX);

      devices++;
    }
  }

  if (devices == 0)
  {
    Serial.println("No I2C devices found!");
  }

  Serial.print("Devices found: ");
  Serial.println(devices);

  Serial.println("----------------------------");

  delay(3000);
}