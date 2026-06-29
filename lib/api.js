import Parser from 'rss-parser';
import { readConfig } from './config.js';

const parser = new Parser({
  customFields: {
    item: [
      ['source', 'source']
    ]
  }
});

/**
 * Fetches news from Google News RSS feed
 * @param {Object} options 
 * @param {('top'|'topic'|'search')} options.type
 * @param {string} [options.topic]
 * @param {string} [options.query]
 * @returns {Promise<Array>} List of articles
 */
export async function fetchNews({ type = 'top', topic = '', query = '' } = {}) {
  const config = readConfig();
  const params = new URLSearchParams({
    hl: config.hl,
    gl: config.gl,
    ceid: config.ceid
  });

  let url = 'https://news.google.com/rss';

  if (type === 'topic' && topic) {
    url = `https://news.google.com/rss/headlines/section/topic/${topic.toUpperCase()}`;
  } else if (type === 'search' && query) {
    url = `https://news.google.com/rss/search`;
    params.set('q', query);
  }

  const fullUrl = `${url}?${params.toString()}`;
  
  try {
    const feed = await parser.parseURL(fullUrl);
    
    // Parse articles
    const articles = feed.items.map(item => {
      let sourceName = 'Unknown Source';
      let sourceUrl = '';

      if (item.source) {
        if (typeof item.source === 'string') {
          sourceName = item.source;
        } else if (typeof item.source === 'object') {
          sourceName = item.source._ || sourceName;
          sourceUrl = item.source.$?.url || '';
        }
      }

      return {
        title: item.title,
        link: item.link,
        pubDate: item.pubDate,
        date: new Date(item.pubDate),
        source: sourceName,
        sourceUrl: sourceUrl,
        snippet: item.contentSnippet || item.content || ''
      };
    });

    // Sort by date descending (though RSS is usually already sorted)
    articles.sort((a, b) => b.date - a.date);

    // Limit output based on config
    return articles.slice(0, config.maxResults);
  } catch (error) {
    throw new Error(`Failed to fetch news from Google: ${error.message}`);
  }
}
