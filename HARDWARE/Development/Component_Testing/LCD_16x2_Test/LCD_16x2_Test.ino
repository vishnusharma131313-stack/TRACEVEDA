#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 4);

void setup()
{
  Wire.begin(21, 22);

  lcd.init();
  lcd.backlight();
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("TRACEVEDA");

  lcd.setCursor(0, 1);
  lcd.print("16x4 LCD TEST");

  lcd.setCursor(0, 2);
  lcd.print("ESP32 + I2C");

  lcd.setCursor(0, 3);
  lcd.print("LCD Working!");
}

void loop()
{
}