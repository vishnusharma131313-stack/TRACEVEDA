const express = require("express");


const app = express();

app.use(express.json());

const PORT = 5000;

app.get("/", (req, res) => {
    res.send("TRACEVEDA Backend is running!");
});

app.listen(PORT, () => {
    console.log(`TRACEVEDA server running on http://localhost:${PORT}`);
});