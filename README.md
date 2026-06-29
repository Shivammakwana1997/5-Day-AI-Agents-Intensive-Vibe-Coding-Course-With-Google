# Google News CLI 📰

A lightweight, premium, interactive terminal application built in Node.js to read, search, and view the latest news from Google News RSS feeds directly in your command line.

---

## Features
- 🔥 **Top Stories**: Instantly view the trending headlines from around the world.
- 📂 **Topic Categories**: Browse news curated by major categories:
  - Technology, Business, Science, Health, Sports, Entertainment, World, and Nation.
- 🔍 **Search Query**: Find specific news articles using keywords or phrases.
- 🌍 **Region / Language Preferences**: Choose from multiple locales (such as US, UK, India, Germany, Japan, etc.) to fetch news in your language and country.
- 🔢 **Custom Limits**: Control the number of articles displayed (5 to 50).
- 🌐 **Browser Integration**: Jump straight from the terminal to the full article on the web.
- ⚡ **Direct Search Mode**: Bypass the menu and search instantly from the command line (e.g. `npm start -- "artificial intelligence"`).

---

## Prerequisites
- [Node.js](https://nodejs.org/) (v18.0.0 or higher recommended)

---

## Installation & Setup

1. **Clone or navigate to the directory**:
   ```bash
   cd "a:\5-day online course\my-first-project"
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

---

## How to Run

### 1. Interactive CLI Mode
Run the tool interactively to navigate menus, select articles, view details, and change settings:
```bash
npm start
```
*Alternatively, if running the CLI file directly:*
```bash
node bin/cli.js
```

### 2. Direct Search Mode
Search for specific news topics immediately:
```bash
npm start -- "artificial intelligence"
# or
node bin/cli.js "artificial intelligence"
```

### 3. Display Options & Help
Get details on command-line arguments and version:
```bash
node bin/cli.js --help
node bin/cli.js --version
```

---

## Configuration Settings
Preferences are stored in a local `.google-news-cli.json` file inside the project directory, so your configuration persists between runs. You can modify these settings via the `⚙ Settings` menu inside the application.

---

## Dependencies
- `@inquirer/prompts` - Modular and fully accessible command line prompts.
- `rss-parser` - Simple, lightweight XML RSS parsing library.
- `chalk` - Terminal color styling.
- `boxen` - Draws elegant border boxes in the terminal.
- `open` - Seamlessly opens URLs in the default browser.
- `ora` - Graceful terminal spinner animations.
