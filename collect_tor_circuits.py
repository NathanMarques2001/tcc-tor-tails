#!/usr/bin/env python3
"""
collect_tor_circuits.py
- conecta ao Tor ControlSocket (unix socket ou TCP)
- coleta circuitos (por evento e/ou polling) e grava CSV com: timestamp, circuit_id, role, fingerprint, nickname, ip, country, asn, as_name
- tenta Geo/IP lookup: primeiro GeoIP local (GeoLite2 mmdb), senão usa ipinfo.io (requere net)
- Requisitos: pip install stem geoip2 requests (opcionais)
"""

import csv
import time
import os
import socket
import json
from datetime import datetime

# tentativa de importar stem (recomendado)
try:
    from stem import CircStatus
    from stem.control import Controller, EventType
    HAVE_STEM = True
except Exception:
    HAVE_STEM = False

# opcionais para geoip local (se tiver mmdb)
HAVE_GEOIP2 = False
try:
    import geoip2.database
    HAVE_GEOIP2 = True
except Exception:
    HAVE_GEOIP2 = False

import requests  # usado para ipinfo fallback and teamcymru queries (se internet disponível)

# CONFIGURAÇÕES
CONTROL_SOCKET_PATHS = ["/run/tor/control", "/var/run/tor/control"]  # tenta esses por padrão
CONTROL_PORT_TCP = 9051  # fallback TCP se existir
CSV_OUT = "tor_circuits_sample.csv"
SAMPLE_TARGET = 100  # número de circuitos a coletar antes de parar (pode ajustar)
USE_EVENTS = True  # se True, usa eventos (recomendado com stem); se False usa polling

# ipinfo token (opcional) - se tiver, coloque aqui para maior rate limit
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")  # export IPINFO_TOKEN=xxx se tiver

# helper: tentativa de conectar via stem com socket autodetect
def connect_controller():
    if not HAVE_STEM:
        return None, "stem-unavailable"
    # tenta socket paths
    for p in CONTROL_SOCKET_PATHS:
        if os.path.exists(p):
            try:
                c = Controller.from_socket_file(p)
                c.authenticate()  # tenta cookie auth or default
                return c, p
            except Exception as e:
                # tenta próximo
                print(f"[WARN] Não conseguiu autenticar via socket {p}: {e}")
    # tenta porta TCP
    try:
        c = Controller.from_port(port=CONTROL_PORT_TCP)
        c.authenticate()
        return c, f"tcp:{CONTROL_PORT_TCP}"
    except Exception as e:
        print(f"[WARN] Não conseguiu conectar via TCP {CONTROL_PORT_TCP}: {e}")
    return None, None

# geo lookup helpers
def geoip_lookup(ip):
    """Tenta geoip local (geoip2) -> ipinfo HTTP -> None"""
    if HAVE_GEOIP2:
        # tente dbs comuns
        for dbpath in ("/usr/share/GeoIP/GeoLite2-City.mmdb", "/usr/share/GeoIP/GeoLite2-ASN.mmdb", "GeoLite2-City.mmdb"):
            if os.path.exists(dbpath):
                try:
                    rdr = geoip2.database.Reader(dbpath)
                    rec = rdr.city(ip)
                    country = rec.country.iso_code if rec and rec.country else ""
                    rdr.close()
                    return country, ""
                except Exception:
                    pass
    # fallback: ipinfo.io
    try:
        url = f"https://ipinfo.io/{ip}/json"
        headers = {}
        if IPINFO_TOKEN:
            url += f"?token={IPINFO_TOKEN}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            j = r.json()
            country = j.get("country","")
            asn = j.get("org","")  # org includes ASN sometimes like "AS15169 Google LLC"
            return country, asn
    except Exception:
        pass
    return "", ""

# team cymru ASN lookup (fast via TCP whois)
def teamcymru_asn_query(ip):
    """
    Query Team Cymru whois service for ASN info.
    Format: " -v <ip>" e.g. " -v 8.8.8.8"
    """
    try:
        s = socket.create_connection(("whois.cymru.com", 43), timeout=6)
        q = f" -v {ip}\n"
        s.sendall(q.encode())
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        text = resp.decode(errors="ignore")
        # parse: skip header lines, last line contains ASN | IP | BGP Prefix | CC | Registry | Allocated | AS Name
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 2:
            last = lines[-1].split("|")
            # sanitize
            last = [p.strip() for p in last]
            # expected indices: ASN (0), IP (1), Prefix (2), CC (3), Registry (4), Allocated (5), AS Name (6)
            if len(last) >= 7:
                asn = last[0]
                cc = last[3]
                as_name = last[6]
                return cc, f"{asn} {as_name}"
    except Exception:
        pass
    return "", ""

# grava cabeçalho CSV se não existir
def prepare_csv(path):
    exists = os.path.exists(path)
    if not exists:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","circuit_id","circuit_purpose","node_index","node_role","fingerprint","nickname","ip","country","asn","as_name","descriptor_source"])
    return

# função principal (usa stem se disponível)
def run_with_stem(target_count=SAMPLE_TARGET):
    ctrl, where = connect_controller()
    if not ctrl:
        print("[ERROR] Não foi possível conectar ao controller Tor (stem).")
        return
    print(f"[OK] Conectado ao Tor controller via {where}")
    prepare_csv(CSV_OUT)
    collected = 0

    def record_circuit(circ):
        nonlocal collected
        # só interesse em BUILT
        try:
            from stem import CircStatus
            if circ.status != CircStatus.BUILT:
                return
        except Exception:
            pass
        ts = datetime.utcnow().isoformat() + "Z"
        cid = str(circ.id)
        purpose = str(circ.purpose)
        # circ.path is list of tuples: (fingerprint, nickname, ip?)
        path = getattr(circ, "path", [])
        # path may be a list of (fingerprint, nickname) or objects
        for i, hop in enumerate(path):
            # hop can be a tuple or a stem object
            fingerprint = ""
            nickname = ""
            ip = ""
            descriptor_source = "circuit.path"
            try:
                if isinstance(hop, tuple) or isinstance(hop, list):
                    fingerprint = hop[0]
                    nickname = hop[1] if len(hop) > 1 else ""
                else:
                    # maybe stem.node object
                    fingerprint = getattr(hop, "fingerprint", "")
                    nickname = getattr(hop, "nickname", "")
            except Exception:
                pass
            # try to get ip from controller get_network_status or get_descriptor (best-effort)
            node_ip = ""
            try:
                desc = ctrl.get_network_status(fingerprint)
                # get_network_status returns None or object with address?
                if desc:
                    node_ip = getattr(desc, "address", "") or ""
                    descriptor_source = "network-status"
            except Exception:
                pass

            # geo / asn
            country, asn_name = "", ""
            if node_ip:
                country, asn_name = teamcymru_asn_query(node_ip)
                if not country:
                    country, asn_name = geoip_lookup(node_ip)
            row = [ts, cid, purpose, i, ("exit" if i==len(path)-1 else ("guard" if i==0 else "middle")), fingerprint, nickname, node_ip or node_ip, country, (asn_name.split()[0] if asn_name else ""), asn_name, descriptor_source]
            with open(CSV_OUT, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(row)
        collected += 1

    # se eventos habilitados, escutar EventType.CIRC
    if USE_EVENTS:
        def circ_handler(event):
            try:
                # get_circuits returns objects with id and path; recompute full
                for c in ctrl.get_circuits():
                    if c.status.name == "BUILT":
                        record_circuit(c)
                        break
            except Exception as e:
                print("[ERR] circ_handler:", e)

        try:
            ctrl.add_event_listener(circ_handler, EventType.CIRC)
            print("[INFO] Listener de CIRC registrado. Navegue no Tor Browser para gerar circuitos.")
            # loop até coletar target_count
            while collected < target_count:
                time.sleep(1)
            ctrl.remove_event_listener(circ_handler)
        except Exception as e:
            print("[WARN] não foi possível usar listeners, fallback para polling:", e)

    # fallback polling (ou se events não funcionarem)
    while collected < target_count:
        try:
            for c in ctrl.get_circuits():
                record_circuit(c)
                if collected >= target_count:
                    break
        except Exception as e:
            print("[ERR] polling get_circuits:", e)
        time.sleep(2)

    print(f"[DONE] coletados ~{collected} circuitos em {CSV_OUT}")
    ctrl.close()

# fallback sem stem: tenta usar control socket via telnet-like minimal parsing (LIMITADO)
def run_without_stem(target_count=SAMPLE_TARGET):
    # tenta socket path
    sockpath = None
    for p in CONTROL_SOCKET_PATHS:
        if os.path.exists(p):
            sockpath = p
            break
    if not sockpath:
        # tenta TCP
        try:
            s = socket.create_connection(("127.0.0.1", CONTROL_PORT_TCP), timeout=4)
            # simple minimal protocol: send "AUTHENTICATE\r\n" (may require cookie or password) -> will likely fail
            s.sendall(b'AUTHENTICATE\r\n')
            resp = s.recv(4096)
            print("resp:", resp)
            s.close()
        except Exception as e:
            print("[ERR] Não encontrou socket de controle e não conseguiu TCP:", e)
            return
    else:
        print(f"[WARN] Modo fallback usando socket raw: {sockpath}. Autenticação pode falhar.")
        # implementação completa sem stem é longa; recomendo instalar stem
        print("[ERROR] Modo sem stem é limitado. Instale 'stem' e rode novamente.")
        return

if __name__ == "__main__":
    prepare_csv(CSV_OUT)
    if HAVE_STEM:
        run_with_stem()
    else:
        print("[WARN] stem não encontrado. Rode: pip install stem")
        run_without_stem()
