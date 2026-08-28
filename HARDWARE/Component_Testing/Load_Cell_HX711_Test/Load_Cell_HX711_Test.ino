#include "HX711.h"

#define HX711_DT 32
#define HX711_SCK 33

HX711 scale;

void setup()
{
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("    TRACEVEDA HX711 CALIBRATION");
  Serial.println("================================");

  scale.begin(HX711_DT, HX711_SCK);

  // Give HX711 time to power up
  delay(1000);

  // Wait for HX711 to become ready
  Serial.println("Waiting for HX711...");

  while (!scale.is_ready())
  {
    Serial.println("HX711 not ready...");
    delay(500);
  }

  Serial.println("HX711 detected!");
  Serial.println();

  // -------------------------
  // TARE
  // -------------------------

  Serial.println("Remove ALL weight from the load cell.");
  Serial.println("Taring in 5 seconds...");

  delay(5000);

  scale.set_scale();
  scale.tare(20);

  Serial.println("Tare complete!");
  Serial.println();

  // -------------------------
  // KNOWN WEIGHT
  // -------------------------

  Serial.println("Place your 177 g phone on the load cell.");
  Serial.println("Waiting 5 seconds...");

  delay(5000);

  long reading = scale.get_value(20);

  Serial.print("Raw reading with 177 g: ");
  Serial.println(reading);

  float calibrationFactor = reading / 177.0;

  Serial.print("Calibration factor: ");
  Serial.println(calibrationFactor, 4);

  scale.set_scale(calibrationFactor);

  Serial.println();
  Serial.println("================================");
  Serial.println("      CALIBRATION COMPLETE");
  Serial.println("================================");
  Serial.println();
}

void loop()
{
  float weight = scale.get_units(10);

  Serial.print("Weight: ");
  Serial.print(weight, 1);
  Serial.print(" g");

  Serial.print("   |   ");

  Serial.print(weight / 1000.0, 3);
  Serial.println(" kg");

  delay(1000);
}