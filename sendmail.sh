#!/bin/bash
set -e

case "$1" in
  start)
    echo "啟動 OPR SendMail..."
    docker compose up -d --build
    echo "已啟動：http://localhost:8080"
    ;;
  stop)
    echo "關閉 OPR SendMail..."
    docker compose down
    ;;
  restart)
    echo "重啟 OPR SendMail..."
    docker compose down
    docker compose up -d --build
    echo "已重啟：http://localhost:8080"
    ;;
  logs)
    docker compose logs -f
    ;;
  status)
    docker compose ps
    ;;
  *)
    echo "用法: $0 {start|stop|restart|logs|status}"
    exit 1
    ;;
esac
