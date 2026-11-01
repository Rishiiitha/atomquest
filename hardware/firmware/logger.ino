/*
 * Proposed ESP32-class logger sketch. Wire map and rates must be checked against
 * selected sensor boards before powering a wet rig. Emits one CSV header and row
 * per sample; timestamps are monotonic milliseconds plus an externally synced
 * ISO timestamp field supplied by the host during the calibration session.
 *
 * Suggested acquisition: analog current at 100 Hz with a one-second RMS window;
 * pulse flow, TDS, temperature, turbidity, and pressure at 1 Hz. This sketch is
 * an interface template and intentionally refuses to invent board-specific ADC
 * calibration constants.
 */
#include <Arduino.h>

constexpr uint32_t SAMPLE_MS = 1000;
constexpr int PIN_FLOW = 27;
constexpr int PIN_CURRENT = 34;
constexpr int PIN_PRESSURE = 35;
constexpr int PIN_TDS_IN = 32;
constexpr int PIN_TDS_OUT = 33;
constexpr int PIN_TEMP = 25;
constexpr int PIN_TURBIDITY = 26;

volatile uint32_t flowPulses = 0;
uint32_t lastSample = 0;

void IRAM_ATTR onFlowPulse() { ++flowPulses; }

void setup() {
  Serial.begin(115200);
  pinMode(PIN_FLOW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW), onFlowPulse, FALLING);
  Serial.println("millis,flow_pulses,current_adc,pressure_adc,tds_in_adc,tds_out_adc,temp_adc,turbidity_adc");
}

void loop() {
  const uint32_t now = millis();
  if (now - lastSample >= SAMPLE_MS) {
    noInterrupts();
    const uint32_t pulses = flowPulses;
    flowPulses = 0;
    interrupts();
    Serial.printf("%lu,%lu,%d,%d,%d,%d,%d,%d\n", (unsigned long)now,
                  (unsigned long)pulses, analogRead(PIN_CURRENT), analogRead(PIN_PRESSURE),
                  analogRead(PIN_TDS_IN), analogRead(PIN_TDS_OUT), analogRead(PIN_TEMP),
                  analogRead(PIN_TURBIDITY));
    lastSample = now;
  }
}
