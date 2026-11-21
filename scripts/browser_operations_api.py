"""Serve one owned combined rehearsal to the headless operations browser test."""
import argparse
import os
from pathlib import Path
import socket

import uvicorn

from provider_directory_truth_layer.operations_rehearsal import rehearse
from provider_directory_truth_layer.intake_api import create_workbench

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
args = parser.parse_args()
report = rehearse(args.root)
os.environ['PDTL_ASSISTANT_ENABLED'] = '0'
app = create_workbench(args.root / 'storage/directory.sqlite3', args.root / 'storage', demo=False)


@app.get('/__test/operations')
def operations():
    return report


with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    print(f'PDTL_OPERATIONS_URL=http://127.0.0.1:{listener.getsockname()[1]}', flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level='warning')).run(sockets=[listener])
