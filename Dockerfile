# Utilisez l'image Python officielle allégée
FROM python:3.12-slim

# Définissez les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Créez le répertoire de travail
WORKDIR /app

# Installez les dépendances système nécessaires pour PostgreSQL et autres outils
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiez le fichier des dépendances et installez-les
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiez le reste du code de l'application
COPY . /app/
