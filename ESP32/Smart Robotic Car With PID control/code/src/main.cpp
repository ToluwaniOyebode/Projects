#include <Arduino.h>
#include "Pins/Pins.h"
#include "gyroscope/gyroscope.h"
#include "ultrasonic/ultrasonic.h"
#include "servo/servo.h"
#include "battery_level/battery_level.h"
#include "UART/UART.h"
#include "WiFi/WiFi.h"
#include "led_indicator/led_indicator.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  gyroscope::begin();
  ultrasonic::begin();
  servo::begin();
  battery_level::begin();
  UART::begin();
  WiFi::begin();
  led_indicator::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  gyroscope::update();
  ultrasonic::update();
  servo::update();
  battery_level::update();
  UART::update();
  WiFi::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
