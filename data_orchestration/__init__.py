"""
Data Orchestration Package

Provides orchestration tools for the medallion architecture pipeline:
- bronze_raw: Phase 1 - Raw data ingestion from EDR API
- bronze_refined: Phase 2 - Transform JSON to Parquet (future)
- silver: Phase 3 - Data quality and validation (future)
"""

__version__ = "1.0.0"
