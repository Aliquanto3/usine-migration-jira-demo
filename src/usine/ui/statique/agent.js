// Écran Agent : charge /api/agent. Mode réel : saisie, POST /api/agent/question, « L'Agent
// consulte le Passage… » pendant l'attente, la réponse remplace la précédente et reçoit le focus.
// Mode repli : pas de saisie, chaque question enregistrée rejoue sa réponse (GET). Les textes
// arrivent écrits par le serveur (AD-9) ; rien n'est inséré comme HTML. Une réponse rejetée
// n'a pas de texte côté serveur : elle n'en affiche pas.
(function () {
  "use strict";

  var u = window.usine;
  var parametres = new URLSearchParams(window.location.search);
  var questionUrl = parametres.get("question");
  var vueCourante = null;
  var numeroDemande = 0;
  var enAttente = false;

  function el(id) {
    return document.getElementById(id);
  }

  function afficherMessage(vue) {
    el("message").textContent = vue.message;
    var lien = el("message-lien");
    if (vue.lien_message) {
      lien.textContent = vue.lien_message.libelle;
      lien.href = vue.lien_message.url;
      lien.hidden = false;
    } else {
      lien.hidden = true;
    }
    el("bloc-message").hidden = false;
    el("bloc-agent").hidden = true;
  }

  function afficherErreur(texte, avecLienRepli) {
    u.poserBandeau("erreur-ecran", "erreur", "alert", texte, null);
    var lien = el("lien-repli");
    if (avecLienRepli && vueCourante && vueCourante.lien_repli) {
      lien.firstChild.textContent = vueCourante.lien_repli.libelle;
      lien.firstChild.href = vueCourante.lien_repli.url;
      lien.hidden = false;
    } else {
      lien.hidden = true;
    }
  }

  function viderErreur() {
    u.retirerBandeau("erreur-ecran");
    el("lien-repli").hidden = true;
  }

  function cacherReponse() {
    el("reponse").hidden = true;
    el("attente").hidden = true;
    el("bulle-question").hidden = true;
    el("bloc-fil").hidden = true;
  }

  function marquerChoix(question) {
    Array.prototype.forEach.call(el("liste-questions").querySelectorAll("button"), function (bouton) {
      bouton.setAttribute("aria-pressed", bouton.textContent === question ? "true" : "false");
    });
  }

  function afficherReponse(reponse) {
    el("attente").hidden = true;
    el("bulle-question").textContent = reponse.question;
    el("bulle-question").hidden = false;
    var texte = el("reponse-texte");
    texte.textContent = reponse.texte !== null ? reponse.texte : reponse.texte_masque;
    var badge = el("reponse-badge");
    badge.textContent = reponse.badge;
    badge.className = "badge badge--" + reponse.badge_code;
    el("libelle-outils").textContent = reponse.libelle_outils;
    var outils = el("reponse-outils");
    u.vider(outils);
    if (reponse.outils.length) {
      reponse.outils.forEach(function (nom) {
        outils.appendChild(u.creer("span", "etiquette-outil", nom));
      });
    } else {
      outils.textContent = reponse.aucun_outil;
    }
    var repli = el("reponse-repli");
    if (reponse.mention_repli) {
      repli.textContent = reponse.mention_repli;
      repli.hidden = false;
    } else {
      repli.hidden = true;
    }
    el("bloc-fil").hidden = false;
    var zone = el("reponse");
    zone.hidden = false;
    marquerChoix(reponse.question);
    // Annonce « Réponse de l'Agent reçue » : le texte change à chaque nouvelle réponse.
    var annonce = el("annonce");
    annonce.textContent = "";
    window.setTimeout(function () {
      annonce.textContent = reponse.annonce;
    }, 50);
    zone.focus();
  }

  function mettreEnAttente(question, vue) {
    enAttente = true;
    viderErreur();
    el("reponse").hidden = true;
    el("bulle-question").textContent = question;
    el("bulle-question").hidden = false;
    el("attente").textContent = vue.attente;
    el("attente").hidden = false;
    el("bloc-fil").hidden = false;
    var bouton = el("envoyer");
    bouton.setAttribute("aria-disabled", "true");
  }

  function finAttente() {
    enAttente = false;
    el("envoyer").removeAttribute("aria-disabled");
  }

  function envoyerQuestion() {
    var champ = el("question");
    var question = champ.value.trim();
    if (!question || enAttente || !vueCourante) {
      return;
    }
    var mien = ++numeroDemande;
    mettreEnAttente(question, vueCourante);
    u.envoyer("/api/agent/question", { question: question }).then(function (resultat) {
      if (mien !== numeroDemande) {
        return;
      }
      finAttente();
      if (resultat === null) {
        cacherReponse();
        return;
      }
      if (resultat.statut === 200) {
        afficherReponse(resultat.donnees);
        return;
      }
      cacherReponse();
      var detail = resultat.donnees && typeof resultat.donnees.detail === "string"
        ? resultat.donnees.detail
        : "Réponse de l'Agent impossible (HTTP " + resultat.statut + ").";
      afficherErreur(detail, true);
    });
  }

  function rejouer(rang, question) {
    var mien = ++numeroDemande;
    viderErreur();
    marquerChoix(question);
    el("reponse").hidden = true;
    el("bulle-question").textContent = question;
    el("bulle-question").hidden = false;
    el("attente").hidden = true;
    el("bloc-fil").hidden = false;
    u.demander("/api/agent/enregistrees/" + rang).then(function (resultat) {
      if (mien !== numeroDemande || resultat === null) {
        return;
      }
      if (resultat.statut === 200) {
        afficherReponse(resultat.donnees);
        return;
      }
      cacherReponse();
      var detail = resultat.donnees && typeof resultat.donnees.detail === "string"
        ? resultat.donnees.detail
        : "Réponse enregistrée indisponible (HTTP " + resultat.statut + ").";
      afficherErreur(detail, false);
    });
  }

  function construireQuestions(vue) {
    el("titre-questions").textContent = vue.titre_questions;
    var liste = el("liste-questions");
    u.vider(liste);
    var repli = vue.mode === "repli";
    vue.questions.forEach(function (item) {
      var bouton = u.creer("button", "question-choix", item.question);
      bouton.type = "button";
      bouton.setAttribute("aria-pressed", "false");
      bouton.addEventListener("click", function () {
        if (repli) {
          rejouer(item.rang, item.question);
        } else {
          var champ = el("question");
          champ.value = item.question;
          marquerChoix(item.question);
          champ.focus();
        }
      });
      var ligne = u.creer("li");
      ligne.appendChild(bouton);
      liste.appendChild(ligne);
    });
    el("bloc-questions").hidden = vue.questions.length === 0;
  }

  function construireOutils(vue) {
    el("titre-outils").textContent = vue.titre_outils;
    var liste = el("liste-outils");
    u.vider(liste);
    vue.outils.forEach(function (outil) {
      var ligne = u.creer("li");
      ligne.appendChild(u.creer("span", "etiquette-outil", outil.nom));
      ligne.appendChild(u.creer("span", "outil-description", outil.description));
      liste.appendChild(ligne);
    });
  }

  function afficher(vue) {
    vueCourante = vue;
    el("bloc-message").hidden = true;
    if (vue.message) {
      afficherMessage(vue);
      return;
    }
    el("bloc-agent").hidden = false;
    var legende = el("legende-agent");
    legende.textContent = vue.legende || "";
    legende.hidden = !vue.legende;
    var repli = el("message-repli");
    if (vue.message_repli) {
      repli.textContent = vue.message_repli;
      repli.hidden = false;
    } else {
      repli.hidden = true;
    }
    var formulaire = el("formulaire-agent");
    if (vue.saisie) {
      formulaire.hidden = false;
      formulaire.querySelector("label").textContent = vue.saisie.libelle;
      el("envoyer").textContent = vue.saisie.bouton;
      var champ = el("question");
      if (!champ.value) {
        champ.value = questionUrl || vue.saisie.valeur_defaut;
      }
    } else {
      formulaire.hidden = true;
    }
    construireQuestions(vue);
    construireOutils(vue);
    if (vue.erreur) {
      afficherErreur(vue.erreur, vue.mode === "reel");
    } else {
      viderErreur();
    }
    if (vue.mode === "repli" && questionUrl) {
      marquerChoix(questionUrl);  // sélectionnée, non rejouée : le clic rejoue
    }
  }

  function brancher() {
    el("formulaire-agent").addEventListener("submit", function (evenement) {
      evenement.preventDefault();
      envoyerQuestion();
    });
    el("question").addEventListener("keydown", function (evenement) {
      if (evenement.key === "Enter" && !evenement.shiftKey && !evenement.isComposing) {
        evenement.preventDefault();
        envoyerQuestion();
      }
    });
    el("envoyer").addEventListener("click", function (evenement) {
      if (el("envoyer").getAttribute("aria-disabled") === "true") {
        evenement.preventDefault();
      }
    });
  }

  brancher();
  u.appeler("/api/agent").then(function (vue) {
    if (vue) {
      afficher(vue);
    }
  });
})();
