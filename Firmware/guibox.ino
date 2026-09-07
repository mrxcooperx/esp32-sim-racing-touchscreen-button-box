/*
  Touch Screen Button Box - LovyanGFX version
  Board: Elegoo/Sunton "Cheap Yellow Display" - ESP32-2432S028R

  3 pages of buttons, a blank flag page, and an adjuster page,
  switched with a vertical slider on the left edge:
    Page 1: blank - just shows the current flag color, nothing else
    Page 2: D-pad plus a small red circle center button
    Page 3: Reset, Tortoise, Wheel Repair, Battery
    Page 4: 2x fuel can + 4x tire (LF/RF/RR/LR)
    Page 5: 3 up/down adjuster pairs (placeholder codes ADJ1/2/3)

  Sends "PRESS:<code>" the instant a button is touched, and
  "RELEASE:<code>" the instant it's let go (or your finger slides
  off it onto something else) - e.g. "PRESS:UP" then "RELEASE:UP".
  This lets the PC side hold a virtual joystick button down for
  exactly as long as you're physically touching the screen, instead
  of a fixed-length tap. The empty placeholder button sends nothing
  at all, in either direction.
*/

#define LGFX_USE_V1
#define LGFX_SUNTON_ESP32_2432S028
#include <LovyanGFX.hpp>
#include <LGFX_AUTODETECT.hpp>
#include "icons.h"   // put icons.h in the same folder as this .ino file

static LGFX lcd;

uint16_t BG_COLOR = TFT_BLACK;   // mutable - this is what flag updates change
bool showCheckerPattern = false; // used by drawAllButtons() below

struct ButtonDef {
  const char* code;   // "" or nullptr = placeholder, sends nothing when tapped
  const char* label;  // small text - shown alone if no icon, or as a corner tag under an icon
  int x, y, w, h;
  const uint16_t* icon;
  int iconW, iconH;
};

const int NUM_PAGES = 5;
const int MAX_BUTTONS_PER_PAGE = 9;
ButtonDef pages[NUM_PAGES][MAX_BUTTONS_PER_PAGE];
int pageCounts[NUM_PAGES] = {0, 0, 0, 0, 0};
int currentPage = 0;

const int SCREEN_W = 320;
const int SCREEN_H = 240;

// Content area is 0-275 to leave room for the slider strip on the right.
const int CONTENT_X = 45;   // shifted right to make room for the slider on the left
const int CONTENT_Y = 5;
const int CONTENT_W = 270;
const int CONTENT_H = 230;

void buildLayout() {
  // =========================================================
  // PAGE 1: intentionally blank - no buttons at all. Just shows
  // the current flag color/pattern full-screen (or plain black
  // when no flag is active). pageCounts[0] stays 0 automatically.
  // =========================================================

  // =========================================================
  // PAGE 2: D-pad, big, using the full content area, plus a
  // small red circle "OK" button in the middle cell.
  // =========================================================
  {
    const int cellW = CONTENT_W / 3;
    const int cellH = CONTENT_H / 3;
    int idx = 0;
    pages[1][idx++] = { "UP",    nullptr, CONTENT_X + 1*cellW, CONTENT_Y + 0*cellH, cellW, cellH, ICON_ARROW_UP,    ICON_ARROW_UP_W,    ICON_ARROW_UP_H };
    pages[1][idx++] = { "LEFT",  nullptr, CONTENT_X + 0*cellW, CONTENT_Y + 1*cellH, cellW, cellH, ICON_ARROW_LEFT,  ICON_ARROW_LEFT_W,  ICON_ARROW_LEFT_H };
    pages[1][idx++] = { "RIGHT", nullptr, CONTENT_X + 2*cellW, CONTENT_Y + 1*cellH, cellW, cellH, ICON_ARROW_RIGHT, ICON_ARROW_RIGHT_W, ICON_ARROW_RIGHT_H };
    pages[1][idx++] = { "DOWN",  nullptr, CONTENT_X + 1*cellW, CONTENT_Y + 2*cellH, cellW, cellH, ICON_ARROW_DOWN,  ICON_ARROW_DOWN_W,  ICON_ARROW_DOWN_H };

    // Small center button, sitting in the D-pad's middle cell.
    // Drawn as a red circle (see the special-case in drawButton()
    // below) sized for ~11mm physical diameter on this 2.8" panel
    // (240x320 px over 2.8" diagonal works out to ~5.6 px/mm).
    {
      int centerCellX = CONTENT_X + 1*cellW;
      int centerCellY = CONTENT_Y + 1*cellH;
      const int diameterPx = 62; // ~11mm
      int smallX = centerCellX + (cellW - diameterPx) / 2;
      int smallY = centerCellY + (cellH - diameterPx) / 2;
      pages[1][idx++] = { "BTN_CENTER", "OK", smallX, smallY, diameterPx, diameterPx, nullptr, 0, 0 };
    }
    pageCounts[1] = idx;
  }

  // =========================================================
  // PAGE 3: Reset, Tortoise, Wheel Repair, Battery. 2x2 grid.
  // =========================================================
  {
    const int cols = 2, rows = 2, gap = 8;
    const int cw = (CONTENT_W - gap*(cols-1)) / cols;
    const int ch = (CONTENT_H - gap*(rows-1)) / rows;

    struct FnDef { const char* code; const char* label; const uint16_t* icon; int w, hgt; };
    FnDef fns[4] = {
      { "BTN_RESET",        nullptr, ICON_RESET,        ICON_RESET_W,        ICON_RESET_H },
      { "BTN_TORTOISE",     nullptr, ICON_TORTOISE,      ICON_TORTOISE_W,     ICON_TORTOISE_H },
      { "BTN_WHEEL_REPAIR", nullptr, ICON_WHEEL_REPAIR,  ICON_WHEEL_REPAIR_W, ICON_WHEEL_REPAIR_H },
      { "BTN_BATTERY",      nullptr, ICON_BATTERY,       ICON_BATTERY_W,      ICON_BATTERY_H },
    };
    int idx = 0;
    for (int r = 0; r < rows; r++) {
      for (int c = 0; c < cols; c++) {
        FnDef &f = fns[r*cols + c];
        pages[2][idx++] = { f.code, f.label, CONTENT_X + c*(cw+gap), CONTENT_Y + r*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
      }
    }
    pageCounts[2] = idx;
  }

  // =========================================================
  // PAGE 4: 2x fuel can + 4x tire (LF/RF/RR/LR). 3x2 grid.
  // Tire buttons share one icon, so each gets a small corner
  // label (LF/RF/RR/LR) to tell them apart.
  // =========================================================
  {
    const int cols = 3, rows = 2, gap = 8;
    const int cw = (CONTENT_W - gap*(cols-1)) / cols;
    const int ch = (CONTENT_H - gap*(rows-1)) / rows;

    struct FnDef { const char* code; const char* label; const uint16_t* icon; int w, hgt; };
    FnDef fns[6] = {
      { "autotogglefuel", "Auto",  ICON_GAS_CAN,    ICON_GAS_CAN_W,    ICON_GAS_CAN_H },
      { "TIRE_RF",   "LF", ICON_TIRE_WHEEL, ICON_TIRE_WHEEL_W, ICON_TIRE_WHEEL_H },
      { "TIRE_LF",   "RF", ICON_TIRE_WHEEL, ICON_TIRE_WHEEL_W, ICON_TIRE_WHEEL_H },
      { "8gallons", "8g",  ICON_GAS_CAN,    ICON_GAS_CAN_W,    ICON_GAS_CAN_H },
      { "TIRE_RR",   "LR", ICON_TIRE_WHEEL, ICON_TIRE_WHEEL_W, ICON_TIRE_WHEEL_H },
      { "TIRE_LR",   "RR", ICON_TIRE_WHEEL, ICON_TIRE_WHEEL_W, ICON_TIRE_WHEEL_H },
    };
    int idx = 0;
    for (int r = 0; r < rows; r++) {
      for (int c = 0; c < cols; c++) {
        FnDef &f = fns[r*cols + c];
        pages[3][idx++] = { f.code, f.label, CONTENT_X + c*(cw+gap), CONTENT_Y + r*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
      }
    }
    pageCounts[3] = idx;
  }

  // =========================================================
  // PAGE 5: 3 up/down adjuster pairs, stacked in columns so each
  // column is one up/down pair. Codes are placeholders (ADJ1/2/3) -
  // rename once you know what each pair should adjust.
  // =========================================================
  {
    const int cols = 3, rows = 2, gap = 8;
    const int cw = (CONTENT_W - gap*(cols-1)) / cols;
    const int ch = (CONTENT_H - gap*(rows-1)) / rows;

    struct FnDef { const char* code; const uint16_t* icon; int w, hgt; };
    FnDef upFns[3] = {
      { "ADJ1_UP", ICON_ARROW_UP, ICON_ARROW_UP_W, ICON_ARROW_UP_H },
      { "ADJ2_UP", ICON_ARROW_UP, ICON_ARROW_UP_W, ICON_ARROW_UP_H },
      { "ADJ3_UP", ICON_ARROW_UP, ICON_ARROW_UP_W, ICON_ARROW_UP_H },
    };
    FnDef downFns[3] = {
      { "ADJ1_DOWN", ICON_ARROW_DOWN, ICON_ARROW_DOWN_W, ICON_ARROW_DOWN_H },
      { "ADJ2_DOWN", ICON_ARROW_DOWN, ICON_ARROW_DOWN_W, ICON_ARROW_DOWN_H },
      { "ADJ3_DOWN", ICON_ARROW_DOWN, ICON_ARROW_DOWN_W, ICON_ARROW_DOWN_H },
    };
    int idx = 0;
    for (int c = 0; c < cols; c++) {
      FnDef &f = upFns[c];
      pages[4][idx++] = { f.code, nullptr, CONTENT_X + c*(cw+gap), CONTENT_Y + 0*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
    }
    for (int c = 0; c < cols; c++) {
      FnDef &f = downFns[c];
      pages[4][idx++] = { f.code, nullptr, CONTENT_X + c*(cw+gap), CONTENT_Y + 1*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
    }
    pageCounts[4] = idx;
  }
}

const uint16_t TAP_HIGHLIGHT_COLOR = TFT_ORANGE;

bool hasCode(const ButtonDef &b) {
  return b.code != nullptr && b.code[0] != '\0';
}

void drawButton(int i, bool pressed) {
  ButtonDef &b = pages[currentPage][i];
  int cx = b.x + b.w / 2;
  int cy = b.y + b.h / 2;

  // Clear this button's area back to the plain background first
  lcd.fillRect(b.x, b.y, b.w, b.h, BG_COLOR);

  if (hasCode(b) && String(b.code) == "BTN_CENTER") {
    // Special case: drawn as a solid red circle instead of the
    // usual icon/label rectangle, per the 11mm round button ask.
    int radius = b.w / 2;
    uint16_t fill = pressed ? TAP_HIGHLIGHT_COLOR : TFT_RED;
    lcd.fillCircle(cx, cy, radius, fill);
    if (b.label != nullptr) {
      lcd.setTextColor(TFT_WHITE, fill);
      lcd.setTextDatum(lgfx::middle_center);
      lcd.setTextSize(2);
      lcd.drawString(b.label, cx, cy);
    }
    return;
  }

  if (!hasCode(b) && b.icon == nullptr) {
    // Empty/reserved placeholder - draw a faint outline only, no fill highlight
    lcd.drawRoundRect(b.x, b.y, b.w, b.h, 8, 0x39C7);
    return;
  }

  int radius = (min(b.w, b.h) / 2) - 4;
  if (radius < 4) radius = 4;
  if (pressed) {
    lcd.fillCircle(cx, cy, radius, TAP_HIGHLIGHT_COLOR);
  }

  if (b.icon != nullptr && b.label != nullptr) {
    // Icon shifted up a bit, small corner-tag label underneath
    int ix = b.x + (b.w - b.iconW) / 2;
    int iy = cy - b.iconH / 2 - 8;
    lcd.pushImage(ix, iy, b.iconW, b.iconH, b.icon, (uint16_t)0x0000);
    lcd.setTextColor(TFT_WHITE, pressed ? TAP_HIGHLIGHT_COLOR : BG_COLOR);
    lcd.setTextDatum(lgfx::middle_center);
    lcd.setTextSize(2);
    lcd.drawString(b.label, cx, iy + b.iconH + 12);
  } else if (b.icon != nullptr) {
    int ix = b.x + (b.w - b.iconW) / 2;
    int iy = b.y + (b.h - b.iconH) / 2;
    lcd.pushImage(ix, iy, b.iconW, b.iconH, b.icon, (uint16_t)0x0000);
  } else if (b.label != nullptr) {
    lcd.setTextColor(TFT_WHITE, pressed ? TAP_HIGHLIGHT_COLOR : BG_COLOR);
    lcd.setTextDatum(lgfx::middle_center);
    lcd.setTextSize(2);
    lcd.drawString(b.label, cx, cy);
  }
}

void drawCheckerboard() {
  const int sqSize = 40; // clean fit: 320/40=8 cols, 240/40=6 rows
  int cols = lcd.width() / sqSize;
  int rows = lcd.height() / sqSize;
  for (int r = 0; r < rows; r++) {
    for (int c = 0; c < cols; c++) {
      uint16_t color = ((r + c) % 2 == 0) ? TFT_WHITE : TFT_BLACK;
      lcd.fillRect(c * sqSize, r * sqSize, sqSize, sqSize, color);
    }
  }
}

void drawAllButtons() {
  if (showCheckerPattern) {
    drawCheckerboard();
  } else {
    lcd.fillScreen(BG_COLOR);
  }
  for (int i = 0; i < pageCounts[currentPage]; i++) {
    drawButton(i, false);
  }
  drawSlider();
}

int touchedButton(int sx, int sy) {
  for (int i = 0; i < pageCounts[currentPage]; i++) {
    ButtonDef &b = pages[currentPage][i];
    if (sx >= b.x && sx <= b.x + b.w && sy >= b.y && sy <= b.y + b.h) {
      return i;
    }
  }
  return -1;
}

int lastPressed = -1;

// ---------- Page slider (right edge) ----------
// A dedicated vertical slider strip, completely separate from the
// button area, so dragging it can never accidentally hit a button.
// Has NUM_PAGES snap positions evenly spaced along the track.
const int SLIDER_X = 5;
const int SLIDER_Y = 10;
const int SLIDER_W = 27;
const int SLIDER_H = 220;
const int HANDLE_H = 50;
const int SLIDER_HIT_X_MAX = 42; // slightly generous grab area to the right of the visible handle
const uint16_t SLIDER_HANDLE_COLOR = TFT_BLUE;

bool isTouching = false;
bool draggingSlider = false;
int handleY = SLIDER_Y;

int handleYForPage(int page) {
  if (NUM_PAGES <= 1) return SLIDER_Y;
  int travel = SLIDER_H - HANDLE_H;
  return SLIDER_Y + (travel * page) / (NUM_PAGES - 1);
}

bool isInSliderRegion(int sx, int sy) {
  return sx <= SLIDER_HIT_X_MAX;
}

void drawSlider() {
  // Clear a bit wider than the handle itself so its old position
  // never leaves a ghost behind while dragging.
  lcd.fillRect(0, 0, SLIDER_X + SLIDER_W + 6, SCREEN_H, BG_COLOR);

  int hy = draggingSlider ? handleY : handleYForPage(currentPage);
  lcd.fillRoundRect(SLIDER_X + 2, hy, SLIDER_W - 4, HANDLE_H, 6, SLIDER_HANDLE_COLOR);
}

void updateSliderDrag(int touchY) {
  handleY = touchY - HANDLE_H / 2;
  if (handleY < SLIDER_Y) handleY = SLIDER_Y;
  if (handleY > SLIDER_Y + SLIDER_H - HANDLE_H) handleY = SLIDER_Y + SLIDER_H - HANDLE_H;
  drawSlider();
}

void finishSliderDrag() {
  int handleCenter = handleY + HANDLE_H / 2;
  int travel = SLIDER_H - HANDLE_H;
  // Which of the NUM_PAGES evenly-spaced snap points is closest?
  int newPage = 0;
  if (travel > 0) {
    float fraction = (float)(handleY - SLIDER_Y) / (float)travel;
    newPage = (int)(fraction * (NUM_PAGES - 1) + 0.5f);
  }
  if (newPage < 0) newPage = 0;
  if (newPage >= NUM_PAGES) newPage = NUM_PAGES - 1;

  if (newPage != currentPage) {
    currentPage = newPage;
    drawAllButtons();
    Serial.print("PAGE:");
    Serial.println(currentPage);
  } else {
    drawSlider();
  }
}

// ---------- Flag color handling ----------
// PC sends lines like "FLAG:GREEN" over the same serial connection.
// On any actual color change, we flash a few times, then settle solid.
uint16_t currentFlagColor = TFT_BLACK;
String currentFlagName = "NONE";
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
  if (name == "BLACK")     return 0x39C7;
  if (name == "CHECKERED") return TFT_WHITE;
  return TFT_BLACK; // "NONE"
}

void handleIncomingLine(const String &line) {
  if (line.startsWith("FLAG:")) {
    String name = line.substring(5);
    uint16_t newColor = colorForFlagName(name);
    if (newColor != currentFlagColor || name != currentFlagName) {
      currentFlagColor = newColor;
      currentFlagName = name;
      BG_COLOR = TFT_BLACK;
      showCheckerPattern = false;
      flashing = true;
      flashOn = false;
      flashesLeft = FLASH_COUNT;
      lastFlashToggle = millis();
      drawAllButtons();
    }
  }
}

void updateFlash() {
  if (!flashing) return;
  unsigned long now = millis();
  if (now - lastFlashToggle < FLASH_INTERVAL_MS) return;

  lastFlashToggle = now;
  flashOn = !flashOn;
  BG_COLOR = flashOn ? currentFlagColor : TFT_BLACK;
  showCheckerPattern = flashOn && (currentFlagName == "CHECKERED");
  drawAllButtons();

  if (!flashOn) {
    flashesLeft--;
    if (flashesLeft <= 0) {
      flashing = false;
      BG_COLOR = currentFlagColor;
      showCheckerPattern = (currentFlagName == "CHECKERED");
      drawAllButtons();
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);

  lcd.init();
  lcd.setRotation(1);

  buildLayout();
  drawAllButtons();

  Serial.println("Button box ready.");
  Serial.print("PAGE:");
  Serial.println(currentPage);
}

void loop() {
  while (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      handleIncomingLine(line);
    }
  }
  updateFlash();

  int32_t x, y;
  bool touchedNow = lcd.getTouch(&x, &y);

  if (touchedNow && !isTouching) {
    isTouching = true;
    draggingSlider = isInSliderRegion(x, y);
  }

  if (touchedNow && isTouching) {
    if (draggingSlider) {
      updateSliderDrag(y);
    } else {
      int idx = touchedButton(x, y);
      bool valid = (idx >= 0 && hasCode(pages[currentPage][idx]));
      int newPressed = valid ? idx : -1;

      if (newPressed != lastPressed) {
        if (lastPressed >= 0) {
          drawButton(lastPressed, false);
          Serial.print("RELEASE:");
          Serial.println(pages[currentPage][lastPressed].code);
        }
        if (newPressed >= 0) {
          drawButton(newPressed, true);
          Serial.print("PRESS:");
          Serial.println(pages[currentPage][newPressed].code);
        }
        lastPressed = newPressed;
      }
    }
  }

  if (!touchedNow && isTouching) {
    isTouching = false;
    if (draggingSlider) {
      finishSliderDrag();
      draggingSlider = false;
    } else if (lastPressed >= 0) {
      drawButton(lastPressed, false);
      Serial.print("RELEASE:");
      Serial.println(pages[currentPage][lastPressed].code);
      lastPressed = -1;
    }
  }

  delay(10);
}
