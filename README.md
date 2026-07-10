# SHEplusplus-ECG-Workshop
Material de taller desarrollado para SHE++, que incluye código de Arduino y una interfaz en Python para la adquisición de ECG en tiempo real con el sensor AD8232.

# Monitor ECG en Tiempo Real — SHE++

Interfaz en Python para adquisición y visualización de señal ECG en tiempo real, desarrollada como material del taller de adquisición de señales biomédicas de **SHE++**.

Usa un sensor **AD8232** conectado a un **Arduino**, que transmite la señal cruda por puerto serial hacia una interfaz gráfica hecha con **PyQt6**.

## ¿Qué hace?

- Grafica la señal ECG en tiempo real.
- Detecta picos R con umbral adaptativo (se ajusta solo a la señal de cada persona).
- Calcula BPM con promedio móvil de intervalos RR.
- Corazón animado que late en sincronía con cada pico R detectado.
- Indicador de color según rango de BPM (bradicardia / normal / taquicardia) — clasificación simplificada, **no diagnóstica**.
- Barra de nivel de esfuerzo físico según `%FCmáx` (`FCmáx = 220 - edad`), con las 5 zonas clásicas: Muy suave, Suave, Moderado, Intenso, Máximo.

## Hardware necesario

- Sensor AD8232 (ECG)
- Arduino (Uno, Nano, o similar)
- Electrodos desechables de ECG
- Cable USB para conexión serial

## Instalación

Requiere Python 3.10+

```bash
pip install pyserial PyQt6 pyqtgraph numpy
```

## Configuración antes de correr

Abre `monitor_ecg_she.py` y ajusta estas dos líneas según tu setup:

```python
PUERTO_SERIAL = "COM7"   # tu puerto real (revisa en Administrador de dispositivos)
BAUD_RATE = 115200       # debe coincidir con el Serial.begin() de tu sketch de Arduino
```

Sube `ADQUISICION_ECG.ino` a tu Arduino antes de correr la interfaz.

## Uso

```bash
python monitor_ecg_she.py
```

Conecta los electrodos (RA, LA, RL) antes de abrir la interfaz para ver la señal desde el inicio.

## Notas técnicas

- El umbral de detección de picos es adaptativo: se recalcula sobre una ventana móvil de 2 segundos, por lo que se ajusta automáticamente a la impedancia electrodo-piel de cada persona.
- La clasificación de esfuerzo por edad usa la fórmula clásica de Fox (`220-edad`), reconocida ampliamente pero con margen de error poblacional (±10-12 lpm); se usa aquí con fines didácticos, no clínicos.

---

Desarrollado para el taller de SHE++ 💓
