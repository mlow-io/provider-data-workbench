"""Immutable defaults shipped with the Python distribution; no checkout lookup."""
from importlib.resources import files


def assets():
    return files('provider_directory_truth_layer').joinpath('assets')
