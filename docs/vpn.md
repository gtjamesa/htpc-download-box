We need the following Wireguard firewall rules to allow LAN access to `192.168.0.0/16`:

```ini
[Interface]
PrivateKey = PRIVATE_KEY_HERE
Address = ADDRESS_HERE
DNS = 10.64.0.1
PostUp = iptables -t nat -A POSTROUTING -o wg+ -j MASQUERADE
PostUp = HOMENET=192.168.0.0/16; DROUTE=$(ip route | grep default | awk '{print $3}'); ip route add "$HOMENET" via "$DROUTE" dev eth0; iptables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL ! -d "$HOMENET" -j REJECT && ip6tables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT
PreDown = iptables -t nat -D POSTROUTING -o wg+ -j MASQUERADE
PreDown = HOMENET=192.168.0.0/16; DROUTE=$(ip route | grep default | awk '{print $3}'); ip route delete "$HOMENET"; iptables -D OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL ! -d "$HOMENET" -j REJECT  && ip6tables -D OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT

[Peer]
PublicKey = PUBLIC_KEY
AllowedIPs = 0.0.0.0/0,::0/0
Endpoint = VPN_SERVER_ENDPOINT:51820
```

Also ensure that Docker is configured to use a different subnet in `/etc/docker/daemon.json`:

```json
{
  "debug" : true,
  "default-address-pools" : [
      {
        "base" : "172.31.0.0/16",
        "size" : 24
      }
  ]
}
```

- https://www.linuxserver.io/blog/routing-docker-host-and-container-traffic-through-wireguard
- https://mullvad.net/en/help/easy-wireguard-mullvad-setup-linux
- https://old.reddit.com/r/linuxquestions/comments/7po3qd/checking_for_dns_leaks_on_the_command_line/
