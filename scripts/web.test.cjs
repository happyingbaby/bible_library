const {test} = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {createWebServer} = require('./web.cjs');

test('local web gateway preserves API authentication and rejects foreign origins', async t => {
  const backend = http.createServer((req,res) => {
    res.writeHead(req.headers['x-app-key'] === 'test-key' ? 200 : 403, {'Content-Type':'application/json'});
    res.end(JSON.stringify({authorization:req.headers.authorization || ''}));
  });
  await new Promise(resolve => backend.listen(0, '127.0.0.1', resolve));
  const web = createWebServer({backendPort:backend.address().port,key:'test-key'});
  t.after(() => {web.closeAllConnections();web.close();backend.closeAllConnections();backend.close();});
  await new Promise(resolve => web.listen(0,'127.0.0.1',resolve));
  const base = `http://127.0.0.1:${web.address().port}`;
  const config = await fetch(base + '/web-config.json');
  assert.equal(config.headers.get('cache-control'),'no-store');
  assert.deepEqual(await config.json(),{key:'test-key'});
  for(const headers of [{Host:'foreign.example'}, {Origin:'https://foreign.example'}, {'Sec-Fetch-Site':'cross-site'}]) {
    const status = await new Promise((resolve,reject) => {
      http.get(base + '/web-config.json',{headers},response => {response.resume();resolve(response.statusCode);}).on('error',reject);
    });
    assert.equal(status,403,JSON.stringify(headers));
  }
  assert.equal((await fetch(base + '/api/me')).status,403);
  const authorized = await fetch(base + '/api/me',{headers:{'X-App-Key':'test-key',Authorization:'Bearer test-session'}});
  assert.equal(authorized.status,200);
  assert.deepEqual(await authorized.json(),{authorization:'Bearer test-session'});
  assert.equal((await fetch(base + '/%2e%2e%2fpackage.json')).status,404);
});
