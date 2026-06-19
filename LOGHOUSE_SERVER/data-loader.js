const fs = require('fs-extra');
const path = require('path');
const glob = require('glob');
const marked = require('marked');
const moment = require('moment');

const LOGHOUSE_PATH = path.resolve(__dirname, '..', '.artifacts', 'LOGHOUSE');

class DataLoader {
  constructor() {
    this.auditPath = path.join(LOGHOUSE_PATH, 'audits');
    this.correlationPath = path.join(LOGHOUSE_PATH, 'correlations');
    this.swotPath = path.join(LOGHOUSE_PATH, 'swot');
    this.cache = {};
    this.cacheExpiry = 60000; // 60 seconds
  }

  async getAllAudits() {
    const cacheKey = 'all-audits';
    if (this.cache[cacheKey] && Date.now() - this.cache[cacheKey].time < this.cacheExpiry) {
      return this.cache[cacheKey].data;
    }

    const files = await this.globAsync(path.join(this.auditPath, '*.md'));
    const audits = [];

    for (const file of files) {
      const content = await fs.readFile(file, 'utf-8');
      const filename = path.basename(file);
      const date = this.extractDateFromFilename(filename);

      audits.push({
        filename,
        date,
        path: file,
        title: this.extractTitle(content),
        preview: this.getPreview(content),
        metrics: this.extractMetrics(content),
        type: 'audit'
      });
    }

    audits.sort((a, b) => new Date(b.date) - new Date(a.date));

    this.cache[cacheKey] = { data: audits, time: Date.now() };
    return audits;
  }

  async getAuditByDate(date) {
    const audits = await this.getAllAudits();
    return audits.find(a => a.date === date) || null;
  }

  async getLatestAudit() {
    const audits = await this.getAllAudits();
    if (audits.length === 0) return null;

    const latest = audits[0];
    return await this.getAuditFull(latest.filename);
  }

  async getAuditFull(filename) {
    const filepath = path.join(this.auditPath, filename);
    if (!await fs.pathExists(filepath)) return null;

    const content = await fs.readFile(filepath, 'utf-8');
    return {
      filename,
      date: this.extractDateFromFilename(filename),
      title: this.extractTitle(content),
      html: marked.parse(content),
      raw: content,
      metrics: this.extractMetrics(content)
    };
  }

  async getAllCorrelations() {
    const files = await this.globAsync(path.join(this.correlationPath, '*.md'));
    const correlations = [];

    for (const file of files) {
      const content = await fs.readFile(file, 'utf-8');
      const filename = path.basename(file);

      correlations.push({
        filename,
        date: this.extractDateFromFilename(filename),
        path: file,
        title: this.extractTitle(content),
        preview: this.getPreview(content),
        type: 'correlation'
      });
    }

    correlations.sort((a, b) => new Date(b.date) - new Date(a.date));
    return correlations;
  }

  async getSWOTAnalysis() {
    const files = await this.globAsync(path.join(this.swotPath, '*.md'));
    const swots = [];

    for (const file of files) {
      const content = await fs.readFile(file, 'utf-8');
      const filename = path.basename(file);

      swots.push({
        filename,
        date: this.extractDateFromFilename(filename),
        path: file,
        title: this.extractTitle(content),
        preview: this.getPreview(content),
        type: 'swot'
      });
    }

    swots.sort((a, b) => new Date(b.date) - new Date(a.date));
    return swots;
  }

  async searchReports(query) {
    const audits = await this.getAllAudits();
    const correlations = await this.getAllCorrelations();
    const swots = await this.getSWOTAnalysis();

    const allReports = [...audits, ...correlations, ...swots];
    const q = query.toLowerCase();

    return allReports.filter(report =>
      report.filename.toLowerCase().includes(q) ||
      report.title.toLowerCase().includes(q) ||
      report.preview.toLowerCase().includes(q)
    );
  }

  async exportReports(format = 'json') {
    const audits = await this.getAllAudits();
    const correlations = await this.getAllCorrelations();
    const swots = await this.getSWOATAnalysis();

    const data = {
      generated: new Date().toISOString(),
      audits: audits.map(a => ({ ...a, type: 'audit' })),
      correlations: correlations.map(c => ({ ...c, type: 'correlation' })),
      swots: swots.map(s => ({ ...s, type: 'swot' }))
    };

    if (format === 'json') {
      return JSON.stringify(data, null, 2);
    }

    if (format === 'csv') {
      const rows = [];
      rows.push('Type,Date,Title,Filename');

      [...audits, ...correlations, ...swots].forEach(item => {
        rows.push(`${item.type},${item.date},"${item.title}",${item.filename}`);
      });

      return rows.join('\n');
    }

    throw new Error(`Unsupported format: ${format}`);
  }

  extractDateFromFilename(filename) {
    const match = filename.match(/(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : null;
  }

  extractTitle(content) {
    const match = content.match(/^# (.+)$/m);
    return match ? match[1] : 'Untitled';
  }

  getPreview(content, words = 30) {
    const text = content.replace(/[#*`]/g, '').replace(/\n\n/g, ' ');
    const preview = text.split(' ').slice(0, words).join(' ');
    return preview.length < text.length ? preview + '...' : preview;
  }

  extractMetrics(content) {
    const metrics = {};

    const toolsMatch = content.match(/(\d+,?\d+)\s+tool/i);
    if (toolsMatch) metrics.tools = toolsMatch[1].replace(/,/g, '');

    const turnsMatch = content.match(/(\d+,?\d+)\s+turn/i);
    if (turnsMatch) metrics.turns = turnsMatch[1].replace(/,/g, '');

    const peakMatch = content.match(/Peak.*?(\d+[\d,]*)\s*tool/i);
    if (peakMatch) metrics.peak = peakMatch[1].replace(/,/g, '');

    return metrics;
  }

  globAsync(pattern) {
    return new Promise((resolve, reject) => {
      glob(pattern, (err, files) => {
        if (err) reject(err);
        else resolve(files);
      });
    });
  }
}

module.exports = new DataLoader();
