"""
View Bronze Raw Metadata

Simple CLI to view what's been loaded.
"""
import sys
from .metadata_tracker import print_status_summary

if __name__ == "__main__":
    print_status_summary()
