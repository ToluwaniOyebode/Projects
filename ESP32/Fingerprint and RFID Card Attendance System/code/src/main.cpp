#include <Arduino.h>
#include "Pins/Pins.h"
#include "fingerprint/fingerprint.h"
#include "RFID/RFID.h"
#include "buttons/buttons.h"
#include "buzzer/buzzer.h"
#include "battery_level/battery_level.h"
#include "WiFi/WiFi.h"
#include "oled_screen/oled_screen.h"
#include "led_indicator/led_indicator.h"
#include "sd_card/sd_card.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"
#include "rtc/rtc.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  fingerprint::begin();
  RFID::begin();
  buttons::begin();
  buzzer::begin();
  battery_level::begin();
   WiFi::begin();
  oled_screen::begin();
  led_indicator::begin();
  sd_card::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
  rtc::begin();
}

void loop() {
  Pins::update();
  fingerprint::update();
  RFID::update();
  buttons::update();
  buzzer::update();
  battery_level::update();
  WiFi::update();
  oled_screen::update();
  led_indicator::update();
  sd_card::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
  rtc::update();
}
