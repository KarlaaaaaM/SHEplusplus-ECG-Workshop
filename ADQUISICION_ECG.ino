const int ECG_PIN = A1; // Pin analógico donde está conectado el AD8232

const unsigned long Ts = 4000; // Periodo de muestreo en microsegundos (250 Hz)
unsigned long t0 = 0;  // Guarda el instante de la última muestra

void setup() {
  Serial.begin(115200);// Inicia la comunicación serial a 115200 baudios
}

void loop() {
  if (micros() - t0 >= Ts) {
    t0 += Ts; //0, 4000, 8000, 12000 ... //Si el tiempo micros() es mayor o igual a 4000 (0.004 seg) se lee el sensor
    int ecg = analogRead(ECG_PIN); //El ADC convierte el voltaje del AD8232 en un valor digital (0-1023)
    Serial.println(ecg); // Envía los datos 
  }
}
