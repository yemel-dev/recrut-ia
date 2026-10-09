**Objet : Refonte UI/UX de l'écran de fin d'entretien ("Entretien terminé")**

**Rôle :** Tu es un Designer UI/UX Senior et Développeur Frontend spécialisé dans les interfaces de visioconférence et de collaboration SaaS haut de gamme (Google Meet, Zoom, Webex, Teams).

**Objectif :** Refondre complètement la page actuelle de fin d'entretien. L'interface actuelle ressemble à un composant "vibecodé" générique (fond bleu nuit très sombre, bouton vert flashy isolé, bannière rouge d'avertissement en haut, cartes flottantes shadcn par défaut). Je veux transformer cet écran pour qu'il soit **élégant, épuré, professionnel et naturel**, sans aucun soupçon de code généré à la hâte par IA.

---

### Directives Visuelles & Inspiration (Google Meet / Zoom / Microsoft Fluent) :

1. **Fond & Atmosphère :**
   * Abandonne le bleu/noir nuit sombre artificiel (`slate-950`).
   * Adopte une palette sobre, équilibrée et moderne :
     * En **mode clair** : un fond très légèrement gris/neutre (`#F8F9FA` ou `#F3F4F6`), propre comme Google Meet.
     * En **mode sombre** (si conservé) : un vrai anthracite profond/mat (`#121212` ou `#1A1D21`), doux pour les yeux, avec un faible contraste sur les cartes.

2. **Layout & Typographie :**
   * Suppression de la grosse bannière rouge d'avertissement en haut ("La salle d'entretien a été fermée"). Ces informations doivent être intégrées de manière fluide sous forme de badge discret ou de sous-titre naturel.
   * Disposition centrale aérée : la confirmation de fin d'appel doit être douce et informative, non punitive.
   * Typographie nette et hiérarchisée (Inter, system-ui ou Roboto), avec un bon équilibre des tailles (`font-normal` et `font-medium` au lieu d'abuser du `font-bold`).

3. **Actions & Boutons :**
   * Remplace le bouton vert pétant "vibecoder" par des actions claires, élégantes et structurées :
     * **Bouton principal (CTA) :** Un bouton sobre et raffiné (ex. bleu Meet `#1A73E8`, indigo soutenu ou neutre sombre `#1E293B`) pour "Voir le compte-rendu / Replay".
     * **Actions secondaires :** Liens ou boutons secondaires outline/ghost pour "Retourner aux candidatures" ou "Rejoindre à nouveau".

4. **Composants d'Information (UX) :**
   * Ajoute un petit résumé informatif discret et utile (ex. durée de l'entretien, date/heure de clôture, participants).
   * Intègre des icônes discrètes et élégantes (Lucide / Heroicons avec `stroke-width={1.5}` pour un rendu très fin).

5. **Clean Code & Design System :**
   * Utilise Tailwind CSS avec des classes propres (`gap-`, `space-y-`, micro-animations douces `transition-all duration-200`).
   * Évite les conteneurs superposés inutilement ou les bordures agressives (`border-slate-800`).

---