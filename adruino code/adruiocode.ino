#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Define the pin for controlling the relay
const int relayPin = 10;
char receivedChar ;

void setup() {
  pinMode(relayPin, OUTPUT);
  Serial.begin(9600);
      // Clear the LCD initially
}

void loop() {
  if (Serial.available() > 0) {
    receivedChar = Serial.read();
    
    if (receivedChar == '1') {
      // Activate the relay to open the door lock
      digitalWrite(relayPin, HIGH);

    } else if (receivedChar == '0') {
      // Deactivate the relay to close the door lock
      digitalWrite(relayPin, LOW);
    }
  }
}
