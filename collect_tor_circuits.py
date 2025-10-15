#!/usr/bin/env python3
import stem.control
import csv
import time
import ipaddress
from datetime import datetime

# O caminho para o banco de dados offline continua sendo necessário para o ASN
IP2ASN_DB_PATH = "/home/amnesia/Persistent/ip2asn/ip2asn-combined.tsv"

# --- Carregamento do banco de dados IP2ASN (Apenas para ASN) ---
ip_data = []
try:
    print(f"[INFO] Carregando banco de dados offline de {IP2ASN_DB_PATH} para consulta de ASN...")
    with open(IP2ASN_DB_PATH, "r", encoding='utf-8') as asn_file:
        reader = csv.reader(asn_file, delimiter="\t")
        for row in reader:
            if len(row) >= 4:
                try:
                    network = ipaddress.ip_network(row[0])
                    asn = row[1]
                    provider = row[2]
                    ip_data.append((network, asn, provider)) # Não precisamos mais carregar o país daqui
                except ValueError:
                    pass
    if not ip_data:
        print("[AVISO] O banco de dados IP2ASN não pôde ser carregado. As informações de ASN não estarão disponíveis.")
    else:
        print(f"[OK] Banco de dados de ASN carregado com {len(ip_data)} redes.")
except FileNotFoundError:
    print(f"[AVISO] Arquivo não encontrado: {IP2ASN_DB_PATH}. As informações de ASN não estarão disponíveis.")
except Exception as e:
    print(f"[AVISO] Falha ao carregar o banco de dados IP2ASN: {e}. As informações de ASN não estarão disponíveis.")

def get_asn_info(ip_str):
    """
    Busca as informações de ASN de um IP no banco de dados carregado em memória.
    """
    if not ip_data or ip_str == "UNKNOWN":
        return "UNKNOWN"
    
    try:
        ip_addr = ipaddress.ip_address(ip_str)
        for network, asn, provider in ip_data:
            if ip_addr in network:
                return f"AS{asn} {provider}"
    except ValueError:
        return "INVALID_IP"
    
    return "NOT_FOUND"

# --- Configuração do arquivo CSV ---
timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"circuits_{timestamp_str}.csv"

with open(csv_filename, "w", newline="", encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        "timestamp", "circuit_id", "role", "fingerprint", "nickname",
        "ip", "bandwidth_kbs", "country", "asn_provider"
    ])
print(f"[OK] Arquivo CSV criado: {csv_filename}")

def circ_handler(event):
    """
    Processa eventos de criação de circuito do Tor.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for idx, (fingerprint, nickname) in enumerate(event.path):
        role = "middle"
        if idx == 0: role = "guard"
        elif idx == len(event.path) - 1: role = "exit"

        ip = "UNKNOWN"
        bandwidth = "UNKNOWN"
        country = "UNKNOWN" # Inicializa o país como UNKNOWN

        try:
            # get_server_descriptor nos dá mais detalhes, incluindo o país
            desc = controller.get_server_descriptor(fingerprint)
            if desc:
                ip = desc.address
                bandwidth = desc.observed_bandwidth
                country = desc.country # <<-- MUDANÇA PRINCIPAL: Obtendo o país diretamente do stem
        except Exception:
            pass 

        # O ASN ainda precisa ser buscado no arquivo offline
        asn_info = get_asn_info(ip)
        
        with open(csv_filename, "a", newline="", encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                ts, event.id, role, fingerprint, nickname,
                ip, bandwidth, country, asn_info
            ])
        
        print(f"[LOG] {ts} | Circuito: {event.id} | Nó: {role} | IP: {ip} | País: {country} | ASN: {asn_info}")

try:
    controller = stem.control.Controller.from_socket_file("/run/tor/control")
    controller.authenticate()
    print("[OK] Conectado ao Tor Controller.")
except Exception as e:
    print(f"[ERRO] Falha ao conectar ao Tor Controller: {e}")
    exit(1)

controller.add_event_listener(circ_handler, stem.control.EventType.CIRC)
print("[INFO] Coleta de dados iniciada. Pressione Ctrl+C para parar.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[INFO] Coleta encerrada. Dados salvos em: {csv_filename}")
