FROM lscr.io/linuxserver/qbittorrent:20.04.1

ARG VUETORRENT_PATH="/opt"

RUN apt update -y && apt install -y jq wget curl \
    && DOWNLOAD_URL=$(curl -s https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest | jq -r '.assets[0].browser_download_url') \
    && echo "Downloading VueTorrent from ${DOWNLOAD_URL}" \
    && wget "$DOWNLOAD_URL" -O /tmp/vuetorrent.zip \
    && unzip /tmp/vuetorrent.zip -d "${VUETORRENT_PATH}" \
    && rm -f /tmp/vuetorrent.zip \
    && apt autoremove -y \
    && apt purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*
