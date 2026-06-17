(() => {
  const dataEl = document.getElementById("hotspots-data");
  const mapEl = document.getElementById("calibration-map");
  const markersEl = document.getElementById("calibration-markers");
  const tableBody = document.getElementById("hotspots-table-body");
  const saveMessage = document.getElementById("save-message");

  if (!dataEl || !mapEl || !markersEl || !tableBody) {
    return;
  }

  let hotspots = JSON.parse(dataEl.textContent || "[]");
  let dragState = null;

  function clampPercent(value) {
    if (Number.isNaN(value)) return 0;
    return Math.max(0, Math.min(100, value));
  }

  function applyMarkerStyle(marker, hotspot) {
    marker.style.top = `${hotspot.top}%`;
    marker.style.left = `${hotspot.left}%`;
    marker.style.width = `${hotspot.width}%`;
    marker.style.height = `${hotspot.height}%`;
    marker.textContent = hotspot.label;
    marker.title = `${hotspot.label} → Área ${hotspot.area_code}`;
  }

  function syncTableRow(index) {
    const hotspot = hotspots[index];
    const topInput = tableBody.querySelector(`.hotspot-top[data-index="${index}"]`);
    const leftInput = tableBody.querySelector(`.hotspot-left[data-index="${index}"]`);
    if (topInput) topInput.value = hotspot.top;
    if (leftInput) leftInput.value = hotspot.left;
  }

  function render() {
    markersEl.innerHTML = "";
    tableBody.innerHTML = "";

    hotspots.forEach((hotspot, index) => {
      const marker = document.createElement("button");
      marker.type = "button";
      marker.className = "calibration-marker";
      marker.dataset.index = String(index);
      applyMarkerStyle(marker, hotspot);
      marker.addEventListener("mousedown", (event) => startDrag(event, index));
      marker.addEventListener("touchstart", (event) => startDrag(event, index), { passive: false });
      markersEl.appendChild(marker);

      const row = document.createElement("tr");
      row.innerHTML = `
        <td><input class="form-control form-control-sm hotspot-label" data-index="${index}" value="${hotspot.label}"></td>
        <td><input class="form-control form-control-sm hotspot-area" data-index="${index}" value="${hotspot.area_code}" maxlength="10"></td>
        <td><input type="number" step="0.1" min="0" max="100" class="form-control form-control-sm hotspot-top" data-index="${index}" value="${hotspot.top}"></td>
        <td><input type="number" step="0.1" min="0" max="100" class="form-control form-control-sm hotspot-left" data-index="${index}" value="${hotspot.left}"></td>
        <td><button type="button" class="btn btn-outline-danger btn-sm hotspot-remove" data-index="${index}">×</button></td>
      `;
      tableBody.appendChild(row);
    });

    bindTableInputs();
  }

  function bindTableInputs() {
    tableBody.querySelectorAll(".hotspot-label").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.dataset.index);
        hotspots[index].label = input.value.trim().toUpperCase();
        render();
      });
    });

    tableBody.querySelectorAll(".hotspot-area").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.dataset.index);
        hotspots[index].area_code = input.value.trim().toUpperCase();
        render();
      });
    });

    tableBody.querySelectorAll(".hotspot-top").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.dataset.index);
        hotspots[index].top = clampPercent(Number(input.value));
        render();
      });
    });

    tableBody.querySelectorAll(".hotspot-left").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.dataset.index);
        hotspots[index].left = clampPercent(Number(input.value));
        render();
      });
    });

    tableBody.querySelectorAll(".hotspot-remove").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.index);
        hotspots.splice(index, 1);
        render();
      });
    });
  }

  function startDrag(event, index) {
    event.preventDefault();
    dragState = { index };
    document.addEventListener("mousemove", onDragMove);
    document.addEventListener("mouseup", stopDrag);
    document.addEventListener("touchmove", onDragMove, { passive: false });
    document.addEventListener("touchend", stopDrag);
  }

  function onDragMove(event) {
    if (!dragState) return;
    event.preventDefault();

    const rect = mapEl.getBoundingClientRect();
    const point = event.touches ? event.touches[0] : event;
    const left = clampPercent(((point.clientX - rect.left) / rect.width) * 100);
    const top = clampPercent(((point.clientY - rect.top) / rect.height) * 100);

    const index = dragState.index;
    hotspots[index].left = Number(left.toFixed(1));
    hotspots[index].top = Number(top.toFixed(1));

    const marker = markersEl.querySelector(`.calibration-marker[data-index="${index}"]`);
    if (marker) {
      applyMarkerStyle(marker, hotspots[index]);
    }
    syncTableRow(index);
  }

  function stopDrag() {
    dragState = null;
    document.removeEventListener("mousemove", onDragMove);
    document.removeEventListener("mouseup", stopDrag);
    document.removeEventListener("touchmove", onDragMove);
    document.removeEventListener("touchend", stopDrag);
  }

  document.getElementById("btn-add-hotspot")?.addEventListener("click", () => {
    const nextIndex = hotspots.length + 1;
    hotspots.push({
      label: `X${nextIndex}`,
      area_code: "A",
      top: 50,
      left: 50,
      width: 2.5,
      height: 4.9,
      description: null,
      sort_order: nextIndex,
    });
    render();
  });

  document.getElementById("btn-restore-hotspots")?.addEventListener("click", async () => {
    if (!window.confirm("¿Restaurar las posiciones por defecto de la cancha?")) {
      return;
    }
    saveMessage.textContent = "Restaurando…";
    saveMessage.className = "small mt-2 text-muted";
    try {
      const response = await fetch("/admin/mapa-calibracion/restaurar", { method: "POST" });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "No se pudo restaurar.");
      }
      hotspots = await response.json();
      render();
      saveMessage.textContent = "Posiciones por defecto restauradas.";
      saveMessage.className = "small mt-2 text-success";
    } catch (error) {
      saveMessage.textContent = error.message || "Error al restaurar.";
      saveMessage.className = "small mt-2 text-danger";
    }
  });

  document.getElementById("btn-save-hotspots")?.addEventListener("click", async () => {
    saveMessage.textContent = "Guardando…";
    saveMessage.className = "small mt-2 text-muted";

    const payload = {
      hotspots: hotspots.map((item, index) => ({
        label: item.label.trim().toUpperCase(),
        area_code: item.area_code.trim().toUpperCase(),
        top: Number(item.top),
        left: Number(item.left),
        width: Number(item.width || 2.5),
        height: Number(item.height || 4.9),
        description: item.description || null,
        sort_order: index,
      })),
    };

    try {
      const response = await fetch("/admin/mapa-calibracion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "No se pudo guardar.");
      }
      hotspots = await response.json();
      render();
      saveMessage.textContent = "Calibración guardada correctamente.";
      saveMessage.className = "small mt-2 text-success";
    } catch (error) {
      saveMessage.textContent = error.message || "Error al guardar.";
      saveMessage.className = "small mt-2 text-danger";
    }
  });

  render();
})();
