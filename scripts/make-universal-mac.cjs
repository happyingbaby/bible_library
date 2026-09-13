const path = require('node:path');
const fs = require('node:fs');
const {makeUniversalApp} = require('@electron/universal');

const [x64AppPath, arm64AppPath, outAppPath] = process.argv.slice(2).map(value => path.resolve(value));
if (!x64AppPath || !arm64AppPath || !outAppPath) {
  console.error('Usage: node scripts/make-universal-mac.cjs <x64.app> <arm64.app> <output.app>');
  process.exit(2);
}

async function build() {
  const backendRelativePath = path.join('Contents', 'Resources', 'backend');
  const stagedX64Backend = `${outAppPath}.backend-x64`;
  const stagedArm64Backend = `${outAppPath}.backend-arm64`;
  fs.rmSync(stagedX64Backend, {recursive: true, force: true});
  fs.rmSync(stagedArm64Backend, {recursive: true, force: true});
  fs.renameSync(path.join(x64AppPath, backendRelativePath), stagedX64Backend);
  fs.renameSync(path.join(arm64AppPath, backendRelativePath), stagedArm64Backend);

  try {
    await makeUniversalApp({
      x64AppPath,
      arm64AppPath,
      outAppPath,
      force: true,
      mergeASARs: true,
    });
    const resourcesPath = path.join(outAppPath, 'Contents', 'Resources');
    fs.renameSync(stagedX64Backend, path.join(resourcesPath, 'backend-x64'));
    fs.renameSync(stagedArm64Backend, path.join(resourcesPath, 'backend-arm64'));
  } finally {
    fs.rmSync(stagedX64Backend, {recursive: true, force: true});
    fs.rmSync(stagedArm64Backend, {recursive: true, force: true});
  }
}

build().catch(error => {
  console.error(error);
  process.exit(1);
});
