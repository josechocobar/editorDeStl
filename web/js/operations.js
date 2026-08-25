import { cutModel, generateSupports } from "./api.js";

function collectCutParams() {
  return {
    mode: document.querySelector('input[name="mode"]:checked').value,
    axis: document.querySelector(".seg button.active")?.dataset.axis || "z",
    position: Number(document.getElementById("pos-slider").value) / 100,
    parts: Number(document.getElementById("parts-input").value),
    connector: {
      type: document.getElementById("conn-type").value,
      diameter: Number(document.getElementById("conn-dia").value),
      depth: Number(document.getElementById("conn-depth").value),
      clearance: Number(document.getElementById("conn-clear").value),
      count: Number(document.getElementById("conn-count").value),
    },
    supports: document.getElementById("sup-enabled").checked
      ? collectSupportsParams()
      : null,
  };
}

function collectSupportsParams() {
  return {
    angle: Number(document.getElementById("sup-angle").value),
    tip_diameter: Number(document.getElementById("sup-tip").value),
    contact_diameter: Number(document.getElementById("sup-contact").value),
    spacing: Number(document.getElementById("sup-spacing").value),
    z_gap: Number(document.getElementById("sup-gap").value),
    base_thickness: Number(document.getElementById("sup-base").value),
  };
}

export const OPERATIONS = {
  cut: {
    label: "Cortar en piezas",
    collectParams: collectCutParams,
    async execute(state, params) {
      return cutModel({ model_id: state.modelId, ...params });
    },
  },
  supports: {
    label: "Solo soportes",
    collectParams: () => ({ enabled: true, ...collectSupportsParams() }),
    async execute(state, params) {
      return generateSupports(state.modelId, params);
    },
  },
};
