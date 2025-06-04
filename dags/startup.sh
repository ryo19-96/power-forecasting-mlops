#!/bin/bash
# 環境変数の設定スクリプト
set -euo pipefail

# MWAA の全プロセス, 各プロセスで環境変数を読み込むための設定
echo "export RAW_BUCKET=power-forecasting-raw-data-dev" >> /etc/profile.d/mwaa_env.sh
echo "export PROCESSED_BUCKET=power-forecasting-processed-data-dev" >> /etc/profile.d/mwaa_env.sh