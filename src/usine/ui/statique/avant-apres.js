// Écran Avant / après : charge /api/avant-apres. Le serveur envoie les valeurs des deux périodes
// déjà formatées ; le segment choisit seulement celle des deux grandes cartes, sans calcul, sans
// écart ni ratio. Le choix se garde dans l'URL (?periode=cumul). Aucune donnée n'est insérée
// comme HTML.
(function () {
  "use strict";

  var u = window.usine;
  var periode = new URLSearchParams(window.location.search).get("periode") === "cumul" ? "cumul" : "rapport";
  var vueCourante = null;

  function el(id) {
    return document.getElementById(id);
  }

  function afficherCarte(identifiant, carte, valeur) {
    var section = el("carte-" + identifiant);
    if (!carte) {
      section.hidden = true;
      return;
    }
    el("titre-" + identifiant).textContent = carte.titre;
    el("etiquette-" + identifiant).textContent = carte.etiquette;
    el("valeur-" + identifiant).textContent = carte.valeurs[valeur];
    section.hidden = false;
  }

  function mettreAJourCartes() {
    afficherCarte("manuel", vueCourante.manuel, periode);
    afficherCarte("chaine", vueCourante.chaine, periode);
    Array.prototype.forEach.call(el("segment-periode").children, function (bouton) {
      bouton.setAttribute("aria-pressed", bouton.getAttribute("data-periode") === periode ? "true" : "false");
    });
  }

  function choisir(valeur) {
    periode = valeur;
    window.history.replaceState(null, "", window.location.pathname + (valeur === "cumul" ? "?periode=cumul" : ""));
    mettreAJourCartes(); // le focus reste sur l'option choisie
  }

  function construireSegment(vue) {
    var segment = el("segment-periode");
    segment.setAttribute("aria-label", vue.libelle_periode);
    u.vider(segment);
    vue.periodes.forEach(function (option) {
      var bouton = u.creer("button", "segment-option", option.libelle);
      bouton.type = "button";
      bouton.setAttribute("data-periode", option.valeur);
      bouton.addEventListener("click", function () {
        choisir(option.valeur);
      });
      segment.appendChild(bouton);
    });
  }

  function construireTableau(tableau) {
    var carte = el("carte-tableau");
    if (!tableau) {
      carte.hidden = true;
      return;
    }
    var table = el("tableau-periodes");
    u.vider(table.tHead);
    u.vider(table.tBodies[0]);
    var entete = u.creer("tr");
    tableau.colonnes.forEach(function (colonne) {
      var th = u.creer("th", null, colonne);
      th.setAttribute("scope", "col");
      entete.appendChild(th);
    });
    table.tHead.appendChild(entete);
    tableau.lignes.forEach(function (ligne) {
      var tr = u.creer("tr");
      ligne.forEach(function (cellule, rang) {
        var element = rang === 0 ? u.creer("th", null, cellule) : u.creer("td", "code", cellule);
        if (rang === 0) {
          element.setAttribute("scope", "row");
        }
        tr.appendChild(element);
      });
      table.tBodies[0].appendChild(tr);
    });
    carte.hidden = false;
  }

  function afficher(vue) {
    vueCourante = vue;
    if (vue.erreur) {
      u.poserBandeau("erreur-ecran", "erreur", "alert", vue.erreur, null);
    } else {
      u.retirerBandeau("erreur-ecran");
    }
    var avertissements = el("avertissements");
    u.vider(avertissements);
    vue.avertissements.forEach(function (texte) {
      avertissements.appendChild(u.creer("p", "avertissement", texte));
    });
    if (vue.message) {
      el("message").textContent = vue.message;
      var lien = el("message-lien");
      if (vue.lien_message) {
        lien.textContent = vue.lien_message.libelle;
        lien.href = vue.lien_message.url;
        lien.hidden = false;
      }
      el("bloc-message").hidden = false;
      el("bloc-avant-apres").hidden = true;
      return;
    }
    el("bloc-message").hidden = true;
    if (!vue.manuel && !vue.chaine) {
      el("bloc-avant-apres").hidden = true;
      return;
    }
    construireSegment(vue);
    mettreAJourCartes();
    construireTableau(vue.tableau);
    var legende = el("legende-avant-apres");
    legende.textContent = vue.legende || "";
    legende.hidden = !vue.legende;
    el("bloc-avant-apres").hidden = false;
  }

  u.appeler("/api/avant-apres").then(function (vue) {
    if (vue) {
      afficher(vue);
    }
  });
})();
