"""
Ute2MQTT - Web UI para configuración del addon.

Proporciona una interfaz web para configurar credenciales de UTE
y seleccionar cuenta/tarifa. Soporta Ingress de Home Assistant.
"""

import json
import logging
import os
import sys
import secrets
import hashlib
import hmac

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort

sys.path.insert(0, "/app")

from ute.auth import UTEAuthenticator
from ute.credentials import CredentialsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ute2mqtt.webui")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

CREDENTIALS_PATH = os.environ.get("CREDENTIALS_PATH", "/data/ute2mqtt")
creds_manager = CredentialsManager(storage_path=CREDENTIALS_PATH)

# Ingress token from HA
INGRESS_TOKEN = os.environ.get("INGRESS_TOKEN", None)


def check_ingress():
    """Verifica token de ingress si está configurado."""
    if not INGRESS_TOKEN:
        return True  # No auth required (direct access)
    token = request.headers.get("X-Ingress-Token") or request.args.get("token")
    if not token:
        return False
    return hmac.compare_digest(token, INGRESS_TOKEN)


@app.before_request
def before_request():
    """Middleware para verificar autenticación."""
    # Si hay INGRESS_TOKEN configurado, verificar en cada request
    if INGRESS_TOKEN and request.path != "/api/health":
        token = request.headers.get("X-Ingress-Token") or request.args.get("token")
        if not token or not hmac.compare_digest(token, INGRESS_TOKEN):
            abort(401)


@app.route("/")
def index():
    """Página principal con formulario de setup."""
    has_config = creds_manager.has_user_credentials()
    config_file = os.path.join(CREDENTIALS_PATH, "ute_config.json")
    config_data = None
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config_data = json.load(f)
        except Exception:
            pass

    return render_template(
        "index.html",
        has_config=has_config,
        config=config_data,
    )


@app.route("/api/health")
def api_health():
    """Endpoint de salud para verificar que el addon funciona."""
    return jsonify({"status": "ok"})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    """
    Paso 1: Autenticar con UTE y obtener cuentas.
    Recibe: username (cédula), password
    Retorna: lista de cuentas disponibles
    """
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Cédula y contraseña son requeridos"}), 400

    try:
        # Obtener config OAuth
        oauth_config = UTEAuthenticator.fetch_setup_config()
        if not oauth_config:
            return jsonify({"error": "No se pudo obtener configuración OAuth de UTE"}), 502

        # Autenticar
        auth = UTEAuthenticator(
            username=username,
            password=password,
            oauth_config=oauth_config,
        )
        if not auth.authenticate():
            return jsonify({"error": "Autenticación fallida. Verificá cédula y contraseña."}), 401

        # Guardar tokens y credenciales
        creds_manager.set_oauth_config(
            unique_id=oauth_config["unique_id"],
            client_id=oauth_config["client_id"],
            client_secret=oauth_config["client_secret"],
            scope=oauth_config.get("scope", ""),
        )
        creds_manager.set_tokens(auth.access_token, auth.refresh_token, auth.expires_in)
        creds_manager.set_user_credentials(username, password)

        # Obtener cuentas
        from ute.session import UTESession
        session = UTESession(creds_manager)
        client = session.get_client()

        if not client:
            return jsonify({"error": "No se pudo crear cliente autenticado"}), 500

        accounts = client.get_accounts()
        if not accounts:
            return jsonify({"error": "No se encontraron cuentas asociadas"}), 404

        # Para cada cuenta, obtener servicios
        result = []
        for account in accounts:
            account_id = account.get("accountId") or account.get("id")
            services = client.get_services(account_id) or []
            for svc in services:
                result.append({
                    "account_id": account_id,
                    "service_id": svc.get("serviceAgreementId") or svc.get("id"),
                    "service_point_id": svc.get("servicePointId") or svc.get("servicePoint", {}).get("id"),
                    "address": svc.get("address", ""),
                    "tariff": svc.get("tariff", ""),
                    "schedule_code": svc.get("scheduleCode", ""),
                })

        return jsonify({"accounts": result})

    except Exception as e:
        logger.exception("Error en setup")
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    """
    Paso 2: Guardar configuración seleccionada.
    Recibe: account_id, service_id, service_point_id, tariff, schedule_code
    """
    data = request.get_json()

    required = ["account_id", "service_id", "service_point_id", "tariff"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    config = {
        "account_id": data["account_id"],
        "service_id": data["service_id"],
        "service_point_id": data["service_point_id"],
        "tariff": data["tariff"].upper(),
        "schedule_code": data.get("schedule_code", ""),
    }

    config_file = os.path.join(CREDENTIALS_PATH, "ute_config.json")
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        logger.info("Configuración UTE guardada")

        # Reiniciar daemon principal para aplicar cambios
        import subprocess
        try:
            # Matar proceso main.py anterior si existe
            subprocess.run(["pkill", "-f", "python3 /app/main.py"], capture_output=True)
            # Iniciar nuevo proceso
            subprocess.Popen(["python3", "/app/main.py"],
                           env={**os.environ, "CREDENTIALS_PATH": CREDENTIALS_PATH})
            logger.info("Daemon principal reiniciado")
        except Exception as e:
            logger.warning(f"No se pudo reiniciar daemon: {e}")

        return jsonify({"ok": True, "message": "Configuración guardada correctamente"})
    except Exception as e:
        logger.error(f"Error al guardar config: {e}")
        return jsonify({"error": f"Error al guardar: {str(e)}"}), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    """Retorna estado actual de la configuración."""
    config_file = os.path.join(CREDENTIALS_PATH, "ute_config.json")
    has_config = os.path.exists(config_file)
    has_tokens = creds_manager.is_token_valid()
    has_creds = creds_manager.has_user_credentials()

    config_data = None
    if has_config:
        try:
            with open(config_file, "r") as f:
                config_data = json.load(f)
        except Exception:
            pass

    return jsonify({
        "has_config": has_config,
        "has_tokens": has_tokens,
        "has_credentials": has_creds,
        "config": config_data,
    })


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Elimina toda la configuración almacenada."""
    try:
        creds_manager.clear_all()
        config_file = os.path.join(CREDENTIALS_PATH, "ute_config.json")
        if os.path.exists(config_file):
            os.remove(config_file)
        return jsonify({"ok": True, "message": "Configuración eliminada"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
