#include <Arduino.h>
#include "Pins/Pins.h"
#include "pir_sensor/pir_sensor.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "battery_level/battery_level.h"
#include "WiFi/WiFi.h"
#include "led_indicator/led_indicator.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  pir_sensor::begin();
  button::begin();
  buzzer::begin();
  battery_level::begin();
   WiFi::begin();
  led_indicator::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  pir_sensor::update();
  button::update();
  buzzer::update();
  battery_level::update();
  WiFi::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
