#include <WiFi.h>
#include <HTTPClient.h>
#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>
#include <time.h>
#include <esp_system.h>

// ================= WIFI =================
const char* ssid     = "";
const char* password = "";

// ================= API =================
const char* apiUrl =
"https://";

// ================= MATRIX =================
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 4
#define CS_PIN 5

MD_Parola matrix(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);
MD_MAX72XX* mx;   // <-- pointer (IMPORTANT)

// Text buffer (must persist for Parola)
char displayBuf[24];
bool isScrolling = false;

// ================= TIMING =================
unsigned long lastRequestTime = 0;
const unsigned long interval = 60000; // 1 minute

// ================= DATA =================
struct SugarData {
  int glucose;
  String trend;
  int64_t epochMs;};   

// ================= ARROW BITMAPS =================
const uint8_t ARROW_UP[8] = {
  B00011000,
  B00111100,
  B01111110,
  B00011000,
  B00011000,
  B00011000,
  B00011000,
  B00000000
};

const uint8_t ARROW_DOWN[8] = {
  B00011000,
  B00011000,
  B00011000,
  B00011000,
  B01111110,
  B00111100,
  B00011000,
  B00000000
};

const uint8_t ARROW_RIGHT[8] = {
  B00001000,
  B00001100,
  B11111110,
  B00001100,
  B00001000,
  B00000000,
  B00000000,
  B00000000
};

const uint8_t ARROW_45_UP[8] = {
  B00000000,
  B00111110,
  B00011110,
  B00111110,
  B01111110,
  B11110010,
  B11100000,
  B01000000
};

const uint8_t ARROW_45_DOWN[8] = {
  B01000000,
  B11100000,
  B11110010,
  B01111110,
  B00111110,
  B00011110,
  B00111110,
  B00000000
};

// Double arrows (stacked or side-by-side)
const uint8_t DOUBLE_ARROW_UP[8] = {
  B00011000,
  B00111100,
  B01111110,
  B00011000,
  B00011000,
  B00111100,
  B01111110,
  B00011000
};

const uint8_t DOUBLE_ARROW_DOWN[8] = {
  B00011000,
  B01111110,
  B00111100,
  B00011000,
  B00011000,
  B01111110,
  B00111100,
  B00011000
};

const uint8_t DOUBLE_ARROW_RIGHT[8] = {
  B00001000,
  B00001100,
  B11111110,
  B00001100,
  B00001000,
  B00001100,
  B11111110,
  B00001100
};

// Triple arrows (compressed)
const uint8_t TRIPLE_ARROW_UP[8] = {
  B00011000,
  B00111100,
  B01111110,
  B00011000,
  B00111100,
  B01111110,
  B00111100,
  B01111110
};

const uint8_t TRIPLE_ARROW_DOWN[8] = {
  B01111110,
  B00111100,
  B01111110,
  B00111100,
  B01111110,
  B00111100,
  B00011000,
  B00011000
};

const uint8_t TRIPLE_ARROW_RIGHT[8] = {
  B00001000,
  B11111110,
  B00001100,
  B00001000,
  B11111110,
  B00001100,
  B00001000,
  B11111110
};

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println("\n=== BG Monitor Started ===");
  Serial.print("Reset reason: ");
  Serial.println(esp_reset_reason());

  matrix.begin();
  matrix.setIntensity(1);
  matrix.displayClear();
  
  // Zone 0: modules 1-3 (text area - 24 columns)
  // Zone 1: module 0 (arrow - 8 columns)
  // FC16: module 0 is physically rightmost
  matrix.setZone(0, 1, MAX_DEVICES - 1);
  matrix.setZone(1, 0, 0);
  
  mx = matrix.getGraphicObject();

  connectWiFi();
  setupTime();
  Serial.println("Time synced");
  hitAPI();
  lastRequestTime = millis();
  Serial.println("Setup complete, entering loop");
}

// ================= LOOP =================
void loop() {
  if (matrix.displayAnimate()) {
    // Animation finished, restart if scrolling
    if (isScrolling) {
      matrix.displayReset(0);
    }
  }
  if (millis() - lastRequestTime >= interval) {
    lastRequestTime = millis();
    hitAPI();
  }
}

// ================= WIFI =================
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  Serial.println("WiFi OK");
}

// ================= TIME =================
void setupTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  time_t now;
  while (time(&now) < 100000) delay(200);
}

// ================= API =================
void hitAPI() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected!");
    return;
  }

  HTTPClient http;
  http.begin(apiUrl);
  int code = http.GET();

  if (code == HTTP_CODE_OK) {
    String payload = http.getString();
    SugarData data = parseResponse(payload);
    
    Serial.print("BG: ");
    Serial.print(data.glucose);
    Serial.print(" ");
    Serial.print(data.trend);
    Serial.print(" (age: ");
    Serial.print(minutesOld(data.epochMs));
    Serial.println("m)");
    
    renderDisplay(data);
  } else {
    Serial.print("HTTP Error: ");
    Serial.println(code);
  }

  http.end();
}


// ================= PARSER =================
SugarData parseResponse(String p) {
  SugarData d;

  int t1 = p.indexOf('\t');
  int t2 = p.indexOf('\t', t1 + 1);
  int t3 = p.indexOf('\t', t2 + 1);
  int t4 = p.indexOf('\t', t3 + 1);

  d.epochMs = atoll(p.substring(t1 + 1, t2).c_str());
  d.glucose = p.substring(t2 + 1, t3).toInt();
  d.trend   = p.substring(t3 + 1, t4);

  d.trend.replace("\"", "");
  d.trend.trim();

  return d;
}

// ================= AGE =================
long minutesOld(int64_t epochMs) {
  time_t now;
  time(&now);
  int64_t nowMs = (int64_t)now * 1000;
  return (nowMs - epochMs) / 60000;
}


// ================= TREND HELPERS =================
bool isInvalidTrend(String t) {
  return t == "NONE" ||
         t == "NOT COMPUTABLE" ||
         t == "RATE OUT OF RANGE";
}

String simplifyTrend(String t) {
  if (t.indexOf("FortyFive") != -1) {
    if (t.indexOf("Down") != -1) return "FortyFiveDown";
    if (t.indexOf("Up") != -1) return "FortyFiveUp";
  }
  if (t.indexOf("Up") != -1) return "Up";
  if (t.indexOf("Down") != -1) return "Down";
  if (t.indexOf("Flat") != -1) return "Flat";
  return t;
}

int arrowCount(String t) {
  if (t.startsWith("Triple")) return 3;
  if (t.startsWith("Double")) return 2;
  return 1;
}

const uint8_t* arrowBitmap(String t) {
  if (t == "Flat") return ARROW_RIGHT;
  if (t == "FortyFiveUp") return ARROW_45_UP;
  if (t == "FortyFiveDown") return ARROW_45_DOWN;
  if (t.endsWith("Up")) return ARROW_UP;
  if (t.endsWith("Down")) return ARROW_DOWN;
  return ARROW_RIGHT;
}

// ================= DISPLAY =================
void renderDisplay(SugarData d) {
  matrix.displayClear();

  if (isInvalidTrend(d.trend)) {
    displayInvalid();
    clearArrowModule();
    return;
  }

  long age = minutesOld(d.epochMs);
  String singleTrend = simplifyTrend(d.trend);

  // Always draw arrow on module 0 (rightmost physically)
  // HARDCODED FOR TESTING:
  displayArrow(singleTrend);

  if (age >= 15) {
    // Scroll glucose + age on zone 0 (modules 1-3)
    snprintf(displayBuf, sizeof(displayBuf), "%d -%ldm", d.glucose, age);
    matrix.displayZoneText(0, displayBuf, PA_LEFT, 80, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
    isScrolling = true;
  } else {
    // Static glucose on zone 0
    snprintf(displayBuf, sizeof(displayBuf), "%d", d.glucose);
    matrix.displayZoneText(0, displayBuf, PA_LEFT, 0, 0, PA_PRINT, PA_NO_EFFECT);
    isScrolling = false;
  }
  matrix.displayReset(0);
}

void clearArrowModule() {
  // Module 0 is physically rightmost (arrow module)
  for (int r = 0; r < 8; r++) {
    mx->setRow(0, r, 0);
  }
}

// ================= TEXT =================
void displayInvalid() {
  snprintf(displayBuf, sizeof(displayBuf), "---");
  matrix.displayZoneText(0, displayBuf, PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);
  isScrolling = false;
  matrix.displayReset(0);
}


// ================= ARROWS =================
void displayArrow(String trend) {
  const uint8_t* bmp = arrowBitmap(trend);
  // Module 0 is physically rightmost on FC16
  for (int r = 0; r < 8; r++) {
    mx->setRow(0, r, bmp[r]);
  }
}