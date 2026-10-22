// Learn more: https://docs.expo.dev/guides/customizing-metro
const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');

const projectRoot = __dirname;
const config = getDefaultConfig(projectRoot);

// The mobile app is a standalone npm project inside a pnpm monorepo. Expo's
// default config would notice pnpm-workspace.yaml one level up and start
// watching the whole repository (including .venv and the web app's
// node_modules). Pin Metro to this folder instead.
config.watchFolders = [projectRoot];
config.resolver.nodeModulesPaths = [path.resolve(projectRoot, 'node_modules')];

module.exports = config;
