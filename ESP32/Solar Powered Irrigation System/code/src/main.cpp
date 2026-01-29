#include <Arduino.h>
#include "Pins/Pins.h"
#include "temp_hum/temp_hum.h"
#include "ultrasonic/ultrasonic.h"
#include "soil_sensor/soil_sensor.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "pump/pump.h"
#include "battery_level/battery_level.h"
#include "solar_level/solar_level.h"
#include "lcd_screen/lcd_screen.h"
#include "led_indicator/led_indicator.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  temp_hum::begin();
  ultrasonic::begin();
  soil_sensor::begin();
  button::begin();
  buzzer::begin();
  pump::begin();
  battery_level::begin();
  solar_level::begin();
  lcd_screen::begin();
  led_indicator::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  temp_hum::update();
  ultrasonic::update();
  soil_sensor::update();
  button::update();
  buzzer::update();
  pump::update();
  battery_level::update();
  solar_level::update();
  lcd_screen::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
