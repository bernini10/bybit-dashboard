# Usar uma imagem base oficial do Python
FROM python:3.9-slim

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Copiar primeiro o arquivo de dependências para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY app.py .

# Expor a porta que o Gunicorn irá usar
EXPOSE 5000

# Comando para rodar a aplicação com um timeout maior (300 segundos)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "app:app"]
