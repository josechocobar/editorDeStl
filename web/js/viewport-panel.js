/**
 * ViewportPanel — renderiza el panel flotante de modelos en el viewport.
 * Consume ViewportModels, emite callbacks al DOM.
 */

export function renderViewportPanel(container, vm, callbacks) {
  const { onToggleVisible, onToggleSelect, onRemove, onTogglePanel } = callbacks;

  function render() {
    const models = vm.getAll();
    const hidden = container.classList.contains("vp-hidden");

    container.innerHTML = `
      <div class="vp-header">
        <span class="vp-title">MODELOS EN ESCENA</span>
        <span class="vp-count">${vm.count} modelo${vm.count !== 1 ? "s" : ""}</span>
        <button class="vp-btn-close" data-action="toggle-panel" title="Ocultar panel">−</button>
      </div>
      ${hidden ? "" : `
      <div class="vp-body">
        ${models.length === 0
          ? '<div class="vp-empty">Sin modelos. Subí o cargá uno desde la librería.</div>'
          : models.map((m) => {
              const dims = m.dims_mm?.length === 3
                ? `${Math.round(m.dims_mm[0])}×${Math.round(m.dims_mm[1])}×${Math.round(m.dims_mm[2])} mm`
                : "—";
              return `
              <div class="vp-row ${m.visible ? "" : "vp-muted"}" data-id="${m.id}">
                <input type="checkbox" class="vp-check" data-action="select" data-id="${m.id}"
                  ${m.selected ? "checked" : ""} title="Incluir en presupuesto" />
                <button class="vp-eye ${m.visible ? "" : "vp-off"}" data-action="visible" data-id="${m.id}"
                  title="${m.visible ? "Ocultar" : "Mostrar"}">
                  ${m.visible ? "👁" : "👁‍🗨"}
                </button>
                <span class="vp-name" title="${m.name}">${m.name}</span>
                <span class="vp-dims">${dims}</span>
                <button class="vp-btn-x" data-action="remove" data-id="${m.id}" title="Quitar del viewport">✕</button>
              </div>`;
            }).join("")
        }
      </div>
      <div class="vp-footer">
        <span>${vm.getSelected().length} cotizar</span>
      </div>
      `}
    `;
    bindEvents();
  }

  function bindEvents() {
    container.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const action = el.dataset.action;
        const id = el.dataset.id;
        if (action === "toggle-panel") {
          container.classList.toggle("vp-hidden");
          if (onTogglePanel) onTogglePanel();
          render();
        } else if (action === "visible" && id) {
          if (onToggleVisible) onToggleVisible(id);
        } else if (action === "remove" && id) {
          if (onRemove) onRemove(id);
        }
      });
    });
    container.querySelectorAll(".vp-check").forEach((el) => {
      el.addEventListener("change", (e) => {
        e.stopPropagation();
        const id = el.dataset.id;
        if (id && onToggleSelect) onToggleSelect(id);
      });
    });
  }

  render();
  return { render };
}
