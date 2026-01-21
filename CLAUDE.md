# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Overview

Docker-based HTPC automation: qBittorrent+WireGuard VPN, Jackett, Sonarr, Radarr, Bazarr, Organizr, FlareSolverr, Firefox.

## Commands

```bash
# Services
docker-compose up -d
docker-compose down
docker-compose logs -f <service>

# Rebuild qbittorrent (VueTorrent UI)
docker-compose build qbittorrent

# Backup (saves config + .env to /mnt/synology-backups)
./run-backup.sh
```

## Environment

Required `.env`:
```bash
TZ=America/New_York
PUID=1000  # id $USER
PGID=1000
ROOT=/media                  # Config root
MEDIA_ROOT=/path/to/media    # Media files
```

## Architecture

**VPN routing** (network_mode: service:vpn): qbittorrent, jackett, flaresolverr, firefox
- WireGuard config: `${ROOT}/config/wireguard/wg0.conf`
- Ports exposed on VPN container

**Volumes**:
- `${ROOT}/config/<service>` - Configs
- `${MEDIA_ROOT}/downloads` - qBittorrent downloads
- `${MEDIA_ROOT}/complete/tv` - Sonarr output
- `${MEDIA_ROOT}/complete/movies` - Radarr output

**Ports**: qBittorrent 8112, Jackett 9117, Sonarr 8989, Radarr 7878, Bazarr 6767, Organizr 8789

## Key Points

- Services use pinned versions (sonarr:3.0.10, radarr:4.5.2, jackett:0.24.338, etc)
- Jackett provides Torznab feeds to Sonarr/Radarr using global API key
- Custom qBittorrent image adds VueTorrent UI (`.docker/vuetorrent/Dockerfile`)
- Fix permissions: `chown -R ${PUID}:${PGID} ${ROOT} ${MEDIA_ROOT}`
- VPN test: `docker-compose exec qbittorrent curl ifconfig.me`
