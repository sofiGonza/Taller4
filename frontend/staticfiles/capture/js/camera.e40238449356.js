/**
 * Captura de cámara vía getUserMedia y consumo de los endpoints de
 * reconocimiento facial expuestos por las vistas de Django, que a su vez
 * reenvían la imagen al backend FastAPI.
 */
(function () {
  "use strict";

  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const scanRadar = document.getElementById("scan-radar");
  const btnRegister = document.getElementById("btn-register");
  const btnRecognize = document.getElementById("btn-recognize");
  const resultBox = document.getElementById("result");

  const accessOverlay = document.getElementById("access-overlay");
  const accessUser = document.getElementById("access-user");
  const accessMeta = document.getElementById("access-meta");
  const accessContinue = document.getElementById("access-continue");
  const accessCheckPath = document.getElementById("access-check-path");
  const accessCheckCircle = document.getElementById("access-check-circle");

  // Se arranca la cámara ANTES de cablear el resto de la página: así, si
  // algún botón o elemento futuro no existe y lanza un error al configurar
  // sus eventos, eso nunca vuelve a bloquear el encendido de la cámara.
  startCamera();

  const ICONS = {
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01M10.3 3.9 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="m9.5 9.5 5 5m0-5-5 5" stroke-linecap="round"/></svg>',
  };

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function showBadge(type, message, meta) {
    resultBox.innerHTML = `
      <div class="status-badge ${type}">
        ${ICONS[type] || ICONS.info}
        <span>${message}${meta ? `<span class="status-meta">${meta}</span>` : ""}</span>
      </div>
    `;
  }

  function setScanning(active) {
    if (scanRadar) scanRadar.classList.toggle("scanning", active);
  }

  // --- Overlay "Acceso concedido" ------------------------------------------

  function primeCheckAnimation() {
    // Prepara el trazo del check y del círculo para poder animarlos con
    // stroke-dashoffset (se calcula la longitud real del path en runtime).
    [accessCheckCircle, accessCheckPath].forEach((el) => {
      if (!el || typeof el.getTotalLength !== "function") return;
      const length = el.getTotalLength();
      el.style.transition = "none";
      el.style.strokeDasharray = `${length}`;
      el.style.strokeDashoffset = `${length}`;
      // Forzar reflow antes de animar.
      // eslint-disable-next-line no-unused-expressions
      el.getBoundingClientRect();
    });
  }

  function playCheckAnimation() {
    if (accessCheckCircle) {
      accessCheckCircle.style.transition = "stroke-dashoffset 0.6s ease";
      accessCheckCircle.style.strokeDashoffset = "0";
    }
    if (accessCheckPath) {
      accessCheckPath.style.transition = "stroke-dashoffset 0.45s ease 0.5s";
      accessCheckPath.style.strokeDashoffset = "0";
    }
  }

  let hideTimer = null;

  function showAccessGranted(username, confidence) {
    if (!accessOverlay) return;
    accessUser.textContent = username
      ? `Bienvenido/a a las instalaciones, ${username}`
      : "Bienvenido/a a las instalaciones";

    const timestamp = new Date().toLocaleTimeString("es-CO", { hour12: false });
    accessMeta.textContent =
      typeof confidence === "number"
        ? `CONFIANZA ${confidence.toFixed(1)} · ${timestamp}`
        : timestamp;

    primeCheckAnimation();
    accessOverlay.classList.add("visible");
    requestAnimationFrame(() => requestAnimationFrame(playCheckAnimation));

    clearTimeout(hideTimer);
    hideTimer = setTimeout(hideAccessGranted, 4500);
  }

  function hideAccessGranted() {
    if (!accessOverlay) return;
    accessOverlay.classList.remove("visible");
    clearTimeout(hideTimer);
  }

  if (accessContinue) accessContinue.addEventListener("click", hideAccessGranted);
  if (accessOverlay) {
    accessOverlay.addEventListener("click", (evt) => {
      if (evt.target === accessOverlay) hideAccessGranted();
    });
  }

  // --- Cámara ---------------------------------------------------------------

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 360, height: 270 },
        audio: false,
      });
      video.srcObject = stream;
    } catch (err) {
      showBadge("error", "No se pudo acceder a la cámara.", err.message);
    }
  }

  function captureFrameAsBase64() {
    canvas.width = video.videoWidth || 360;
    canvas.height = video.videoHeight || 270;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    // toDataURL incluye el encabezado "data:image/jpeg;base64,..."
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  async function postImage(url, imageBase64) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ image_base64: imageBase64 }),
    });
    const data = await response.json();
    return { status: response.status, data };
  }

  function lockRegisterButton() {
    if (!btnRegister) return;
    const wrapper = document.createElement("span");
    wrapper.className = "face-registered-badge";
    wrapper.style.flex = "1";
    wrapper.style.justifyContent = "center";
    wrapper.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 13 4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>Rostro ya registrado';
    btnRegister.replaceWith(wrapper);
  }

  if (btnRegister) {
    btnRegister.addEventListener("click", async () => {
      setScanning(true);
      showBadge("info", "Registrando rostro…");
      const image = captureFrameAsBase64();
      try {
        const { status, data } = await postImage("/capture/api/register-face/", image);
        if (status === 200 && data.ok) {
          const badgeType = data.enrollment_complete ? "success" : "info";
          const meta = `MUESTRA ${data.total_samples}/${data.required_samples}`;
          showBadge(badgeType, data.detail, meta);
          if (data.enrollment_complete) {
            lockRegisterButton();
          }
        } else {
          showBadge("error", data.error || "No se pudo registrar el rostro.");
        }
      } catch (err) {
        showBadge("error", "Error de red.", err.message);
      } finally {
        setScanning(false);
      }
    });
  }

  btnRecognize.addEventListener("click", async () => {
    setScanning(true);
    showBadge("info", "Analizando rostro…");
    const image = captureFrameAsBase64();
    try {
      const { status, data } = await postImage("/capture/api/recognize-face/", image);
      if (status === 200 && data.ok) {
        const confidence = typeof data.confidence === "number" ? data.confidence : null;
        const meta = `CONFIANZA: ${confidence !== null ? confidence.toFixed(1) : "N/D"} · UMBRAL: 60.0 (más bajo es mejor)`;
        showBadge(data.matched ? "success" : "warning", data.message, meta);
        if (data.matched) {
          showAccessGranted(data.username, confidence);
        }
      } else {
        showBadge("error", data.error || "No se pudo reconocer el rostro.");
      }
    } catch (err) {
      showBadge("error", "Error de red.", err.message);
    } finally {
      setScanning(false);
    }
  });
})();
