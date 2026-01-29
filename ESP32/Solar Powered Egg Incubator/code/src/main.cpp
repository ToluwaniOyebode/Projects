#include <Arduino.h>
#include "Pins/Pins.h"
#include "temp_hum/temp_hum.h"
#include "ultrasonic/ultrasonic.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "fan/fan.h"
#include "heater/heater.h"
#include "spinner/spinner.h"
#include "humidifier/humidifier.h"
#include "solar_level/solar_level.h"
#include "battery_level/battery_level.h"

#include "WiFi/WiFi.h"
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
  button::begin();
  buzzer::begin();
  fan::begin();
  heater::begin();
  spinner::begin();
  humidifier::begin();
  solar_level::begin();
  battery_level::begin();
  
  WiFi::begin();
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
  button::update();
  buzzer::update();
  fan::update();
  heater::update();
  spinner::update();
  humidifier::update();
  solar_level::update();
  battery_level::update();
 
  WiFi::update();
  lcd_screen::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
