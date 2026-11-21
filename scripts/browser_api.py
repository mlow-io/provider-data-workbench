"""An E2E server with invocation-owned storage and no server reuse."""
import os
from pathlib import Path
import subprocess
import tempfile

from demo_fixtures import generate
root = Path(tempfile.mkdtemp(prefix='browser-'))
# The Playwright invocation owns these inputs, as well as its separate database.
fixtures = Path(os.environ.get('PDTL_BROWSER_INPUTS', str(root/'inputs')))
generate(fixtures)
print(f'Browser root: {root}; inputs: {fixtures}', flush=True)
os.environ['PDTL_ROOT'] = str(root)
os.environ['PDTL_DB'] = str(root / 'directory.sqlite3')
os.environ['PYTHONPATH'] = 'src'
os.environ['PDTL_DEMO'] = '1'
subprocess.run(['python3','-m','provider_directory_truth_layer.cli','run','--as-of','2026-06-26','--payer-listings','data/raw/synthetic_payer_directory_listings.csv'], check=True)
from provider_directory_truth_layer.intake_api import create_workbench
from provider_directory_truth_layer import fhir_acquisition_api
from provider_directory_truth_layer.fhir_acquisition import Acquisition
from browser_fhir_source import start
from functools import partial
# Source injection exists only in this isolated test launcher. The production
# application still constructs the fixed public source and accepts no URL input.
fhir_acquisition_api.Acquisition = partial(Acquisition, source=start())
from provider_directory_truth_layer import mapping_assistant_api
from provider_directory_truth_layer.mapping_assistant import MappingAssistant, Configuration
from browser_mapping_model import respond
mapping_assistant_api.MappingAssistant = partial(MappingAssistant,
    configuration=Configuration(enabled=True, api_key='controlled-browser-key'), transport=respond)
import uvicorn
uvicorn.run(create_workbench(), host='127.0.0.1', port=8100)
