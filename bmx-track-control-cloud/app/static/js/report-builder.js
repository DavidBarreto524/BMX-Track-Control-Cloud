(() => {
  const checkboxes = Array.from(document.querySelectorAll(".report-photo-check"));
  const generateBtn = document.getElementById("btn-generate-pdf");
  const selectAllBtn = document.getElementById("btn-select-all");
  const clearAllBtn = document.getElementById("btn-clear-all");
  const selectedCountEl = document.getElementById("selected-count");
  const messageEl = document.getElementById("report-message");
  const titleInput = document.getElementById("report-title");
  const saveNotesInput = document.getElementById("save-notes");

  if (!checkboxes.length || !generateBtn) {
    return;
  }

  function getSelectedItems() {
    return checkboxes
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => {
        const photoId = Number(checkbox.value);
        const notesField = document.getElementById(`photo-notes-${photoId}`);
        return {
          photo_id: photoId,
          notes: notesField ? notesField.value.trim() : "",
        };
      });
  }

  function updateSelectionState() {
    const count = getSelectedItems().length;
    selectedCountEl.textContent = String(count);
    generateBtn.disabled = count === 0;
  }

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectionState);
  });

  selectAllBtn?.addEventListener("click", () => {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = true;
    });
    updateSelectionState();
  });

  clearAllBtn?.addEventListener("click", () => {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = false;
    });
    updateSelectionState();
  });

  function setMessage(text, isError = false) {
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.className = `small mt-2 ${isError ? "text-danger" : "text-success"}`;
  }

  generateBtn.addEventListener("click", async () => {
    const photos = getSelectedItems();
    if (!photos.length) {
      setMessage("Selecciona al menos una foto.", true);
      return;
    }

    generateBtn.disabled = true;
    setMessage("Generando PDF, espera un momento...");

    try {
      const response = await fetch("/reportes/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: titleInput?.value?.trim() || "Reporte de fotos BMX",
          photos,
          save_notes: Boolean(saveNotesInput?.checked),
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "No se pudo generar el reporte.");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      link.href = url;
      link.download = `reporte-bmx-${stamp}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("PDF generado correctamente.");
    } catch (error) {
      setMessage(error.message || "Error al generar el PDF.", true);
    } finally {
      updateSelectionState();
    }
  });

  updateSelectionState();
})();
