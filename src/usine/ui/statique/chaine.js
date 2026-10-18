// Écran Lancement de la Chaîne : lance `usine rapport` (POST /api/chaine), sonde l'état chaque
// seconde (GET /api/chaine, intervalle donné par le serveur) et gère le bouton de mode
// (POST /api/mode). Le serveur envoie des textes déjà écrits (AD-9) ; aucune donnée n'est insérée comme HTML.
// Le sondage s'arrête à la fin ou à l'échec et reprend à la réouverture de la page.
(function () {
  "use strict";

  var u = window.usine;
  var minuteur = null;
  var dernierBandeau = null;
  var derniereAnnonce = "";
  var lignes = [];
  var vueCourante = null;

  function el(id) {
    return document.getElementById(id);
  }

  // Bouton `aria-disabled` : reste focalisable ; le motif, visible dessous, lui est lié.
  function poserBouton(bouton, motif, vue) {
    bouton.textContent = vue.libelle;
    if (vue.bloque) {
      bouton.setAttribute("aria-disabled", "true");
    } else {
      bouton.removeAttribute("aria-disabled");
    }
    if (vue.motif) {
      motif.textContent = vue.motif;
      motif.hidden = false;
      bouton.setAttribute("aria-describedby", motif.id);
    } else {
      motif.textContent = "";
      motif.hidden = true;
      bouton.removeAttribute("aria-describedby");
    }
  }

  function creerLigneEtape(vue) {
    var li = u.creer("li", "etape");
    li.appendChild(u.creer("span", "etape-puce"));
    var texte = u.creer("div", "etape-texte");
    texte.appendChild(u.creer("span", "etape-nom", vue.nom));
    texte.appendChild(u.creer("span", "legende", vue.description));
    li.appendChild(texte);
    li.appendChild(u.creer("span", "etape-badge"));
    return li;
  }

  function afficherEtapes(vue) {
    var liste = el("etapes");
    if (lignes.length !== vue.etapes.length) {
      u.vider(liste);
      lignes = vue.etapes.map(function (etape) {
        var li = creerLigneEtape(etape);
        liste.appendChild(li);
        return li;
      });
    }
    vue.etapes.forEach(function (etape, rang) {
      var li = lignes[rang];
      li.className = "etape etape--" + etape.etat;
      if (etape.etat === "en_cours") {
        li.setAttribute("aria-current", "step");
      } else {
        li.removeAttribute("aria-current");
      }
      li.firstChild.textContent = etape.etat === "reussie" ? "✓" : String(etape.numero);
      li.lastChild.textContent = etape.duree
        ? etape.libelle_etat + " (" + etape.duree + ")"
        : etape.libelle_etat;
    });
  }

  function afficherProgression(vue) {
    el("compteur").textContent = vue.compteur;
    var barre = el("barre");
    barre.setAttribute("aria-valuenow", String(vue.terminees));
    barre.setAttribute("aria-valuemax", String(vue.total));
    el("barre-remplissage").style.width = (100 * vue.terminees) / vue.total + "%";
    // La région status n'annonce que ce qui change : étape, fin, échec (jamais chaque sondage).
    if (vue.annonce && vue.annonce !== derniereAnnonce) {
      el("annonce").textContent = vue.annonce;
      derniereAnnonce = vue.annonce;
    }
    if (vue.statut === "attente") {
      derniereAnnonce = "";
      el("annonce").textContent = "";
    }
  }

  function afficherJournal(vue) {
    var liste = el("journal");
    u.vider(liste);
    if (vue.journal.length === 0) {
      liste.appendChild(u.creer("li", null, vue.journal_vide));
      return;
    }
    vue.journal.forEach(function (ligne) {
      var li = u.creer("li");
      li.appendChild(u.creer("span", "journal-heure", ligne.horodatage));
      li.appendChild(document.createTextNode(ligne.texte));
      liste.appendChild(li);
    });
  }

  function afficherBandeau(vue) {
    var signature = JSON.stringify(vue.bandeau);
    if (signature === dernierBandeau) {
      return; // même contenu : on ne touche à rien, pour ne pas relancer l'annonce
    }
    dernierBandeau = signature;
    var zone = el("bandeau-resultat");
    u.vider(zone);
    var b = vue.bandeau;
    if (!b) {
      return;
    }
    var erreur = b.variante === "erreur";
    var bandeau = u.creer("div", "bandeau bandeau--" + b.variante);
    bandeau.setAttribute("role", erreur ? "alert" : "status");
    bandeau.appendChild(u.creer("p", null, b.texte));
    if (b.lignes.length > 0) {
      bandeau.appendChild(u.creer("pre", "erreur-lignes", b.lignes.join("\n")));
    }
    if (b.complement) {
      bandeau.appendChild(u.creer("p", null, b.complement));
    }
    if (b.lien) {
      var p = u.creer("p");
      var lien = u.creer("a", null, b.lien.libelle);
      lien.href = b.lien.url;
      p.appendChild(lien);
      bandeau.appendChild(p);
    }
    zone.appendChild(bandeau);
  }

  function afficherDernierPassage(vue) {
    var zone = el("dernier-passage");
    u.vider(zone);
    if (!vue.dernier_passage) {
      zone.appendChild(u.creer("p", "legende", vue.message_dernier_passage));
      return;
    }
    vue.dernier_passage.lignes.forEach(function (ligne) {
      zone.appendChild(u.creer("p", "legende", ligne));
    });
  }

  function afficherErreur(texte) {
    var element = el("erreur-chaine");
    if (texte) {
      if (element.textContent !== texte) {
        element.textContent = texte;
      }
      element.hidden = false;
    } else {
      element.textContent = "";
      element.hidden = true;
    }
  }

  function afficher(vue) {
    vueCourante = vue;
    poserBouton(el("bouton-lancement"), el("motif-lancement"), vue.bouton_lancement);
    poserBouton(el("bouton-mode"), el("motif-mode"), vue.bouton_mode);
    afficherProgression(vue);
    afficherEtapes(vue);
    afficherJournal(vue);
    afficherBandeau(vue);
    afficherDernierPassage(vue);
    afficherErreur(vue.erreur);
  }

  function programmer(delaiMs) {
    if (minuteur !== null) {
      window.clearTimeout(minuteur);
    }
    minuteur = window.setTimeout(charger, delaiMs);
  }

  // Un sondage ; il se reprogramme tant que la Chaîne tourne (ou que le serveur ne répond plus).
  function charger() {
    minuteur = null;
    return u.appeler("/api/chaine").then(function (vue) {
      if (vue) {
        afficher(vue);
      }
      if (vue === null ? vueCourante && vueCourante.en_cours : vue.en_cours) {
        programmer(vueCourante.intervalle_ms);
      } else {
        if (vue && vue.statut !== "attente") {
          u.rafraichirCadre(); // l'en-tête prend le nouveau Passage publié
        }
      }
    });
  }

  function refusSansEffet(bouton) {
    return bouton.getAttribute("aria-disabled") === "true";
  }

  function lancer() {
    var bouton = el("bouton-lancement");
    if (refusSansEffet(bouton)) {
      return;
    }
    bouton.setAttribute("aria-disabled", "true"); // pas de second clic avant la réponse
    u.envoyer("/api/chaine").then(function (reponse) {
      if (reponse && reponse.statut === 202) {
        afficher(reponse.donnees);
        programmer(reponse.donnees.intervalle_ms);
        return;
      }
      charger(); // refus (409) ou serveur muet : on relit l'état réel
    });
  }

  function changerMode() {
    var bouton = el("bouton-mode");
    if (refusSansEffet(bouton) || !vueCourante) {
      return;
    }
    bouton.setAttribute("aria-disabled", "true");
    u.envoyer("/api/mode", { mode: vueCourante.mode_cible }).then(function () {
      u.rafraichirCadre();
      charger();
    });
  }

  el("bouton-lancement").addEventListener("click", lancer);
  el("bouton-mode").addEventListener("click", changerMode);

  charger();
  // Retour sur l'onglet ou page restaurée : le suivi reprend là où la Chaîne en est.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      charger();
    }
  });
  window.addEventListener("pageshow", function (evenement) {
    if (evenement.persisted) {
      charger();
    }
  });
})();
