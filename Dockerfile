# Usar uma imagem base oficial do Python
FROM python:3.9-slim

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Copiar primeiro o arquivo de dependências para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar TODOS os outros arquivos e pastas (incluindo a pasta 'templates') para o WORKDIR
COPY . .

# Expor a porta que o Gunicorn irá usar
EXPOSE 5000

# Comando para rodar a aplicação em produção usando Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
