FROM lscr.io/linuxserver/qbittorrent:14.3.9.99202110311443-7435-01519b5e7ubuntu20.04.1-ls162

ARG VUETORRENT_PATH="/opt"

COPY vuetorrent.zip /tmp/vuetorrent.zip

RUN unzip /tmp/vuetorrent.zip -d "${VUETORRENT_PATH}" \
    && rm -f /tmp/vuetorrent.zip
