# API Data Collector

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

Um script Python modular e robusto para coletar dados de APIs (SAP Cloud ALM, OpenWeatherMap) e salvá-los em arquivos de log estruturados (JSON Lines) para posterior processamento por agentes de monitoramento como o Datadog.

## Funcionalidades

- **Coleta Modular**: Facilmente configurável para coletar dados da API do SAP Cloud ALM ou da OpenWeatherMap (para testes).
- **Configuração Centralizada**: Todas as configurações, incluindo credenciais e modo de operação, são gerenciadas no arquivo `config.ini`.
- **Saída Estruturada**: Os logs são gerados no formato JSON Lines, ideal para parsing automático por coletores de log.
- **Rotação Automática de Logs**: Utiliza o `TimedRotatingFileHandler` do Python para gerenciar o tamanho e a retenção dos arquivos de log, evitando o esgotamento de disco.
- **Gerenciamento como Serviço**: Inclui um arquivo de unidade `systemd` (`api-collector.service`) para garantir que o script seja executado de forma confiável em segundo plano, inicie com o sistema e reinicie automaticamente em caso de falhas.

## Estrutura do Projeto

```
/opt/api-collector/
├── venv/                   # Ambiente virtual Python
├── main.py                 # O script principal da aplicação
├── config.ini              # Arquivo de configuração (NÃO DEVE SER VERSIONADO COM SEGREDOS)
├── config.ini.example      # Um template do arquivo de configuração
├── requirements.txt        # Dependências Python do projeto
└── .gitignore              # Arquivos e pastas a serem ignorados pelo Git
```

## Pré-requisitos

- Um sistema operacional Linux compatível com `systemd` (Ubuntu, Debian, CentOS, Oracle Linux, etc.).
- Python 3.8 ou superior.
- Acesso à internet para baixar dependências e conectar-se às APIs.

## Instalação

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/seu-usuario/api-data-collector.git](https://github.com/seu-usuario/api-data-collector.git)
    cd api-data-collector
    ```

2.  **Crie um ambiente virtual e instale as dependências:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure a aplicação:**
    - Copie o arquivo de exemplo de configuração:
      ```bash
      cp config.ini.example config.ini
      ```
    - Edite o `config.ini` e preencha os valores necessários, como as chaves de API e o modo de operação desejado.

## Executando como um Serviço (systemd)

1.  **Crie o diretório de log:**
    ```bash
    sudo mkdir -p /var/log/api-collector
    ```

2.  **Copie o arquivo de serviço para o diretório do systemd:**
    *Um arquivo `api-collector.service` de exemplo está disponível na documentação do projeto.*
    ```bash
    sudo nano /etc/systemd/system/api-collector.service
    ```
    - Cole o conteúdo do arquivo de serviço e salve.

3.  **Recarregue o daemon do systemd, habilite e inicie o serviço:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable api-collector.service
    sudo systemctl start api-collector.service
    ```

## Verificação e Uso

- **Verificar o status do serviço:**
  ```bash
  sudo systemctl status api-collector.service
  ```

- **Visualizar os logs da aplicação em tempo real:**
  ```bash
  sudo tail -f /var/log/api-collector/api_data.log
  ```

- **Visualizar os logs do serviço (saídas de print e erros):**
  ```bash
  sudo journalctl -u api-collector.service -f
  ```
