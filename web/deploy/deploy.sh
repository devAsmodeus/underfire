#!/usr/bin/env bash
# Выкладка клиента на свой сервер (Ubuntu, nginx). Адрес — UF_DEPLOY_HOST в .env (например root@1.2.3.4),
# домен — UF_DOMAIN там же (необязательно: без домена nginx отвечает по IP на любой Host).
#
#   web/deploy/deploy.sh             собрать web/dist и выложить
#   web/deploy/deploy.sh --nginx     + поставить nginx (если его нет) и обновить конфиг сайта
#   web/deploy/deploy.sh --assets    + скачать на сервер ассеты релиза (≈450 МБ, один раз на версию)
#   web/deploy/deploy.sh --status    только показать состояние
#
# На сервере: /var/www/underfire/dist — сборка Vite (заменяется целиком, атомарно),
# /var/www/underfire/assets — ассеты релиза, nginx отдаёт их как /assets/ (underfire.nginx.conf).
# Ассеты сервер скачивает сам из GitHub Release скриптом tools/fetch_assets.py (одна стандартная
# библиотека), поэтому с компьютера уходит только сборка (~1 МБ).
set -euo pipefail
cd "$(dirname "$0")/../.."

env_var() { grep -m1 "^$1=" .env 2>/dev/null | cut -d= -f2- || true; }
HOST="${UF_DEPLOY_HOST:-$(env_var UF_DEPLOY_HOST)}"
DOMAIN="${UF_DOMAIN:-$(env_var UF_DOMAIN)}"
[ -n "$HOST" ] || { echo "нет UF_DEPLOY_HOST в .env (образец — .env.example)"; exit 1; }
SITE=/var/www/underfire
ssh_() { ssh -o BatchMode=yes "$HOST" "$@"; }

status() {
  ssh_ "echo \"nginx: \$(systemctl is-active nginx 2>/dev/null || echo нет)\"; \
        echo \"ufw: \$(ufw status 2>/dev/null | head -1 | cut -d' ' -f2- || echo нет)\"; \
        du -sh $SITE/dist $SITE/assets 2>/dev/null || true; \
        grep -m2 -E '\"(version|built)\"' $SITE/assets/manifest.json 2>/dev/null || echo 'ассетов нет'; \
        for p in / /assets/manifest.json; do \
          echo \"GET \$p (на сервере) → \$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1\$p)\"; done"
  # Снаружи, с этой машины: если на сервере 200, а здесь нет ответа — порт 80 закрыт файрволом
  # (ufw на сервере или Hetzner Cloud Firewall в консоли).
  local ip="${HOST#*@}"
  echo "GET http://$ip/ (снаружи) → $(curl -s -o /dev/null -m 10 -w '%{http_code}' "http://$ip/" || echo 'нет ответа: порт 80 закрыт?')"
}

for arg in "$@"; do
  case "$arg" in --nginx|--assets|--status) ;; *) echo "неизвестный флаг: $arg"; exit 1 ;; esac
done
[[ " $* " == *" --status "* ]] && { status; exit 0; }

echo "[deploy] → $HOST"
if [[ " $* " == *" --nginx "* ]]; then
  ssh_ "command -v nginx >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx; }"
  sed "s|__DOMAIN__|${DOMAIN:-_}|" web/deploy/underfire.nginx.conf | ssh_ "cat > /etc/nginx/sites-available/underfire"
  ssh_ "set -e; install -d -m 755 $SITE; \
        ln -sf /etc/nginx/sites-available/underfire /etc/nginx/sites-enabled/underfire; \
        rm -f /etc/nginx/sites-enabled/default; \
        nginx -t -q && systemctl enable -q --now nginx && systemctl reload nginx; \
        if ufw status 2>/dev/null | grep -q '^Status: active'; then ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; fi"
  echo "  nginx: сайт underfire (${DOMAIN:-по IP}), стандартный сайт default отключён, в ufw открыты 80 и 443"
fi

(cd web && npm ci --no-audit --no-fund --silent && npm run build --silent)
[ -f web/dist/index.html ] || { echo "нет web/dist/index.html"; exit 1; }
COPYFILE_DISABLE=1 tar czf - --no-xattrs -C web/dist . \
  | ssh_ "set -e; install -d -m 755 $SITE; rm -rf $SITE/dist.new $SITE/dist.old; mkdir $SITE/dist.new; \
          tar xzf - -C $SITE/dist.new; \
          if [ -d $SITE/dist ]; then mv $SITE/dist $SITE/dist.old; fi; \
          mv $SITE/dist.new $SITE/dist; rm -rf $SITE/dist.old"
echo "  сборка: web/dist → $SITE/dist"

if [[ " $* " == *" --assets "* ]]; then
  ssh_ "cat > /tmp/underfire_fetch_assets.py" < tools/fetch_assets.py
  ssh_ "python3 /tmp/underfire_fetch_assets.py --out $SITE/assets && rm -f /tmp/underfire_fetch_assets.py"
  echo "  ассеты: релиз → $SITE/assets"
fi

status
