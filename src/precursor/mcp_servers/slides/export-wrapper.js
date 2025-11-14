#!/usr/bin/env node

/**
 * Wrapper script for Slidev PDF export that handles environment issues
 * This ensures proper working directory and dependency resolution
 */

import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function exportToPDF(inputFile, outputFile, options = {}) {
  try {
    console.error(`🔧 Starting PDF export wrapper...`);
    console.error(`📁 Working directory: ${process.cwd()}`);
    console.error(`📄 Input: ${inputFile}`);
    console.error(`💾 Output: ${outputFile}`);

        // Store original working directory
    const originalCwd = process.cwd();
    const projectRoot = resolve(__dirname);
    console.error(`📁 Original working directory: ${originalCwd}`);
    console.error(`🏠 Project root: ${projectRoot}`);

    // Try to find the input file in multiple locations
    let mdPath = null;
    const possiblePaths = [
      resolve(originalCwd, inputFile),           // Relative to original CWD
      resolve(projectRoot, inputFile),          // Relative to project root
      resolve(inputFile),                       // Absolute path
      resolve(originalCwd, 'presentations', inputFile.replace(/^presentations\//, '')), // In original/presentations/
      resolve(projectRoot, 'presentations', inputFile.replace(/^presentations\//, ''))  // In project/presentations/
    ];

    for (const possiblePath of possiblePaths) {
      if (existsSync(possiblePath)) {
        mdPath = possiblePath;
        console.error(`✅ Found input file: ${mdPath}`);
        break;
      }
    }

    if (!mdPath) {
      console.error(`❌ File not found in any of these locations:`);
      possiblePaths.forEach(path => console.error(`   - ${path}`));
      throw new Error(`Input file not found: ${inputFile}`);
    }

    // Change to project root for export operations
    process.chdir(projectRoot);
    console.error(`✅ Changed to project root: ${projectRoot}`);

    // Resolve output path (always relative to project root)
    const outputPath = resolve(projectRoot, outputFile);
    console.error(`📄 Resolved output: ${outputPath}`);

    // Ensure output directory exists
    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
      console.error(`📁 Created output directory: ${outputDir}`);
    }

    // Install dependencies globally if needed
    try {
      console.error(`🔍 Checking global playwright-chromium...`);
      execSync('npm list -g playwright-chromium', { stdio: 'pipe' });
      console.error(`✅ Global playwright-chromium found`);
    } catch (e) {
      console.error(`⚠️  Installing global playwright-chromium...`);
      try {
        execSync('npm install -g playwright-chromium', {
          stdio: 'inherit',
          timeout: 120000
        });
        console.error(`✅ Global playwright-chromium installed`);
      } catch (installError) {
        console.error(`❌ Failed to install global playwright-chromium: ${installError.message}`);
        // Continue anyway, might work with local
      }
    }

    // Build export command with working directory context
    const exportCommands = [
      // Try with explicit working directory
      `cd "${projectRoot}" && npx slidev export "${mdPath}" --output "${outputPath}"`,
      // Try with global slidev but local playwright
      `cd "${projectRoot}" && slidev export "${mdPath}" --output "${outputPath}"`,
      // Try direct node execution
      `cd "${projectRoot}" && node node_modules/@slidev/cli/bin/slidev.mjs export "${mdPath}" --output "${outputPath}"`
    ];

    // Add options to commands
    const optionFlags = [];
    if (options.withClicks) optionFlags.push('--with-clicks');
    if (options.range) optionFlags.push(`--range "${options.range}"`);
    if (options.dark) optionFlags.push('--dark');

    const flagString = optionFlags.join(' ');
    if (flagString) {
      exportCommands.forEach((cmd, i) => {
        exportCommands[i] = cmd.replace(' --output', ` ${flagString} --output`);
      });
    }

    let exportSuccessful = false;
    let lastError = null;

    // Try export commands
    for (let i = 0; i < exportCommands.length; i++) {
      const command = exportCommands[i];
      try {
        console.error(`🚀 Attempting method ${i + 1}: ${command}`);

        const result = execSync(command, {
          encoding: 'utf8',
          cwd: projectRoot,
          timeout: 300000, // 5 minutes
          stdio: 'pipe',
          env: {
            ...process.env,
            NODE_PATH: `${projectRoot}/node_modules:${process.env.NODE_PATH || ''}`,
            PATH: `${projectRoot}/node_modules/.bin:${process.env.PATH}`
          }
        });

        console.error(`✅ Export command succeeded`);
        exportSuccessful = true;
        break;

      } catch (cmdError) {
        lastError = cmdError;
        console.error(`❌ Method ${i + 1} failed: ${cmdError.message}`);

        // If it's a playwright error, try to fix it
        if (cmdError.message.includes('playwright') && i === 0) {
          console.error(`🔧 Playwright issue detected, trying to install...`);
          try {
            execSync('npm install -D playwright-chromium', {
              cwd: projectRoot,
              timeout: 120000,
              stdio: 'inherit'
            });
            console.error(`✅ Local playwright-chromium installed`);
          } catch (installErr) {
            console.error(`⚠️  Local install failed: ${installErr.message}`);
          }
        }

        // Continue to next method
      }
    }

    if (!exportSuccessful) {
      throw lastError || new Error("All export methods failed");
    }

    // Verify PDF was created (check multiple possible locations)
    const possibleOutputPaths = [
      outputPath,                                    // Absolute path as specified
      resolve(projectRoot, outputFile),             // Relative to project root
      join(projectRoot, outputFile),                // Join with project root
      join(process.cwd(), outputFile)               // Relative to current working directory
    ];

    let actualPdfPath = null;
    for (const possiblePath of possibleOutputPaths) {
      if (existsSync(possiblePath)) {
        actualPdfPath = possiblePath;
        console.error(`✅ Found PDF at: ${actualPdfPath}`);
        break;
      }
    }

    if (!actualPdfPath) {
      console.error(`❌ PDF not found in any of these locations:`);
      possibleOutputPaths.forEach(path => console.error(`   - ${path}`));
      throw new Error(`PDF file was not created in any expected location`);
    }

    const stats = await import('fs').then(fs => fs.promises.stat(actualPdfPath));
    console.error(`✅ PDF created successfully: ${actualPdfPath} (${Math.round(stats.size / 1024)}KB)`);

    return {
      success: true,
      pdfPath: actualPdfPath,
      message: `PDF exported successfully: ${actualPdfPath}`
    };

  } catch (error) {
    console.error(`💥 Export failed: ${error.message}`);
    return {
      success: false,
      pdfPath: '',
      message: `PDF export failed: ${error.message}`
    };
  }
}

// CLI usage
if (process.argv[1] === __filename) {
  const [,, inputFile, outputFile, ...optionArgs] = process.argv;

  if (!inputFile || !outputFile) {
    console.error('Usage: node export-wrapper.js <input.md> <output.pdf> [--with-clicks] [--dark] [--range "1,3-5"]');
    process.exit(1);
  }

  const options = {
    withClicks: optionArgs.includes('--with-clicks'),
    dark: optionArgs.includes('--dark'),
    range: optionArgs.find(arg => arg.startsWith('--range'))?.split('=')[1]
  };

  exportToPDF(inputFile, outputFile, options)
    .then(result => {
      console.log(JSON.stringify(result, null, 2));
      process.exit(result.success ? 0 : 1);
    })
    .catch(error => {
      console.error('Wrapper failed:', error.message);
      process.exit(1);
    });
}

export default exportToPDF;