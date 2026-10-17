// Écran Carte météo : charge /api/carte et affiche tuiles, tableau filtrable et livrables.
// Le serveur envoie des valeurs déjà formatées (AD-9) ; le filtre agit dans le navigateur, sans
// rechargement, et annonce le nombre d'Entités dans la région role="status".
(function () {
  "use strict";

  var u = window.usine;

  function afficherMessage(vue) {
    document.getElementById("message").textContent = vue.message;
    var lien = document.getElementById("message-lien");
    if (vue.lien_message) {
      lien.textContent = vue.lien_message.libelle;
      lien.href = vue.lien_message.url;
      lien.hidden = false;
    } else {
      lien.hidden = true;
    }
    document.getElementById("bloc-message").hidden = false;
  }

  function afficherTuiles(vue) {
    var liste = document.getElementById("tuiles");
    u.vider(liste);
    vue.comptages.forEach(function (comptage) {
      var tuile = u.creer("li", "carte tuile");
      tuile.appendChild(u.pastilleMeteo(comptage.meteo));
      tuile.appendChild(u.creer("p", "tuile-chiffre", String(comptage.nombre)));
      liste.appendChild(tuile);
    });
  }

  function cellule(balise, texte, portee) {
    var element = u.creer(balise, null, texte);
    if (portee) {
      element.setAttribute("scope", portee);
    }
    return element;
  }

  function afficherTableau(vue) {
    var table = document.getElementById("tableau-entites");
    document.getElementById("legende-tableau").textContent = vue.legende;
    var entete = table.tHead;
    u.vider(entete);
    var ligneEntete = u.creer("tr");
    ["Entité", "Météo", "Tendance", "Règle principale", "Tickets en cause", "Détail"].forEach(
      function (titre) {
        ligneEntete.appendChild(cellule("th", titre, "col"));
      }
    );
    entete.appendChild(ligneEntete);

    var corps = table.tBodies[0];
    u.vider(corps);
    vue.lignes.forEach(function (ligne) {
      var tr = u.creer("tr");
      tr.setAttribute("data-meteo", ligne.meteo.couleur);
      var entite = cellule("th", ligne.entite, "row");
      entite.className = "code";
      tr.appendChild(entite);
      var meteo = u.creer("td");
      meteo.appendChild(u.pastilleMeteo(ligne.meteo));
      tr.appendChild(meteo);
      tr.appendChild(u.creer("td", null, ligne.tendance));
      tr.appendChild(u.creer("td", "code", ligne.regle_principale));
      var tickets = u.creer("td");
      if (ligne.tickets.length) {
        tickets.appendChild(u.listeTickets(ligne.tickets));
        if (ligne.suite) {
          tickets.appendChild(u.creer("span", null, " " + ligne.suite));
        }
      } else {
        tickets.textContent = vue.vide;
      }
      tr.appendChild(tickets);
      var action = u.creer("td", "action");
      var lien = u.creer("a", "lien-action", ligne.libelle_detail);
      lien.href = ligne.url_detail;
      action.appendChild(lien);
      tr.appendChild(action);
      corps.appendChild(tr);
    });
  }

  // Filtre météo : masque les lignes d'une autre couleur et annonce le résultat.
  function brancherFiltre(vue) {
    var filtre = vue.filtre;
    var champ = document.getElementById("filtre-meteo");
    document.getElementById("libelle-filtre").textContent = filtre.libelle;
    u.vider(champ);
    filtre.options.forEach(function (option) {
      var element = u.creer("option", null, option.libelle);
      element.value = option.valeur;
      champ.appendChild(element);
    });
    var annonce = document.getElementById("annonce-filtre");

    function appliquer() {
      var choisie = champ.value;
      var affichees = 0;
      var lignes = document.querySelectorAll("#tableau-entites tbody tr");
      Array.prototype.forEach.call(lignes, function (ligne) {
        var visible = choisie === "toutes" || ligne.getAttribute("data-meteo") === choisie;
        ligne.hidden = !visible;
        if (visible) {
          affichees += 1;
        }
      });
      var texte;
      if (affichees === 0) {
        var option = filtre.options.filter(function (o) {
          return o.valeur === choisie;
        })[0];
        texte = option.message_vide;
      } else if (affichees === 1) {
        texte = filtre.annonce_une;
      } else {
        texte = filtre.annonce_plusieurs.replace("{n}", String(affichees));
      }
      annonce.textContent = texte;
      document.getElementById("tableau-entites").hidden = affichees === 0;
    }

    champ.addEventListener("change", appliquer);
    appliquer();
  }

  function afficherLivrables(vue) {
    var liste = document.getElementById("livrables");
    u.vider(liste);
    vue.livrables.forEach(function (livrable) {
      var item = u.creer("li", "livrable");
      if (livrable.url) {
        var lien = u.creer("a", "livrable-lien", livrable.libelle + " · " + livrable.fichier);
        lien.href = livrable.url;
        lien.setAttribute("download", livrable.fichier);
        item.appendChild(lien);
        item.appendChild(u.creer("p", "legende", livrable.description));
      } else {
        item.appendChild(u.creer("strong", null, livrable.libelle + " · " + livrable.fichier));
        item.appendChild(u.creer("p", "legende", livrable.absent));
      }
      liste.appendChild(item);
    });
  }

  function afficher(vue) {
    if (vue.erreur) {
      u.poserBandeau("erreur-ecran", "erreur", "alert", vue.erreur, null);
    } else {
      u.retirerBandeau("erreur-ecran");
    }
    if (vue.message) {
      afficherMessage(vue);
      return;
    }
    if (vue.erreur) {
      return;
    }
    document.getElementById("date-arrete").textContent = vue.sous_titre;
    afficherTuiles(vue);
    afficherTableau(vue);
    brancherFiltre(vue);
    afficherLivrables(vue);
    document.getElementById("bloc-carte").hidden = false;
  }

  u.appeler("/api/carte").then(function (vue) {
    if (vue) {
      afficher(vue);
    }
  });
})();
