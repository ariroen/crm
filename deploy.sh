#!/bin/bash
# ============================================
# 🪖 Контракт-61: Скрипт деплоя
# Для VPS/VDS (Ubuntu 22.04+, Debian 12+)
# ============================================

set -euo pipefail

# ── Конфигурация ──────────────────────────────────────────
PROJECT_NAME="contract61"
PROJECT_DIR="/opt/${PROJECT_NAME}"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATA_DIR="${PROJECT_DIR}/data"
LOG_FILE="/var/log/${PROJECT_NAME}.log"
SERVICE_NAME="${PROJECT_NAME}_bot"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[✅]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠️]${NC} $1"; }
err() { echo -e "${RED}[❌]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[ℹ️]${NC} $1"; }

# ── Проверки ──────────────────────────────────────────────

check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "Запустите с sudo: sudo bash deploy.sh"
    fi
}

check_env() {
    if [[ ! -f "${REPO_DIR}/.env" ]]; then
        if [[ -f "${REPO_DIR}/.env.example" ]]; then
            warn ".env не найден. Копирую .env.example → .env"
            cp "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"
            warn "ОБЯЗАТЕЛЬНО заполните .env перед запуском!"
            warn "  nano ${REPO_DIR}/.env"
            exit 1
        else
            err ".env и .env.example не найдены!"
        fi
    fi

    # Проверяем ключевые переменные
    source "${REPO_DIR}/.env"
    if [[ -z "${BOT_TOKEN:-}" || "${BOT_TOKEN}" == "your_bot_token_here" ]]; then
        err "BOT_TOKEN не заполнен в .env!"
    fi
    if [[ -z "${GROQ_API_KEY:-}" || "${GROQ_API_KEY}" == "gsk_your_key_here" ]]; then
        err "GROQ_API_KEY не заполнен в .env!"
    fi
    log "Переменные окружения OK"
}

# ── Установка зависимостей ────────────────────────────────

install_system_deps() {
    info "Обновление системы и установка зависимостей..."
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv docker.io docker-compose curl git > /dev/null 2>&1
    systemctl enable docker
    systemctl start docker
    log "Системные зависимости установлены"
}

# ── Настройка проекта ─────────────────────────────────────

setup_project() {
    info "Настройка директорий..."

    mkdir -p "${PROJECT_DIR}" "${BACKUP_DIR}" "${DATA_DIR}"

    # Копируем файлы проекта
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='data/' --exclude='.env' \
        "${REPO_DIR}/" "${PROJECT_DIR}/"

    # .env копируем отдельно (не перезаписываем если уже есть)
    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        cp "${REPO_DIR}/.env" "${PROJECT_DIR}/.env"
    fi

    log "Проект скопирован в ${PROJECT_DIR}"
}

# ── Docker Deploy ─────────────────────────────────────────

deploy_docker() {
    info "Деплой через Docker..."

    cd "${PROJECT_DIR}"

    # Остановить старый контейнер (если есть)
    docker-compose down 2>/dev/null || true

    # Собрать и запустить
    docker-compose up --build -d

    # Проверить что запустился
    sleep 3
    if docker ps | grep -q "${PROJECT_NAME}"; then
        log "Docker-контейнер запущен!"
        docker logs --tail 10 "${PROJECT_NAME}_bot"
    else
        err "Контейнер не запустился! Логи:"
        docker logs "${PROJECT_NAME}_bot" 2>&1 | tail -20
    fi
}

# ── Systemd Deploy (без Docker) ──────────────────────────

deploy_systemd() {
    info "Деплой через systemd..."

    cd "${PROJECT_DIR}"

    # Virtual environment
    if [[ ! -d "${PROJECT_DIR}/venv" ]]; then
        python3 -m venv "${PROJECT_DIR}/venv"
        log "Виртуальное окружение создано"
    fi

    "${PROJECT_DIR}/venv/bin/pip" install -q -r requirements.txt
    log "Python-зависимости установлены"

    # Systemd unit
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Контракт-61: Диспетчер (Telegram Bot)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/python -m app.main
Restart=always
RestartSec=10
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable ${SERVICE_NAME}
    systemctl restart ${SERVICE_NAME}

    sleep 2
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        log "Сервис ${SERVICE_NAME} запущен!"
        systemctl status ${SERVICE_NAME} --no-pager | head -10
    else
        err "Сервис не запустился! Логи:"
        journalctl -u ${SERVICE_NAME} --no-pager -n 20
    fi
}

# ── Бэкап ─────────────────────────────────────────────────

setup_backup() {
    info "Настройка автобэкапов..."

    cat > /etc/cron.d/${PROJECT_NAME}_backup << EOF
# Бэкап БД Контракт-61 каждые 6 часов
0 */6 * * * root cp ${DATA_DIR}/contract61.db ${BACKUP_DIR}/contract61_\$(date +\%Y\%m\%d_\%H\%M).db && find ${BACKUP_DIR} -name "*.db" -mtime +7 -delete
EOF

    log "Автобэкап настроен (каждые 6 часов, хранение 7 дней)"
}

# ── Управление ────────────────────────────────────────────

show_status() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🪖 Контракт-61: Статус"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if docker ps 2>/dev/null | grep -q "${PROJECT_NAME}"; then
        echo -e "Docker:  ${GREEN}✅ Работает${NC}"
        docker ps --filter "name=${PROJECT_NAME}" --format "  {{.Names}} | {{.Status}} | {{.Ports}}"
    elif systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
        echo -e "Systemd: ${GREEN}✅ Работает${NC}"
        echo "  $(systemctl show ${SERVICE_NAME} -p ActiveState,SubState --value | tr '\n' ' ')"
    else
        echo -e "Статус:  ${RED}❌ Не запущен${NC}"
    fi

    echo ""
    if [[ -f "${DATA_DIR}/contract61.db" ]]; then
        local db_size=$(du -h "${DATA_DIR}/contract61.db" | cut -f1)
        echo "БД: ${db_size} (${DATA_DIR}/contract61.db)"
    fi
    local backup_count=$(ls -1 "${BACKUP_DIR}"/*.db 2>/dev/null | wc -l)
    echo "Бэкапов: ${backup_count}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ── Главное меню ──────────────────────────────────────────

usage() {
    echo ""
    echo "🪖 Контракт-61: Скрипт деплоя"
    echo ""
    echo "Использование: sudo bash deploy.sh [команда]"
    echo ""
    echo "Команды:"
    echo "  install    — Полная установка (система + Docker)"
    echo "  systemd    — Установка через systemd (без Docker)"
    echo "  update     — Обновить код и перезапустить"
    echo "  status     — Показать статус"
    echo "  logs       — Показать логи"
    echo "  stop       — Остановить"
    echo "  restart    — Перезапустить"
    echo "  backup     — Сделать бэкап сейчас"
    echo ""
}

# ── Обработка команд ──────────────────────────────────────

case "${1:-}" in
    install)
        check_root
        check_env
        install_system_deps
        setup_project
        deploy_docker
        setup_backup
        show_status
        ;;
    systemd)
        check_root
        check_env
        install_system_deps
        setup_project
        deploy_systemd
        setup_backup
        show_status
        ;;
    update)
        check_root
        setup_project
        if docker ps 2>/dev/null | grep -q "${PROJECT_NAME}"; then
            cd "${PROJECT_DIR}" && docker-compose up --build -d
        else
            systemctl restart ${SERVICE_NAME}
        fi
        log "Обновлено и перезапущено!"
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        if docker ps 2>/dev/null | grep -q "${PROJECT_NAME}"; then
            docker logs -f --tail 50 "${PROJECT_NAME}_bot"
        else
            tail -f -n 50 "${LOG_FILE}"
        fi
        ;;
    stop)
        check_root
        docker-compose -f "${PROJECT_DIR}/docker-compose.yml" down 2>/dev/null || true
        systemctl stop ${SERVICE_NAME} 2>/dev/null || true
        log "Остановлено"
        ;;
    restart)
        check_root
        if docker ps 2>/dev/null | grep -q "${PROJECT_NAME}"; then
            cd "${PROJECT_DIR}" && docker-compose restart
        else
            systemctl restart ${SERVICE_NAME}
        fi
        log "Перезапущено!"
        ;;
    backup)
        cp "${DATA_DIR}/contract61.db" "${BACKUP_DIR}/contract61_$(date +%Y%m%d_%H%M).db"
        log "Бэкап создан: ${BACKUP_DIR}/contract61_$(date +%Y%m%d_%H%M).db"
        ;;
    *)
        usage
        ;;
esac
