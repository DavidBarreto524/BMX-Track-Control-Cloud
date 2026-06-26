(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  const MIC_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">' +
    '<path d="M3.5 6.5A.5.5 0 0 1 4 7v1a4 4 0 0 0 8 0V7a.5.5 0 0 1 1 0v1a5 5 0 0 1-4.5 4.975V15h3a.5.5 0 0 1 0 1h-7a.5.5 0 0 1 0-1h3v-2.025A5 5 0 0 1 3 8V7a.5.5 0 0 1 .5-.5"/>' +
    '<path d="M10 8a2 2 0 1 1-4 0V3a2 2 0 1 1 4 0zM8 0a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V3a3 3 0 0 0-3-3"/>' +
    "</svg>";

  function isSupported() {
    return Boolean(SpeechRecognition);
  }

  function appendTranscript(field, text) {
    const chunk = text.trim();
    if (!chunk) return;
    const current = field.value.trim();
    field.value = current ? `${current} ${chunk}` : chunk;
    field.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function ensureGroup(field) {
    const existing = field.closest(".speech-dictation-group");
    if (existing) return existing;

    const group = document.createElement("div");
    group.className = "input-group speech-dictation-group";
    field.parentNode.insertBefore(group, field);
    group.appendChild(field);
    return group;
  }

  function ensureStatus(field) {
    const group = field.closest(".speech-dictation-group");
    if (!group) return null;

    let status = group.parentElement?.querySelector(".speech-dictation-status");
    if (!status) {
      status = document.createElement("div");
      status.className = "form-text speech-dictation-status";
      status.setAttribute("aria-live", "polite");
      group.insertAdjacentElement("afterend", status);
    }
    return status;
  }

  function attachDictation(field, options = {}) {
    if (field.dataset.speechDictationReady === "true") return;
    field.dataset.speechDictationReady = "true";

    const lang = options.lang || "es-CO";
    const group = ensureGroup(field);
    const status = ensureStatus(field);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary speech-dictation-btn";
    button.title = "Dictar nota";
    button.setAttribute("aria-label", "Dictar nota por voz");
    button.innerHTML = MIC_ICON;
    group.appendChild(button);

    if (!isSupported()) {
      button.disabled = true;
      button.title = "Dictado no disponible en este navegador";
      if (status) {
        status.textContent =
          "El dictado por voz funciona en Chrome, Edge o Safari. Escribe la nota manualmente.";
      }
      return;
    }

    let recognition = null;
    let listening = false;
    let interimText = "";

    function setStatus(message, isError = false) {
      if (!status) return;
      status.textContent = message || "";
      status.classList.toggle("text-danger", isError);
    }

    function stopListening() {
      listening = false;
      interimText = "";
      button.classList.remove("listening");
      button.setAttribute("aria-pressed", "false");
      button.title = "Dictar nota";
      setStatus("");
      if (recognition) {
        try {
          recognition.stop();
        } catch (_err) {
          /* ignore */
        }
      }
    }

    function startListening() {
      recognition = new SpeechRecognition();
      recognition.lang = lang;
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onstart = function () {
        listening = true;
        button.classList.add("listening");
        button.setAttribute("aria-pressed", "true");
        button.title = "Detener dictado";
        setStatus("Escuchando… habla ahora.");
      };

      recognition.onresult = function (event) {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const transcript = result[0].transcript;
          if (result.isFinal) {
            appendTranscript(field, transcript);
          } else {
            interim += transcript;
          }
        }
        interimText = interim.trim();
        if (interimText) {
          setStatus(`Escuchando: ${interimText}`);
        } else if (listening) {
          setStatus("Escuchando… habla ahora.");
        }
      };

      recognition.onerror = function (event) {
        const code = event.error;
        if (code === "aborted" || code === "no-speech") {
          stopListening();
          return;
        }
        if (code === "not-allowed") {
          setStatus("Permiso de micrófono denegado. Actívalo en el navegador.", true);
        } else if (code === "service-not-allowed") {
          setStatus("El dictado requiere HTTPS y un navegador compatible.", true);
        } else {
          setStatus("No se pudo usar el dictado. Intenta de nuevo.", true);
        }
        stopListening();
      };

      recognition.onend = function () {
        if (listening) {
          try {
            recognition.start();
          } catch (_err) {
            stopListening();
          }
        }
      };

      try {
        recognition.start();
      } catch (_err) {
        setStatus("No se pudo iniciar el micrófono.", true);
        stopListening();
      }
    }

    button.addEventListener("click", function () {
      if (listening) {
        stopListening();
        return;
      }
      setStatus("");
      startListening();
    });

    field.addEventListener("blur", function () {
      if (document.activeElement === button) return;
      stopListening();
    });
  }

  function initSpeechDictation(selector, options = {}) {
    document.querySelectorAll(selector).forEach(function (field) {
      attachDictation(field, options);
    });
  }

  window.SpeechDictation = {
    init: initSpeechDictation,
    isSupported: isSupported,
  };

  document.addEventListener("DOMContentLoaded", function () {
    initSpeechDictation(".speech-dictation-field");
  });
})();
