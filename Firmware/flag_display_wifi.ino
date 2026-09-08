/*
  Flag-Only Display - WiFi (UDP) version
  Board: Elegoo/Sunton "Cheap Yellow Display" - ESP32-2432S028R

  Same as flag_display_only.ino, but receives "FLAG:<NAME>" commands
  over WiFi instead of a USB cable - so this board can be mounted
  anywhere with WiFi coverage (a wall, a shelf, wherever) with just a
  power cable, no tether to your PC at all.

  Uses UDP rather than a "real" connection, since this board only
  ever receives commands and never has anything to send back - a
  plain, connectionless message is all that's needed.

  SETUP
  -----
  1. Edit WIFI_SSID / WIFI_PASSWORD below.
  2. Upload, then open Serial Monitor once at 115200 baud right after
     boot - it prints the IP address it was assigned. You'll need
     this (or the printed flagdisplay.local name) for the PC script.
  3. Recommended: on your router, set a DHCP reservation (a fixed IP)
     for this board's MAC address, so the address never changes after
     a power outage or router restart.
*/

#define LGFX_USE_V1
#define LGFX_SUNTON_ESP32_2432S028
#include <LovyanGFX.hpp>
#include <LGFX_AUTODETECT.hpp>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPmDNS.h>

static LGFX lcd;

// ---------- WiFi settings - edit these ----------
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const unsigned int UDP_PORT = 4210;
const char* MDNS_NAME = "flagdisplay"; // reachable as flagdisplay.local on most networks

WiFiUDP udp;
char packetBuffer[64];

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

void drawCheckerboard() {
  const int sqSize = 40;
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

// ---------- Party mode easter egg (same as the USB version) ----------
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
  flashing = false;
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
      drawFlagFrame(false);
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
      drawFlagFrame(true);
    }
  }
}

void connectWiFi() {
  lcd.fillScreen(TFT_BLACK);
  lcd.setTextDatum(lgfx::middle_center);
  lcd.setTextColor(TFT_WHITE);
  lcd.setTextSize(2);
  lcd.drawString("Connecting to WiFi...", lcd.width() / 2, lcd.height() / 2);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  if (MDNS.begin(MDNS_NAME)) {
    Serial.print("Also reachable as: ");
    Serial.print(MDNS_NAME);
    Serial.println(".local");
  }

  udp.begin(UDP_PORT);
  Serial.print("Listening for UDP flag commands on port ");
  Serial.println(UDP_PORT);

  // Show the IP on screen for a few seconds so you can read it off
  // the board directly during setup, without needing a laptop nearby.
  lcd.fillScreen(TFT_BLACK);
  lcd.setTextSize(2);
  lcd.drawString("IP: " + WiFi.localIP().toString(), lcd.width() / 2, lcd.height() / 2 - 20);
  lcd.setTextSize(1);
  lcd.drawString(String(MDNS_NAME) + ".local", lcd.width() / 2, lcd.height() / 2 + 15);
  delay(4000);
}

void setup() {
  Serial.begin(115200);
  delay(300);

  lcd.init();
  lcd.setRotation(3); // match your button box - flip to 1 if upside down

  connectWiFi();
  drawFlagFrame(true);

  Serial.println("Flag display (WiFi) ready.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi dropped - reconnecting...");
    connectWiFi();
    drawFlagFrame(true);
  }

  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) packetBuffer[len] = 0;
    String line = String(packetBuffer);
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
