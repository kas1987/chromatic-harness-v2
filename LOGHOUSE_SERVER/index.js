const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const fs = require('fs-extra');

const dataLoader = require('./data-loader');
const apiRoutes = require('./routes/api');
const healthRoutes = require('./routes/health');

const app = express();
const PORT = process.env.PORT || 3333;
const LOGHOUSE_PATH = path.resolve(__dirname, '..', '.artifacts', 'LOGHOUSE');

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Serve static files from client build
const clientBuildPath = path.join(__dirname, 'client', 'build');
if (fs.existsSync(clientBuildPath)) {
  app.use(express.static(clientBuildPath));
}

// API Routes
app.use('/api/health', healthRoutes);
app.use('/api/audits', apiRoutes);

// Root API endpoint - server info
app.get('/api', (req, res) => {
  res.json({
    name: 'LOGHOUSE Server',
    version: '1.0.0',
    port: PORT,
    loghouse_path: LOGHOUSE_PATH,
    endpoints: [
      '/api/health',
      '/api/audits/reports',
      '/api/audits/latest',
      '/api/audits/by-date/:date',
      '/api/audits/correlations',
      '/api/audits/swot',
      '/api/audits/search',
      '/api/audits/export/:type',
      '/api/audits/git-correlation/:date'
    ]
  });
});

// Serve React app for all other routes
app.get('*', (req, res) => {
  const indexPath = path.join(clientBuildPath, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(200).json({
      message: 'LOGHOUSE Server is running',
      status: 'ok',
      note: 'React client build not found. Run: npm run build-client',
      api_available: true,
      web_ui_available: false
    });
  }
});

// Error handling
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.message);
  res.status(500).json({
    error: err.message,
    status: 'error'
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════╗
║          🏛️  LOGHOUSE SERVER STARTED              ║
╠════════════════════════════════════════════════════╣
║  Server:    http://localhost:${PORT}                 ║
║  API:       http://localhost:${PORT}/api             ║
║  Data:      ${LOGHOUSE_PATH}                ║
║  Status:    Ready                            ║
╚════════════════════════════════════════════════════╝
  `);
  console.log('Available endpoints:');
  console.log('  • GET  /api/audits/reports          - List all audit reports');
  console.log('  • GET  /api/audits/latest           - Get latest audit');
  console.log('  • GET  /api/audits/by-date/:date    - Get audit by date');
  console.log('  • GET  /api/audits/correlations     - Get correlation reports');
  console.log('  • GET  /api/audits/swot             - Get SWOT analysis');
  console.log('  • GET  /api/audits/search?q=term    - Search reports');
  console.log('  • GET  /api/audits/export/:type     - Export (csv/json)');
  console.log('  • GET  /api/audits/git-correlation/:date - Git history for date');
  console.log('  • GET  /api/health                  - Server health check');
  console.log('');
});
