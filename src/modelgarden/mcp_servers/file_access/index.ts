#!/usr/bin/env node

// Set default paths as command line arguments before importing
const homePath = process.env.HOME || process.env.USERPROFILE || "";
const defaultPaths = [
  `${homePath}/Documents`,
  `${homePath}/Desktop`
];

// If no args provided, add defaults
if (process.argv.length === 2) {
  process.argv.push(...defaultPaths);
}

// Import and run the filesystem server
import "@modelcontextprotocol/server-filesystem/dist/index.js";