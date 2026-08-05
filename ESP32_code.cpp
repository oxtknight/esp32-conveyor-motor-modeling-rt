#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define WIFI_NETWORK "inelecer"
#define WIFI_PASSWORD "20301782"
#define WIFI_TIMEOUT_MS 100000

#define PIN_VOLTAGE 4
#define PIN_ENCODER 25


volatile uint32_t count = 0;
float Real_Speed = 0;
unsigned long passing_time = 0;
unsigned long measurement_time = 0;
unsigned long timing = 0;
float Real_Voltage = 0;
float Real_Current = 0;
int httpResponseCode = 0;

// Encoder pulses per revolution
#define PPR 20

void IRAM_ATTR encoderISR()
{
    count++;
}


void setup()
{
    Serial.begin(9600);
    pinMode(PIN_VOLTAGE, INPUT);
    pinMode(PIN_ENCODER, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER),encoderISR, RISING);
    connectToWifi();
    Serial.println("System Started");
}

void loop()
{
    timing = millis();
    if(timing - passing_time >= 100)
    {
        Real_Voltage =analogRead(PIN_VOLTAGE)* (3.3 / 4095.0);
        noInterrupts();
        uint32_t pulses = count;
        count = 0;
        interrupts();
        Real_Speed = pulses * 60.0 /(PPR * 0.1);    
        passing_time = timing;
        measurement_time += 100;
        httpResponseCode =
        sendMeasurement(Real_Voltage, Real_Speed, measurement_time);
        Serial.print("Voltage: ");
        Serial.print(Real_Voltage);
        Serial.print(" RPM: ");
        Serial.print(Real_Speed);
        Serial.print(" HTTP: ");
        Serial.println(httpResponseCode);
}
delay(1);
}


void connectToWifi()
{
Serial.print("Connecting to Wifi");
WiFi.mode(WIFI_STA);
WiFi.begin(WIFI_NETWORK,WIFI_PASSWORD);

unsigned long start = millis();

while( WiFi.status()!=WL_CONNECTED && millis()-start<WIFI_TIMEOUT_MS)
{
Serial.print(".");
delay(100);
}

if(WiFi.status()!=WL_CONNECTED)
{
Serial.println(" Failed!");
}
else
{
Serial.print("Connected! ");
Serial.println(WiFi.localIP());
}
}


int sendMeasurement(float Voltage, float Speed, unsigned int timer)
{
if(WiFi.status()==WL_CONNECTED)
{
HTTPClient http;
http.begin("http://10.52.32.25:5000/telemetry");
http.addHeader("Content-Type","application/json");

StaticJsonDocument<256> doc;
doc["Vr"] = Voltage;
doc["Wr"] = Speed;
doc["time"] = timer;
String body;
serializeJson(doc,body);

Serial.print("Sending: ");
Serial.println(body);

int response =http.POST(body);
if(response > 0)
{
Serial.println(http.getString());
}
http.end();
return response;
}
return -1;
}
