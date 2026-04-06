# MTF EMA Confluencia

Script que consulta en tiempo real la confluencia (cruce) de medias móviles exponenciales (EMA 7 / EMA 20) en múltiples temporalidades para cualquier par de mercado de Binance. Calcula un binario de 5 bits y lo traduce a un porcentaje de operabilidad (Long) mediante una tabla de referencia fija.

---

## Cómo funciona

Para cada temporalidad (5m, 15m, 1H, 4H, 1D) el script:

1. Descarga las últimas velas del par indicado desde Binance.
2. Calcula EMA 7 y EMA 20 sobre los cierres.
3. Evalúa sobre la **última vela cerrada** (no la vela en formación):
   - **Sesgo**: `ALCISTA` si EMA7 > EMA20, `BAJISTA` en caso contrario.
   - **Cruce reciente**: busca cruce EMA7/EMA20 en las últimas N velas cerradas:
     - 5m y 15m → ventana de **3 velas**
     - 1H, 4H y 1D → ventana de **2 velas**
4. Asigna el bit `1` (alcista) o `0` (bajista) para esa temporalidad.

Con los 5 bits ordenados como `5m · 15m · 1H · 4H · 1D` forma el binario (p.ej. `11100`), lo convierte a decimal (28) y obtiene el porcentaje de operabilidad Long de la tabla de referencia.

---

## Requisitos

- Python 3.10 o superior
- Dependencias:

```
ccxt>=4.4.0
pandas>=2.0.0
```

Instalación:

```powershell
pip install -r requirements.txt
```

---

## Uso

### Consulta única

```powershell
python .\mtf_ema_confluencia.py --once
```

```powershell
python .\mtf_ema_confluencia.py --once --symbol ETH/USDT
```

### Modo continuo (cada N minutos)

```powershell
python .\mtf_ema_confluencia.py --symbol BTC/USDT --interval 5
```

### Ver tabla de combinaciones binarias

Imprime las 32 combinaciones posibles con su decimal y porcentaje de operabilidad Long. No requiere conexión al exchange.

```powershell
python .\mtf_ema_confluencia.py --tabla
```

---

## Parámetros

| Parámetro    | Tipo    | Por defecto | Descripción                                                   |
|--------------|---------|-------------|---------------------------------------------------------------|
| `--symbol`   | string  | `DOGE/USDT` | Par de mercado en formato Binance (p.ej. `ETH/USDT`).         |
| `--interval` | entero  | `5`         | Minutos entre consultas en modo continuo.                     |
| `--once`     | flag    | —           | Ejecuta una sola consulta y termina.                          |
| `--tabla`    | flag    | —           | Muestra la tabla de referencia binario→operabilidad y termina.|

---

## Ejemplo de salida

```
+=================================================================================================+
| HORA    : 2026-04-05 23:01:04 UTC                                                               |
| SYMBOL  : BTC/USDT      EXCHANGE: BINANCE                                                       |
+=====+===============+==========================+==============+==============+==================+
| TF  | SESGO         | CRUCE                    | EMA7         | EMA20        | VELA             |
+=====+===============+==========================+==============+==============+==================+
| 5m  | SESGO ALCISTA | SIN CRUCE (ult 3v)       | 67972.5838   | 67739.0196   | 2026-04-05 22:55 |
+-----+---------------+--------------------------+--------------+--------------+------------------+
| 15m | SESGO ALCISTA | SIN CRUCE (ult 3v)       | 67794.1721   | 67562.3144   | 2026-04-05 22:45 |
+-----+---------------+--------------------------+--------------+--------------+------------------+
| 1H  | SESGO ALCISTA | SIN CRUCE (ult 2v)       | 67636.5183   | 67331.4074   | 2026-04-05 22:00 |
+-----+---------------+--------------------------+--------------+--------------+------------------+
| 4H  | SESGO ALCISTA | CRUCE AL ALZA (ult 2v)   | 67182.8337   | 67156.7247   | 2026-04-05 16:00 |
+-----+---------------+--------------------------+--------------+--------------+------------------+
| 1D  | SESGO BAJISTA | SIN CRUCE (ult 2v)       | 67416.5345   | 68361.6893   | 2026-04-04 00:00 |
+-----+---------------+--------------------------+--------------+--------------+------------------+
| BINARIO [1 1 1 1 0]  COMBO 30  OPERABILIDAD LONG: 70%                                          |
+=================================================================================================+
```

### Lectura del reporte

- **SESGO**: estado actual de la EMA en esa temporalidad. Puede ser alcista sin que haya habido un cruce reciente (el cruce ocurrió antes de la ventana de revisión).
- **CRUCE**: indica si hubo cruce al alza o a la baja dentro de la ventana de velas revisada.
- **BINARIO**: `1` por cada temporalidad alcista, `0` por bajista, en orden 5m→1D.
- **COMBO**: valor decimal del binario. Rango 0–31.
- **OPERABILIDAD LONG**: porcentaje de confluencia favorable para posiciones largas según la tabla de referencia. 100% = todas las temporalidades alineadas al alza.

---

## Tabla de referencia rápida

```
+===========================+=========+===================+
| BINARIO (5m 15m 1H 4H 1D) | DECIMAL | OPERABILIDAD LONG |
+===========================+=========+===================+
| 0 0 0 0 0                 | 0       | 0%                |
| 1 1 1 1 1                 | 31      | 100%              |
+---------------------------+---------+-------------------+
```

Consulta la tabla completa con:

```powershell
python .\mtf_ema_confluencia.py --tabla
```

