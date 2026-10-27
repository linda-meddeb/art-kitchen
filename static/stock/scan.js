// Page de scan — douchette USB (mode « clavier » : elle tape le code puis Entrée).
(function () {
  "use strict";

  const cfg = window.SCAN_CONFIG;
  const champCode = document.getElementById("code");
  const champQte = document.getElementById("qte");
  const etat = document.getElementById("etat");
  const zone = document.getElementById("zone");
  const resultat = document.getElementById("resultat");
  const journal = document.getElementById("journal");
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const boutonsMode = document.querySelectorAll(".mode");

  const LIBELLES = { entree: "Entrée", sortie: "Sortie", perte: "Perte", consulter: "Consultation" };
  let mode = "sortie";
  let file = Promise.resolve(); // traite les scans un par un, dans l'ordre

  // ---------- Mode ----------
  function choisirMode(m) {
    mode = m;
    boutonsMode.forEach((b) => b.classList.toggle("actif", b.dataset.mode === m));
    zone.dataset.mode = m;
    champQte.disabled = m === "consulter";
    etat.textContent = `Mode ${LIBELLES[m]} — scannez un produit.`;
    champCode.focus();
  }
  boutonsMode.forEach((b) => b.addEventListener("click", () => choisirMode(b.dataset.mode)));
  document.addEventListener("keydown", (e) => {
    const touches = { F1: "sortie", F2: "entree", F3: "perte", F4: "consulter" };
    if (touches[e.key]) { e.preventDefault(); choisirMode(touches[e.key]); }
  });

  // ---------- Garder le focus sur le champ code ----------
  // La douchette tape « dans le vide » si aucun champ n'a le focus.
  document.addEventListener("click", (e) => {
    if (!e.target.closest("input, button, a, select, textarea")) champCode.focus();
  });
  champCode.addEventListener("blur", () => {
    setTimeout(() => {
      const actif = document.activeElement;
      if (!actif || actif === document.body) champCode.focus();
    }, 150);
  });
  // Entrée dans le champ quantité → retour au champ code
  champQte.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); champCode.focus(); champCode.select(); }
  });

  // ---------- Son ----------
  let audio;
  function bip(ok) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const o = audio.createOscillator();
      const g = audio.createGain();
      o.frequency.value = ok ? 1200 : 220;
      o.type = ok ? "sine" : "square";
      g.gain.value = 0.08;
      o.connect(g); g.connect(audio.destination);
      o.start(); o.stop(audio.currentTime + (ok ? 0.08 : 0.35));
    } catch (_) { /* pas de son, tant pis */ }
  }

  // ---------- Scan ----------
  champCode.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== "Tab") return; // certaines douchettes envoient Tab
    e.preventDefault();
    const code = champCode.value.trim();
    champCode.value = "";
    if (!code) return;
    const quantite = champQte.value || "1";
    champQte.value = "1"; // la quantité saisie ne vaut que pour le scan suivant
    file = file.then(() => envoyer(code, mode, quantite));
  });

  async function envoyer(code, modeScan, quantite) {
    etat.textContent = `Code ${code}…`;
    let data;
    try {
      const rep = await fetch(cfg.apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ code, mode: modeScan, quantite }),
      });
      data = await rep.json();
    } catch (err) {
      afficher(false, `Erreur réseau : ${err.message}`);
      return;
    }

    if (data.inconnu) {
      afficher(false, `Code <code>${esc(data.code)}</code> inconnu.
        <a class="btn" href="${data.url_creation}">Créer ce produit</a>`);
      return;
    }
    if (!data.ok) {
      afficher(false, esc(data.erreur));
      return;
    }

    const p = data.produit;
    const alerte = p.en_alerte ? ' <span class="badge badge-perte">stock bas</span>' : "";
    if (modeScan === "consulter") {
      afficher(true, `<strong>${esc(p.nom)}</strong> : ${p.quantite} ${esc(p.unite)} en stock${alerte}
        ${p.date_peremption ? `<br>DLC : ${p.date_peremption}` : ""}
        <br><a href="${p.url}">Voir la fiche</a>`);
    } else {
      const signe = modeScan === "entree" ? "+" : "−";
      afficher(true, `${LIBELLES[modeScan]} ${signe}${data.quantite} <strong>${esc(p.nom)}</strong>
        → ${p.quantite} ${esc(p.unite)}${alerte}`);
      ajouterJournal(data, modeScan, signe);
    }
  }

  function afficher(ok, html) {
    bip(ok);
    resultat.hidden = false;
    resultat.className = "resultat " + (ok ? "ok" : "erreur");
    resultat.innerHTML = html;
    zone.classList.remove("flash-ok", "flash-erreur");
    void zone.offsetWidth; // relance l'animation
    zone.classList.add(ok ? "flash-ok" : "flash-erreur");
    etat.textContent = `Mode ${LIBELLES[mode]} — prêt.`;
    champCode.focus();
  }

  function ajouterJournal(data, modeScan, signe) {
    const p = data.produit;
    const tr = document.createElement("tr");
    const heure = new Date().toLocaleTimeString("fr-FR");
    tr.innerHTML = `<td>${heure}</td><td><a href="${p.url}">${esc(p.nom)}</a></td>
      <td><span class="badge badge-${modeScan}">${LIBELLES[modeScan]}</span> ${signe}${data.quantite}</td>
      <td>${p.quantite} ${esc(p.unite)}</td>
      <td><button type="button" class="lien">Annuler</button></td>`;
    tr.querySelector("button").addEventListener("click", () => annuler(data.mouvement_id, tr));
    journal.querySelector("tr").after(tr);
  }

  async function annuler(id, tr) {
    const rep = await fetch(cfg.annulerUrl.replace("/0/", `/${id}/`), {
      method: "POST", headers: { "X-CSRFToken": csrf },
    });
    const data = await rep.json();
    if (data.ok) {
      tr.classList.add("annule");
      tr.querySelector("button").replaceWith("annulé");
      afficher(true, `Annulé — ${esc(data.produit.nom)} : ${data.produit.quantite} ${esc(data.produit.unite)}`);
    } else {
      afficher(false, esc(data.erreur));
    }
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  choisirMode("sortie");
})();
