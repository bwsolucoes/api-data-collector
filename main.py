import configparser
import json
import os
import sys
import time

import requests
import xml.etree.ElementTree as ET

# ===================================================================
# FUNÇÕES DE CONFIGURAÇÃO E ENVIO DE LOGS
# ===================================================================

def load_config():
    config = configparser.ConfigParser()
    config_path = '/app/config.ini'
    if not os.path.exists(config_path):
        print(f"ERRO: Arquivo de configuração '{config_path}' não encontrado.", file=sys.stderr)
        sys.exit(1)
    config.read(config_path)
    return config

def send_log_to_datadog(log_payload, config):
    try:
        api_key = config.get('datadog', 'api_key')
        dd_url = config.get('datadog', 'log_url')
        
        headers = {'Content-Type': 'application/json', 'DD-API-KEY': api_key}

        dd_payload = {
            "ddsource": log_payload.get("source_api", "api-collector"),
            "ddtags": f"env:lab,city:{log_payload.get('city', 'n/a')},entity:{log_payload.get('entity', 'n/a')}",
            "hostname": os.getenv("HOSTNAME", "k8s-pod"),
            "service": "api-collector",
            "message": log_payload
        }
        
        response = requests.post(dd_url, headers=headers, json=dd_payload, timeout=10)
        response.raise_for_status()
        print(f"Log enviado com sucesso para o Datadog: source={dd_payload['ddsource']}")
        
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao enviar log para o Datadog: {e}", file=sys.stderr)
    except configparser.NoOptionError as e:
        print(f"ERRO: Chave de configuração faltando para o Datadog: {e}", file=sys.stderr)

# ===================================================================
# MÓDULOS DE COLETA
# ===================================================================

def fetch_weather_data(config):
    try:
        api_key = config.get('openweathermap', 'api_key')
        city = config.get('openweathermap', 'city')
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {'q': city, 'appid': api_key, 'units': 'metric', 'lang': 'pt_br'}
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "source_api": "openweathermap", "city": data.get('name'),
            "temperature_celsius": data['main'].get('temp'),
            "weather_description": data['weather'][0].get('description') if data.get('weather') else None,
            "status": "success"
        }
    except Exception as e:
        print(f"ERRO ao buscar dados do OpenWeatherMap: {e}", file=sys.stderr)
        return {"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), "source_api": "openweathermap", "status": "error", "error_message": str(e)}

def get_sap_token(config):
    token_url = config.get('sap', 'token_url')
    client_id = config.get('sap', 'client_id')
    client_secret = config.get('sap', 'client_secret')
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "client_credentials"}
    response = requests.post(token_url, data=payload, headers=headers, auth=(client_id, client_secret), timeout=15)
    response.raise_for_status()
    return response.json()["access_token"]

def process_sap_data(config):
    # ESTA É A VERSÃO CORRIGIDA DA FUNÇÃO
    try:
        access_token = get_sap_token(config)
        base_url = config.get('sap', 'base_api_url')
        metadata_url = f"{base_url}$metadata"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/xml"}
        response_metadata = requests.get(metadata_url, headers=headers, timeout=15)
        response_metadata.raise_for_status()
        namespaces = {'edm': 'http://docs.oasis-open.org/odata/ns/edm'}
        root = ET.fromstring(response_metadata.content)
        entity_sets = root.findall(".//edm:EntitySet", namespaces)
        entity_names = [e.attrib["Name"] for e in entity_sets]
        all_logs = []
        for entity in entity_names:
            odata_url = f"{base_url}{entity}"
            headers_json = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            response = requests.get(odata_url, headers=headers_json, timeout=15)
            if response.status_code == 200:
                data = response.json().get("value", [])
                for item in data:
                    log_entry = {
                        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        "source_api": "sap_cloud_alm", "entity": entity,
                        "name": item.get("Name", "N/A"), "status": item.get("Status", "N/A"),
                        "raw_data": item
                    }
                    all_logs.append(log_entry) # Adiciona o dicionário diretamente
        return all_logs
    except Exception as e:
        print(f"ERRO ao processar dados da SAP: {e}", file=sys.stderr)
        return [{"timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), "source_api": "sap_cloud_alm", "status": "error", "error_message": str(e)}]

# ===================================================================
# BLOCO DE EXECUÇÃO PRINCIPAL
# ===================================================================

if __name__ == "__main__":
    try:
        config = load_config()
        mode = config.get('general', 'mode')
        interval = config.getint('general', 'collection_interval_seconds')
        
        print(f"Iniciando coletor em modo '{mode}' com intervalo de {interval} segundos.")

        while True:
            if mode == 'openweathermap':
                log_to_send = fetch_weather_data(config)
                if log_to_send:
                    send_log_to_datadog(log_to_send, config)
            elif mode == 'sap':
                # Lógica ajustada para iterar sobre a lista de dicionários
                sap_logs = process_sap_data(config)
                for log_entry in sap_logs:
                    send_log_to_datadog(log_entry, config)
            else:
                print(f"Modo '{mode}' inválido. Encerrando.", file=sys.stderr)
                break
                
            time.sleep(interval)
    except Exception as e:
        print(f"Ocorreu um erro crítico no loop principal: {e}", file=sys.stderr)
        time.sleep(60)