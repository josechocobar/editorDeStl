async function parse(res, fallback) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || fallback);
  return data;
}

export async function uploadModel(file) {
  const fd = new FormData();
  fd.append("file", file);
  return parse(await fetch("/api/models", { method: "POST", body: fd }), "Error subiendo");
}

export async function cutModel(body) {
  return parse(
    await fetch("/api/cut", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    "Error procesando"
  );
}

export async function generateSupports(modelId, spec) {
  return parse(
    await fetch(`/api/models/${modelId}/supports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(spec),
    }),
    "Error procesando"
  );
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
