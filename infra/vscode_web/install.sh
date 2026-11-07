#!/usr/bin/env bash
set -euo pipefail
python -m pip install --index-url https://packagefeedproxy.microsoft.io/pypi/simple/ -r requirements.txt --user -q
printf '%s\n' 'FactoryPulse dependencies installed. Configure this checkout using docs/DeploymentGuide.md.'
