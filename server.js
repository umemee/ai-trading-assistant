// server.js ― Express 프록시 서버
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import morgan from 'morgan';
import dotenv from 'dotenv';

dotenv.config();
const app = express();

app.use(morgan('dev'));
app.use(express.json());
app.use(express.static('public'));

// Alpaca 프록시
app.use('/api/alpaca', createProxyMiddleware({
  target: 'https://data.alpaca.markets',
  changeOrigin: true,
  pathRewrite: { '^/api/alpaca': '' },
  headers: {
    'APCA-API-KEY-ID': process.env.ALPACA_KEY,
    'APCA-API-SECRET-KEY': process.env.ALPACA_SEC
  }
}));

// Google Sheets 프록시
app.use('/api/sheets', createProxyMiddleware({
  target: 'https://sheets.googleapis.com',
  changeOrigin: true,
  pathRewrite: { '^/api/sheets': '/v4/spreadsheets' },
  onProxyReq: (proxyReq) => {
    proxyReq.setHeader('X-Goog-Api-Key', process.env.SHEET_API);
  }
}));

// Gemini 프록시
app.post('/api/gemini', async (req, res) => {
  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=${process.env.GEMINI_KEY}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ text: req.body.prompt }] }]
        })
      }
    );
    res.json(await response.json());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`✅ 프록시 서버 실행: http://localhost:${PORT}`);
});
