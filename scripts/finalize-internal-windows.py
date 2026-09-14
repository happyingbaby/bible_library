"""Repackage a native Windows x64 CI installer with local DB defaults. Never upload output."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
KEYS = ('BIBLE_DB_HOST', 'BIBLE_DB_PORT', 'BIBLE_DB_USER', 'BIBLE_DB_PASSWORD', 'BIBLE_DB_NAME')


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.STDOUT)


def verify_x64(binary):
    with binary.open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('Expected a Windows PE executable')
        stream.seek(0x3c)
        offset = struct.unpack('<I', stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b'PE\0\0' or struct.unpack('<H', stream.read(2))[0] != 0x8664:
            raise ValueError('Application or backend is not Windows x64')


def extract_installer(sevenzip, source, target):
    target.mkdir()
    run(sevenzip, 'x', str(source), '-o' + str(target), '-y')
    archives = list(target.rglob('app-64.7z'))
    if len(archives) != 1:
        raise ValueError('Expected exactly one Windows x64 application archive')
    app = target / 'unpacked'
    run(sevenzip, 'x', str(archives[0]), '-o' + str(app), '-y')
    verify_x64(app / '圣经讲义.exe')
    verify_x64(app / 'resources/backend/bible-backend.exe')
    return app


def finalize(source, output, config_path):
    config = dotenv_values(config_path)
    if any(not config.get(key) for key in KEYS):
        raise ValueError('Missing database values in configuration')
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    sevenzip = run('node', '-e', 'require("app-builder-lib/out/toolsets/7zip").getPath7za().then(console.log)').decode().strip().splitlines()[-1]
    # Keep credentials out of command arguments, logs, source control, and CI artifacts.
    previous_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix='bible-internal-windows-') as temporary:
            stage = Path(temporary)
            app = extract_installer(sevenzip, source, stage / 'source')
            print('Native Windows application and backend verified as x64.', flush=True)
            defaults = list((app / 'resources/backend').rglob('.env'))
            if len(defaults) != 1:
                raise ValueError('Expected exactly one bundled database configuration')
            defaults[0].write_text('', encoding='utf-8')
            for key in KEYS:
                set_key(defaults[0], key, config[key], quote_mode='always', encoding='utf-8')
            print('Building internal NSIS installer with local database defaults...', flush=True)
            run('node', 'node_modules/electron-builder/cli.js', '--win', 'nsis', '--x64',
                '--prepackaged', str(app), '--publish', 'never',
                '--config.win.signAndEditExecutable=false',
                '--config.directories.output=' + str(stage / 'output'),
                '--config.artifactName=' + output.name)
            built = stage / 'output' / output.name
            print('Re-extracting final installer for verification...', flush=True)
            verified = extract_installer(sevenzip, built, stage / 'verification')
            actual = dotenv_values(verified / 'resources/backend/_internal/.env')
            if any(actual.get(key) != config[key] for key in KEYS):
                raise ValueError('Repacked database configuration does not match')
            # Copy only the verified installer, excluding intermediate archives and metadata.
            import shutil
            shutil.copyfile(built, output)
            output.chmod(0o600)
    finally:
        os.umask(previous_umask)
    print(f'Internal Windows x64 installer created; PE architecture and DB defaults verified: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / '.env')
    args = parser.parse_args()
    try:
        finalize(args.source.resolve(), args.output.resolve(), args.config.resolve())
    except subprocess.CalledProcessError as exc:
        # Tool output may contain paths to private staging files; omit it from normal logs.
        raise SystemExit(f'Packaging command failed: {exc.cmd[0]} (exit {exc.returncode})')
