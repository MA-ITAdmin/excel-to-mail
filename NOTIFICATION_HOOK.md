# 任務完成通知系統 (Task Completion Hook)

您已成功建設一個 macOS 桌面通知系統。當我完成您交代的編碼任務時，系統會自動發送通知並記錄到日誌。

## 📋 文件說明

- **`notify.py`** — Python 核心通知模組，用來發送 macOS 桌面通知
- **`task_complete.sh`** — Shell 腳本包裝器，便於快速調用
- **`notification.log`** — 通知日誌檔案（自動生成）

## 🚀 使用方式

### 方式 1：直接調用 Python 腳本
```bash
python3 notify.py "任務標題" "任務描述"
```

**例子：**
```bash
python3 notify.py "✓ 功能已實現" "已為前端新增登入頁面"
python3 notify.py "✓ Bug 已修復" "修復了 Excel 解析的標題欄問題"
```

### 方式 2：使用 Shell 腳本（更簡潔）
```bash
./task_complete.sh "任務描述"
```

**例子：**
```bash
./task_complete.sh "API 路由已重構完成"
./task_complete.sh "前端樣式已更新"
```

### 方式 3：從後端代碼呼叫
在 Python 後端或 Node.js 中，可以調用通知系統：

**Python 後端範例：**
```python
import subprocess

def notify_task_complete(task_name):
    subprocess.run([
        "python3", 
        "/Users/chao/Documents/projects/opr-sendmail/notify.py",
        "✓ 編碼任務完成",
        task_name
    ])
```

**Node.js 前端/腳本範例：**
```javascript
const { execSync } = require('child_process');

function notifyTaskComplete(taskName) {
    try {
        execSync(`python3 notify.py "✓ 編碼任務完成" "${taskName}"`);
    } catch (error) {
        console.error('通知發送失敗:', error);
    }
}
```

## 💾 日誌查看

所有通知都會被記錄到 `notification.log`，您可以查看完成的任務歷史：

```bash
cat notification.log
```

## 🎯 工作流程

當我在這個對話中完成您的編碼任務時：
1. ✅ 我會在對話中報告任務已完成
2. 📲 我會呼叫通知系統發送桌面通知
3. 📝 通知內容會記錄到 `notification.log`
4. 🔔 您會在 macOS 通知中心收到完成提示

## 🔧 自訂設定

如果需要修改通知內容或日誌位置，可編輯 `notify.py` 中的以下部分：

```python
log_file = "/Users/chao/Documents/projects/opr-sendmail/notification.log"
```

## ⚠️ 注意事項

- 需要 Python 3.6+
- 僅在 macOS 上有效
- 通知可能需要允許 Terminal/iTerm 權限才能顯示
  - 系統偏好設定 → 通知 → Terminal → 允許通知

---

**建立時間：** 2026-03-24  
**系統：** macOS  
**狀態：** ✅ 已就緒
