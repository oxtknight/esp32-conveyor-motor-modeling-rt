#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define WIFI_NETWORK "TK's M16"
#define WIFI_PASSWORD "knight20072006"
#define WIFI_TIMEOUT_MS 100000

int count = 0;
float Real_Speed = 0;
unsigned long passing_time = 0;
unsigned long measurement_time = 0;
unsigned long timing = 0;
float Real_Voltage = 0;
float Real_Current = 0;
bool Encoder = LOW;
bool previous_Encoder = LOW;
int httpResponseCode = 0;

void setup() {
    Serial.begin(9600);
    connectToWifi();
    pinMode(25, INPUT);
}

void loop() {

    timing = millis();

    Real_Voltage = analogRead(A0) * (3.3 / 4095.0);
    Real_Current = analogRead(A2) * (3.3 / 4095.0);

    Encoder = digitalRead(25);

    if (timing - passing_time <= 100) {

        if (Encoder == HIGH && previous_Encoder == LOW) {
            count++;
        }

        previous_Encoder = Encoder;

    } else {

        Real_Speed = 60.0 * count / (20.0 * 0.1);

        passing_time = timing;
        measurement_time += 100;
        count = 0;

        httpResponseCode = sendMeasurement(
            Real_Voltage,
            Real_Current,
            Real_Speed,
            measurement_time
        );

        if (httpResponseCode > 0) {
            Serial.print("HTTP Response: ");
            Serial.println(httpResponseCode);
        } else {
            Serial.print("Error sending POST: ");
            Serial.println(httpResponseCode);
        }
    }
}

void connectToWifi() {

    Serial.print("Connecting to Wifi");

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_NETWORK, WIFI_PASSWORD);

    unsigned long start = millis();

    while (WiFi.status() != WL_CONNECTED &&
           millis() - start < WIFI_TIMEOUT_MS) {

        Serial.print(".");
        delay(100);
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(" Failed!");
    } else {
        Serial.print("Connected! ");
        Serial.println(WiFi.localIP());
    }
}

int sendMeasurement(float Voltage, float Current, float Speed, unsigned int timer)
{
    if (WiFi.status() == WL_CONNECTED) {

        HTTPClient http;
        http.begin("http://10.52.32.25:5000/telemetry");
        http.addHeader("Content-Type", "application/json");

        StaticJsonDocument<256> doc;

        doc["Vr"] = Voltage;
        doc["Wr"] = Speed;
        doc["time"] = timer;

        String body;
        serializeJson(doc, body);

        Serial.print("Sending: ");
        Serial.println(body);

        int response = http.POST(body);

        Serial.print("HTTP Response: ");
        Serial.println(response);

        if (response > 0) {
            Serial.println(http.getString());
        }

        http.end();
        return response;
    }

    Serial.println("WiFi disconnected");
    return -1;
}
