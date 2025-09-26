# Estágio 1: Use uma imagem base oficial e leve do Python.
FROM python:3.10-slim-bookworm

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker.
COPY requirements.txt .

# Instala as dependências.
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos da aplicação para o diretório de trabalho.
COPY main.py .
COPY config.ini .

# Comando que será executado quando o contêiner iniciar.
CMD ["python3", "main.py"]