import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Store config in the workspace directory (parent of lib/)
const CONFIG_FILE_PATH = path.resolve(__dirname, '../.google-news-cli.json');

const DEFAULT_CONFIG = {
  hl: 'en',
  gl: 'US',
  ceid: 'US:en',
  maxResults: 15
};

export const REGIONS = [
  { name: 'United States (English)', gl: 'US', hl: 'en', ceid: 'US:en' },
  { name: 'India (English)', gl: 'IN', hl: 'en', ceid: 'IN:en' },
  { name: 'United Kingdom (English)', gl: 'GB', hl: 'en', ceid: 'GB:en' },
  { name: 'Canada (English)', gl: 'CA', hl: 'en', ceid: 'CA:en' },
  { name: 'Australia (English)', gl: 'AU', hl: 'en', ceid: 'AU:en' },
  { name: 'Germany (German)', gl: 'DE', hl: 'de', ceid: 'DE:de' },
  { name: 'France (French)', gl: 'FR', hl: 'fr', ceid: 'FR:fr' },
  { name: 'Japan (Japanese)', gl: 'JP', hl: 'ja', ceid: 'JP:ja' },
  { name: 'Spain (Spanish)', gl: 'ES', hl: 'es', ceid: 'ES:es' }
];

export function readConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE_PATH)) {
      const data = fs.readFileSync(CONFIG_FILE_PATH, 'utf8');
      return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
    }
  } catch (err) {
    // Return defaults if parsing/reading fails
  }
  return { ...DEFAULT_CONFIG };
}

export function writeConfig(config) {
  try {
    const data = JSON.stringify(config, null, 2);
    fs.writeFileSync(CONFIG_FILE_PATH, data, 'utf8');
    return true;
  } catch (err) {
    return false;
  }
}
