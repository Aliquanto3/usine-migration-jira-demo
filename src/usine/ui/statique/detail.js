// Écran Détail d'une Entité : charge /api/entites/{entite}[?palier=1] et affiche Météo, Règles,
// KPI, Prévision, Risque et Explication. Le serveur envoie des valeurs déjà formatées (AD-9) ;
// aucune donnée n'est insérée comme HTML. Le segment de Palier met à jour l'URL (?palier=1) sans
// recharger la page et garde le focus sur l'option choisie.
(function () {
  "use strict";

  var u = window.usine;
  var morceaux = window.location.pathname.split("/");
  var entite = decodeURIComponent(morceaux[morceaux.length - 1]);
  var palierDemande = new URLSearchParams(window.location.search).get("palier") === "1" ? 1 : 2;
  var construit = false;

  function texte(balise, classe, contenu) {
    return u.creer(balise, classe, contenu);
  }

  function liste(items) {
    var ul = texte("ul", "liste");
    items.forEach(function (item) {
      ul.appendChild(texte("li", null, item));
    });
    return ul;
  }

  function tableau(colonnes, lignes, legende) {
    var table = texte("table");
    table.appendChild(texte("caption", "sr-seul", legende));
    var entete = texte("tr");
    colonnes.forEach(function (colonne) {
      var th = texte("th", null, colonne);
      th.setAttribute("scope", "col");
      entete.appendChild(th);
    });
    table.appendChild(texte("thead")).appendChild(entete);
    var corps = texte("tbody");
    lignes.forEach(function (ligne) {
      var tr = texte("tr");
      ligne.forEach(function (cellule) {
        tr.appendChild(texte("td", "code", cellule));
      });
      corps.appendChild(tr);
    });
    table.appendChild(corps);
    var zone = texte("div", "table-defile");
    zone.setAttribute("role", "region");
    zone.setAttribute("aria-label", legende);
    zone.tabIndex = 0;
    zone.appendChild(table);
    return zone;
  }

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
    document.getElementById("bloc-detail").hidden = true;
  }

  // Formulaire de sélection : choisir une Entité ne navigue qu'au clic sur « Afficher ».
  function construireSelection(vue) {
    var lien = document.getElementById("lien-carte");
    lien.textContent = vue.lien_carte.libelle;
    lien.href = vue.lien_carte.url;
    var champ = document.getElementById("choix-entite");
    u.vider(champ);
    vue.entites.forEach(function (option) {
      var element = texte("option", null, option.libelle);
      element.value = option.url;
      champ.appendChild(element);
    });
    document.getElementById("formulaire-entite").addEventListener("submit", function (evenement) {
      evenement.preventDefault();
      window.location.href = champ.value;
    });
  }

  function mettreAJourSelection(vue) {
    var champ = document.getElementById("choix-entite");
    Array.prototype.forEach.call(champ.options, function (option) {
      option.selected = option.textContent === vue.entite;
    });
  }

  function segmentPalier(vue) {
    var bloc = document.getElementById("bloc-segment");
    if (!vue.segment_palier) {
      bloc.hidden = true;
      return;
    }
    var segment = document.getElementById("segment-palier");
    if (!segment.firstChild) {
      vue.segment_palier.options.forEach(function (option) {
        var bouton = texte("button", "segment-option", option.libelle);
        bouton.type = "button";
        bouton.setAttribute("data-palier", String(option.valeur));
        bouton.addEventListener("click", function () {
          choisirPalier(option.valeur);
        });
        segment.appendChild(bouton);
      });
      document.getElementById("legende-segment").textContent = vue.segment_palier.legende;
    }
    vue.segment_palier.options.forEach(function (option) {
      var bouton = segment.querySelector('[data-palier="' + option.valeur + '"]');
      bouton.setAttribute("aria-pressed", option.actif ? "true" : "false");
    });
    bloc.hidden = false;
  }

  function choisirPalier(palier) {
    palierDemande = palier;
    var adresse = window.location.pathname + (palier === 1 ? "?palier=1" : "");
    window.history.replaceState(null, "", adresse);
    charger();
  }

  function afficherRegles(vue) {
    var zone = document.getElementById("zone-regles");
    var table = document.getElementById("tableau-regles");
    var aucune = document.getElementById("aucune-regle");
    if (!vue.regles.length) {
      aucune.textContent = vue.aucune_regle;
      aucune.hidden = false;
      zone.hidden = true;
      return;
    }
    aucune.hidden = true;
    zone.hidden = false;
    u.vider(table.tHead);
    var entete = texte("tr");
    ["Règle", "Tickets en cause"].forEach(function (titre) {
      var th = texte("th", null, titre);
      th.setAttribute("scope", "col");
      entete.appendChild(th);
    });
    table.tHead.appendChild(entete);
    var corps = table.tBodies[0];
    u.vider(corps);
    vue.regles.forEach(function (regle) {
      var tr = texte("tr");
      tr.appendChild(texte("td", "code", regle.regle));
      var cellule = texte("td");
      if (!regle.tickets.length) {
        cellule.textContent = vue.vide;
      } else {
        cellule.appendChild(u.listeTickets(regle.tickets.slice(0, regle.visibles)));
        var reste = regle.tickets.slice(regle.visibles);
        if (reste.length) {
          var suite = texte("span", "tickets-suite");
          suite.hidden = true;
          suite.appendChild(document.createTextNode(", "));
          suite.appendChild(u.listeTickets(reste));
          var bouton = texte("button", "bouton-texte", "+" + reste.length);
          bouton.type = "button";
          bouton.setAttribute("aria-expanded", "false");
          bouton.addEventListener("click", function () {
            var ouvert = bouton.getAttribute("aria-expanded") === "true";
            bouton.setAttribute("aria-expanded", ouvert ? "false" : "true");
            suite.hidden = ouvert;
          });
          cellule.appendChild(document.createTextNode(" "));
          cellule.appendChild(bouton);
          cellule.appendChild(suite);
        }
      }
      tr.appendChild(cellule);
      corps.appendChild(tr);
    });
  }

  function afficherKpi(vue) {
    var ul = document.getElementById("liste-kpi");
    u.vider(ul);
    var aucun = document.getElementById("aucun-kpi");
    if (!vue.kpi.length) {
      aucun.textContent = vue.aucun_kpi;
      aucun.hidden = false;
      return;
    }
    aucun.hidden = true;
    vue.kpi.forEach(function (ligne) {
      var tuile = texte("li", "tuile-kpi");
      tuile.appendChild(texte("p", "legende", ligne.libelle));
      tuile.appendChild(texte("p", "tuile-chiffre", ligne.valeur));
      ul.appendChild(tuile);
    });
  }

  function afficherBlocs(section, conteneur) {
    u.vider(conteneur);
    if (section.message) {
      conteneur.appendChild(texte("p", null, section.message));
      return;
    }
    section.blocs.forEach(function (bloc) {
      var div = texte("div", "bloc");
      if (bloc.titre) {
        div.appendChild(texte("p", "bloc-titre", bloc.titre));
      }
      if (bloc.texte) {
        div.appendChild(texte("p", null, bloc.texte));
      }
      if (bloc.items.length) {
        div.appendChild(liste(bloc.items));
      }
      if (bloc.sous_titre) {
        div.appendChild(texte("p", "bloc-titre", bloc.sous_titre));
        div.appendChild(liste(bloc.sous_items));
      }
      if (bloc.note) {
        div.appendChild(texte("p", "legende", bloc.note));
      }
      conteneur.appendChild(div);
    });
    if (section.tableau) {
      conteneur.appendChild(
        tableau(section.tableau.colonnes, section.tableau.lignes, section.titre)
      );
    }
  }

  function afficherExplication(vue) {
    var section = vue.explication;
    document.getElementById("titre-explication").textContent = section.titre;
    var conteneur = document.getElementById("contenu-explication");
    u.vider(conteneur);
    if (section.message) {
      conteneur.appendChild(texte("p", null, section.message));
      return;
    }
    section.explications.forEach(function (explication) {
      var div = texte("div", "bloc");
      div.appendChild(texte("span", "badge badge--" + explication.statut_code, explication.statut));
      var paragraphe = texte("p", "lecture");
      explication.segments.forEach(function (segment) {
        paragraphe.appendChild(
          segment.ticket ? u.ticket(segment.ticket) : document.createTextNode(segment.texte)
        );
      });
      div.appendChild(paragraphe);
      if (explication.citations.length) {
        var citations = texte("p", "legende", explication.titre_citations + " : ");
        citations.appendChild(u.listeTickets(explication.citations));
        div.appendChild(citations);
      }
      if (explication.phrases_retirees) {
        div.appendChild(texte("p", "legende", explication.phrases_retirees));
      }
      conteneur.appendChild(div);
    });
  }

  function afficher(vue) {
    if (vue.erreur) {
      u.poserBandeau("erreur-ecran", "erreur", "alert", vue.erreur, null);
      return;
    }
    u.retirerBandeau("erreur-ecran");
    if (!construit) {
      construit = true;
      if (vue.entites.length) {
        construireSelection(vue);
      }
    }
    if (vue.message) {
      afficherMessage(vue);
      return;
    }
    document.getElementById("bloc-message").hidden = true;
    mettreAJourSelection(vue);
    segmentPalier(vue);
    var meteo = document.getElementById("meteo-entite");
    u.vider(meteo);
    meteo.appendChild(u.pastilleMeteo(vue.meteo));
    afficherRegles(vue);
    afficherKpi(vue);
    var prevision = document.getElementById("section-prevision");
    prevision.hidden = vue.prevision === null;
    if (vue.prevision) {
      document.getElementById("titre-prevision").textContent = vue.prevision.titre;
      afficherBlocs(vue.prevision, document.getElementById("contenu-prevision"));
    }
    document.getElementById("titre-risque").textContent = vue.risque.titre;
    afficherBlocs(vue.risque, document.getElementById("contenu-risque"));
    afficherExplication(vue);
    document.getElementById("bloc-detail").hidden = false;
  }

  function charger() {
    var adresse =
      "/api/entites/" + encodeURIComponent(entite) + (palierDemande === 1 ? "?palier=1" : "");
    return u.appeler(adresse).then(function (vue) {
      if (vue) {
        afficher(vue);
      }
    });
  }

  charger();
})();
