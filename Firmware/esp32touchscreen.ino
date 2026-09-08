/*
  Touch Screen Button Box - LovyanGFX version
  Board: Elegoo/Sunton "Cheap Yellow Display" - ESP32-2432S028R

  3 pages of buttons, a blank flag page, and an adjuster page,
  switched with a stack of tap-to-select buttons on the left edge:
    Page 1: blank - just shows the current flag color, nothing else
    Page 2: Reset, Tortoise, Wheel Repair, Battery
    Page 3: 2x fuel can + 4x tire (LF/RF/RR/LR)
    Page 4: D-pad plus a small red circle center button
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
bool showStripePattern = false;  // yellow/red debris flag pattern

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
  // PAGE 2: Reset, Tortoise, Wheel Repair, Battery. 2x2 grid.
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
        pages[1][idx++] = { f.code, f.label, CONTENT_X + c*(cw+gap), CONTENT_Y + r*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
      }
    }
    pageCounts[1] = idx;
  }

  // =========================================================
  // PAGE 3: 2x fuel can + 4x tire (LF/RF/RR/LR). 3x2 grid.
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
        pages[2][idx++] = { f.code, f.label, CONTENT_X + c*(cw+gap), CONTENT_Y + r*(ch+gap), cw, ch, f.icon, f.w, f.hgt };
      }
    }
    pageCounts[2] = idx;
  }

  // =========================================================
  // PAGE 4: D-pad, big, using the full content area, plus a
  // small red circle "OK" button in the middle cell.
  // =========================================================
  {
    const int cellW = CONTENT_W / 3;
    const int cellH = CONTENT_H / 3;
    int idx = 0;
    pages[3][idx++] = { "UP",    nullptr, CONTENT_X + 1*cellW, CONTENT_Y + 0*cellH, cellW, cellH, ICON_ARROW_UP,    ICON_ARROW_UP_W,    ICON_ARROW_UP_H };
    pages[3][idx++] = { "LEFT",  nullptr, CONTENT_X + 0*cellW, CONTENT_Y + 1*cellH, cellW, cellH, ICON_ARROW_LEFT,  ICON_ARROW_LEFT_W,  ICON_ARROW_LEFT_H };
    pages[3][idx++] = { "RIGHT", nullptr, CONTENT_X + 2*cellW, CONTENT_Y + 1*cellH, cellW, cellH, ICON_ARROW_RIGHT, ICON_ARROW_RIGHT_W, ICON_ARROW_RIGHT_H };
    pages[3][idx++] = { "DOWN",  nullptr, CONTENT_X + 1*cellW, CONTENT_Y + 2*cellH, cellW, cellH, ICON_ARROW_DOWN,  ICON_ARROW_DOWN_W,  ICON_ARROW_DOWN_H };

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
      pages[3][idx++] = { "BTN_CENTER", "OK", smallX, smallY, diameterPx, diameterPx, nullptr, 0, 0 };
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

void drawStripes() {
  // Yellow/red vertical stripes - the "debris on track" surface flag
  const int stripeW = 40;
  int cols = lcd.width() / stripeW + 1;
  for (int c = 0; c < cols; c++) {
    uint16_t color = (c % 2 == 0) ? TFT_YELLOW : TFT_RED;
    lcd.fillRect(c * stripeW, 0, stripeW, lcd.height(), color);
  }
}

// ---------- Best lap time display (page 1 / blank flag page only) ----------
// PC sends "LAPTIME:<seconds>" whenever your best lap changes.
String currentLapTimeStr = "--:--.---";

String formatLapTime(float totalSeconds) {
  if (totalSeconds <= 0) return "--:--.---";
  int minutes = (int)(totalSeconds / 60.0f);
  float secs = totalSeconds - (minutes * 60.0f);
  char buf[16];
  snprintf(buf, sizeof(buf), "%d:%06.3f", minutes, secs);
  return String(buf);
}

// Draws text with a black outline so it stays readable over ANY
// background - solid color, checkerboard, or stripes alike.
void drawOutlinedText(const String &text, int x, int y, int textSize) {
  lcd.setTextDatum(lgfx::middle_center);
  lcd.setTextSize(textSize);
  lcd.setTextColor(TFT_BLACK);
  const int off = 2;
  lcd.drawString(text, x - off, y);
  lcd.drawString(text, x + off, y);
  lcd.drawString(text, x, y - off);
  lcd.drawString(text, x, y + off);
  lcd.setTextColor(TFT_WHITE);
  lcd.drawString(text, x, y);
}

void drawLapTimeDisplay() {
  int cx = SCREEN_W / 2;
  drawOutlinedText("BEST LAP", cx, 95, 2);
  drawOutlinedText(currentLapTimeStr, cx, 135, 4);
}

void drawAllButtons() {
  if (showCheckerPattern) {
    drawCheckerboard();
  } else if (showStripePattern) {
    drawStripes();
  } else {
    lcd.fillScreen(BG_COLOR);
  }
  for (int i = 0; i < pageCounts[currentPage]; i++) {
    drawButton(i, false);
  }
  if (currentPage == 0) {
    drawLapTimeDisplay();
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

// ---------- Page buttons (right edge) ----------
// A stack of small buttons, one per page, same width the old slider
// used - completely separate from the button area so tapping here
// can never accidentally hit a content button. Tap one to jump
// straight to that page; the current page's button is filled in,
// the rest are just outlined.
const int SLIDER_X = 5;
const int SLIDER_Y = 10;
const int SLIDER_W = 27;
const int SLIDER_H = 220;
const int PAGE_BTN_GAP = 4;
const int SLIDER_HIT_X_MAX = 42; // slightly generous grab area to the right of the buttons
const uint16_t PAGE_BTN_COLOR = TFT_BLUE;

bool isTouching = false;

int pageBtnHeight() {
  return (SLIDER_H - PAGE_BTN_GAP * (NUM_PAGES - 1)) / NUM_PAGES;
}

int pageBtnY(int page) {
  return SLIDER_Y + page * (pageBtnHeight() + PAGE_BTN_GAP);
}

bool isInSliderRegion(int sx, int sy) {
  return sx <= SLIDER_HIT_X_MAX;
}

// Returns which page button (0..NUM_PAGES-1) contains this point, or
// -1 if the tap landed in a gap/outside all of them.
int pageButtonAt(int sy) {
  int h = pageBtnHeight();
  for (int p = 0; p < NUM_PAGES; p++) {
    int by = pageBtnY(p);
    if (sy >= by && sy <= by + h) return p;
  }
  return -1;
}

void drawSlider() {
  // Clear a bit wider than the buttons themselves so nothing lingers
  lcd.fillRect(0, 0, SLIDER_X + SLIDER_W + 6, SCREEN_H, BG_COLOR);

  int h = pageBtnHeight();
  for (int p = 0; p < NUM_PAGES; p++) {
    int by = pageBtnY(p);
    if (p == currentPage) {
      lcd.fillRoundRect(SLIDER_X + 2, by, SLIDER_W - 4, h, 6, PAGE_BTN_COLOR);
    } else {
      lcd.drawRoundRect(SLIDER_X + 2, by, SLIDER_W - 4, h, 6, TFT_WHITE);
    }
  }
}

void selectPage(int newPage) {
  if (newPage < 0 || newPage >= NUM_PAGES || newPage == currentPage) return;
  currentPage = newPage;
  drawAllButtons();
  Serial.print("PAGE:");
  Serial.println(currentPage);
}

// ---------- Hidden easter egg ----------
// Send the exact text "TestAll:PARTY" over serial (no button for this
// on purpose) to run a quick flash-through of every flag color and
// pattern - see the non-blocking startParty()/updateParty() system
// further down, which does the actual work.

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
String flagBeforeParty = "NONE";

uint16_t colorForFlagName(const String &name) {
  if (name == "GREEN")     return TFT_GREEN;
  if (name == "YELLOW")    return TFT_YELLOW;
  if (name == "RED")       return TFT_RED;
  if (name == "BLUE")      return TFT_BLUE;
  if (name == "WHITE")     return TFT_WHITE;
  if (name == "BLACK")     return 0x39C7;
  if (name == "CHECKERED") return TFT_WHITE;
  if (name == "DEBRIS")    return TFT_YELLOW;
  return TFT_BLACK; // "NONE"
}

void applyPartyFrame() {
  String name = PARTY_SEQUENCE[partyIndex];
  currentFlagColor = colorForFlagName(name);
  currentFlagName = name;
  BG_COLOR = currentFlagColor;
  showCheckerPattern = (name == "CHECKERED");
  showStripePattern = (name == "DEBRIS");
  drawAllButtons();
}

void startParty() {
  flagBeforeParty = currentFlagName;
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
    // Done - restore whatever flag was actually showing before party mode
    partyMode = false;
    currentFlagColor = colorForFlagName(flagBeforeParty);
    currentFlagName = flagBeforeParty;
    BG_COLOR = currentFlagColor;
    showCheckerPattern = (flagBeforeParty == "CHECKERED");
    showStripePattern = (flagBeforeParty == "DEBRIS");
    drawAllButtons();
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
    if (newColor != currentFlagColor || name != currentFlagName) {
      currentFlagColor = newColor;
      currentFlagName = name;
      BG_COLOR = TFT_BLACK;
      showCheckerPattern = false;
      showStripePattern = false;
      flashing = true;
      flashOn = false;
      flashesLeft = FLASH_COUNT;
      lastFlashToggle = millis();
      drawAllButtons();
    }
  } else if (line.startsWith("LAPTIME:")) {
    float t = line.substring(8).toFloat();
    currentLapTimeStr = formatLapTime(t);
    if (currentPage == 0) {
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
  showStripePattern = flashOn && (currentFlagName == "DEBRIS");
  drawAllButtons();

  if (!flashOn) {
    flashesLeft--;
    if (flashesLeft <= 0) {
      flashing = false;
      BG_COLOR = currentFlagColor;
      showCheckerPattern = (currentFlagName == "CHECKERED");
      showStripePattern = (currentFlagName == "DEBRIS");
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
  if (partyMode) {
    updateParty();
  } else {
    updateFlash();
  }

  int32_t x, y;
  bool touchedNow = lcd.getTouch(&x, &y);

  if (touchedNow && !isTouching) {
    isTouching = true;
    if (isInSliderRegion(x, y)) {
      int tappedPage = pageButtonAt(y);
      if (tappedPage >= 0) {
        selectPage(tappedPage);
      }
    }
  }

  if (touchedNow && isTouching) {
    // Normal content-button handling. This is naturally a no-op when x
    // falls in the page-button column, since no content button lives
    // there - the two zones never overlap.
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

  if (!touchedNow && isTouching) {
    isTouching = false;
    if (lastPressed >= 0) {
      drawButton(lastPressed, false);
      Serial.print("RELEASE:");
      Serial.println(pages[currentPage][lastPressed].code);
      lastPressed = -1;
    }
  }

  delay(10);
}
