FROM lscr.io/linuxserver/qbittorrent:4.6.1

ARG VUETORRENT_PATH="/opt"
ARG VUETORRENT_VERSION="1.5.10"

RUN wget "https://github.com/WDaan/VueTorrent/releases/download/v${VUETORRENT_VERSION}/vuetorrent.zip" -O /tmp/vuetorrent.zip \
    && unzip /tmp/vuetorrent.zip -d "${VUETORRENT_PATH}" \
    && rm -f /tmp/vuetorrent.zip
