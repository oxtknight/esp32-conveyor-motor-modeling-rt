#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#define WIFI_NETWORK ""
#define WIFI_PASSWORD ""
#define WIFI_TIMEOUT_MS 100000
#define slots 20
int count = 0;
float Real_Speed = 0;
unsigned long passing_time = 0;
unsigned long measurement_time =0;

void setup() {
Serial.begin(9600);
connectToWifi();
pinMode(25,INPUT);
}

void loop() {
int httpResponseCode = http.POST(body);
if (httpResponseCode > 0) {
Serial.println(httpResponseCode);
Serial.println(http.getString());
unsigned long timing = millis();
float Real_Voltage = analogRead(A0);
float Real_Current = analogRead(A2);
bool Encoder = digitalRead(25);
if(timing - passing_time <= 100)
{
bool previous_Encoder = LOW;
if(Encoder == HIGH && previous_Encoder == LOW)
{
count++;
}
previous_Encoder=Encoder;
}
else
{
Real_Speed = 60*count/(20*0.1);
passing_time = timing;
measurement_time+=100;
count = 0;
}
sendMeasurement(Real_Voltage,Real_Current,Real_Speed,measurement_time);
} 
else 
{
Serial.print("Error sending POST: ");
Serial.println(httpResponseCode);
}
}
// the wifi connection function
void connectToWifi() {
Serial.print("Connecting to Wifi");
WiFi.mode(WIFI_STA);
WiFi.begin(WIFI_NETWORK, WIFI_PASSWORD);
unsigned long start = millis();
while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
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

void sendMeasurement(float Voltage, float Current, float Speed, unsigned int timer)
{
if (WiFi.status() == WL_CONNECTED) {
HTTPClient http;
http.begin("http://192.168.112.21:5000/gps");
http.addHeader("Content-Type", "application/json");

StaticJsonDocument<5000> doc;
doc["Voltage"] = Voltage;
doc["Current"] = Current;
doc["Speed"] = Speed;
doc["timer"] = timer;
String body;
serializeJson(doc, body);
int httpResponseCode = http.POST(body);
http.end();
} else {
Serial.println("WiFi disconnected");
}
}
