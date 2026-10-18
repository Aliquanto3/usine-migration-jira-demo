// Écran « Ce qu'il faut pour le faire en vrai » : charge /api/outillage. Le serveur rend la fiche
// Markdown en HTML (markdown-it-py, HTML brut désactivé) : c'est le seul HTML inséré, produit par
// le serveur à partir d'un fichier du dépôt, jamais une donnée saisie.
(function () {
  "use strict";

  var u = window.usine;

  u.appeler("/api/outillage").then(function (vue) {
    if (!vue) {
      return;
    }
    if (vue.erreur) {
      u.poserBandeau("erreur-ecran", "erreur", "alert", vue.erreur, null);
    } else {
      u.retirerBandeau("erreur-ecran");
    }
    if (vue.message) {
      document.getElementById("message").textContent = vue.message;
      document.getElementById("bloc-message").hidden = false;
    }
    var legende = document.getElementById("legende-fiche");
    legende.textContent = vue.legende || "";
    legende.hidden = !vue.legende;
    if (vue.html) {
      document.getElementById("fiche").innerHTML = vue.html;
    }
  });
})();
