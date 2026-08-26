/**
 * ViewportModels — estado puro de modelos cargados en el viewport.
 * Sin DOM, sin Three.js. Solo lógica de estado testable.
 *
 * Cada modelo: { id, name, dims_mm, volume_cm3, mesh, visible, selected }
 */

export class ViewportModels {
  constructor() {
    this._models = [];
  }

  add(model) {
    if (this.has(model.id)) return false;
    this._models.push({
      id: model.id,
      name: model.name || model.id,
      dims_mm: model.dims_mm || [],
      volume_cm3: model.volume_cm3 || 0,
      mesh: model.mesh || null,
      visible: true,
      selected: false,
    });
    return true;
  }

  remove(id) {
    const idx = this._models.findIndex((m) => m.id === id);
    if (idx === -1) return null;
    const [removed] = this._models.splice(idx, 1);
    return removed;
  }

  has(id) {
    return this._models.some((m) => m.id === id);
  }

  get(id) {
    return this._models.find((m) => m.id === id) || null;
  }

  getAll() {
    return [...this._models];
  }

  getVisible() {
    return this._models.filter((m) => m.visible);
  }

  getSelected() {
    return this._models.filter((m) => m.selected);
  }

  toggleVisible(id) {
    const m = this.get(id);
    if (!m) return null;
    m.visible = !m.visible;
    return m.visible;
  }

  setVisible(id, visible) {
    const m = this.get(id);
    if (!m) return null;
    m.visible = !!visible;
    return m.visible;
  }

  toggleSelected(id) {
    const m = this.get(id);
    if (!m) return null;
    m.selected = !m.selected;
    return m.selected;
  }

  setSelected(id, selected) {
    const m = this.get(id);
    if (!m) return null;
    m.selected = !!selected;
    return m.selected;
  }

  clear() {
    const removed = [...this._models];
    this._models = [];
    return removed;
  }

  get count() {
    return this._models.length;
  }

  get selectedCount() {
    return this._models.filter((m) => m.selected).length;
  }

  get visibleCount() {
    return this._models.filter((m) => m.visible).length;
  }

  toQuoteModels(density) {
    return this.getSelected().map((m) => ({
      name: m.name,
      dims_mm: m.dims_mm,
      volume_cm3: m.volume_cm3,
      weight_g: Math.round(m.volume_cm3 * (density || 1.24) * 10) / 10,
    }));
  }
}
