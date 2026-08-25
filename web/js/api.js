export async function uploadModel(file, replace = false) {
  const fd = new FormData();
  fd.append("file", file);
  const url = replace ? "/api/models?replace=true" : "/api/models";
  const res = await fetch(url, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (res.ok) return data;
  const err = new Error(data.detail || "Error subiendo");
  err.status = res.status;
  err.existing = data.existing || null;
  throw err;
}

export async function cutModel(body) {
  const res = await fetch("/api/cut", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Error procesando");
  return data;
}

export async function generateSupports(modelId, spec) {
  const res = await fetch(`/api/models/${modelId}/supports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Error procesando");
  return data;
}

export async function suggestConnector(modelId, params) {
  try {
    const qs = new URLSearchParams(params);
    const res = await fetch(`/api/models/${modelId}/suggest-connector?${qs}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function listModels() {
  const res = await fetch("/api/models");
  if (!res.ok) return [];
  return res.json();
}

export async function deleteModel(modelId) {
  const res = await fetch(`/api/models/${modelId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("No se pudo borrar");
  return true;
}
