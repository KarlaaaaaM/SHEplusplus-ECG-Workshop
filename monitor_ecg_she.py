''' Adquisición y visualización de ECG en tiempo real --> Taller SHE++ — Adquisición de señal biomédica

Requisitos:
Instalar las siguientes librerías antes de ejecutar:
    pip install pyserial
    pip install PyQt6
    pip install pyqtgraph
    pip install numpy

Las siguientes librerías ya vienen incluidas con Python:
    sys
    collections (deque)

pip install numpy pyserial pyqtgraph PyQt6

'''

import sys
from collections import deque

import numpy as np
import pyqtgraph as pg
import serial
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QProgressBar
from PyQt6.QtGui import QPixmap




#CONFIGURACIÓN INCIAL
PUERTO_SERIAL = "COM5"      # cámbialo a tu puerto (Administrador de dispositivos)
BAUD_RATE = 115200          # debe coincidir EXACTO con el Serial.begin() de tu Arduino (115200)


#PARÁMETROS DE PROCESAMIENTO 
FS = 250                    # Hz, frecuencia de muestreo
VENTANA_SEGUNDOS = 5        # segundos de señal visibles en la gráfica
REFRACTARIO_MS = 300        # periodo refractario fisiológico
REFRACTARIO_MUESTRAS = int(REFRACTARIO_MS / 1000 * FS)
N_MUESTRAS_BUFFER = VENTANA_SEGUNDOS * FS
N_PICOS_PARA_BPM = 6        # promedio móvil de los últimos N intervalos RR

#Umbral ADAPTATIVO 
VENTANA_UMBRAL_SEGUNDOS = 2         # cuántos segundos recientes se usan para estimar el umbral
N_MUESTRAS_VENTANA_UMBRAL = VENTANA_UMBRAL_SEGUNDOS * FS
FRACCION_UMBRAL = 0.55              # umbral = min_ventana + FRACCION_UMBRAL * (max_ventana - min_ventana)
UMBRAL_INICIAL = 450                # se usa solo mientras la ventana de calibración no está llena

#Umbrales clínicos para clasificación por color
BPM_BRADICARDIA = 60        # < 60 -> amarillo
BPM_TAQUICARDIA = 100       # > 100 -> rojo
                            # entre ambos -> verde (normal)

#Niveles de esfuerzo físico según %FCmáx (FCmáx = 220 - edad)
#Orden: (nombre, porcentaje_min, porcentaje_max, color)
NIVELES_ESFUERZO = [
    ("Máximo",    90, 999, "#e53935"),   # 999 cubre cualquier % por encima de 90, sin límite superior real
    ("Intenso",   80, 90,  "#fb8c00"),
    ("Moderado",  70, 80,  "#2e7d32"),
    ("Suave",     60, 70,  "#1565c0"),
    ("Muy suave", 50, 60,  "#1a237e"),
]
EDAD_DEFAULT = 22


class HiloSerial(QThread):
    #Lee el puerto serial en un hilo separado para no congelar la UI.
    nueva_muestra = pyqtSignal(int)
    error_conexion = pyqtSignal(str)

    def __init__(self, puerto, baud):
        super().__init__()
        self.puerto = puerto
        self.baud = baud
        self._corriendo = True

    def run(self):
        try:
            arduino = serial.Serial(self.puerto, self.baud, timeout=1)
        except serial.SerialException as e:
            self.error_conexion.emit(str(e))
            return

        while self._corriendo:
            try:
                linea = arduino.readline().decode("utf-8", errors="ignore").strip()
                if linea:
                    valor = int(linea)
                    self.nueva_muestra.emit(valor)
            except (ValueError, UnicodeDecodeError):
                continue
            except serial.SerialException as e:
                self.error_conexion.emit(str(e))
                break

        arduino.close()

    def detener(self):
        self._corriendo = False
        self.wait()


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor ECG — SHE++")
        self.resize(950, 600)

        #Buffers 
        self.buffer_y = deque([0] * N_MUESTRAS_BUFFER, maxlen=N_MUESTRAS_BUFFER)
        self.buffer_x = deque(
            [i / FS for i in range(-N_MUESTRAS_BUFFER, 0)], maxlen=N_MUESTRAS_BUFFER
        )
        self.contador_muestras = 0

        #Detección de picos 
        self.muestras_desde_ultimo_pico = REFRACTARIO_MUESTRAS
        self.intervalos_rr = deque(maxlen=N_PICOS_PARA_BPM)
        self.total_picos = 0

        #Umbral adaptativo
        self.ventana_umbral = deque(maxlen=N_MUESTRAS_VENTANA_UMBRAL)
        self.umbral_actual = UMBRAL_INICIAL
        self.hay_pico_previo = False  # el primer pico detectado no tiene un intervalo RR válido aún

        self._armar_ui()

        self.hilo = HiloSerial(PUERTO_SERIAL, BAUD_RATE)
        self.hilo.nueva_muestra.connect(self.procesar_muestra)
        self.hilo.error_conexion.connect(self.mostrar_error_serial)
        self.hilo.start()

    def _armar_ui(self):
        widget_central = QWidget()
        widget_central.setStyleSheet("background-color: #D98CF4;")
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setSpacing(12)
        layout_principal.setContentsMargins(20, 15, 20, 15)

        # Fila superior: logo + título
        layout_titulo = QHBoxLayout()

        self.label_logo = QLabel()
        pixmap = QPixmap("LOGOSHE++.png")
        if pixmap.isNull():
            print("ADVERTENCIA: no se encontró 'LOGOSHE++.png' en la carpeta de trabajo")
        else:
            pixmap = pixmap.scaledToHeight(60)
            self.label_logo.setPixmap(pixmap)

        titulo = QLabel("💓 Monitor de ECG")
        titulo.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")

        label_edad = QLabel("Edad:")
        label_edad.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        self.spin_edad = QSpinBox()
        self.spin_edad.setRange(10, 90)
        self.spin_edad.setValue(EDAD_DEFAULT)
        self.spin_edad.setFixedWidth(60)
        self.spin_edad.valueChanged.connect(self._actualizar_texto_zonas)

        layout_titulo.addWidget(self.label_logo)
        layout_titulo.addWidget(titulo)
        layout_titulo.addStretch()
        layout_titulo.addWidget(label_edad)
        layout_titulo.addWidget(self.spin_edad)

        layout_principal.addLayout(layout_titulo)

        subtitulo = QLabel("Adquisición de señal biomédica — AD8232")
        subtitulo.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout_principal.addWidget(subtitulo)


        #Gráfica
        pg.setConfigOption("background", "#FEF8F0")
        pg.setConfigOption("foreground", "black")
        self.grafica = pg.PlotWidget()
        self.grafica.setLabel("left", "Amplitud (ADC counts)")
        self.grafica.setLabel("bottom", "Tiempo (s)")
        self.grafica.showGrid(x=True, y=True, alpha=0.3)
        self.curva = self.grafica.plot(pen=pg.mkPen(color="#8CA7F4", width=2))
        layout_principal.addWidget(self.grafica)

        # Panel inferior: corazón, BPM, contador, estado
        panel_info = QHBoxLayout()

        self.label_corazon = QLabel("❤")
        self.label_corazon.setStyleSheet("color: #ff4d6d; font-size: 50px;")
        self.label_corazon.setFixedSize(90, 90)
        self.label_corazon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_bpm = QLabel("BPM: --")
        self.label_bpm.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")

        self.label_picos = QLabel("Picos detectados: 0")
        self.label_picos.setStyleSheet("color: #aaaaaa; font-size: 13px;")

        self.label_estado = QLabel("● Conectando...")
        self.label_estado.setStyleSheet("color: #DBF48C; font-size: 13px; font-weight: bold;")

        panel_info.addWidget(self.label_corazon)
        panel_info.addWidget(self.label_bpm)
        panel_info.addStretch()
        panel_info.addWidget(self.label_picos)
        panel_info.addStretch()
        panel_info.addWidget(self.label_estado)

        layout_principal.addLayout(panel_info)

        # Panel de nivel de esfuerzo físico (%FCmáx) — barra + etiqueta
        self.label_esfuerzo = QLabel("Nivel de esfuerzo: --")
        self.label_esfuerzo.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        layout_principal.addWidget(self.label_esfuerzo)

        self.barra_esfuerzo = QProgressBar()
        self.barra_esfuerzo.setRange(0, 100)  # 0-100% de FCmáx
        self.barra_esfuerzo.setValue(0)
        self.barra_esfuerzo.setTextVisible(False)
        self.barra_esfuerzo.setFixedHeight(28)
        self.barra_esfuerzo.setStyleSheet("""
            QProgressBar {
                border: 2px solid white;
                border-radius: 8px;
                background-color: #3a3a3a;
            }
            QProgressBar::chunk {
                background-color: #555555;
                border-radius: 6px;
            }
        """)
        layout_principal.addWidget(self.barra_esfuerzo)

        self.setCentralWidget(widget_central)

    def procesar_muestra(self, valor):
        self.label_estado.setText("● Adquiriendo señal")
        self.label_estado.setStyleSheet("color: #DBF48C; font-size: 13px; font-weight: bold;")

        # Buffers 
        self.buffer_y.append(valor)
        self.contador_muestras += 1
        self.buffer_x.append(self.contador_muestras / FS)

        # Umbral adaptativo: se recalcula con cada muestra sobre la ventana reciente 
        self.ventana_umbral.append(valor)
        if len(self.ventana_umbral) == N_MUESTRAS_VENTANA_UMBRAL:
            minimo = min(self.ventana_umbral)
            maximo = max(self.ventana_umbral)
            self.umbral_actual = minimo + FRACCION_UMBRAL * (maximo - minimo)
        # mientras la ventana no esté llena (primeros ~2s), se usa UMBRAL_INICIAL como respaldo

        # Detección de pico R
        self.muestras_desde_ultimo_pico += 1
        if valor > self.umbral_actual and self.muestras_desde_ultimo_pico >= REFRACTARIO_MUESTRAS:
            if self.hay_pico_previo:
                # Solo es un intervalo RR válido si ya hubo un pico anterior real
                intervalo_s = self.muestras_desde_ultimo_pico / FS
                self.intervalos_rr.append(intervalo_s)
                self._actualizar_bpm()
                self._animar_latido()
            else:
                self.hay_pico_previo = True  # este fue el primer pico, aún no hay intervalo que medir

            self.muestras_desde_ultimo_pico = 0
            self.total_picos += 1
            self.label_picos.setText(f"Picos detectados: {self.total_picos}")

        #Redibujar
        self.curva.setData(list(self.buffer_x), list(self.buffer_y))

    def _actualizar_bpm(self):
        if len(self.intervalos_rr) == 0:
            return
        promedio_rr = np.mean(self.intervalos_rr)
        bpm = 60.0 / promedio_rr
        self.label_bpm.setText(f"BPM: {bpm:.0f}")

        # --- Color según rango (clasificación simplificada, NO diagnóstica) ---
        if bpm < BPM_BRADICARDIA:
            color = "#ffca28"   # amarillo — bradicardia
        elif bpm > BPM_TAQUICARDIA:
            color = "#ff5252"   # rojo — taquicardia
        else:
            color = "#DBF48C"   # verde — rango normal
        self.label_bpm.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold;")

        self._clasificar_esfuerzo(bpm)

    def _clasificar_esfuerzo(self, bpm):
        """Calcula %FCmáx = BPM / (220 - edad) y clasifica en la zona correspondiente."""
        edad = self.spin_edad.value()
        fc_max = 220 - edad
        porcentaje = (bpm / fc_max) * 100
        valor_barra = min(max(int(porcentaje), 0), 100)  # la barra visual no pasa de 100

        for nombre, pct_min, pct_max, color in NIVELES_ESFUERZO:
            if porcentaje >= pct_min:
                bpm_min = round(pct_min / 100 * fc_max)
                if nombre == "Máximo":
                    texto_rango = f"≥ {bpm_min} BPM"
                else:
                    bpm_max = round(pct_max / 100 * fc_max)
                    texto_rango = f"{bpm_min}-{bpm_max} BPM"
                self.label_esfuerzo.setText(
                    f"Nivel de esfuerzo: {nombre}  ({texto_rango})  —  {porcentaje:.0f}% FCmáx"
                )
                self._pintar_barra(valor_barra, color)
                return

        # Por debajo del 50% de FCmáx: fuera de las 5 zonas (caso normal en reposo)
        bpm_techo_reposo = round(0.5 * fc_max)
        self.label_esfuerzo.setText(
            f"En reposo — fuera de zona de entrenamiento (< {bpm_techo_reposo} BPM)  —  {porcentaje:.0f}% FCmáx"
        )
        self._pintar_barra(valor_barra, "#555555")

    def _pintar_barra(self, valor, color):
        self.barra_esfuerzo.setValue(valor)
        self.barra_esfuerzo.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid white;
                border-radius: 8px;
                background-color: #3a3a3a;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

    def _actualizar_texto_zonas(self):
        """Se llama cuando cambia la edad en el spinbox: recalcula con el último BPM mostrado."""
        texto_bpm = self.label_bpm.text().replace("BPM:", "").strip()
        if texto_bpm.isdigit():
            self._clasificar_esfuerzo(int(texto_bpm))

    def _animar_latido(self):
        #Agranda el corazón al detectar un pico real y lo regresa a tamaño normal poco después.
        self.label_corazon.setStyleSheet("color: red; font-size: 70px;")
        QTimer.singleShot(150, lambda: self.label_corazon.setStyleSheet(
            "color: red; font-size: 50px;"
        ))

    def mostrar_error_serial(self, mensaje):
        self.label_estado.setText(f"● Error: {mensaje}")
        self.label_estado.setStyleSheet("color: #DBF48C; font-size: 13px; font-weight: bold;")

    def closeEvent(self, event):
        self.hilo.detener()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())