BUTTON BOX SKETCH - CODE WALKTHROUGH
======================================
This explains how button_box_8btn.ino works, section by section,
in roughly the order things appear in the file.


SETUP AND BOARD CONFIG (top of file)
-------------------------------------
    #define LGFX_USE_V1
    #define LGFX_SUNTON_ESP32_2432S028
    #include <LovyanGFX.hpp>
    #include <LGFX_AUTODETECT.hpp>

These four lines tell LovyanGFX "I'm using the Sunton/CYD board" -
instead of manually wiring up pin numbers for the display and touch
chip, this uses the library's built-in profile for this exact board.

    static LGFX lcd;

This is the one object you call everything through - lcd.fillScreen(),
lcd.getTouch(), etc.


THE DATA MODEL: WHAT A "BUTTON" ACTUALLY IS
---------------------------------------------
    struct ButtonDef {
      const char* code;   // "" or nullptr = placeholder, sends nothing
      const char* label;  // small text - shown alone, or as a tag under an icon
      int x, y, w, h;
      const uint16_t* icon;
      int iconW, iconH;
    };

This struct is the core idea the whole sketch is built around. Every
button - D-pad arrow, tire, gas can, whatever - is just one of these.
It knows where it lives on screen (x, y, w, h), what to send over
serial when tapped (code), and what to draw (icon and/or label).

    ButtonDef pages[NUM_PAGES][MAX_BUTTONS_PER_PAGE];
    int pageCounts[NUM_PAGES] = {0, 0, 0, 0};
    int currentPage = 0;

"pages" is a 2D array - think of it as 4 separate buckets (one per
page), each holding up to 9 buttons. "pageCounts" remembers how many
buttons are ACTUALLY used in each bucket (page 1 only fills 4 of its
9 slots, for example). "currentPage" is simply "which bucket am I
looking at right now" - almost every other function reads from
pages[currentPage].


buildLayout() - THE MATH THAT POSITIONS EVERYTHING
----------------------------------------------------
This function runs once at startup and fills in the pages[] arrays
with real coordinates. The pattern repeats for every page:

    const int cols = 2, rows = 2, gap = 8;
    const int cw = (CONTENT_W - gap*(cols-1)) / cols;
    const int ch = (CONTENT_H - gap*(rows-1)) / rows;

This is just "how wide/tall should each button be so N of them fit
evenly across the available space, with a gap between them." Then a
loop walks through rows and columns, placing each button at
CONTENT_X + c*(cw+gap), CONTENT_Y + r*(ch+gap) - standard grid math.

The local FnDef structs (like { "BTN_RESET", nullptr, ICON_RESET, ... })
are just a convenient shorthand list you edit when you want to change
which icon/code goes in which slot - the loop converts each one into
a full ButtonDef with real pixel coordinates.


DRAWING A BUTTON (drawButton function)
------------------------------------------
This one function handles every visual case:

    if (!hasCode(b) && b.icon == nullptr) {
      lcd.drawRoundRect(b.x, b.y, b.w, b.h, 8, 0x39C7);
      return;
    }

Empty placeholder -> just draw a faint outline and stop.

    if (b.icon != nullptr && b.label != nullptr) {
      // icon + small text tag (used for the 4 identical tire icons)
    } else if (b.icon != nullptr) {
      // icon alone
    } else if (b.label != nullptr) {
      // text alone
    }

This is why the tire buttons show "LF"/"RF" text under an otherwise
identical icon, while the D-pad arrows show icon only.

The actual icon-drawing line is worth understanding:

    lcd.pushImage(ix, iy, b.iconW, b.iconH, b.icon, (uint16_t)0x0000);

Your icons are stored as solid white-on-BLACK 64x64 images (that's
what icons.h contains - raw pixel color values). The last argument,
0x0000 (black), tells pushImage "treat this exact color as
transparent." Every black pixel in the icon gets skipped, and only
the white icon shape actually draws - that's how icons appear to
"float" on whatever background color is behind them, including
during a flag flash.


HIT-TESTING (touchedButton function)
----------------------------------------
    if (sx >= b.x && sx <= b.x + b.w && sy >= b.y && sy <= b.y + b.h) {
      return i;
    }

Simple rectangle math - "is this touch point inside this button's
box." Loops through the current page's buttons and returns the index
of whichever one contains the touch point, or -1 if none do.


THE SLIDER
-------------
The trickiest part conceptually. A few key ideas:

- SLIDER_HIT_X_MIN defines an invisible line near the right edge -
  any touch starting past that x-coordinate is claimed by the
  slider, never by a button. That's decided ONCE, the instant your
  finger touches down (draggingSlider = isInSliderRegion(x, y)), and
  stays true for the whole gesture even if your finger later drifts
  left.

- handleYForPage() does the reverse of hit-testing - given a page
  number, it calculates where the handle SHOULD sit, evenly spacing
  however many pages exist along the track:
      SLIDER_Y + (travel * page) / (NUM_PAGES - 1)
  This is why adding a 4th page didn't need any hardcoded pixel
  tweaking - the math just spreads 4 positions instead of 3.

- While dragging, updateSliderDrag() just follows your finger,
  clamped so the handle can't slide off either end of the track.

- On release, finishSliderDrag() figures out which of the
  evenly-spaced snap points your finger ended up closest to, and
  switches pages if it's different.


THE FLAG/FLASH SYSTEM
-------------------------
handleIncomingLine() watches for text like "FLAG:GREEN" arriving
over USB serial (sent by the Python script on your PC). When the
flag actually changes, it doesn't just flip the color - it kicks off
a small animation:
    flashing = true;
    flashesLeft = 6;

Then updateFlash(), called every loop, toggles the background
between black and the flag color every 150ms, counting down
flashesLeft until it settles on the solid color.

This is a NON-BLOCKING animation - there's no delay() sitting inside
a loop waiting. It just checks "has enough time passed since the
last toggle?" and does one step if so, then immediately returns.
That's what lets the touchscreen stay responsive to taps DURING a
flag flash instead of freezing.


loop() - THE TOUCH STATE MACHINE
------------------------------------
This is the heart of the whole program, running about 100 times a
second (delay(10) at the bottom). Each pass:
  1. Checks for incoming serial flag commands
  2. Advances the flash animation one step if needed
  3. Reads the touch controller once (lcd.getTouch(&x, &y))

The touch logic is a small state machine built around comparing "was
I touching last frame" (isTouching) to "am I touching right now"
(touchedNow):
  - Just started touching -> decide ONCE whether it's a slider grab
    or a button tap
  - Still touching -> keep updating whichever one it was
  - Just stopped touching -> finalize: snap the slider, or release
    the button highlight

The DEBOUNCE_MS check:
    idx != lastPressed || (now - lastPressTime) > DEBOUNCE_MS

This is what lets you hold a D-pad button down and have it keep
re-sending its code every 200ms, while still not spamming duplicate
sends every single 10ms loop cycle.


QUESTIONS?
-------------
The three spots most people find least obvious at first glance:
  1. The icon color-key trick (black = transparent)
  2. The slider math (evenly spacing N pages along a track)
  3. The debounce / touch state machine logic

Feel free to ask for a deeper dive on any of these.
