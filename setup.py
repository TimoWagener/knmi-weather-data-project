"""
Setup script for KNMI Weather Data Pipeline
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="knmi-weather-pipeline",
    version="1.0.0",
    author="Weather Data Pipeline Project",
    description="Modern data lakehouse for KNMI weather data using medallion architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/LocalWeatherDataProject",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "knmi-ingest=src.ingest_bronze_raw:main",
            "knmi-refine=src.transform_bronze_refined:main",
            "knmi-silver=src.transform_silver:main",
            "knmi-query=src.query_demo:main",
        ],
    },
)
