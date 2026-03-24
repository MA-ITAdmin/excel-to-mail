# excel-to-mail

Excel 批次寄信工具，支援個人化內容與 PDF 附件。

## 部署（Server）

### 前提條件

```bash
# 安裝 Docker（Ubuntu/Debian）
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

# 將目前使用者加入 docker 群組（免 sudo）
sudo usermod -aG docker $USER && newgrp docker
```

### 首次部署

```bash
# 1. 拉取專案
git clone git@github.com:MA-ITAdmin/excel-to-mail.git
cd excel-to-mail

# 2. 建立 .env
cp .env.example .env
vi .env

# 3. 啟動
./sendmail.sh start
```

啟動後：
- 前端：`http://SERVER_IP:8080`
- 後端：`http://SERVER_IP:8000`

> 防火牆需開放 8080 與 8000 port。

### 日常操作

```bash
./sendmail.sh start    # 啟動
./sendmail.sh stop     # 關閉
./sendmail.sh restart  # 重啟
./sendmail.sh logs     # 查看 log
./sendmail.sh status   # 查看容器狀態
```

### 更新版本

```bash
git pull
./sendmail.sh restart
```

## Excel 格式

欄位順序（第一列為標題）：

| Sales | Attn | E-mail | Email CC | Attachment | Email Subject | Email Content |
|-------|------|--------|----------|------------|---------------|---------------|

- **Attachment**：填附件檔名（需先透過介面上傳至 `attachments/`），留空則不帶附件
- **Email Subject / Email Content**：可使用 `{Sales}`、`{Attn}` 等欄位名稱作為替換變數

點選介面上的「下載範例 Excel」可取得範例檔。
