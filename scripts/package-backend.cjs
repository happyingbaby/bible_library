const {spawnSync} = require('node:child_process');
const path = require('node:path');

const project = process.platform === 'win32' && process.arch === 'ia32' ? 'backend/win32' : 'backend';
const result = spawnSync('uv', ['run', '--project', project, '--locked', '--group', 'build', 'python', 'backend/scripts/package_backend.py'], {
  cwd: path.resolve(__dirname, '..'),
  stdio: 'inherit',
});
process.exit(result.status ?? 1);
