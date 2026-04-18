# InvestPlatform - High-Frequency Trading & MLM App

Une plateforme d'investissement professionnel complète (Backend Django + Frontend Responsive) dotée d'un système de marketing multi-niveaux (MLM) asynchrone et d'un tableau de bord de pointe (SuperAdmin).

## 🚀 Fonctionnalités Principales

### 1. Modèle d'Affaires : Paliers VIP (Tiers)
- Achats directs des Paliers d'investissement sans wallet intermédiaire ("Direct Checkout").
- Calcul des rendements quotidiens automatiques via **Intérêts Composés**.
- Gamification avancée (Points VIP, Badges de fidélité).

### 2. Algorithme Binaire & Parrainage (MLM)
- Système de parrainage dynamique avec Patte Gauche et Patte Droite.
- CRON asynchrone calculant le volume de vente de l'arbre et reversant un **Bonus Binaire** sur la patte la plus faible.

### 3. Gestion Bancaire Sécurisée
- Logique anti "Double-Spend" avec verrouillage de base de données (`select_for_update`).
- Processus de Retrait à double validation (Manager & Client).
- Intégration simulée (Mobile Money : Orange, Moov, Wave).

### 4. Backoffice Manager & SuperAdmin
- Analyses graphiques interactives de la trésorerie entrante vs sortante.
- Interface d'approbation des investissements (`PENDING` vers `ACTIVE`).
- Console de contrôle pour désactiver des produits en un clic.

## 🛠 Stack Technique
- **Backend framework**: Django 5 / Python 3.12
- **Tâches Asynchrones**: Celery & Redis
- **Base de données**: PostgreSQL
- **Frontend**: HTML5, Vanilla CSS, JS (Chart.js & AlpineJS pour la réactivité)
- **Containerisation**: Docker & Docker Compose

## 📖 Installation Rapide (Environnement de Dév)

1. **Cloner le répertoire**
   ```bash
   git clone https://github.com/votre-nom/invest.git
   cd invest
   ```

2. **Démarrer les conteneurs Docker**
   ```bash
   docker-compose up -d --build
   ```

3. **Exécuter les migrations**
   ```bash
   docker-compose exec web python manage.py makemigrations
   docker-compose exec web python manage.py migrate
   ```

4. **Créer un Super Administrateur**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

L'application est disponible sur : `http://localhost:8000/`

## 🔒 Sécurité
- Sessions sécurisées & hachage Argon2/PBKDF2.
- Protections CSRF et XSS intégrées.
- Validation rigoureuse des transactions avant chaque exécution Celery.
