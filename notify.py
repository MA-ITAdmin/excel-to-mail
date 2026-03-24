#!/usr/bin/env python3
"""
macOS 任務完成通知工具 
用法：python notify.py "任務標題" "任務描述"
使用 Apple Script 警告對話框發送系統提示
"""

import sys
import subprocess
from datetime import datetime


def send_alert_dialog(title: str, message: str = ""):
    """
    使用 Apple Script 發送可見的警告對話框
    這在自動化環境中最可靠
    """
    try:
        script = f'''
        tell app "System Events"
            activate
            display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK"
        end tell
        '''
        subprocess.run(
            ['osascript', '-e', script],
            check=True,
            timeout=30
        )
        return True
    except Exception as e:
        return False


def send_visual_notification(title: str, message: str):
    """
    在終端中显示視覺化通知（帶顏色和邊框）
    """
    # 颜色代碼
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    # 邊框
    border = "╔" + "═" * 58 + "╗"
    footer = "╚" + "═" * 58 + "╝"
    
    # 显示视觉通知
    print(f"\n{GREEN}{border}{RESET}")
    print(f"{GREEN}║{RESET} {BOLD}{YELLOW}✓ {title}{RESET}{' ' * (55 - len(title))} {GREEN}║{RESET}")
    print(f"{GREEN}{border.replace('╔', '╠').replace('╗', '╣')}{RESET}")
    if message:
        lines = message.split('\n')
        for line in lines:
            # 限制行寬度
            line = line[:56]
            padding = ' ' * (56 - len(line))
            print(f"{GREEN}║{RESET} {BLUE}{line}{padding} {GREEN}║{RESET}")
    print(f"{GREEN}{footer}{RESET}\n")


def log_notification(title: str, message: str):
    """
    將通知記錄到檔案
    """
    log_file = "/Users/chao/Documents/projects/opr-sendmail/notification.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {title}: {message}\n")


def send_notification(title: str, message: str = ""):
    """
    發送通知
    1. 系統警告對話框（最可靠）
    2. 終端視覺提示
    3. 記錄到日誌
    """
    # 1. 系統警告對話框（最重要）
    dialog_shown = send_alert_dialog(title, message)
    
    # 2. 視覺提示（終端內）
    send_visual_notification(title, message)
    
    # 3. 記錄到日誌
    log_notification(title, message)
    
    return dialog_shown


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python notify.py '標題' ['描述']")
        sys.exit(1)
    
    title = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else "任務已完成"
    
    send_notification(title, message)
