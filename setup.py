#!/usr/bin/env python3
"""
Script de Configuración de Ute2MQTT.

Configuración interactiva para validar credenciales y descubrir información de la cuenta.
"""

import sys
import getpass
import secrets
import os
from pathlib import Path

# Agregar directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from ute.auth import UTEAuthenticator
from ute.client import UTEClient
from ute.credentials import CredentialsManager
from ute.session import UTESession


def print_header():
    """Imprime el encabezado de configuración."""
    print()
    print("=" * 60)
    print("   Ute2MQTT - Setup")
    print("=" * 60)
    print()


def get_credentials():
    """Obtiene las credenciales del usuario de forma interactiva."""
    print("📝 Ingresa tus credenciales")
    print("   (Las mismas que usas en la app móvil)")
    print()
    
    username = input("   Cédula de identidad: ").strip()
    password = getpass.getpass("   Contraseña: ")
    
    return username, password


def get_oauth_config(creds_manager: CredentialsManager) -> dict:
    """Obtiene la configuración OAuth desde el servidor o la caché."""
    print("🔄 Obteniendo configuración OAuth del servidor...")
    config = UTEAuthenticator.fetch_setup_config()
    
    if not config:
        print("❌ No se pudo obtener la configuración OAuth")
        sys.exit(1)
    
    # Guardar config
    creds_manager.set_oauth_config(
        unique_id=config["unique_id"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scope=config["scope"]
    )
    
    print("✅ Configuración OAuth obtenida y guardada")
    print(f"   Unique ID: {config['unique_id'][:8]}...")
    
    return config


def test_login(username: str, password: str, oauth_config: dict) -> UTEAuthenticator:
    """Prueba el inicio de sesión con las credenciales proporcionadas."""
    print()
    print("🔐 Verificando credenciales...")
    
    auth = UTEAuthenticator(username, password, oauth_config=oauth_config)
    
    if not auth.authenticate():
        print("❌ Login falló. Verificar credenciales.")
        sys.exit(1)
    
    print("✅ Login exitoso!")
    return auth


def list_accounts(auth: UTEAuthenticator, creds_manager: CredentialsManager) -> list:
    """Lista las cuentas disponibles."""
    print()
    print("📋 Obteniendo cuentas...")
    
    session = UTESession(creds_manager)
    session.auth = auth
    client = UTEClient(session)
    accounts = client.get_accounts()
    
    if not accounts:
        print("❌ No se encontraron cuentas.")
        sys.exit(1)
    
    print()
    print("📍 Cuentas disponibles:")
    print("-" * 60)
    
    for i, account in enumerate(accounts, 1):
        account_id = account.get("accountId", "N/A")
        address = account.get("address", "N/A")
        alias = account.get("alias", "")
        
        print(f"   [{i}] Account ID: {account_id}")
        print(f"       Dirección: {address}")
        if alias and alias != "Configure el nombre":
            print(f"       Alias: {alias}")
        print()
    
    print("-" * 60)

    # Obtener servicios para cada cuenta
    for account in accounts:
        account_id = account.get("accountId")
        if account_id:
            try:
                services = client.get_services(account_id)
                if services:
                    account["services"] = services
            except Exception as e:
                print(f"⚠️ Error al obtener servicios para cuenta {account_id}: {e}")
    
    return accounts


def save_tokens(auth: UTEAuthenticator, creds_manager: CredentialsManager):
    """Guarda los tokens en disco."""
    print()
    print("🔐 Guardando tokens...")
    
    creds_manager.set_tokens(
        auth.access_token,
        auth.refresh_token,
        auth.expires_in
    )
    
    print("✅ Tokens guardados (cifrados)")


def print_instructions(accounts: list, encryption_key: str):
    """
    Imprime las instrucciones de configuración para el archivo .env.
    
    Args:
        accounts: Lista de cuentas encontradas
        encryption_key: Clave de cifrado utilizada/generada
    """
    print()
    print("=" * 60)
    print("   Configuración del .env")
    print("=" * 60)
    print()
    print("Agrega las siguientes variables a tu archivo .env:")
    print()
    print("-" * 60)
    
    # Imprimir la clave de cifrado
    print(f"ENCRYPTION_KEY={encryption_key}")
    print()
    
    if len(accounts) == 1:
        account = accounts[0]
        account_id = account.get("accountId", "")
        print(f"UTE_ACCOUNT_ID={account_id}")
        
        services = account.get("services", [])
        if services:
            service = services[0]
            print(f"UTE_SERVICE_ID={service.get('serviceAgreementId', '')}")
            print(f"UTE_SERVICE_POINT_ID={service.get('servicePointId', '')}")
            print(f"UTE_TARIFF={service.get('tariff', '').upper()}")
            
    else:
        print("# Elige UNA de las siguientes cuentas:")
        for account in accounts:
            account_id = account.get("accountId", "")
            address = account.get("address", "")
            print(f"# {address}")
            print(f"UTE_ACCOUNT_ID={account_id}")
            
            services = account.get("services", [])
            if services:
                service = services[0]
                print(f"UTE_SERVICE_ID={service.get('serviceAgreementId', '')}")
                print(f"UTE_SERVICE_POINT_ID={service.get('servicePointId', '')}")
                print(f"UTE_TARIFF={service.get('tariff', '').upper()}")
            print()
    
    print("-" * 60)
    print()
    print("📝 Configura también MQTT_BROKER, MQTT_PORT, etc. en el .env")
    print()


def main():
    """Flujo principal de configuración."""
    print_header()
    
    # Inicializar credentials manager
    creds_path = Path(__file__).parent / "ute/credentials" 
    # NOTA: Antes estaba en credentials/, ahora movimos credentials.py a ute/credentials.py
    # pero la ruta de almacenamiento por defecto en credentials.py es "./credentials".
    # Debemos mantener la ubicación de datos consistente o explícita.
    # El script de configuración solía inicializar CredsManager con:
    # creds_path = Path(__file__).parent / "credentials"
    # El valor por defecto en CredsManager es "./credentials".
    # Mantendré el directorio de DATOS como está ("credentials" en la raíz).
    
    data_path = Path(__file__).parent / "credentials"
    
    # Obtener o generar clave de cifrado para el setup
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        print("🔑 Generando nueva clave de cifrado...")
        encryption_key = secrets.token_hex(32)
        print(f"   Clave generada: {encryption_key}")
    else:
        print("🔑 Usando clave de cifrado existente del entorno")

    creds_manager = CredentialsManager(str(data_path), encryption_key=encryption_key)
    
    # Limpiar configuración anterior para iniciar de cero
    print("🧹 Limpiando configuración anterior...")
    creds_manager.clear_all()
    
    # Obtener OAuth config (del servidor, siempre fresca)
    oauth_config = get_oauth_config(creds_manager)
    
    # Get user credentials
    username, password = get_credentials()
    
    # Test login
    auth = test_login(username, password, oauth_config)
    
    # Save user credentials
    print()
    print("🔐 Guardando credenciales...")
    creds_manager.set_user_credentials(username, password)
    print("✅ Credenciales guardadas (cifradas)")
    
    # List accounts
    accounts = list_accounts(auth, creds_manager)
    
    # Guardar tokens
    save_tokens(auth, creds_manager)
    
    # Imprimir instrucciones
    print_instructions(accounts, encryption_key)
    
    print("✅ Setup completado!")
    print()


if __name__ == "__main__":
    main()
