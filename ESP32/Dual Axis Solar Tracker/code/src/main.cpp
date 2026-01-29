#include <Arduino.h>
#include "Pins/Pins.h"
#include "sun_sensor/sun_sensor.h"
#include "rotary_encoder/rotary_encoder.h"
#include "motor_driver/motor_driver.h"
#include "led_indicator/led_indicator.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  sun_sensor::begin();
  rotary_encoder::begin();
  motor_driver::begin();
  led_indicator::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  sun_sensor::update();
  rotary_encoder::update();
  motor_driver::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
