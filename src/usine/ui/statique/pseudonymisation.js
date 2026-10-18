// Écran Pseudonymisation : charge /api/pseudonymisation[?ticket=DEMO-17]. Original et aperçu
// s'affichent en texte brut (textContent, retours à la ligne conservés), côte à côte, sans
// surlignage des pseudonymes (AD-11). Un moteur absent est nommé dans le bandeau d'erreur.
(function () {
  "use strict";

  var u = window.usine;
  var ticket = new URLSearchParams(window.location.search).get("ticket");

  function el(id) {
    return document.getElementById(id);
  }

  function construireSelection(vue) {
    el("libelle-ticket").textContent = vue.libelle_ticket;
    var champ = el("choix-ticket");
    u.vider(champ);
    vue.tickets.forEach(function (cle) {
      var option = u.creer("option", null, cle);
      option.value = cle;
      option.selected = !!vue.ticket && vue.ticket.cle === cle;
      champ.appendChild(option);
    });
  }

  function afficher(vue) {
    if (vue.erreur) {
      u.poserBandeau("erreur-ecran", "erreur", "alert", vue.erreur, null);
    } else {
      u.retirerBandeau("erreur-ecran");
    }
    if (vue.message) {
      el("message").textContent = vue.message;
      var lien = el("message-lien");
      if (vue.lien_message) {
        lien.textContent = vue.lien_message.libelle;
        lien.href = vue.lien_message.url;
        lien.hidden = false;
      }
      el("bloc-message").hidden = false;
      el("bloc-pseudo").hidden = true;
      return;
    }
    el("bloc-message").hidden = true;
    if (!vue.tickets.length) {
      el("bloc-pseudo").hidden = true;
      return;
    }
    construireSelection(vue);
    var courant = el("ticket-courant");
    u.vider(courant);
    if (vue.ticket) {
      courant.appendChild(document.createTextNode(vue.libelle_ticket + " : "));
      courant.appendChild(u.ticket(vue.ticket));
      courant.hidden = false;
    } else {
      courant.hidden = true;
    }
    var legende = el("legende-pseudo");
    legende.textContent = vue.legende || "";
    legende.hidden = !vue.legende;
    var panneaux = el("panneaux");
    if (vue.original !== null && vue.pseudonymise !== null) {
      el("titre-original").textContent = vue.titre_original;
      el("titre-pseudo").textContent = vue.titre_pseudonymise;
      el("etiquette-pseudo").textContent = vue.etiquette_pseudonymise;
      el("texte-original").textContent = vue.original;
      el("texte-pseudo").textContent = vue.pseudonymise;
      panneaux.hidden = false;
    } else {
      panneaux.hidden = true;
    }
    el("bloc-pseudo").hidden = false;
  }

  var adresse = "/api/pseudonymisation" + (ticket ? "?ticket=" + encodeURIComponent(ticket) : "");
  u.appeler(adresse).then(function (vue) {
    if (vue) {
      afficher(vue);
    }
  });
})();
