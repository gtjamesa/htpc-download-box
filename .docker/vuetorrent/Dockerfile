FROM lscr.io/linuxserver/qbittorrent:4.6.5

ARG VUETORRENT_PATH="/opt"

RUN DOWNLOAD_URL=$(curl -s https://api.github.com/repos/VueTorrent/VueTorrent/releases/latest | jq -r '.assets[0].browser_download_url') \
    && echo "Downloading VueTorrent from ${DOWNLOAD_URL}" \
    && wget "$DOWNLOAD_URL" -O /tmp/vuetorrent.zip \
    && unzip /tmp/vuetorrent.zip -d "${VUETORRENT_PATH}" \
    && rm -f /tmp/vuetorrent.zip
