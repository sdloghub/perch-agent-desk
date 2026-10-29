"""Install the Perch agent descriptor and a launcher; Magpie owns the key."""
from pathlib import Path
import os,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
bin_dir=Path.home()/'.local/bin';bin_dir.mkdir(parents=True,exist_ok=True)
launcher=bin_dir/'perch'
if launcher.exists() and 'Perch launcher' not in launcher.read_text():raise SystemExit('Existing perch command is unrelated; not overwritten')
launcher.write_text('#!/bin/sh\n# Perch launcher\nexec /usr/bin/open '+shlex.quote(str(ROOT/'desktop/Perch.app'))+' "$@"\n');launcher.chmod(0o755)
os.environ['PATH']=str(bin_dir)+':'+os.environ['PATH']
for args in [('plugin','add',str(ROOT/'magpie-plugin')),('perch','provider','magpie')]:
 subprocess.run(['magpie',*args],check=True,stdout=subprocess.DEVNULL)
config=Path.home()/'.config/perch/gateway.json'
if not config.exists():raise SystemExit('Magpie did not write the gateway configuration')
config.chmod(0o600)
print('Perch Agent installed and connected. Gateway credentials remain local.')
