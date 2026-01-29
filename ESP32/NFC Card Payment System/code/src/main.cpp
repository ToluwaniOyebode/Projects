#include <Arduino.h>
#include "Pins/Pins.h"
#include "NFC_module/NFC_module.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "battery_level/battery_level.h"

#include "WiFi/WiFi.h"
#include "oled_screen/oled_screen.h"
#include "led_indicator/led_indicator.h"
#include "sd_card/sd_card.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "rtc/rtc.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  NFC_module::begin();
  button::begin();
  buzzer::begin();
  battery_level::begin();
 
  WiFi::begin();
  oled_screen::begin();
  led_indicator::begin();
  sd_card::begin();
  sleep_wake::begin();
  error_handling::begin();
  rtc::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  NFC_module::update();
  button::update();
  buzzer::update();
  battery_level::update();
 
  WiFi::update();
  oled_screen::update();
  led_indicator::update();
  sd_card::update();
  sleep_wake::update();
  error_handling::update();
  rtc::update();
  reset::update();
}
