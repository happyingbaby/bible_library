"""Add local DB credentials to a downloaded CI DMG; never upload the output."""
import argparse
import json
import plistlib
import subprocess
import tempfile
from pathlib import Path


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT)


def finalize(source, output, arch, config_path):
    config = json.loads(config_path.read_text())
    expected = {'host':'39.102.143.118', 'port':3306, 'username':'bible_library', 'database':'bible_library'}
    if any(config.get(k) != v for k,v in expected.items()) or not config.get('password'):
        raise ValueError('Missing credentials or unexpected database target')
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bible-internal-dmg-') as temporary:
        stage = Path(temporary)/'stage'
        stage.mkdir()
        mounted = plistlib.loads(run('hdiutil','attach','-readonly','-nobrowse','-plist',str(source)))
        volumes = [Path(e['mount-point']) for e in mounted['system-entities'] if 'mount-point' in e]
        if not volumes:
            raise ValueError('DMG did not expose a mounted volume')
        try:
            apps = [app for volume in volumes for app in volume.glob('*.app')]
            if len(apps) != 1:
                raise ValueError('Expected exactly one application in the DMG')
            app = stage/apps[0].name
            run('ditto',str(apps[0]),str(app))
        finally:
            for volume in reversed(volumes):
                run('hdiutil','detach',str(volume))
        binaries = [app/'Contents/MacOS/圣经讲义', app/'Contents/Resources/backend/bible-backend']
        expected_arch = 'x86_64' if arch=='x64' else 'arm64'
        for binary in binaries:
            if run('lipo','-archs',str(binary)).decode().strip() != expected_arch:
                raise ValueError('Application or backend architecture mismatch')
        defaults = list((app/'Contents/Resources/backend').rglob('database-defaults.json'))
        if len(defaults) != 1:
            raise ValueError('Expected exactly one bundled database configuration')
        defaults[0].write_text(json.dumps(config),encoding='utf-8')
        defaults[0].chmod(0o600)
        run('codesign','--force','--deep','--sign','-',str(app))
        run('codesign','--verify','--deep','--strict',str(app))
        (stage/'Applications').symlink_to('/Applications',target_is_directory=True)
        run('hdiutil','create','-volname','圣经讲义','-srcfolder',str(stage),'-format','UDZO',str(output))
        output.chmod(0o600)
        run('hdiutil','verify',str(output))
    print(f'Internal {arch} DMG created and verified: {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--arch',choices=['arm64','x64'],required=True)
    parser.add_argument('--config',type=Path,default=Path(__file__).resolve().parents[1]/'.local/database-defaults.json')
    args=parser.parse_args()
    try:
        finalize(args.source.resolve(),args.output.resolve(),args.arch,args.config)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f'Packaging command failed: {exc.cmd[0]} (exit {exc.returncode})')
