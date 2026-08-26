const CONFIG_KEY = "stlfiles_quote_config";

export const defaultConfig = {
  machine_cost: 329000,
  machine_life_hrs: 8760,
  electricity_kwh: 50,
  power_watts: 150,
  maintenance_per_hr: 10,
  labor_per_hr: 3000,
  filament_per_kg: 12000,
  profit_pct: 30,
};

export function loadConfig() {
  try {
    const saved = localStorage.getItem(CONFIG_KEY);
    return saved ? { ...defaultConfig, ...JSON.parse(saved) } : { ...defaultConfig };
  } catch {
    return { ...defaultConfig };
  }
}

export function saveConfig(cfg) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
}

export function formatCurrency(v) {
  return "$ " + v.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function quoteCalc(config, input) {
  const machineHr = config.machine_life_hrs > 0 ? config.machine_cost / config.machine_life_hrs : 0;
  const energyHr = (config.power_watts / 1000) * config.electricity_kwh;
  const opsHr = config.maintenance_per_hr + config.labor_per_hr;
  const totalHrs = input.hours + input.minutes / 60;

  const costTime = totalHrs * (machineHr + energyHr + opsHr);
  const costMaterial = (input.grams / 1000) * config.filament_per_kg;
  const subtotal = costTime + costMaterial;
  const extraDiff = subtotal * (input.difficulty - 1);
  const subWithDiff = subtotal + extraDiff;
  const profit = subWithDiff * (config.profit_pct / 100);
  const finalPrice = subWithDiff + profit;

  return {
    machine_per_hr: machineHr,
    energy_per_hr: energyHr,
    cost_time: costTime,
    cost_material: costMaterial,
    subtotal,
    extra_difficulty: extraDiff,
    subtotal_with_difficulty: subWithDiff,
    profit,
    final_price: finalPrice,
    total_hours: totalHrs,
    grams: input.grams,
    difficulty: input.difficulty,
  };
}

async function postBlob(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Error generando archivo");
  }
  return res.blob();
}

export async function downloadPDF(config, input) {
  const blob = await postBlob("/api/quote/pdf", { config, input });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "presupuesto.pdf";
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadPNG(config, input) {
  const blob = await postBlob("/api/quote/png", { config, input });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "presupuesto.png";
  a.click();
  URL.revokeObjectURL(url);
}
