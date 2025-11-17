#!/usr/bin/env node

/**
 * Wrapper script for Slidev PDF export that handles environment issues
 * This ensures proper working directory and dependency resolution
 */

import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { join, resolve, dirname, basename } from 'path';
import { fileURLToPath } from 'url';
import { homedir } from 'os';
import crypto from 'crypto';

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
    const wrapperRoot = resolve(__dirname);
    console.error(`📁 Original working directory: ${originalCwd}`);
    console.error(`🏠 Wrapper root: ${wrapperRoot}`);

    // Try to find the input file in multiple locations
    let mdPath = null;
    const possiblePaths = [
      resolve(originalCwd, inputFile),           // Relative to original CWD
      resolve(wrapperRoot, inputFile),          // Relative to wrapper root
      resolve(inputFile),                       // Absolute path
      resolve(originalCwd, 'presentations', inputFile.replace(/^presentations\//, '')), // In original/presentations/
      resolve(wrapperRoot, 'presentations', inputFile.replace(/^presentations\//, ''))  // In wrapper/presentations/
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

    // Determine canonical Slidev project directory
    function getDefaultCanonicalDir() {
      const home = homedir();
      if (process.platform === 'darwin') {
        return join(home, 'Library', 'Application Support', 'precursor', 'slidev_project');
      }
      if (process.platform === 'win32') {
        const base = process.env.LOCALAPPDATA || process.env.APPDATA || join(home, 'AppData', 'Local');
        return join(base, 'precursor', 'slidev_project');
      }
      return join(home, '.local', 'share', 'precursor', 'slidev_project');
    }
    const canonicalRoot = process.env.SLIDEV_DIR && process.env.SLIDEV_DIR.length > 0
      ? resolve(process.env.SLIDEV_DIR)
      : getDefaultCanonicalDir();

    if (!existsSync(canonicalRoot)) {
      mkdirSync(canonicalRoot, { recursive: true });
      console.error(`📁 Created canonical Slidev project at: ${canonicalRoot}`);
    }

    // Ensure basic project setup (package.json and cli)
    try {
      // Initialize package.json if missing
      if (!existsSync(join(canonicalRoot, 'package.json'))) {
        console.error('🧰 Initializing Slidev project (package.json)...');
        execSync('npm init -y', { cwd: canonicalRoot, stdio: 'pipe' });
      }
      // Ensure Slidev CLI is available in canonical project
      try {
        execSync('node -e "require.resolve(\'@slidev/cli\')"', { cwd: canonicalRoot, stdio: 'pipe' });
        console.error('✅ @slidev/cli available in canonical project');
      } catch {
        console.error('📦 Installing @slidev/cli (non-interactive)...');
        execSync('npm install -D @slidev/cli --no-audit --no-fund --prefer-offline --silent', {
          cwd: canonicalRoot,
          stdio: 'inherit',
          timeout: 300000
        });
        console.error('✅ @slidev/cli installed');
      }
      // Ensure default theme to avoid prompts on vanilla files
      try {
        execSync('node -e "require.resolve(\'@slidev/theme-default\')"', { cwd: canonicalRoot, stdio: 'pipe' });
        console.error('✅ @slidev/theme-default available');
      } catch {
        console.error('📦 Installing @slidev/theme-default (non-interactive)...');
        execSync('npm install -D @slidev/theme-default --no-audit --no-fund --prefer-offline --silent', {
          cwd: canonicalRoot,
          stdio: 'inherit',
          timeout: 300000
        });
        console.error('✅ @slidev/theme-default installed');
      }
    } catch (setupErr) {
      console.error(`⚠️  Slidev project setup check failed: ${setupErr.message}`);
    }

    // Stage entry markdown inside canonical project to align theme resolution
    const slidesDir = join(canonicalRoot, 'slides');
    if (!existsSync(slidesDir)) {
      mkdirSync(slidesDir, { recursive: true });
    }
    const mdBaseName = basename(mdPath);
    const mdHash = crypto.createHash('sha1').update(mdPath).digest('hex').slice(0, 8);
    const stagedMdName = `${mdBaseName.replace(/\.md$/i, '')}-${mdHash}.md`;
    const stagedMdRelPath = join('slides', stagedMdName);
    const stagedMdAbsPath = join(canonicalRoot, stagedMdRelPath);
    try {
      // Copy to avoid cross-filesystem symlink issues
      const fsmod = await import('fs');
      fsmod.copyFileSync(mdPath, stagedMdAbsPath);
      console.error(`📎 Staged entry at: ${stagedMdAbsPath}`);
    } catch (stageErr) {
      console.error(`❌ Failed to stage entry markdown: ${stageErr.message}`);
      throw stageErr;
    }

    // Switch to canonical project for export operations
    process.chdir(canonicalRoot);
    console.error(`✅ Changed to canonical project root: ${canonicalRoot}`);

    // Resolve output path (always relative to project root) and compute a safe filename
    const outputPath = resolve(canonicalRoot, outputFile);
    const desiredOutputFilename = basename(outputPath); // pass only filename to Slidev
    console.error(`📄 Resolved output: ${outputPath}`);
    console.error(`📝 Using output filename for Slidev: ${desiredOutputFilename}`);

    // Ensure output directory exists
    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
      console.error(`📁 Created output directory: ${outputDir}`);
    }

    // Ensure local playwright is present and browsers installed inside canonical project
    try {
      execSync('node -e "require.resolve(\'playwright-chromium\')"', {
        stdio: 'pipe',
        cwd: canonicalRoot,
      });
      console.error(`✅ Local playwright-chromium found`);
    } catch {
      console.error('📦 Installing playwright-chromium locally (non-interactive)...');
      try {
        execSync('npm install -D playwright-chromium --no-audit --no-fund --prefer-offline --silent', {
          cwd: canonicalRoot,
          stdio: 'inherit',
          timeout: 300000,
        });
        console.error('✅ playwright-chromium installed');
      } catch (e) {
        console.error(`⚠️  Failed to install playwright-chromium: ${e.message}`);
      }
    }
    // Attempt to install Chromium for Playwright (idempotent)
    try {
      execSync('npx playwright install chromium --with-deps', {
        cwd: canonicalRoot,
        stdio: 'inherit',
        timeout: 600000,
      });
      console.error('✅ Playwright Chromium installed');
    } catch (e) {
      console.error(`⚠️  Failed to install Playwright Chromium: ${e.message}`);
    }

    // Build export command with working directory context
    const exportCommands = [
      // Use only a filename for output to avoid issues with directories/spaces
      `cd "${canonicalRoot}" && npx slidev export "${stagedMdRelPath}" --output "${desiredOutputFilename}"`,
      `cd "${canonicalRoot}" && node node_modules/@slidev/cli/bin/slidev.mjs export "${stagedMdRelPath}" --output "${desiredOutputFilename}"`
    ];

    // Add options to commands
    const optionFlags = [];
    if (options.withClicks) optionFlags.push('--with-clicks');
    if (options.range) optionFlags.push(`--range "${options.range}"`);
    if (options.dark) optionFlags.push('--dark');

    // Honor explicit theme in frontmatter by ensuring the package exists (non-interactive)
    try {
      const fsmod = await import('fs');
      const mdText = fsmod.readFileSync(mdPath, 'utf8');
      const themeMatch = mdText.match(/^---[\s\S]*?\btheme\s*:\s*"?([^"\n]+)"?[\s\S]*?---/m);
      const frontmatterTheme = themeMatch?.[1]?.trim();
      if (frontmatterTheme && frontmatterTheme.toLowerCase() !== 'none') {
        const derivePkgName = (themeName) => {
          if (themeName.includes('/') || themeName.startsWith('@')) return themeName;
          if (themeName.startsWith('theme-')) return `@slidev/${themeName}`;
          return `@slidev/theme-${themeName}`;
        };
        const pkgName = derivePkgName(frontmatterTheme);
        try {
          execSync(`node -e "require.resolve('${pkgName}')"`, { stdio: 'pipe', cwd: canonicalRoot });
          console.error(`✅ Theme package available: ${pkgName}`);
        } catch {
          console.error(`ℹ️  Theme package not found locally: ${pkgName}. Installing...`);
          try {
            execSync(`npm install -D ${pkgName} --no-audit --no-fund --prefer-offline --silent`, {
              cwd: canonicalRoot,
              stdio: 'inherit',
              timeout: 180000,
            });
            console.error(`✅ Theme installed: ${pkgName}`);
          } catch (instErr) {
            console.error(`⚠️  Failed to install theme ${pkgName}: ${instErr.message}`);
          }
        }
      }
    } catch {
      // If reading fails, continue without modification
    }

    const flagString = optionFlags.join(' ');
    if (flagString) {
      exportCommands.forEach((cmd, i) => {
        exportCommands[i] = cmd.replace(' export "', ` export ${flagString} "`);
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
          cwd: canonicalRoot,
          timeout: 300000, // 5 minutes
          stdio: 'pipe',
          env: {
            ...process.env,
            NODE_PATH: `${canonicalRoot}/node_modules:${process.env.NODE_PATH || ''}`,
            PATH: `${canonicalRoot}/node_modules/.bin:${process.env.PATH}`
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
            execSync('npm install -D playwright-chromium --no-audit --no-fund --prefer-offline --silent', {
              cwd: canonicalRoot,
              timeout: 300000,
              stdio: 'inherit',
            });
            execSync('npx playwright install chromium --with-deps', {
              cwd: canonicalRoot,
              timeout: 600000,
              stdio: 'inherit',
            });
            console.error(`✅ Local playwright-chromium and Chromium installed`);
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
    const mdBase = basename(mdPath).replace(/\.md$/i, '');
    const possibleOutputPaths = [
      outputPath,                                    // Absolute path as specified
      resolve(canonicalRoot, outputFile),           // Relative to canonical project
      join(canonicalRoot, outputFile),              // Join with canonical project
      join(process.cwd(), outputFile),              // Relative to current working directory
      // Common Slidev defaults if flags were ignored:
      join(canonicalRoot, desiredOutputFilename),
      join(dirname(stagedMdAbsPath), desiredOutputFilename),
      join(canonicalRoot, 'slides-export.pdf'),
      join(dirname(stagedMdAbsPath), 'slides-export.pdf'),
      join(canonicalRoot, `${mdBase}.pdf`),
      join(canonicalRoot, `${mdBase}-export.pdf`),
      join(dirname(stagedMdAbsPath), `${mdBase}.pdf`),
      join(dirname(stagedMdAbsPath), `${mdBase}-export.pdf`)
    ];

    let actualPdfPath = null;
    for (const possiblePath of possibleOutputPaths) {
      if (existsSync(possiblePath)) {
        actualPdfPath = possiblePath;
        console.error(`✅ Found PDF at: ${actualPdfPath}`);
        break;
      }
    }

    // If we found a default-named PDF but not at the desired outputPath, copy it there
    if (actualPdfPath && actualPdfPath !== outputPath) {
      try {
        const { copyFileSync } = await import('fs');
        copyFileSync(actualPdfPath, outputPath);
        console.error(`📄 Copied PDF to requested output path: ${outputPath}`);
        actualPdfPath = outputPath;
      } catch (copyErr) {
        console.error(`⚠️  Failed to copy PDF to output path: ${copyErr.message}`);
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