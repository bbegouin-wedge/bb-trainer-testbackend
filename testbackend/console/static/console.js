// La console : un client de l'API de pilotage, rien de plus.
//
// L'extension htmx « json-body » envoie en JSON le corps d'un bouton
// (data-body) ou d'un formulaire. Dans un formulaire : data-type="int",
// "float" ou "json" convertit la valeur (vide : champ omis), une case à
// cocher vaut true ou false, un nom pointé (variants.hello) fait un objet
// imbriqué, un nom en « _ » n'est pas envoyé.

(function () {
  function setPath(body, path, value) {
    let node = body;
    path.slice(0, -1).forEach(function (key) { node = node[key] = node[key] || {}; });
    node[path[path.length - 1]] = value;
  }

  function convert(input) {
    const raw = input.value;
    const type = input.dataset.type;
    if (!type) return raw;
    if (raw.trim() === "") return undefined;
    if (type === "json") return JSON.parse(raw);
    const number = type === "int" ? parseInt(raw, 10) : parseFloat(raw);
    if (Number.isNaN(number)) throw new Error(input.name + " : nombre attendu");
    return number;
  }

  function bodyOf(elt) {
    if (elt.dataset.body !== undefined) return JSON.parse(elt.dataset.body);
    const form = elt.tagName === "FORM" ? elt : elt.closest("form");
    const body = {};
    Array.from(form.elements).forEach(function (input) {
      if (!input.name || input.name[0] === "_" || input.disabled) return;
      if (input.type === "radio" && !input.checked) return;
      const value = input.type === "checkbox" ? input.checked : convert(input);
      if (value !== undefined) setPath(body, input.name.split("."), value);
    });
    return body;
  }

  function flash(message) {
    const box = document.getElementById("flash");
    box.textContent = message;
    box.hidden = !message;
  }

  htmx.defineExtension("json-body", {
    onEvent: function (name, evt) {
      if (name !== "htmx:configRequest") return true;
      const elt = evt.detail.elt;
      try {
        elt._jsonBody = JSON.stringify(bodyOf(elt));
      } catch (err) {
        flash("Saisie invalide : " + err.message);
        evt.preventDefault();
        return false;
      }
      evt.detail.headers["Content-Type"] = "application/json";
      const stage = document.getElementById("stage-select");
      if (elt.hasAttribute("data-stageable") && stage && stage.value) {
        evt.detail.path = evt.detail.path.replace(/\/actions$/, "/pending/" + stage.value + "/stage");
      }
      return true;
    },
    encodeParameters: function (xhr, parameters, elt) {
      xhr.overrideMimeType("application/json");
      return elt._jsonBody;
    },
  });

  document.addEventListener("htmx:afterRequest", function (evt) {
    const xhr = evt.detail.xhr;
    if (xhr.status >= 400) {
      let detail = xhr.responseText;
      try { detail = JSON.stringify(JSON.parse(detail).detail); } catch (err) { /* texte brut */ }
      flash("Refusé (" + xhr.status + ") : " + detail);
      return;
    }
    flash("");
    if (evt.detail.elt.dataset.then === "open-game") {
      location.href = "/ui/games/" + JSON.parse(xhr.responseText).game_id;
    }
  });

  // Le websocket redessine les régions : on garde ce que l'opérateur a choisi.
  let kept = {};
  document.addEventListener("htmx:wsBeforeMessage", function () {
    const stage = document.getElementById("stage-select");
    const wire = document.getElementById("wire");
    kept = {
      stage: stage && stage.value,
      atBottom: !wire || wire.scrollHeight - wire.scrollTop - wire.clientHeight < 40,
    };
  });
  document.addEventListener("htmx:wsAfterMessage", function () {
    const stage = document.getElementById("stage-select");
    if (stage && kept.stage && stage.querySelector('option[value="' + kept.stage + '"]')) stage.value = kept.stage;
    const wire = document.getElementById("wire");
    if (wire && kept.atBottom) wire.scrollTop = wire.scrollHeight;
  });

  document.addEventListener("DOMContentLoaded", function () {
    const catalog = JSON.parse((document.getElementById("catalog") || {}).textContent || "{}");

    document.querySelectorAll(".tabs button[data-tab]").forEach(function (button) {
      button.addEventListener("click", function () {
        const tabs = button.parentElement;
        tabs.querySelectorAll("button[data-tab]").forEach(function (b) { b.classList.toggle("on", b === button); });
        tabs.nextElementSibling.querySelectorAll(".tab-pane").forEach(function (pane) {
          pane.classList.toggle("on", pane.id === button.dataset.tab);
        });
      });
    });

    document.querySelectorAll("select[data-fill]").forEach(function (select) {
      const form = select.closest("form");
      function fill() {
        if (select.dataset.fill === "request") {
          if (!select.value) return;
          form.elements.key.value = select.value;
          form.elements.options.value = JSON.stringify(catalog.requests[select.value], null, 2);
        } else {
          form.elements.fact.value = JSON.stringify(catalog.facts[select.value], null, 2);
        }
      }
      select.addEventListener("change", fill);
      fill();
    });

    document.querySelectorAll("[data-hide]").forEach(function (box) {
      box.addEventListener("change", function () {
        box.closest(".wire").classList.toggle("hide-" + box.dataset.hide, !box.checked);
      });
    });

    const wire = document.getElementById("wire");
    if (wire) wire.scrollTop = wire.scrollHeight;
  });

  window.copyText = function (text) { navigator.clipboard.writeText(text); };
})();
