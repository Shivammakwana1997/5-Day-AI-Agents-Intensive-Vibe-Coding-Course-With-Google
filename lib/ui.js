import chalk from 'chalk';
import boxen from 'boxen';

/**
 * Formats a date into a friendly relative string (e.g. "2h ago")
 * @param {Date} date 
 * @returns {string}
 */
export function formatRelativeTime(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'yesterday';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * Cleans the article title by removing the source suffix
 * @param {string} title 
 * @param {string} source 
 * @returns {string}
 */
export function cleanTitle(title, source) {
  const suffixes = [` - ${source}`, ` | ${source}`];
  let cleaned = title;
  for (const suffix of suffixes) {
    if (cleaned.toLowerCase().endsWith(suffix.toLowerCase())) {
      cleaned = cleaned.slice(0, -suffix.length);
      break;
    }
  }
  return cleaned.trim();
}

/**
 * Prints the main application header
 */
export function printHeader() {
  const title = chalk.bold.whiteBright(' GOOGLE NEWS CLI ');
  const banner = boxen(
    `${chalk.cyanBright('📰 Latest stories, custom topics, and keyword search')}\n` +
    `${chalk.dim('Powered by Google News RSS')}`,
    {
      title,
      titleAlignment: 'center',
      borderStyle: 'round',
      borderColor: 'cyan',
      padding: 1,
      margin: { top: 1, bottom: 1 }
    }
  );
  console.clear();
  console.log(banner);
}

/**
 * Prints a beautiful section divider/header
 * @param {string} title 
 */
export function printSectionHeader(title) {
  console.log('\n' + chalk.bgCyan.black(`  ${title.toUpperCase()}  `) + '\n');
}

/**
 * Prints article details inside a neat box
 * @param {Object} article 
 */
export function printArticleDetails(article) {
  const cleaned = cleanTitle(article.title, article.source);
  const dateStr = article.date.toLocaleString();
  
  const content = 
    `${chalk.bold.yellowBright(cleaned)}\n\n` +
    `${chalk.bold('Source:')} ${chalk.green(article.source)}\n` +
    `${chalk.bold('Published:')} ${chalk.dim(dateStr)} (${formatRelativeTime(article.date)})\n` +
    `${chalk.bold('Link:')} ${chalk.blue.underline(article.link)}`;

  const box = boxen(content, {
    borderStyle: 'single',
    borderColor: 'yellow',
    padding: 1,
    margin: { top: 1, bottom: 1 }
  });

  console.log(box);
}

/**
 * Prints success message
 * @param {string} msg 
 */
export function printSuccess(msg) {
  console.log(chalk.greenBright(`✔ ${msg}`));
}

/**
 * Prints error message
 * @param {string} msg 
 */
export function printError(msg) {
  console.log(chalk.redBright(`✘ Error: ${msg}`));
}
