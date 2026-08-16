# esp32-conveyor-motor-modeling-rt

A digital twin for a **JGB37-520 conveyor motor**, built for a real-time anomaly detection and predictive maintenance pipeline. The system reads live voltage/speed telemetry from an ESP32, computes a model-predicted speed on the server, and flags an anomaly whenever the measured and predicted speeds diverge past a threshold.

A data-driven equation predicts the motor's speed, and this prediction is compared in real time against the real measured speed. When they diverge beyond a threshold, that's flagged as a potential anomaly (friction, load change, developing fault), making it the basis for predictive maintenance. Part of an Industry 4.0 project. Developed during an internship at **CDTA** (Centre de Développement des Technologies Avancées), Division Productique et Robotique (DPR), under the supervision of Mr. Bendjelloule.

## Overview

The project explores two modelling approaches for the same motor:

1. **Physics-based model** (`twin_motor.py`) — a DC motor ODE model (electrical + mechanical equations), integrated with adaptive sub-stepping. Kept as a legacy/reference model.
2. **Data-driven model** (`fitting_parameters.py`) — a normalised algebraic polynomial fitted to logged telemetry using `lmfit` (Levenberg-Marquardt), used in production for the live twin.

The live pipeline runs: **ESP32 → Flask server → MySQL + in-memory buffer → dashboard (Chart.js)**. The Flask server computes the model speed on each incoming reading, persists it, and serves both a live "latest reading" endpoint and a short-term rolling history for the dashboard chart.

> **Note:** All data used for the final fit and validation was collected via a **Wokwi ESP32 simulation**, not the physical motor — the CDTA protoboard runs at 24V while the JGB37-520 requires 12V, which ruled out physical deployment during this internship. See the full report for details and caveats.

## Repository structure

```
.
├── dataset/                  # Logged telemetry used for model fitting
│   ├── final_combined_dataset.csv
│   ├── low_voltage_data.csv
│   └── V_measurements.csv
├── datasheets/                # Manufacturer datasheet for the JGB37-520
│   └── jgb37_520_60rpm_12v_datasheet.jpg
├── ESP32_code.cpp             # ESP32 firmware (acquisition + telemetry POST)
├── labview_files/
│   └── DC_Motor_Model.vi      # LabVIEW reference model
├── model_in_python/
│   ├── dashboard.html         # Live dashboard (Chart.js, served by Flask)
│   ├── feed.py                # Telemetry feeder / test client
│   ├── feed_csv.py            # Replays a CSV dataset as simulated telemetry
│   ├── fitting_parameters.py  # Fits the data-driven polynomial to MotorLogs
│   ├── flask_server_v2.py     # Main server: ingestion, model computation, API
│   ├── model_with_checking.py # SINDy-based equation discovery (exploratory)
│   ├── Model_with_PySindy.py  # SINDy-based equation discovery (exploratory)
│   ├── templates/
│   │   └── dashboard.html
│   ├── twin_motor.py          # Physics-based ODE motor model
│   └── wm_equation_coeffs.json # Latest fitted polynomial coefficients
├── pics/                      # Hardware photos (encoder, driver, motor)
├── results/                   # Result plots (fit vs. data, tracking over time)
├── virtualData.sql            # MySQL schema / seed data
├── LICENSE
└── README.md
```

## Hardware

| Component | Role |
|---|---|
| JGB37-520 DC motor (12V, 168:1 gearbox) | Drives the conveyor belt |
| Rotary encoder (20 PPR) | Speed feedback |
| ACS712 current sensor | Present on hardware, not yet integrated into telemetry |
| BTS7960 motor driver | H-bridge, PWM voltage control |
| ESP32 (WiFi, 12-bit ADC) | Reads sensors, sends telemetry over HTTPS |

## Software pipeline

- **ESP32** samples voltage and encoder pulses every 100ms, computes speed, and POSTs `{Vr, Wr, time}` to the Flask server's `/telemetry` endpoint.
- **Flask server** (`flask_server_v2.py`) computes the model speed `Wm` from the fitted polynomial, inserts each reading into the `MotorLogs` MySQL table, and appends it (with deviation) to an in-memory rolling buffer used for short-term chart backfill.
- **Fitting script** (`fitting_parameters.py`) periodically refits the polynomial against historical `MotorLogs` data and exports coefficients to `wm_equation_coeffs.json`.
- **Dashboard** (`dashboard.html`) polls `/latest` every 500ms and plots real vs. model speed, with a status badge that turns red when deviation exceeds a 5 RPM threshold.

**Known limitation, stated plainly**: this equation uses both `Vr` and `Wr` (the real measured speed) as inputs to compute `Wm`. This means `Wm` is not fully independent of the value it's being compared against — worth treating this as closer to a calibrated smoothing/estimation model than a fully independent virtual twin. See the report's Discussion/Limitations section for the full reasoning.

## Model performance

The data-driven polynomial was fit against MotorLogs telemetry:

| Metric | Value |
|---|---|
| Average twin accuracy | 93.04% |
| Average percentage error | 6.96% |
| RMSE | 1.232 RPM |
| MAE | 0.819 RPM |

**Important caveat:** the polynomial takes the real measured speed (`Wr`) as an input alongside voltage (`Vr`), so this accuracy reflects how closely the fitted curve reproduces `Wr` given both `Vr` and `Wr` — it is a calibration/smoothing curve, not an independent forward predictor. It's still useful for residual-based anomaly detection, since a sudden jump in `|Wr - Wm|` is meaningful regardless. A fully independent model (`Wm = f(Vr, Ir)`, not using `Wr`) is listed as future work.

## Known limitations

- All fitting/validation data comes from the Wokwi simulator, not the physical motor.
- `/history` is served from an in-memory buffer (not MySQL), so it resets on server restart.
- The `MotorLogs.deviation` column is defined but never written by the server; deviation is computed on the fly.
- The anomaly threshold (5 RPM) is hardcoded in the dashboard's JavaScript only, with no server-side source of truth.
- `flask_server_v2.py` runs on Flask's development server and is not production-ready.

See the full internship report for a detailed discussion of limitations and future work.

## Future work
if possible:
- Real hardware validation once a 12V-compatible protoboard is available.
- Persist `/history` to MySQL.
- Incorporate ACS712 current sensing for load-torque estimation.
- Replace the static anomaly threshold with a server-side statistical control chart.
- Independent forward model (`Wm = f(Vr, Ir)`) that doesn't depend on the measured speed.

## Authors

Aicha Badi and Chaima Mokeddem — internship project at CDTA, DPR (July 2026), supervised by Mr. Bendjelloule.

## License

See [LICENSE](./LICENSE).
