/** Завантаження asset через fetch (ngrok на мобільному блокує <img src>). */
async function fetchAssetBlob(url) {
  const res = await fetch(url, {
    headers: { "ngrok-skip-browser-warning": "1" },
    credentials: "same-origin",
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("text/html")) {
    throw new Error("ngrok HTML");
  }
  return res.blob();
}
