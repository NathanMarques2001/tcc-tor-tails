#!/usr/bin/env python3
import stem.control
import csv
import time
from datetime import datetime

# --- Funções auxiliares para país e ASN (fallback pra UNKNOWN) ---

def get_country(ip):
    # Aqui dá pra integrar com bases offline depois (GeoLite2, etc.)
    # Por enquanto retorna UNKNOWN para não travar o script
    return "UNKNOWN"

def get_asn(ip):
    # Mesma ideia: pode integrar base MaxMind, IP2ASN ou whois depois
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
    
    # Tenta obter descrições dos relays
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
