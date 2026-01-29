#include <Arduino.h>
#include "Pins/Pins.h"
#include "pzem_sensor/pzem_sensor.h"
#include "rotary_encoder/rotary_encoder.h"
#include "load_relay/load_relay.h"
#include "source_relay/source_relay.h"
#include "gpio_expander/gpio_expander.h"
#include "regulator/regulator.h"
#include "nepa_sense/nepa_sense.h"
#include "inverter_sense/inverter_sense.h"

#include "WiFi/WiFi.h"
#include "lcd_screen/lcd_screen.h"
#include "led_indicator/led_indicator.h"
#include "sleep_wake/sleep_wake.h"
#include "error_handling/error_handling.h"
#include "reset/reset.h"

void setup() {
  Serial.begin(115200);
  Pins::begin();
  pzem_sensor::begin();
  rotary_encoder::begin();
  load_relay::begin();
  source_relay::begin();
  gpio_expander::begin();
  regulator::begin();
  nepa_sense::begin();
  inverter_sense::begin();
 
  WiFi::begin();
  lcd_screen::begin();
  led_indicator::begin();
  sleep_wake::begin();
  error_handling::begin();
  reset::begin();
}

void loop() {
  Pins::update();
  pzem_sensor::update();
  rotary_encoder::update();
  load_relay::update();
  source_relay::update();
  gpio_expander::update();
  regulator::update();
  nepa_sense::update();
  inverter_sense::update();
 
  WiFi::update();
  lcd_screen::update();
  led_indicator::update();
  sleep_wake::update();
  error_handling::update();
  reset::update();
}
