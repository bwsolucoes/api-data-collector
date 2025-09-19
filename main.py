import configparser
import json
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

import requests
import xml.etree.ElementTree as ET

# ===================================================================
# FUNÇÕES DE CONFIGURAÇÃO E LOG
# ===================================================================

def setup_logging(config):
    """
    Configura o sistema de logging para salvar em um arquivo com rotação diária.
    Os logs são mantidos por um período definido no config.ini.
    """
    try:
        log_file_path = config.get('logging', 'log_file_path')
        log_dir = os.path.dirname(log_file_path)

        # Cria o diretório de log se ele não existir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Configuração do logger
        logger = logging.getLogger("APIDataLogger")
        logger.setLevel(logging.INFO)

        # Prevenir duplicação de logs se o script for recarregado
        if logger.hasHandlers():
            logger.handlers.clear()

        # Handler para rotação de arquivos
        # Gira o log à meia-noite e mantém 7 arquivos de backup (7 dias)
        handler = TimedRotatingFileHandler(
            log_file_path,
            when=config.get('logging', 'log_rotation_interval'),
            interval=1,
            backupCount=config.getint('logging', 'log_backup_count')
        )
        # Formato do log: apenas a mensagem, pois a mensagem já é um JSON completo
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    except Exception as e:
        # Se o logging falhar, imprime o erro na saída padrão e encerra
        print(f"Erro crítico ao configurar o logging: {e}", file=sys.stderr)
        sys.exit(1)

def load_config():
    """
    Carrega as configurações do arquivo config.ini.
    """
    config = configparser.ConfigParser()
    # Assume que config.ini está no mesmo diretório do script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError("Arquivo 'config.ini' não encontrado no diretório do script.")
        
    config.read(config_path)
    return config

# ===================================================================
# MÓDULO DE COLETA - OPENWEATHERMAP
# ===================================================================

def fetch_weather_data(config):
    """
    Busca os dados de clima da API OpenWeatherMap.
    """
    api_key = config.get('openweathermap', 'api_key')
    city = config.get('openweathermap', 'city')
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    params = {
        'q': city,
        'appid': api_key,
        'units': 'metric', # Para temperatura em Celsius
        'lang': 'pt_br'
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()  # Lança uma exceção para status HTTP 4xx/5xx
        data = response.json()
        
        # Estrutura o log no formato JSON Lines
        log_entry = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "source_api": "openweathermap",
            "city": data.get('name'),
            "temperature_celsius": data['main'].get('temp'),
            "feels_like_celsius": data['main'].get('feels_like'),
            "humidity_percent": data['main'].get('humidity'),
            "weather_description": data['weather'][0].get('description') if data.get('weather') else None,
            "status": "success"
        }
        return json.dumps(log_entry)

    except requests.exceptions.RequestException as e:
        error_log = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "source_api": "openweathermap",
            "status": "error",
            "error_message": str(e)
        }
        return json.dumps(error_log)

# ===================================================================
# MÓDULO DE COLETA - SAP CLOUD ALM 
# ===================================================================

def get_sap_token(config):
    """
    Obtém o token de acesso OAuth2 da API da SAP.
    """
    token_url = config.get('sap', 'token_url')
    client_id = config.get('sap', 'client_id')
    client_secret = config.get('sap', 'client_secret')

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "client_credentials"}
    
    response = requests.post(token_url, data=payload, headers=headers, auth=(client_id, client_secret), timeout=15)
    response.raise_for_status()
    
    return response.json()["access_token"]

def process_sap_data(config):
    """
    Orquestra a coleta de dados da SAP, adaptada para registrar em log.
    O envio diretamente para o Datadog foi desabilitado para este script.
    """
    try:
        access_token = get_sap_token(config)
        base_url = config.get('sap', 'base_api_url')
        metadata_url = f"{base_url}$metadata"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/xml"}

        # Consulta os metadados para descobrir as entidades
        response_metadata = requests.get(metadata_url, headers=headers, timeout=15)
        response_metadata.raise_for_status()

        # Extrai os nomes das entidades do XML
        namespaces = {'edm': 'http://docs.oasis-open.org/odata/ns/edm'}
        root = ET.fromstring(response_metadata.content)
        entity_sets = root.findall(".//edm:EntitySet", namespaces)
        entity_names = [e.attrib["Name"] for e in entity_sets]

        # Coleta os logs para cada entidade
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
                        "source_api": "sap_cloud_alm",
                        "entity": entity,
                        "name": item.get("Name", "N/A"),
                        "status": item.get("Status", "N/A"),
                        "raw_data": item # Adiciona o dado bruto para análise posterior
                    }
                    all_logs.append(json.dumps(log_entry))
        
        return all_logs

    except Exception as e:
        error_log = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "source_api": "sap_cloud_alm",
            "status": "error",
            "error_message": str(e)
        }
        return [json.dumps(error_log)]

# ===================================================================
# BLOCO DE EXECUÇÃO PRINCIPAL
# ===================================================================

if __name__ == "__main__":
    try:
        # Carrega as configurações
        config = load_config()
        
        # Configura o logger para salvar os dados em arquivo
        data_logger = setup_logging(config)
        
        # Obtém o modo de operação e o intervalo do config.ini
        mode = config.get('general', 'mode')
        interval = config.getint('general', 'collection_interval_seconds')
        
        print(f"Iniciando coletor em modo '{mode}' com intervalo de {interval} segundos.")
        print(f"Logs serão salvos em: {config.get('logging', 'log_file_path')}")

        # Loop principal de execução
        while True:
            if mode == 'openweathermap':
                # Modo OpenWeatherMap: busca um registro e loga
                weather_log = fetch_weather_data(config)
                if weather_log:
                    data_logger.info(weather_log)
                    
            elif mode == 'sap':
                # Modo SAP: busca múltiplos registros e loga um por um
                sap_logs = process_sap_data(config)
                if sap_logs:
                    for log_entry in sap_logs:
                        data_logger.info(log_entry)
            else:
                # Se o modo for inválido, loga um erro e sai
                print(f"Modo '{mode}' inválido no config.ini. Saindo.", file=sys.stderr)
                break
                
            # Aguarda o intervalo definido antes da próxima execução
            time.sleep(interval)

    except FileNotFoundError as e:
        print(f"Erro de configuração: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nServiço interrompido pelo usuário.")
    except Exception as e:
        # Pega qualquer outra exceção inesperada
        print(f"Ocorreu um erro inesperado no loop principal: {e}", file=sys.stderr)
        # Em um cenário real, poderíamos logar isso em um arquivo de erro separado
        time.sleep(60) # Espera um pouco mais antes de tentar de novo
