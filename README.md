# API Data Collector

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

Um script Python modular e robusto para coletar dados de APIs (SAP Cloud ALM, OpenWeatherMap) e salvá-los em arquivos de log estruturados (JSON Lines) para posterior processamento por agentes de monitoramento como o Datadog.

# Guia de Integração: Coletor de Logs SAP para Kubernetes

## 1. Visão Geral

Este pacote contém os artefatos necessários para construir e implantar o serviço de coleta de logs da API SAP Cloud ALM em um ambiente Kubernetes (AWS EKS).

O serviço opera como um `Deployment` que coleta dados da API SAP e os envia diretamente para o endpoint de ingestão de logs do Datadog. A configuração é gerenciada através de um `Secret` do Kubernetes, desacoplado da imagem do contêiner.

## 2. Componentes do Pacote

* `main.py`: O código-fonte da aplicação em Python.
* `requirements.txt`: As dependências Python necessárias.
* `Dockerfile`: O manifesto para a construção da imagem do contêiner.
* `config.ini.example`: Um template para o arquivo de configuração.
* `k8s/deployment.yaml`: O manifesto de implantação para o Kubernetes.

## 3. Pré-requisitos

* Um cluster AWS EKS funcional e acessível.
* Um registro de contêiner interno (ex: AWS ECR) para hospedar a imagem da aplicação.
* Um ambiente de pipeline (CI/CD) com acesso ao cluster e capacidade de executar comandos `docker` e `kubectl`.
* Credenciais da API da SAP e da API do Datadog.

## 4. Fluxo de Integração e Implantação

O processo a seguir deve ser adaptado e integrado à sua pipeline de CI/CD.

### Passo 4.1: Configuração

Crie um arquivo `config.ini` a partir do template `config.ini.example`. Preencha este arquivo com as credenciais e parâmetros específicos do seu ambiente (SAP e Datadog). Este arquivo será usado para criar o `Secret` no Kubernetes e **não deve ser adicionado à imagem do contêiner**.

### Passo 4.2: Construção e Publicação da Imagem do Contêiner

A pipeline deve executar o build da imagem Docker a partir do `Dockerfile` contido neste pacote e publicá-la em seu registro de contêiner interno.

```bash
# Exemplo de comandos para a pipeline

# 1. Construir a imagem
docker build -t SEU_REGISTRY/api-collector:v1.0 .

# 2. Publicar a imagem
docker push SEU_REGISTRY/api-collector:v1.0
```
*Substitua `SEU_REGISTRY` pela URL do seu repositório de contêineres (ex: `123456789012.dkr.ecr.us-east-1.amazonaws.com`).*

### Passo 4.3: Atualização do Manifesto de Implantação

Edite o arquivo `k8s/deployment.yaml`. É **mandatório** que a linha `image:` seja atualizada para apontar para a imagem que você publicou no passo anterior.

```yaml
# k8s/deployment.yaml
...
spec:
  containers:
  - name: api-collector-container
    # ATUALIZE ESTA LINHA
    image: SEU_REGISTRY/api-collector:v1.0
...
```

### Passo 4.4: Implantação no EKS

A pipeline deve executar os seguintes comandos `kubectl`, autenticada no cluster de destino.

1.  **Criação do `Secret`:**
    *Este comando utiliza o arquivo `config.ini` preenchido para criar um `Secret` no cluster.*
    ```bash
    kubectl create secret generic api-config --from-file=config.ini
    ```

2.  **Implantação da Aplicação:**
    *Este comando aplica o manifesto e cria os recursos no cluster.*
    ```bash
    kubectl apply -f k8s/deployment.yaml
    ```

## 5. Validação

1.  **Verifique o status do Pod:**
    ```bash
    kubectl get pods -l app=api-collector
    ```
    Aguarde o status `Running`.

2.  **Monitore os logs da aplicação:**
    ```bash
    POD_NAME=$(kubectl get pods -l app=api-collector -o jsonpath='{.items[0].metadata.name}')
    kubectl logs -f $POD_NAME
    ```

3.  **Confirme no Datadog:** Verifique se os logs com `source: sap_cloud_alm` estão sendo recebidos.

## 6. Gerenciamento do Ciclo de Vida

### Atualizar a Configuração

Para alterar qualquer parâmetro no `config.ini`:
1.  Execute novamente o Passo 4.4.1 (delete e recrie o `Secret` a partir do arquivo atualizado).
2.  Force a reinicialização do `Deployment` para carregar a nova configuração:
    ```bash
    kubectl rollout restart deployment api-collector-deployment
    ```

### Desinstalação

Para remover a aplicação do cluster, execute:
```bash
kubectl delete -f k8s/deployment.yaml
kubectl delete secret api-config
```
