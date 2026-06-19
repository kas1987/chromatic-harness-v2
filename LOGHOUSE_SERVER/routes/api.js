const express = require('express');
const router = express.Router();
const dataLoader = require('../data-loader');
const { execSync } = require('child_process');
const path = require('path');

// GET all audit reports
router.get('/reports', async (req, res) => {
  try {
    const audits = await dataLoader.getAllAudits();
    res.json({
      status: 'success',
      count: audits.length,
      reports: audits
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET latest audit report
router.get('/latest', async (req, res) => {
  try {
    const latest = await dataLoader.getLatestAudit();
    if (!latest) {
      return res.status(404).json({ error: 'No audit reports found' });
    }
    res.json({
      status: 'success',
      report: latest
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET audit by specific date
router.get('/by-date/:date', async (req, res) => {
  try {
    const audit = await dataLoader.getAuditByDate(req.params.date);
    if (!audit) {
      return res.status(404).json({ error: `No audit found for ${req.params.date}` });
    }

    const full = await dataLoader.getAuditFull(audit.filename);
    res.json({
      status: 'success',
      report: full
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET correlation reports
router.get('/correlations', async (req, res) => {
  try {
    const correlations = await dataLoader.getAllCorrelations();
    res.json({
      status: 'success',
      count: correlations.length,
      reports: correlations
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET SWOT analysis reports
router.get('/swot', async (req, res) => {
  try {
    const swots = await dataLoader.getSWOTAnalysis();
    res.json({
      status: 'success',
      count: swots.length,
      reports: swots
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// SEARCH reports
router.get('/search', async (req, res) => {
  try {
    const query = req.query.q || '';
    if (query.length < 2) {
      return res.status(400).json({ error: 'Query must be at least 2 characters' });
    }

    const results = await dataLoader.searchReports(query);
    res.json({
      status: 'success',
      query,
      count: results.length,
      results
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// EXPORT reports
router.get('/export/:type', async (req, res) => {
  try {
    const format = req.params.type || 'json';
    if (!['json', 'csv'].includes(format)) {
      return res.status(400).json({ error: 'Format must be json or csv' });
    }

    const data = await dataLoader.exportReports(format);

    if (format === 'csv') {
      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename=loghouse-reports.csv');
    } else {
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Content-Disposition', 'attachment; filename=loghouse-reports.json');
    }

    res.send(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET git correlation for specific date
router.get('/git-correlation/:date', async (req, res) => {
  try {
    const date = req.params.date;
    const repoPath = path.resolve(__dirname, '..', '..');

    // Get commits for the date
    const cmd = `cd "${repoPath}" && git log --since="${date} 00:00" --until="${date} 23:59" --pretty=format:"%h %ai %s" 2>/dev/null || echo ""`;
    const output = execSync(cmd, { encoding: 'utf-8' });
    const commits = output.trim().split('\n').filter(line => line.length > 0);

    res.json({
      status: 'success',
      date,
      commits_count: commits.length,
      commits: commits.map(line => {
        const parts = line.split(' ');
        return {
          hash: parts[0],
          timestamp: `${parts[1]} ${parts[2]}`,
          message: parts.slice(3).join(' ')
        };
      })
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
