#!/usr/bin/env python3
import stem.control
import csv
import time
from datetime import datetime
import requests

# --- Funções com integração na API ip-api.com ---

def get_country(ip):
    if ip in ("UNKNOWN", None, ""):
        return "UNKNOWN"
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = resp.json()
        if data.get("status") == "success":
            return data.get("country", "UNKNOWN")
    except Exception:
        pass
    return "UNKNOWN"

def get_asn(ip):
    if ip in ("UNKNOWN", None, ""):
        return "UNKNOWN"
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = resp.json()
        if data.get("status") == "success":
            raw_as = data.get("as", "")
            return raw_as if raw_as else "UNKNOWN"
    except Exception:
        pass
    return "UNKNOWN"


# --- Nome do arquivo CSV com datetime ---
timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"circuits_{timestamp_str}.csv"

# Cria e escreve cabeçalho
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


# --- Função para tratar eventos de circuito ---
def circ_handler(event):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    circuit_id = event.id
    path = event.path  # lista de (fingerprint, nickname)
    
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
        
        try:
            desc = controller.get_network_status(fingerprint)
            if desc:
                ip = desc.address or "UNKNOWN"
        except Exception:
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

        print(f"[LOG] {ts} | CID:{circuit_id} | {role} | {fingerprint} | {ip} | {country} | {asn}")


# --- Conecta ao Tor Controller e registra handler ---
try:
    controller = stem.control.Controller.from_socket_file("/run/tor/control")
    controller.authenticate()
    print("[OK] Conectado ao Tor Controller via /run/tor/control")
except Exception as e:
    print(f"[ERRO] Não foi possível conectar ao Tor Controller: {e}")
    exit(1)

controller.add_event_listener(circ_handler, stem.control.EventType.CIRC)
print("[INFO] Monitorando novos circuitos. Navegue no Tor Browser...")


# --- Mantém o script vivo até CTRL+C ---
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[INFO] Interrompido pelo usuário. CSV final salvo:", csv_filename)
