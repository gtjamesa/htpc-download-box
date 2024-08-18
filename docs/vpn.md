We need the following Wireguard firewall rules to allow LAN access to `192.168.0.0/16`:

```ini
PostUp = iptables -t nat -A POSTROUTING -o wg+ -j MASQUERADE                                                                                                                                                                                                                                                                  
PostUp = HOMENET=192.168.0.0/16; DROUTE=$(ip route | grep default | awk '{print $3}'); ip route add "$HOMENET" via "$DROUTE" dev eth0; iptables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL ! -d "$HOMENET" -j REJECT && ip6tables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT
PreDown = iptables -t nat -D POSTROUTING -o wg+ -j MASQUERADE                                                                                                                                                                                                                                                                 
PreDown = HOMENET=192.168.0.0/16; DROUTE=$(ip route | grep default | awk '{print $3}'); ip route delete "$HOMENET"; iptables -D OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL ! -d "$HOMENET" -j REJECT  && ip6tables -D OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT
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
