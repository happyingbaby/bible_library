const {spawn} = require('node:child_process');
const path = require('node:path');
const root = path.join(__dirname, '..');

async function startDev({launchElectron = () => spawn(require('electron'), ['.'], {cwd:root, stdio:'inherit'})} = {}) {
  const {createServer} = await import('vite');
  const vite = await createServer({configFile:path.join(root, 'frontend/vite.config.ts')});
  let electron;
  let stopping;
  const stop = () => stopping ||= (async () => {
    electron?.kill('SIGTERM');
    await vite.close();
  })();
  try {
    // Await this server's successful bind; another service's HTTP response is not readiness.
    await vite.listen();
    vite.printUrls();
    electron = launchElectron();
    await new Promise((resolve, reject) => {
      electron.once('spawn', resolve);
      electron.once('error', reject);
    });
    return {vite, electron, stop};
  } catch (error) {
    await stop();
    throw error;
  }
}

async function main() {
  const {electron, stop} = await startDev();
  const finish = code => {process.exitCode = code;return stop();};
  process.once('SIGINT', () => finish(0));
  process.once('SIGTERM', () => finish(0));
  electron.once('exit', code => finish(code || 0));
  electron.once('error', error => {console.error(error.message);finish(1);});
}

module.exports = {startDev};
if (require.main === module) main().catch(error => {
  console.error(`桌面开发服务启动失败：${error.message}`);
  process.exitCode = 1;
});
