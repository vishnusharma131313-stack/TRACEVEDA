void setup()
{
    Serial.begin(115200);

    Serial.println("================================");
    Serial.println("TRACEVEDA ESP32 TEST");
    Serial.println("ESP32 is working!");
    Serial.println("================================");
}

void loop()
{
    Serial.println("ESP32 running...");
    delay(1000);
}