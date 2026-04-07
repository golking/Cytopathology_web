const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const publicDir = path.join(__dirname, "public");

app.use(express.static(publicDir));

app.listen(PORT, () => {
  console.log(`Web UI started: http://127.0.0.1:${PORT}`);
});