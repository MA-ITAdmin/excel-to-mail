#!/bin/bash
# 快速發送完成通知的 Shell 腳本
# 用法: ./task_complete.sh "任務名稱"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_NAME="${1:-任務已完成}"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 調用 Python 通知腳本
python3 "${SCRIPT_DIR}/notify.py" "✓ 編碼任務完成" "${TASK_NAME}"

# 也可選擇使用原生 osascript（如果系統沒有 Python）
# osascript -e "display notification \"${TASK_NAME}\" with title \"✓ 編碼任務完成\""

echo "[${TIMESTAMP}] 已通知: ${TASK_NAME}" >> "${SCRIPT_DIR}/notifications.log"
