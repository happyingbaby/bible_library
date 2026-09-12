const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {startDev} = require('./dev.cjs');
const {createWebServer} = require('./web.cjs');
const listen = server => new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(5174, '127.0.0.1', resolve);
});
const close = server => new Promise(resolve => {server.close(resolve);server.closeAllConnections();});

test('desktop Vite and web gateway coexist; stopping desktop preserves web', async () => {
  const web = createWebServer({backendPort:1, key:'isolated-web-test'});
  await new Promise(resolve => web.listen(0, '127.0.0.1', resolve));
  let desktop;
  try {
    desktop = await startDev({launchElectron:() => spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'])});
    assert.equal(desktop.vite.config.server.port, 5174);
    const webUrl = `http://127.0.0.1:${web.address().port}/web-config.json`;
    assert.deepEqual(await (await fetch(webUrl)).json(), {key:'isolated-web-test'});
    assert.match(await (await fetch('http://127.0.0.1:5174/')).text(), /\/@vite\/client/);
    const exited = once(desktop.electron, 'exit');
    await desktop.stop();await exited;
    assert.equal((await fetch(webUrl)).status, 200);
    const probe = http.createServer();await listen(probe);await close(probe);
  } finally {await desktop?.stop();await close(web);}
});

test('occupied desktop port fails before starting Electron and preserves the owner', async () => {
  const owner = http.createServer((req, res) => res.end('existing service'));
  await listen(owner);
  let launched = false;
  try {
    await assert.rejects(startDev({launchElectron:() => {launched = true;throw Error('must not launch');}}), /5174.*already in use/);
    assert.equal(launched, false);
    assert.equal(await (await fetch('http://127.0.0.1:5174/')).text(), 'existing service');
  } finally {await close(owner);}
});

test('Electron spawn failure releases the desktop port', async () => {
  await assert.rejects(startDev({launchElectron:() => spawn('/nonexistent-bible-electron')}), /ENOENT/);
  const probe = http.createServer();await listen(probe);await close(probe);
});
