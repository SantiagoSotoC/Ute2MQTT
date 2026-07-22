# Home Assistant Add-on: Ute2MQTT

Obtiene datos de consumo eléctrico desde la API de UTE (Uruguay) y los publica a Home Assistant via MQTT con auto-descubrimiento.

## Instalación

1. Asegurate de tener MQTT configurado en Home Assistant (addon Mosquitto o integración core MQTT).
2. Ve a **Settings** > **Add-ons** > **Add-on Store**.
3. Agregá este repositorio o copiá los archivos del addon.
4. Buscá "Ute2MQTT" y hacé clic en **Install**.
5. Iniciá el addon.

## Configuración

### Paso 1: Configurar MQTT

El addon detecta automáticamente la configuración MQTT de Home Assistant. Solo necesitás tener MQTT funcionando (Mosquitto addon o integración core MQTT).

### Paso 2: Configurar credenciales UTE

1. Abrí la **Web UI** del addon (botón "Open Web UI").
2. Ingresá tu cédula de identidad y contraseña de UTE.
3. Seleccioná la cuenta y servicio que querés monitorear.
4. Guardá la configuración.

### Paso 3: Ajustar horario (opcional)

En la configuración del addon podés cambiar:

| Opción | Descripción | Default |
|--------|-------------|---------|
| `cron_schedule` | Expresión cron para ejecución | `0 8 * * *` (8:00 AM todos los días) |
| `mqtt_topic_prefix` | Prefijo para topics MQTT | `UTE` |
| `log_level` | Nivel de log | `info` |

Ejemplos de cron:
- `0 8 * * *` - Todos los días a las 8:00
- `0 */6 * * *` - Cada 6 horas
- `0 9 * * 1-5` - Días laborales a las 9:00
- `30 7 * * *` - Todos los días a las 7:30

## Sensores

Los siguientes sensores se crean automáticamente via MQTT Discovery:

| Sensor | Descripción | Tarifas |
|--------|-------------|---------|
| `sensor.ute_{id}_consumo_actual` | Consumo total (kWh) | Todas |
| `sensor.ute_{id}_gasto_actual` | Gasto estimado ($) | Todas |
| `sensor.ute_{id}_deuda_total` | Deuda pendiente ($) | Todas |
| `sensor.ute_{id}_consumo_punta` | Consumo punta (kWh) | TRT, TRD |
| `sensor.ute_{id}_consumo_llano` | Consumo llano (kWh) | TRT |
| `sensor.ute_{id}_consumo_valle` | Consumo valle (kWh) | TRT |
| `sensor.ute_{id}_ultima_actualizacion` | Timestamp | Todas |

## Tarifas soportadas

- **TRT** (Triple): Punta, Llano, Valle
- **TRD** (Doble): Punta, Fuera de Punta
- **TRS/TGS** (Simple): Solo consumo total

## Solución de problemas

### El addon no inicia

1. Verificá que MQTT esté funcionando en HA.
2. Revisá los logs del addon en **Settings** > **Add-ons** > **Ute2MQTT** > **Logs**.

### No se conecta a UTE

1. Abrí la Web UI y re-configurá las credenciales.
2. Verificá que la contraseña no haya cambiado.

### No aparecen sensores

1. Verificá que MQTT Discovery esté habilitado en HA.
2. Revisá los logs para errores de conexión MQTT.

## Ejemplo de dashboard

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-entity-card
    entity: sensor.ute_SERVICIO_consumo_actual
    name: Consumo actual
    icon: mdi:lightning-bolt
    icon_color: blue
  - type: custom:mushroom-entity-card
    entity: sensor.ute_SERVICIO_gasto_actual
    name: Gasto actual
    icon: mdi:currency-usd
    icon_color: green
  - type: custom:mushroom-entity-card
    entity: sensor.ute_SERVICIO_deuda_total
    name: Deuda
    icon: mdi:cash-clock
    icon_color: red
```

Reemplazá `SERVICIO` con tu ID de servicio.
