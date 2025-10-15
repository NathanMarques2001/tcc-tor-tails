#!/usr/bin/env python3
import stem.control
import csv
import time
import ipaddress # Biblioteca nativa para lidar com endereços IP e redes
from datetime import datetime

# Caminho para o banco de dados offline unificado
IP2ASN_DB_PATH = "/home/amnesia/Persistent/ip2asn/ip2asn-combined.tsv"

# --- Carregamento otimizado do banco de dados IP2ASN ---
# Vamos carregar os dados em uma lista para uma busca mais eficiente.
# Cada item será uma tupla contendo: (objeto_de_rede, asn, provedor, pais)
ip_data = []
try:
    print(f"[INFO] Carregando banco de dados offline de {IP2ASN_DB_PATH}...")
    with open(IP2ASN_DB_PATH, "r", encoding='utf-8') as asn_file:
        reader = csv.reader(asn_file, delimiter="\t")
        for row in reader:
            # O formato esperado é: IP_RANGE (CIDR), ASN, PROVIDER, COUNTRY_CODE
            if len(row) >= 4:
                try:
                    # Usamos ipaddress.ip_network para criar um objeto que entende a faixa de IP
                    network = ipaddress.ip_network(row[0])
                    asn = row[1]
                    provider = row[2]
                    country_code = row[3]
                    ip_data.append((network, asn, provider, country_code))
                except ValueError:
                    # Ignora linhas com formato de CIDR inválido
                    pass
    if not ip_data:
        print("[ERRO] O banco de dados IP2ASN não pôde ser carregado ou está vazio.")
        exit(1)
    print(f"[OK] Banco de dados carregado com {len(ip_data)} redes.")
except FileNotFoundError:
    print(f"[ERRO] Arquivo não encontrado: {IP2ASN_DB_PATH}")
    print("[INFO] Certifique-se de que o caminho para o arquivo ip2asn-combined.tsv está correto.")
    exit(1)
except Exception as e:
    print(f"[ERRO] Falha ao carregar o banco de dados IP2ASN: {e}")
    exit(1)

def find_ip_info(ip_str):
    """
    Busca as informações de um IP no banco de dados carregado em memória.
    Retorna o país e as informações do ASN.
    """
    if not ip_data or ip_str == "UNKNOWN":
        return "UNKNOWN", "UNKNOWN"
    
    try:
        # Converte a string do IP para um objeto de endereço IP
        ip_addr = ipaddress.ip_address(ip_str)
        # Itera sobre os dados carregados para encontrar a rede correspondente
        for network, asn, provider, country_code in ip_data:
            if ip_addr in network:
                # Formata a string do ASN para um padrão comum
                asn_info = f"AS{asn} {provider}"
                return country_code, asn_info
    except ValueError:
        # Caso o IP fornecido seja inválido
        return "INVALID_IP", "INVALID_IP"
    
    # Se não encontrar em nenhuma rede
    return "NOT_FOUND", "NOT_FOUND"

# --- Nome do arquivo CSV com timestamp ---
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
        if idx == 0:
            role = "guard"
        elif idx == len(event.path) - 1:
            role = "exit"
        else:
            role = "middle"

        ip = "UNKNOWN"
        bandwidth = "UNKNOWN"

        try:
            desc = controller.get_network_status(fingerprint)
            if desc:
                ip = desc.address
                # A largura de banda no get_network_status já está em KB/s
                bandwidth = desc.bandwidth
        except Exception:
            pass # Mantém os valores como "UNKNOWN" em caso de erro

        # Busca país e ASN usando nossa função unificada
        country, asn_info = find_ip_info(ip)
        
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

# Adiciona o listener para o evento de criação de circuitos (CIRC)
controller.add_event_listener(circ_handler, stem.control.EventType.CIRC)
print("[INFO] Coleta de dados iniciada. Pressione Ctrl+C para parar.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[INFO] Coleta encerrada. Dados salvos em: {csv_filename}")
