#!/usr/bin/env node

/**
 * Installation script for Slidev MCP PDF export dependencies
 * Run this if you encounter "playwright-chromium not installed" errors
 */

import { execSync } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';

console.log('🔧 Installing Slidev MCP PDF export dependencies...\n');

const dependencies = [
  '@slidev/cli',
  'playwright-chromium',
  '@slidev/theme-apple-basic'
];

function runCommand(command, description) {
  try {
    console.log(`📦 ${description}...`);
    execSync(command, { stdio: 'inherit', timeout: 120000 });
    console.log(`✅ ${description} completed\n`);
    return true;
  } catch (error) {
    console.error(`❌ ${description} failed: ${error.message}\n`);
    return false;
  }
}

function checkDependency(dep) {
  try {
    execSync(`npm list ${dep}`, { stdio: 'pipe' });
    return true;
  } catch (error) {
    return false;
  }
}

async function main() {
  // Check if package.json exists
  if (!existsSync('package.json')) {
    console.error('❌ package.json not found. Please run this from the project root.');
    process.exit(1);
  }

  console.log('🔍 Checking existing dependencies...');
  const missingDeps = dependencies.filter(dep => !checkDependency(dep));

  if (missingDeps.length === 0) {
    console.log('✅ All dependencies are already installed!');
    console.log('\n🧪 Testing PDF export...');

    // Test if Slidev CLI works with multiple methods
    const testCommands = [
      'npx slidev --version',
      'node node_modules/@slidev/cli/bin/slidev.mjs --version'
    ];

    let anyWorking = false;
    for (const cmd of testCommands) {
      if (runCommand(cmd, `Testing: ${cmd}`)) {
        anyWorking = true;
        break;
      }
    }

    if (anyWorking) {
      console.log('🎉 PDF export dependencies are ready!');
    } else {
      console.log('⚠️  Slidev CLI test failed. You may need to reinstall dependencies.');
    }
    return;
  }

  console.log(`📝 Missing dependencies: ${missingDeps.join(', ')}\n`);

  // Install missing dependencies
  const installCmd = `npm install -D ${missingDeps.join(' ')}`;

  if (!runCommand(installCmd, 'Installing missing dependencies')) {
    console.error('❌ Installation failed. Please run manually:');
    console.error(`   ${installCmd}`);
    process.exit(1);
  }

  // Test installation
  console.log('🧪 Testing installation...');

  // Test installation with multiple methods
  const testCommands = [
    'npx slidev --version',
    'node node_modules/@slidev/cli/bin/slidev.mjs --version'
  ];

  let installWorking = false;
  for (const cmd of testCommands) {
    if (runCommand(cmd, `Testing: ${cmd}`)) {
      installWorking = true;
      break;
    }
  }

  if (installWorking) {
    console.log('🎉 PDF export dependencies installed successfully!');
    console.log('\n📋 Next steps:');
    console.log('1. Restart your MCP server (npm start)');
    console.log('2. Try the export_to_pdf tool again');
    console.log('3. Your n8n agent should now be able to export PDFs');
  } else {
    console.error('⚠️  Installation completed but Slidev CLI test failed.');
    console.error('   You may need to restart your terminal or check PATH settings.');
  }
}

main().catch(error => {
  console.error('💥 Installation script failed:', error.message);
  process.exit(1);
});