// Local browser entry point; keeps the existing API key and account checks.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const {randomBytes} = require('node:crypto');
const root = path.resolve(__dirname, '..');

function createWebServer({backendPort, key, dist = path.join(root, 'frontend', 'dist')}) {
  return http.createServer(async (req, res) => {
    const origin = `http://127.0.0.1:${req.socket.localPort}`;
    // Reject DNS rebinding and requests initiated by unrelated websites.
    if (req.headers.host !== new URL(origin).host ||
        (req.headers.origin && req.headers.origin !== origin) ||
        req.headers['sec-fetch-site'] === 'cross-site') {
      res.writeHead(403).end('Forbidden'); return;
    }
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Content-Security-Policy', "frame-ancestors 'none'");
    res.setHeader('Cache-Control', 'no-store');
    if (req.url.startsWith('/api/')) {
      // Forward the client's key, never supply it on behalf of an unauthenticated request.
      const proxy = http.request({hostname:'127.0.0.1', port:backendPort,
        path:req.url, method:req.method, headers:{...req.headers, host:`127.0.0.1:${backendPort}`}}, upstream => {
        res.writeHead(upstream.statusCode, upstream.headers);
        upstream.pipe(res);
      });
      proxy.on('error', () => {
        if (!res.headersSent) res.writeHead(503, {'Content-Type':'application/json'});
        res.end(JSON.stringify({detail:'本地服务已停止，请重新启动网页版。'}));
      });
      req.on('aborted', () => proxy.destroy());
      req.pipe(proxy); return;
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') {res.writeHead(405).end();return;}
    if (req.url === '/web-config.json') {
      res.writeHead(200, {'Content-Type':'application/json'});
      res.end(JSON.stringify({key}));return;
    }
    try {
      const pathname = decodeURIComponent(new URL(req.url, origin).pathname);
      const file = path.resolve(dist, '.' + (pathname === '/' ? '/index.html' : pathname));
      if (!file.startsWith(path.resolve(dist) + path.sep)) {res.writeHead(404).end();return;}
      const data = await fs.promises.readFile(file);
      const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
      res.writeHead(200, {'Content-Type':types[path.extname(file)] || 'application/octet-stream'});
      res.end(req.method === 'HEAD' ? undefined : data);
    } catch {res.writeHead(404).end('Not found');}
  });
}

async function listen(server, port) {
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolve);
  });
  return server.address().port;
}

async function main() {
  const key = randomBytes(32).toString('hex');
  const reservation = http.createServer();
  const backendPort = await listen(reservation, 0);
  await new Promise(resolve => reservation.close(resolve));
  const server = createWebServer({backendPort, key});
  // Claim the web port before starting a backend that can apply migrations.
  const port = await listen(server, Number(process.env.BIBLE_WEB_PORT || 5173));
  const dataDir = process.env.BIBLE_DATA_DIR || path.join(os.homedir(), 'Library/Application Support/圣经讲义/library');
  const backend = spawn(path.join(root, '.venv/bin/python'), [path.join(root, 'backend/launcher.py')], {
    cwd:root, env:{...process.env, BIBLE_DATA_DIR:dataDir, BIBLE_APP_KEY:key, BIBLE_PORT:String(backendPort)},
    stdio:['ignore','ignore','ignore']
  });
  let stopped = false;
  const stop = (code = 0) => {
    if (stopped) return;
    stopped = true;backend.kill('SIGTERM');server.close();server.closeAllConnections();process.exitCode=code;
  };
  process.on('SIGINT', () => stop());
  process.on('SIGTERM', () => stop());
  backend.on('error', () => {console.error('无法启动 Python 服务，请检查 .venv 依赖。');stop(1);});
  backend.on('exit', () => {if(!stopped){console.error('本地服务已停止。');stop(1);}});
  for (let i=0;i<100 && !stopped;i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${backendPort}/api/status`, {
        headers:{'X-App-Key':key},signal:AbortSignal.timeout(1000)
      });
      if(response.ok) {
        const status = await response.json();
        if(!status.connected) console.error(status.error || '请在网页中配置数据库连接。');
        console.log(`网页版已启动：http://127.0.0.1:${port}`);
        console.log('仅供本机访问；关闭此进程后网页版停止。');return;
      }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  if(!stopped){console.error('服务启动超时。');stop(1);}
}

module.exports = {createWebServer};
if (require.main === module) main().catch(() => {console.error('网页版启动失败，请检查端口是否被占用。');process.exitCode=1;});
