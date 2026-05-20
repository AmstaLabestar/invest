# InvestPlatform

Plateforme web Django permettant aux utilisateurs de creer un compte, souscrire a une categorie d'investissement, suivre leurs gains, demander des retraits et parrainer d'autres utilisateurs.

## Fonctionnalites

- Catalogue de categories conforme au cahier des charges.
- Rendements journaliers automatises par categorie.
- Bonus partenaire de 50 000 FCFA tous les 15 jours pour Partenaire 1 et Partenaire 2.
- Parrainage simple avec lien unique, bonus credite apres validation et delai de 24h.
- Retrait limite aux gains disponibles, avec controle des montants et validation admin.
- Paiements Mobile Money limites a Orange Money, Moov Money et Telecel Money.
- Back-office pour utilisateurs, categories, transactions, retraits et statistiques.
- Interface mobile-first responsive.

## Stack

- Django 5 / Python 3.12
- PostgreSQL en Docker
- SQLite possible en environnement cloud sans `DATABASE_URL`
- Celery / Redis pour les traitements asynchrones
- HTML, CSS, Alpine.js et Chart.js

## Installation locale

```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_data
docker-compose exec web python manage.py createsuperuser
```

Application locale : `http://localhost:8000/`

## Paiements

Le code garde un mode de validation admin tant que les API operateurs ne sont pas connectees. Les fournisseurs actifs sont centralises dans `investments/payments.py` afin de brancher ensuite les adaptateurs Orange Money, Moov Money et Telecel Money sans refonte du parcours transactionnel.

## Securite

- Sessions Django securisees.
- Protection CSRF.
- Validation serveur des moyens de paiement.
- Verrouillage transactionnel lors des demandes de retrait.
- Variables d'environnement pour les secrets, hosts et base de donnees.
