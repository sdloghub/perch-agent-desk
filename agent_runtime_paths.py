import os,shutil
from pathlib import Path
NODE=os.environ.get('PERCH_NODE') or shutil.which('node') or str(next(iter((Path.home()/'.nvm/versions/node').glob('*/bin/node')),Path('/usr/local/bin/node')))
