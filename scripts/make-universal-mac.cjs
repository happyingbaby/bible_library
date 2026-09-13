const path = require('node:path');
const {makeUniversalApp} = require('@electron/universal');

const [x64AppPath, arm64AppPath, outAppPath] = process.argv.slice(2).map(value => path.resolve(value));
if (!x64AppPath || !arm64AppPath || !outAppPath) {
  console.error('Usage: node scripts/make-universal-mac.cjs <x64.app> <arm64.app> <output.app>');
  process.exit(2);
}

makeUniversalApp({
  x64AppPath,
  arm64AppPath,
  outAppPath,
  force: true,
  mergeASARs: true,
}).catch(error => {
  console.error(error);
  process.exit(1);
});
