# Site « Papiers en Paix »

Le site d'Enzo : aide administrative à domicile pour les seniors.

Il est fait en HTML et en CSS, sans outil compliqué. Pour le voir, il suffit d'ouvrir le fichier `index.html` dans un navigateur, avec un double-clic.

## Les fichiers

| Fichier | Contenu |
|---|---|
| `index.html` | La page principale, avec toutes les sections |
| `mentions-legales.html` | Les mentions légales |
| `confidentialite.html` | La politique de confidentialité |
| `css/style.css` | Les couleurs, les tailles et la mise en page |
| `fonts/` | Les polices, hébergées sur le site (aucun service externe) |
| `img/` | Ici, la photo d'Enzo |

## 1. Ce qui reste à remplir

Les coordonnées d'Enzo sont déjà en place (Colfontaine, 0495 62 09 10, e-mail, adresse, hébergeur Vercel). Il reste :

| À chercher | Remplacer par | Exemple |
|---|---|---|
| `[NUMÉRO BCE]` | Le numéro d'entreprise, dès qu'il est attribué | `BE 0123.456.789` |

Dans un éditeur de texte (VS Code, Notepad++…), utilisez **Rechercher et remplacer dans tous les fichiers**. Pour vérifier qu'il ne reste rien, cherchez `[` dans les fichiers `.html`.

**Quand vous aurez un nom de domaine** (par exemple `papiersenpaix.be`) :

- dans `index.html`, sous la ligne `<meta name="description" …>`, ajoutez : `<link rel="canonical" href="https://papiersenpaix.be/">` ;
- dans le bloc `application/ld+json`, sous la ligne `"name"`, ajoutez : `"url": "https://papiersenpaix.be/",` ;
- dans le flyer (en bas de `index.html`), ajoutez l'adresse du site à la dernière ligne.

**Pour changer le numéro de téléphone** plus tard, il apparaît sous deux formes : `0495&nbsp;62&nbsp;09&nbsp;10` (le texte affiché) et `+32495620910` (le lien d'appel, toujours sans espaces). Remplacez les deux.

**Le nom** « Papiers en Paix » est provisoire. Pour le changer, remplacez `Papiers en Paix` partout.

## 2. Ajouter la photo d'Enzo

1. Prenez une vraie photo, en lumière naturelle, de préférence en format portrait (plus haute que large).
2. Réduisez-la à environ 800 × 1000 pixels et enregistrez-la en JPEG, sous `img/enzo.jpg`. Visez moins de 200 Ko : le site gratuit <https://squoosh.app> le fait très bien.
3. Dans `index.html`, cherchez « Photo d'Enzo à venir ». Supprimez la ligne `<div class="portrait__cadre" …>…</div>` et mettez à la place :

```html
<img src="img/enzo.jpg" alt="Enzo, assis à une table avec un classeur" width="800" height="1000">
```

Adaptez le texte de `alt` à ce que montre vraiment la photo.

## 3. Modifier un texte

Ouvrez `index.html` dans un éditeur de texte. Chaque section commence par un commentaire, par exemple `<!-- 6. Tarif -->`. Changez seulement le texte entre les balises, sans toucher aux `<` et `>`.

Quelques règles pour garder le site lisible :

- des phrases courtes, des mots simples ;
- pas d'anglais, pas de jargon ;
- pas de chiffres inventés ni de faux avis.

## 4. Ajouter de vrais témoignages

La section des témoignages existe déjà, mais elle est cachée. Quand vous aurez de **vrais** avis, avec l'accord écrit des personnes :

1. dans `index.html`, cherchez `t-temoignages` ;
2. sur la ligne `<section … hidden>`, supprimez le mot `hidden` ;
3. ajoutez les témoignages en suivant l'exemple en commentaire juste en dessous.

## 5. Changer les couleurs

Les couleurs sont regroupées en haut de `css/style.css`, dans le bloc `:root`. Si vous en changez une, vérifiez que le contraste reste fort sur <https://webaim.org/resources/contrastchecker/> (au moins 7:1 pour le texte).

Contrastes actuels sur le fond ivoire : texte 15:1, texte secondaire 9:1, bleu encre 9,6:1, texte blanc sur bouton bleu 10,8:1. Sur le bandeau sombre des engagements : 11:1 au minimum. Tous sont au niveau AAA.

## 6. Le flyer pour les professionnels

Le bouton « Imprimer le flyer (A4) » imprime une seule page A4 propre, avec les services, les engagements, le tarif et le téléphone. On peut aussi choisir « Enregistrer en PDF » dans la fenêtre d'impression, pour l'envoyer par e-mail à une pharmacie ou à un CPAS.

## 7. Publier le site (gratuit)

### Avec Netlify (le plus simple)

1. Créez un compte sur <https://app.netlify.com>.
2. Allez dans **Sites**, puis glissez-déposez le dossier `site-conciergerie` entier dans la zone prévue.
3. Le site est en ligne en quelques secondes. Netlify vous donne une adresse du type `xxx.netlify.app`.
4. Pour un nom de domaine à vous (`papiersenpaix.be`), achetez-le auprès d'un registraire belge et suivez **Domain settings** dans Netlify.

Hébergeur à indiquer dans les mentions légales : *Netlify, Inc., 101 2nd Street, San Francisco, CA 94105, États-Unis*.

### Avec Vercel

1. Créez un compte sur <https://vercel.com> et liez-le à GitHub.
2. Cliquez sur **Add New… > Project** et choisissez ce dépôt.
3. Dans **Root Directory**, indiquez `site-conciergerie`. Laissez le reste par défaut (pas de framework, pas de commande de compilation).
4. Cliquez sur **Deploy**.

Hébergeur à indiquer dans les mentions légales : *Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis*.

Vérifiez l'adresse de l'hébergeur sur son site au moment de publier : elle peut changer.

## 8. Ce que le site ne fait pas, volontairement

- Aucun cookie, aucune statistique, aucun Google Analytics.
- Aucune police ni image chargée depuis un autre site.
- Aucun formulaire : le contact se fait par téléphone ou par e-mail, pour ne jamais recevoir d'informations médicales par le site.

Si vous ajoutez un outil de ce genre plus tard, il faudra mettre à jour la politique de confidentialité.

## Licences

Polices Atkinson Hyperlegible (Braille Institute) et Literata (TypeTogether), sous licence SIL Open Font License 1.1. Les licences se trouvent dans le dossier `fonts/`.
