# Nepsis Account Qualifier

Actif de démonstration pour le cas Bulldozer / Nepsis.

## Ce que fait l'app

Entrée : nom d'une entreprise.

Sortie :
- score /10 explicable ;
- statut `CONTACT`, `WATCH` ou `INSUFFICIENT` ;
- motif de qualification ;
- persona commerciale recommandée ;
- geste commercial recommandé ;
- preuves publiques avec URL et date quand détectable ;
- temps de traitement ;
- coût API direct v1 = 0 €.

## Fichiers à mettre sur GitHub

Tous les fichiers de ce dossier doivent être placés à la racine du dépôt `nepsis-account-qualifier`.

## Déploiement Railway

Railway lit automatiquement `railway.toml` et `Dockerfile`.
Le service écoute le port fourni par Railway via `$PORT`.
Aucune clé API n'est nécessaire pour la v1.

Pour limiter la consommation sur une offre gratuite, activer **Sleep / Serverless** sur le service Railway.

## Démo jury

1. Ouvrir l'URL Railway avant la restitution.
2. Tester un compte connu.
3. Montrer le statut, le score, les preuves et le geste.
4. Tester un compte donné par le jury.
5. Si la preuve est insuffisante, valoriser `INSUFFICIENT` plutôt que forcer une conclusion.

## Benchmark

L'onglet **Benchmark 20 comptes** applique exactement les mêmes règles aux 20 comptes présents dans `test_accounts.csv`.
Le fichier exporté contient aussi des champs de revue humaine.

## Limites assumées

- recherche publique non exhaustive ;
- parent / SPV parfois ambigu ;
- dates parfois absentes des snippets ;
- un appel d'offres gagné ne prouve pas à lui seul une fenêtre d'achat ;
- la qualification priorise une revue commerciale, elle ne la remplace pas.
