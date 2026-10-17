// Cadre commun : charge /api/cadre et affiche la pastille « Passage publié », la pastille de
// mode et les bandeaux. Sans framework, sans calcul ni formatage : les libellés arrivent écrits
// par le serveur (AD-9). Ressources locales seulement (NFR-12).
(function () {
  "use strict";

  var MESSAGE_INJOIGNABLE = "L'interface ne joint plus le serveur. Relancer usine ui.";

  // Un seul bandeau de chaque type à la fois : `cle` identifie le type.
  function poserBandeau(cle, variante, role, texte, html) {
    var existant = document.getElementById("bandeau-" + cle);
    if (existant) {
      // Même contenu : on ne touche à rien, pour ne pas relancer l'annonce.
      if (existant.getAttribute("data-contenu") === texte) {
        return;
      }
      existant.remove();
    }
    var element = document.createElement("p");
    element.id = "bandeau-" + cle;
    element.className = "bandeau bandeau--" + variante;
    element.setAttribute("role", role);
    element.setAttribute("data-contenu", texte);
    if (html) {
      element.innerHTML = html; // texte constant du serveur (Markdown en ligne rendu)
    } else {
      element.textContent = texte;
    }
    document.getElementById("bandeaux").appendChild(element);
  }

  function retirerBandeau(cle) {
    var existant = document.getElementById("bandeau-" + cle);
    if (existant) {
      existant.remove();
    }
  }

  function signalerServeurInjoignable() {
    poserBandeau("injoignable", "erreur", "alert", MESSAGE_INJOIGNABLE, null);
  }

  // Appel JSON : une réponse absente ou non conforme affiche le bandeau d'erreur une seule fois.
  function appeler(chemin) {
    return fetch(chemin, { headers: { Accept: "application/json" } })
      .then(function (reponse) {
        if (!reponse.ok) {
          throw new Error("HTTP " + reponse.status);
        }
        return reponse.json();
      })
      .then(function (donnees) {
        retirerBandeau("injoignable");
        return donnees;
      })
      .catch(function () {
        signalerServeurInjoignable();
        return null;
      });
  }

  function afficherCadre(vue) {
    var passage = document.getElementById("pastille-passage");
    if (vue.passage_publie) {
      passage.textContent = vue.passage_publie;
      passage.hidden = false;
    } else {
      passage.hidden = true;
    }

    var mode = document.getElementById("pastille-mode");
    mode.textContent = vue.libelle_mode;
    mode.className = "pastille-mode pastille-mode--" + vue.mode;
    mode.hidden = false;

    if (vue.bandeau_repli_html) {
      poserBandeau("repli", "repli", "status", vue.bandeau_repli_html, vue.bandeau_repli_html);
    } else {
      retirerBandeau("repli");
    }
    if (vue.erreur) {
      poserBandeau("erreur", "erreur", "alert", vue.erreur, null);
    } else {
      retirerBandeau("erreur");
    }
  }

  function chargerCadre() {
    return appeler("/api/cadre").then(function (vue) {
      if (vue) {
        afficherCadre(vue);
      }
    });
  }

  // Éléments du DOM : textContent et createElement seulement, jamais innerHTML (données du
  // serveur non fiables). Les textes arrivent déjà écrits par le serveur (AD-9).
  function creer(balise, classe, texte) {
    var element = document.createElement(balise);
    if (classe) {
      element.className = classe;
    }
    if (texte !== undefined && texte !== null) {
      element.textContent = texte;
    }
    return element;
  }

  function vider(element) {
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  // Clé de ticket : lien Jira dans un nouvel onglet, ou texte simple (url absente, Mode repli).
  function ticket(vue) {
    if (!vue.url) {
      return creer("span", "ticket", vue.cle);
    }
    var lien = creer("a", "ticket ticket--lien", vue.cle);
    lien.href = vue.url;
    lien.target = "_blank";
    lien.rel = "noopener noreferrer";
    lien.setAttribute("aria-label", vue.nom_accessible);
    return lien;
  }

  // Pastille météo : la couleur nomme la teinte, le libellé porte l'information.
  function pastilleMeteo(vue) {
    var pastille = creer("span", "pastille-meteo pastille-meteo--" + vue.couleur);
    pastille.appendChild(creer("span", "pastille-meteo-point"));
    pastille.appendChild(creer("span", "pastille-meteo-libelle", vue.libelle));
    return pastille;
  }

  // Liste de clés de ticket séparées par des virgules ; tableau vide : cellule vide.
  function listeTickets(tickets) {
    var conteneur = creer("span", "tickets");
    tickets.forEach(function (vue, rang) {
      if (rang > 0) {
        conteneur.appendChild(document.createTextNode(", "));
      }
      conteneur.appendChild(ticket(vue));
    });
    return conteneur;
  }

  // Aux écrans de 7.14 à 7.16 : même fonction d'appel, même bandeau d'erreur unique.
  window.usine = {
    appeler: appeler,
    creer: creer,
    vider: vider,
    ticket: ticket,
    pastilleMeteo: pastilleMeteo,
    listeTickets: listeTickets,
    poserBandeau: poserBandeau,
    retirerBandeau: retirerBandeau,
  };

  chargerCadre();
  // Retour sur l'onglet : relit le cadre ; un serveur arrêté entre-temps affiche le bandeau.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      chargerCadre();
    }
  });
  window.addEventListener("pageshow", function (evenement) {
    if (evenement.persisted) {
      chargerCadre();
    }
  });
})();
