FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências do sistema para faster-whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pré-download do modelo Whisper durante a build.
# Isso baixa o modelo pro cache do huggingface (~/.cache/huggingface) DENTRO
# da camada da imagem, então nenhum container que subir a partir dela
# precisa de rede pra buscar o modelo na hora da requisição do aluno.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

EXPOSE 8080

# Forma shell (não exec) é necessária aqui pra permitir a expansão de
# variável de ambiente. Railway injeta $PORT; localmente cai no fallback 8080.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}