"""Build a local macOS Chromium app from the pinned Electron distribution."""
from pathlib import Path
import plistlib,shutil,subprocess
ROOT=Path(__file__).resolve().parent
source=ROOT/'node_modules/electron/dist/Electron.app'
dest=ROOT/'Perch.app'
if dest.exists():raise SystemExit('Perch.app already exists; preserve it or remove it explicitly before rebuilding')
shutil.copytree(source,dest,symlinks=True)
plist=dest/'Contents/Info.plist';data=plistlib.loads(plist.read_bytes())
data.update(CFBundleDisplayName='Perch · 栖',CFBundleName='Perch',CFBundleIdentifier='app.perch.agentdesk',CFBundleShortVersionString='0.1.0')
plist.write_bytes(plistlib.dumps(data))
resources=dest/'Contents/Resources/app';resources.mkdir()
for name in ['main.cjs','package.json']:shutil.copy2(ROOT/name,resources/name)
subprocess.run(['codesign','--force','--deep','--sign','-',str(dest)],check=True)
print(dest)
