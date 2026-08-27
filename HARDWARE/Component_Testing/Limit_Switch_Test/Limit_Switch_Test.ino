#define LIMIT_SWITCH_PIN 27

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LIMIT_SWITCH_PIN, INPUT_PULLUP);

  Serial.println("================================");
  Serial.println("     TRACEVEDA LIMIT SWITCH TEST");
  Serial.println("================================");
}

void loop() {
  int state = digitalRead(LIMIT_SWITCH_PIN);

  if (state == HIGH) {
    Serial.println("Switch: PRESSED / DOOR CLOSED");
  } else {
    Serial.println("Switch: RELEASED / DOOR OPEN");
  }

  delay(500);
}