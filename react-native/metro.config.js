const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

config.resolver.blockList = [
  new RegExp('python-backend/.*'),
];

module.exports = config;