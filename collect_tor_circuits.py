#!/usr/bin/env python3
import stem.control
import csv
import time
from datetime import datetime

# Caminhos padrão para os bancos offline
GEOIP_DB_PATH = "/home/amnesia/Persistent/geoip/GeoLite2-Country.mmdb"
IP2ASN_DB_PATH = "/home/amnesia/Persistent/ip2asn/ip2asn-combined.tsv"

# --- Tentativa de import da base GeoIP ---
geoip_reader = None
try:
    import geoip2.database
    geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
except Exception:
    geoip_reader = None

# --- Tentativa de carregamento do IP2ASN offline ---
asn_db = None
try:
    asn_db = {}
    with open(IP2ASN_DB_PATH, "r") as asn_file:
        for line in asn_file:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                ip_range = parts[0]
                asn_info = parts[2]
                asn_db[ip_range] = asn_info
except Exception:
    asn_db = None

def get_country(ip):
    if geoip_reader:
        try:
            record = geoip_reader.country(ip)
            return record.country.iso_code or "UNKNOWN"
        except:
            return "UNKNOWN"
    return "UNKNOWN"

def get_asn(ip):
    if asn_db:
        for ip_range, asn_info in asn_db.items():
            if ip.startswith(ip_range.split("/")[0]):
                return asn_info
    return "UNKNOWN"

# --- Nome do arquivo CSV com timestamp ---
timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"circuits_{timestamp_str}.csv"

with open(csv_filename, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        "timestamp",
        "circuit_id",
        "role",
        "fingerprint",
        "nickname",
        "ip",
        "bandwidth",
        "country",
        "asn"
    ])

print(f"[OK] CSV criado: {csv_filename}")

def circ_handler(event):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    circuit_id = event.id
    path = event.path
    
    for idx, (fingerprint, nickname) in enumerate(path):
        if idx == 0:
            role = "guard"
        elif idx == len(path) - 1:
            role = "exit"
        else:
            role = "middle"

        fingerprint = fingerprint or "UNKNOWN"
        nickname = nickname or "UNKNOWN"
        ip = "UNKNOWN"
        bandwidth = "UNKNOWN"

        # IP e bandwidth do descriptor, se existir
        try:
            desc = controller.get_network_status(fingerprint)
            if desc:
                ip = desc.address or "UNKNOWN"

            server_desc = controller.get_server_descriptor(fingerprint)
            if server_desc and hasattr(server_desc, 'observed_bandwidth'):
                bandwidth = str(server_desc.observed_bandwidth)
        except:
            pass

        country = get_country(ip)
        asn = get_asn(ip)

        with open(csv_filename, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                ts,
                circuit_id,
                role,
                fingerprint,
                nickname,
                ip,
                bandwidth,
                country,
                asn
            ])

        print(f"[LOG] {ts} | {circuit_id} | {role} | {fingerprint} | {ip} | {country} | {asn}")

try:
    controller = stem.control.Controller.from_socket_file("/run/tor/control")
    controller.authenticate()
    print("[OK] Conectado ao Tor Controller.")
except Exception as e:
    print(f"[ERRO] Falha ao conectar ao Tor Controller: {e}")
    exit(1)

controller.add_event_listener(circ_handler, stem.control.EventType.CIRC)
print("[INFO] Coleta iniciada. Use Ctrl+C para parar.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[INFO] Encerrado. Dados salvos em: {csv_filename}")
