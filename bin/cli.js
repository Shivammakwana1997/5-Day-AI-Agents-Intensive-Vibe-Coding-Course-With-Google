#!/usr/bin/env node

import { select, input, confirm } from '@inquirer/prompts';
import ora from 'ora';
import open from 'open';
import chalk from 'chalk';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import { fetchNews } from '../lib/api.js';
import { readConfig, writeConfig, REGIONS } from '../lib/config.js';
import {
  printHeader,
  printSectionHeader,
  printArticleDetails,
  formatRelativeTime,
  cleanTitle,
  printSuccess,
  printError
} from '../lib/ui.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read package.json version
const packageJson = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, '../package.json'), 'utf8')
);

// CLI Command Help
function showHelp() {
  console.log(`
${chalk.bold.cyan('Google News CLI')} - Get the latest news from Google News directly in your terminal.

${chalk.bold('Usage:')}
  ${chalk.green('google-news')}                  ${chalk.dim('# Start interactive CLI mode')}
  ${chalk.green('google-news [search query]')}   ${chalk.dim('# Direct news search (e.g., google-news "artificial intelligence")')}

${chalk.bold('Options:')}
  ${chalk.yellow('-h, --help')}                  ${chalk.dim('Show help details')}
  ${chalk.yellow('-v, --version')}               ${chalk.dim('Show application version')}

${chalk.bold('Interactive Features:')}
  • Browse Top Stories or specific categories (Tech, Business, Science, etc.)
  • Search for specific news terms
  • View detailed source & publication details
  • Open full articles in your default web browser
  • Configure preferred region/language (default: US)
`);
}

async function handleDirectSearch(query) {
  const spinner = ora({
    text: `Searching Google News for "${query}"...`,
    color: 'cyan'
  }).start();

  try {
    const articles = await fetchNews({ type: 'search', query });
    spinner.succeed(`Found ${articles.length} articles`);
    
    if (articles.length === 0) {
      console.log(chalk.yellow(`\nNo articles found for "${query}". Try a different keyword.`));
      return;
    }

    await showArticles(articles, `Search: "${query}"`);
  } catch (error) {
    spinner.fail('Failed to fetch news');
    printError(error.message);
  }
}

async function showArticles(articles, typeLabel) {
  let viewing = true;
  while (viewing) {
    printHeader();
    printSectionHeader(typeLabel);

    const choices = articles.map((art, idx) => {
      const displayTitle = cleanTitle(art.title, art.source);
      const sourceInfo = `${art.source} • ${formatRelativeTime(art.date)}`;
      
      // Let's truncate title if it is too long to keep list readable
      const maxLen = 70;
      const truncatedTitle = displayTitle.length > maxLen 
        ? displayTitle.slice(0, maxLen) + '...'
        : displayTitle;

      return {
        name: `${chalk.cyan((idx + 1).toString().padStart(2, ' '))} ${truncatedTitle} ${chalk.dim(`(${sourceInfo})`)}`,
        value: art
      };
    });

    // Add back option
    choices.push({
      name: chalk.yellow('   ← Return to Main Menu'),
      value: 'BACK'
    });

    const choice = await select({
      message: 'Use arrow keys to select an article:',
      choices
    });

    if (choice === 'BACK') {
      viewing = false;
    } else {
      await handleArticleDetails(choice, articles, typeLabel);
    }
  }
}

async function handleArticleDetails(article, articles, typeLabel) {
  let insideDetails = true;
  while (insideDetails) {
    printHeader();
    printSectionHeader(`${typeLabel} > Article Details`);
    
    printArticleDetails(article);

    const action = await select({
      message: 'Select action:',
      choices: [
        { name: '🌐 Open in Default Browser', value: 'OPEN' },
        { name: '← Back to Articles List', value: 'LIST' },
        { name: '🏠 Return to Main Menu', value: 'MENU' }
      ]
    });

    if (action === 'OPEN') {
      const spinner = ora('Opening browser...').start();
      try {
        await open(article.link);
        spinner.succeed('Article opened in browser');
      } catch (err) {
        spinner.fail('Could not open browser');
        printError(err.message);
      }
      // Wait for a brief moment before rendering details again
      await new Promise(resolve => setTimeout(resolve, 1500));
    } else if (action === 'LIST') {
      insideDetails = false;
    } else if (action === 'MENU') {
      // Clear detail flag and modify the list loop control by mutating parent-scope if needed,
      // but returning a special code works perfectly.
      insideDetails = false;
      // Triggers immediate exit from parent loop too
      articles.length = 0; // Clears it to exit loop
    }
  }
}

async function runTopicMenu() {
  const topics = [
    { name: '💻 Technology', value: 'TECHNOLOGY' },
    { name: '📈 Business', value: 'BUSINESS' },
    { name: '🔬 Science', value: 'SCIENCE' },
    { name: '🏥 Health', value: 'HEALTH' },
    { name: '⚽ Sports', value: 'SPORTS' },
    { name: '🎬 Entertainment', value: 'ENTERTAINMENT' },
    { name: '🌍 World', value: 'WORLD' },
    { name: '🇺🇸 Nation', value: 'NATION' },
    { name: '← Back to Main Menu', value: 'BACK' }
  ];

  const selectedTopic = await select({
    message: 'Select a Topic Category:',
    choices: topics
  });

  if (selectedTopic === 'BACK') return;

  const spinner = ora({
    text: `Fetching latest stories for ${selectedTopic}...`,
    color: 'cyan'
  }).start();

  try {
    const articles = await fetchNews({ type: 'topic', topic: selectedTopic });
    spinner.succeed(`Loaded ${articles.length} articles`);
    await showArticles(articles, `Topic: ${selectedTopic}`);
  } catch (error) {
    spinner.fail('Failed to fetch news');
    printError(error.message);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}

async function runInteractiveSearch() {
  const query = await input({
    message: 'Enter keyword/phrase to search:',
    validate: (val) => val.trim().length > 0 ? true : 'Please enter a search term'
  });

  await handleDirectSearch(query.trim());
}

async function runSettingsMenu() {
  let insideSettings = true;
  while (insideSettings) {
    const config = readConfig();
    const currentRegion = REGIONS.find(r => r.gl === config.gl && r.hl === config.hl)?.name || `${config.gl} (${config.hl})`;

    printHeader();
    printSectionHeader('Settings');
    console.log(`${chalk.bold('Current Configuration:')}`);
    console.log(` • Region/Language: ${chalk.cyan(currentRegion)}`);
    console.log(` • Max Results:     ${chalk.cyan(config.maxResults)}\n`);

    const action = await select({
      message: 'Choose setting to update:',
      choices: [
        { name: '🌍 Change Default Region / Language', value: 'REGION' },
        { name: '🔢 Change Max Articles Limit', value: 'MAX_LIMIT' },
        { name: '← Back to Main Menu', value: 'BACK' }
      ]
    });

    if (action === 'REGION') {
      const regionChoices = REGIONS.map(reg => ({
        name: reg.name,
        value: reg
      }));

      const selectedRegion = await select({
        message: 'Select preferred region/language:',
        choices: regionChoices
      });

      config.gl = selectedRegion.gl;
      config.hl = selectedRegion.hl;
      config.ceid = selectedRegion.ceid;

      writeConfig(config);
      printSuccess(`Region updated to ${selectedRegion.name}`);
      await new Promise(resolve => setTimeout(resolve, 1500));

    } else if (action === 'MAX_LIMIT') {
      const limitStr = await input({
        message: 'Enter max articles count (5 - 50):',
        validate: (val) => {
          const num = parseInt(val, 10);
          if (isNaN(num) || num < 5 || num > 50) {
            return 'Please enter an integer between 5 and 50';
          }
          return true;
        }
      });

      config.maxResults = parseInt(limitStr, 10);
      writeConfig(config);
      printSuccess(`Max articles limit updated to ${config.maxResults}`);
      await new Promise(resolve => setTimeout(resolve, 1500));

    } else if (action === 'BACK') {
      insideSettings = false;
    }
  }
}

async function runInteractiveMenu() {
  let running = true;
  while (running) {
    printHeader();
    
    const choice = await select({
      message: 'Main Menu:',
      choices: [
        { name: '🔥 Top Stories', value: 'TOP' },
        { name: '📂 Browse by Topic', value: 'TOPIC' },
        { name: '🔍 Search News', value: 'SEARCH' },
        { name: '⚙ Settings', value: 'SETTINGS' },
        { name: '❌ Exit', value: 'EXIT' }
      ]
    });

    if (choice === 'TOP') {
      const spinner = ora({
        text: 'Fetching top stories...',
        color: 'cyan'
      }).start();
      try {
        const articles = await fetchNews({ type: 'top' });
        spinner.succeed(`Loaded ${articles.length} articles`);
        await showArticles(articles, 'Top Stories');
      } catch (error) {
        spinner.fail('Failed to fetch news');
        printError(error.message);
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    } else if (choice === 'TOPIC') {
      await runTopicMenu();
    } else if (choice === 'SEARCH') {
      await runInteractiveSearch();
    } else if (choice === 'SETTINGS') {
      await runSettingsMenu();
    } else if (choice === 'EXIT') {
      running = false;
      console.log(chalk.cyan('\nThank you for using Google News CLI. Goodbye!\n'));
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  
  if (args.length > 0) {
    const argStr = args.join(' ').trim();
    
    if (argStr === '-h' || argStr === '--help') {
      showHelp();
      process.exit(0);
    }
    
    if (argStr === '-v' || argStr === '--version') {
      console.log(`google-news version ${packageJson.version}`);
      process.exit(0);
    }
    
    // Treat any other argument as direct search
    await handleDirectSearch(argStr);
  } else {
    // Start interactive menu
    await runInteractiveMenu();
  }
}

main().catch(err => {
  printError(err.message);
  process.exit(1);
});
