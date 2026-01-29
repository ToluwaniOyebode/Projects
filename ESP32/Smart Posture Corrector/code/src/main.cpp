#include <Arduino.h>
#include "Pins/Pins.h"
#include "gyroscope/gyroscope.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "vibrator/vibrator.h"
#include "battery_level/battery_level.h"

#include "WiFi/WiFi.h"
#include "led_indicator/led_indicator.h"
#include "sd_card/sd_card.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  gyroscope::begin();
  button::begin();
  buzzer::begin();
  vibrator::begin();
  battery_level::begin();

  WiFi::begin();
  led_indicator::begin();
  sd_card::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  gyroscope::update();
  button::update();
  buzzer::update();
  vibrator::update();
  battery_level::update();
 
  WiFi::update();
  led_indicator::update();
  sd_card::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
