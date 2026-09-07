/*
  Flag-Only Display - LovyanGFX version
  Board: Elegoo/Sunton "Cheap Yellow Display" - ESP32-2432S028R

  Pure display, no touch/buttons. Listens for "FLAG:<NAME>" lines
  over USB serial (sent by the same PC script that drives the main
  button box) and fills the whole screen with that flag's color,
  flashing a few times whenever the flag changes, then shows the
  flag name as text.

  Pairs with button_box_vjoy_autodetect.py - that script now
  auto-detects and broadcasts flag updates to ALL connected CYD
  boards, so this one and your button box can both be plugged into
  the same PC at once.
*/

#define LGFX_USE_V1
#define LGFX_SUNTON_ESP32_2432S028
#include <LovyanGFX.hpp>
#include <LGFX_AUTODETECT.hpp>

static LGFX lcd;

uint16_t currentColor = TFT_BLACK;
String currentName = "NONE";

bool flashing = false;
bool flashOn = false;
int flashesLeft = 0;
unsigned long lastFlashToggle = 0;
const unsigned long FLASH_INTERVAL_MS = 150;
const int FLASH_COUNT = 6;

uint16_t colorForFlagName(const String &name) {
  if (name == "GREEN")     return TFT_GREEN;
  if (name == "YELLOW")    return TFT_YELLOW;
  if (name == "RED")       return TFT_RED;
  if (name == "BLUE")      return TFT_BLUE;
  if (name == "WHITE")     return TFT_WHITE;
  if (name == "BLACK")     return 0x39C7; // dark gray - true black would look "off"
  if (name == "CHECKERED") return TFT_WHITE;
  if (name == "DEBRIS")    return TFT_YELLOW;
  return TFT_BLACK; // "NONE"
}

// Picks readable text color for a given background
uint16_t textColorFor(uint16_t bg) {
  if (bg == TFT_WHITE || bg == TFT_YELLOW) return TFT_BLACK;
  return TFT_WHITE;
}

void drawCheckerboard() {
  const int sqSize = 40; // 320/40=8 cols, 240/40=6 rows - clean fit, no partial squares
  int cols = lcd.width() / sqSize;
  int rows = lcd.height() / sqSize;
  for (int r = 0; r < rows; r++) {
    for (int c = 0; c < cols; c++) {
      uint16_t color = ((r + c) % 2 == 0) ? TFT_WHITE : TFT_BLACK;
      lcd.fillRect(c * sqSize, r * sqSize, sqSize, sqSize, color);
    }
  }
}

void drawStripes() {
  const int stripeW = 40;
  int cols = lcd.width() / stripeW + 1;
  for (int c = 0; c < cols; c++) {
    uint16_t color = (c % 2 == 0) ? TFT_YELLOW : TFT_RED;
    lcd.fillRect(c * stripeW, 0, stripeW, lcd.height(), color);
  }
}

// "on" = show the flag's real look (color or pattern), false = the
// black "off" frame used only during the flash blinking
void drawFlagFrame(bool on) {
  if (!on) {
    lcd.fillScreen(TFT_BLACK);
    return;
  }
  if (currentName == "CHECKERED") {
    drawCheckerboard();
  } else if (currentName == "DEBRIS") {
    drawStripes();
  } else {
    lcd.fillScreen(currentColor);
  }
}

// ---------- Party mode easter egg ----------
// Send "TestAll:PARTY" to rapid-fire through every flag color/pattern
// as a fun quick self-test, then automatically restore whatever the
// real flag was showing before it started.
bool partyMode = false;
int partyIndex = 0;
unsigned long lastPartyStep = 0;
const unsigned long PARTY_STEP_MS = 220;
const char* PARTY_SEQUENCE[] = {"GREEN", "YELLOW", "RED", "BLUE", "WHITE", "BLACK", "CHECKERED", "DEBRIS"};
const int PARTY_SEQUENCE_LEN = 8;
String nameBeforeParty = "NONE";

void applyPartyFrame() {
  String name = PARTY_SEQUENCE[partyIndex];
  currentColor = colorForFlagName(name);
  currentName = name;
  drawFlagFrame(true);
}

void startParty() {
  nameBeforeParty = currentName;
  flashing = false; // cancel any in-progress flash so it can't fight with party mode
  partyMode = true;
  partyIndex = 0;
  lastPartyStep = millis();
  applyPartyFrame();
}

void updateParty() {
  unsigned long now = millis();
  if (now - lastPartyStep < PARTY_STEP_MS) return;
  lastPartyStep = now;
  partyIndex++;

  if (partyIndex >= PARTY_SEQUENCE_LEN) {
    partyMode = false;
    currentColor = colorForFlagName(nameBeforeParty);
    currentName = nameBeforeParty;
    drawFlagFrame(true);
    return;
  }
  applyPartyFrame();
}

void handleIncomingLine(const String &line) {
  if (line == "TestAll:PARTY") {
    startParty();
    return;
  }
  if (line.startsWith("FLAG:")) {
    String name = line.substring(5);
    uint16_t newColor = colorForFlagName(name);
    if (newColor != currentColor || name != currentName) {
      currentColor = newColor;
      currentName = name;
      flashing = true;
      flashOn = false;
      flashesLeft = FLASH_COUNT;
      lastFlashToggle = millis();
      drawFlagFrame(false); // first flash frame is "off"
    }
  }
}

void updateFlash() {
  if (!flashing) return;
  unsigned long now = millis();
  if (now - lastFlashToggle < FLASH_INTERVAL_MS) return;

  lastFlashToggle = now;
  flashOn = !flashOn;
  drawFlagFrame(flashOn);

  if (!flashOn) {
    flashesLeft--;
    if (flashesLeft <= 0) {
      flashing = false;
      drawFlagFrame(true); // settle on the real color/pattern
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);

  lcd.init();
  lcd.setRotation(3); // match your button box - flip to 1 if upside down

  drawFlagFrame(true);

  Serial.println("Flag display ready.");
}

void loop() {
  while (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      handleIncomingLine(line);
    }
  }
  if (partyMode) {
    updateParty();
  } else {
    updateFlash();
  }
  delay(10);
}
