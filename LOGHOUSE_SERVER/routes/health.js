const express = require('express');
const router = express.Router();
const fs = require('fs-extra');
const path = require('path');

router.get('/', async (req, res) => {
  const LOGHOUSE_PATH = path.resolve(__dirname, '..', '.artifacts', 'LOGHOUSE');
  const auditPath = path.join(LOGHOUSE_PATH, 'audits');
  const correlationPath = path.join(LOGHOUSE_PATH, 'correlations');
  const swotPath = path.join(LOGHOUSE_PATH, 'swot');

  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    server: {
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      pid: process.pid
    },
    loghouse: {
      path: LOGHOUSE_PATH,
      directories: {
        audits: await getFileCount(auditPath),
        correlations: await getFileCount(correlationPath),
        swot: await getFileCount(swotPath)
      }
    }
  };

  res.json(health);
});

async function getFileCount(dirPath) {
  try {
    const files = await fs.readdir(dirPath);
    const mdFiles = files.filter(f => f.endsWith('.md')).length;
    return { total: files.length, markdown: mdFiles };
  } catch {
    return { total: 0, markdown: 0 };
  }
}

module.exports = router;
