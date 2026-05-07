const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

app.use(express.static(path.join(__dirname, "public")));

// Proxy the backend so the frontend doesn't hardcode the backend address
app.get("/api/consensus", async (req, res) => {
  try {
    const { default: fetch } = await import("node-fetch").catch(() => ({ default: globalThis.fetch }));
    const url = `${BACKEND_URL}/api/consensus`;
    const upstream = await fetch(url);
    const data = await upstream.json();
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "Backend unavailable", detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Frontend running at http://localhost:${PORT}`);
  console.log(`Proxying API calls to ${BACKEND_URL}`);
});
