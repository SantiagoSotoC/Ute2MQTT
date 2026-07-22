"""
Módulo de Lógica de Tarifas.

Maneja la interpretación y transformación de datos según el tipo de tarifa.
"""

from typing import Dict, Any, List, Optional

class TariffProcessor:
    """Procesa y agrega datos de consumo según la tarifa."""

    @staticmethod
    def process_bands(tariff: str, band_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Procesa la lista de bandas recibida de la API y devuelve un diccionario simplificado.
        
        Args:
            tariff: Código de tarifa (TRT, TRD, etc.)
            band_data: Lista de diccionarios devuelta por get_consumption_by_band
            
        Returns:
            Diccionario con claves como 'consumption_punta', 'consumption_valle', etc.
        """
        raw_bands = {}
        for band in band_data:
            tou = band.get("tou", "").lower()
            raw_bands[f"consumption_{tou}"] = band.get("consumption", 0)
            
        result = {}
        
        if tariff == "TRT":
            # Tarifa Triple: Pasa directo
            result["consumption_punta"] = raw_bands.get("consumption_punta", 0)
            result["consumption_llano"] = raw_bands.get("consumption_llano", 0)
            result["consumption_valle"] = raw_bands.get("consumption_valle", 0)
            
        elif tariff == "TRD":
            # Tarifa Doble: Agrupa Llano+Valle en Fuera de Punta
            punta = raw_bands.get("consumption_punta", 0)
            llano = raw_bands.get("consumption_llano", 0)
            valle = raw_bands.get("consumption_valle", 0)
            
            result["consumption_punta"] = punta
            result["consumption_fuera_punta"] = llano + valle
            
        # Para otras tarifas no hacemos nada especial (o no soportan bandas)
        return result

    @staticmethod
    def get_schedule_code_from_id(peak_start_id: int) -> Optional[str]:
        """Convierte el ID numérico de inicio de horario punta a código de tarifa."""
        # Mapeo de IDs a códigos
        schedule_map = {
            1: "TRIPLERES17", 
            2: "TRIPLERES18", 
            3: "TRIPLERES19"
        }
        return schedule_map.get(peak_start_id)
