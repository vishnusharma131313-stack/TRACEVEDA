#include <WiFi.h>

const char* ssid = "new";
const char* password = "YOUR_WIFI_PASSWORD";

void setup()
{
  Serial.begin(115200);
  delay(1000);

  Serial.println("================================");
  Serial.println("   TRACEVEDA STORAGE WIFI TEST");
  Serial.println("================================");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.println();

  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  Serial.print("Signal Strength: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");

  Serial.println();
  Serial.println("Storage Node WiFi test PASSED.");
}

void loop()
{
}