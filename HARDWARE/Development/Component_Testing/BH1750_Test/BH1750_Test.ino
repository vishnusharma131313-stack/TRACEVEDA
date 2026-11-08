#include <Wire.h>
#include <BH1750.h>

BH1750 lightMeter;

void setup()
{
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("       TRACEVEDA BH1750 TEST");
  Serial.println("================================");

  Wire.begin(21, 22);

  if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE))
  {
    Serial.println("BH1750 initialized successfully!");
  }
  else
  {
    Serial.println("BH1750 initialization failed!");
  }
}

void loop()
{
  float lux = lightMeter.readLightLevel();

  Serial.print("Light intensity: ");
  Serial.print(lux);
  Serial.println(" lux");

  delay(1000);
}