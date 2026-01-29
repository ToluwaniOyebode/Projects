#include <Arduino.h>
#include "Pins/Pins.h"
#include "temp_sensor/temp_sensor.h"
#include "vibration_sensor/vibration_sensor.h"
#include "button/button.h"
#include "buzzer/buzzer.h"
#include "load_relay/load_relay.h"
#include "current_sensor/current_sensor.h"

#include "WiFi/WiFi.h"
#include "lcd_screen/lcd_screen.h"
#include "led_indicator/led_indicator.h"
#include "sd_card/sd_card.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  temp_sensor::begin();
  vibration_sensor::begin();
  button::begin();
  buzzer::begin();
  load_relay::begin();
  current_sensor::begin();

  WiFi::begin();
  lcd_screen::begin();
  led_indicator::begin();
  sd_card::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  temp_sensor::update();
  vibration_sensor::update();
  button::update();
  buzzer::update();
  load_relay::update();
  current_sensor::update();
 
  WiFi::update();
  lcd_screen::update();
  led_indicator::update();
  sd_card::update();
  error_handling::update();
  reset::update();
}
