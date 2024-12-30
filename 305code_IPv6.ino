// **ESP32 Code with LCD Integration and Server Synchronization (Link-Local IPv6 Enabled)**

// Include necessary libraries
#include <WiFi.h>
#include <HTTPClient.h>
#include <PulseSensorPlayground.h>
#include <Wire.h>
#include <LiquidCrystal_PCF8574.h>
#include "lwip/netif.h"
#include "lwip/ip6_addr.h"

// **Wi-Fi Credentials**
const char* ssid = "Sakan";             // Your Wi-Fi SSID
const char* password = "1SSID_M0462";     // Your Wi-Fi Password

// **Server Details**
// Replace with your Flask server's link-local IPv6 address with percent-encoded zone index
// For "%3", percent-encode '%' as "%25", so "%3" becomes "%253"
const char* serverIP = "http://[fe80::1ee5:a94:cd93:149b]:5000";

// **Pulse Sensor Setup**
const int PulseSensorPin = 34;       // Use GPIO 34 for pulse sensor input
PulseSensorPlayground pulseSensor;

// **LCD Setup**
#define I2C_ADDR 0x27                // Replace with your LCD's I2C address
LiquidCrystal_PCF8574 lcd(I2C_ADDR);

// **Function to display messages on the LCD**
void displayMessage(const char* line1, const char* line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

// **Function to send data to server**
void sendDataToServer(const String& measurement, float value) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String(serverIP) + "/upload_sensor_data";
    http.begin(url);

    http.addHeader("Content-Type", "application/x-www-form-urlencoded");

    // **Prepare Data**
    String postData = "measurement=" + measurement + "&value=" + String(value);

    // **Send HTTP POST Request**
    int httpResponseCode = http.POST(postData);

    if (httpResponseCode > 0) {
      String response = http.getString(); // Get the response payload
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
      Serial.println("Response from server: " + response);

      // Check if server acknowledges receipt
      if (response.indexOf("\"status\": \"success\"") >= 0) {
        displayMessage((measurement + " sent:").c_str(), String(value).c_str());
      } else {
        displayMessage("Error sending", (measurement + " data").c_str());
      }
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
      displayMessage("Error sending", (measurement + " data").c_str());
    }

    http.end(); // Free resources
  } else {
    Serial.println("Wi-Fi not connected");
    displayMessage("Wi-Fi not", "connected");
  }
}

// **Function to check if pulse data is needed from the server**
bool needPulseData() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String(serverIP) + "/need_pulse_data";
    http.begin(url);

    int httpResponseCode = http.GET();

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Pulse data needed response: " + response);

      if (response.indexOf("\"need_pulse\": true") >= 0) {
        return true;
      } else {
        return false;
      }
    } else {
      Serial.print("Error checking if pulse data is needed: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  } else {
    Serial.println("Wi-Fi not connected");
    displayMessage("Wi-Fi not", "connected");
  }
  return false;
}

// **Function to print the ESP32's IPv6 Addresses**
void printLocalIPv6() {
  // Iterate over the network interfaces
  struct netif* netif = netif_list;

  while (netif != NULL) {
    if (netif_is_up(netif)) {
      for (int i = 0; i < LWIP_IPV6_NUM_ADDRESSES; i++) {
        if (ip6_addr_isvalid(netif_ip6_addr_state(netif, i))) {
          char address[40];
          ip6addr_ntoa_r(netif_ip6_addr(netif, i), address, sizeof(address));
          Serial.print("ESP32 IPv6 Address: ");
          Serial.println(address);
        }
      }
    }
    netif = netif->next;
  }
}

// **Wi-Fi Event Handler**
void WiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP6:
      Serial.println("ESP32 obtained an IPv6 address:");
      printLocalIPv6();
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print("IPv4 Address: ");
      Serial.println(WiFi.localIP());
      break;
    default:
      break;
  }
}

void setup() {
  // **Initialize Serial Communication**
  Serial.begin(115200);

  // **Enable IPv6**
  WiFi.enableIPv6();

  // **Initialize Pulse Sensor**
  pulseSensor.analogInput(PulseSensorPin);
  pulseSensor.setThreshold(350);  // Adjust threshold as needed

  // **Initialize the LCD**
  lcd.begin(16, 2);  // Set up the LCD's number of columns and rows
  lcd.setBacklight(255);
  displayMessage("Initializing...", "");

  // **Register Wi-Fi Event Handler**
  WiFi.onEvent(WiFiEvent);

  // **Connect to Wi-Fi**
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  displayMessage("Connecting to", "Wi-Fi...");

  // Wait until connected
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }

  Serial.println("\nConnected to Wi-Fi network.");

  // **Display IP Addresses**
  Serial.print("IPv4 Address: ");
  Serial.println(WiFi.localIP());
  printLocalIPv6(); // Print IPv6 addresses

  displayMessage("Wi-Fi", "Connected");

  // **Start Pulse Sensor**
  if (pulseSensor.begin()) {
    Serial.println("Pulse sensor started successfully!");
    displayMessage("Pulse Sensor", "Started");
  } else {
    Serial.println("Pulse sensor failed to start. Check your connections.");
    displayMessage("Pulse Sensor", "Failed");
  }

  delay(2000); // Wait before starting measurements
}

void loop() {
  // **Ensure Wi-Fi is Connected**
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Reconnecting...");
    displayMessage("Wi-Fi", "Reconnecting...");
    WiFi.reconnect();
    delay(1000);
    return;
  }

  // **Check if Pulse Data is Needed**
  if (needPulseData()) {
    Serial.println("Pulse data is needed by the server.");
    displayMessage("Measure your", "pulse now");

    // **Pulse Measurement**
    Serial.println("Starting pulse measurement...");

    // **Wait for Pulse Data**
    bool pulseDataSent = false;
    unsigned long startTime = millis();

    while (!pulseDataSent && (millis() - startTime) < 20000) { // Wait for 20 seconds max
      int myBPM = pulseSensor.getBeatsPerMinute();

      if (pulseSensor.sawStartOfBeat()) {
        Serial.println("Beat detected!");
        Serial.print("BPM: ");
        Serial.println(myBPM);

        displayMessage("Pulse Measured:", String(myBPM).c_str());
        delay(2000); // Display the BPM for 2 seconds

        // **Send Pulse Data to Server**
        sendDataToServer("pulse", myBPM);
        pulseDataSent = true;
      } else {
        Serial.println("No beat detected.");
        displayMessage("No beat", "detected");
      }

      delay(1000); // Wait before the next reading
    }

    if (!pulseDataSent) {
      Serial.println("Failed to measure pulse within the time limit.");
      displayMessage("Pulse Measure", "Failed");
    }

    // **End of Measurement**
    displayMessage("Measurement", "Complete");
    Serial.println("Measurement completed.");

    delay(5000); // Display the completion message for 5 seconds
  } else {
    // **Idle State**
    displayMessage("Waiting for", "instructions...");
    Serial.println("Waiting for measurement instructions from server.");
    delay(5000); // Wait before checking again
  }
}