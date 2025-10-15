import csv
import os
from datetime import datetime
from stem.control import Controller

# Gera nome do arquivo CSV baseado no datetime
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"circuits_{timestamp}.csv"

# Cria CSV e cabeçalho
with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["circuit_id", "status", "relays"])

def handle_circuit(controller, event):
    """
    Função chamada sempre que houver alteração em circuitos.
    """
    # Tratando a questão do .status vs string
    status_attr = getattr(event, "status", "")
    status_str = status_attr.name if hasattr(status_attr, "name") else str(status_attr)

    if status_str.upper() != "BUILT":
        return  # Desconsidera se não estiver finalizado

    circuit_id = getattr(event, "id", "N/A")
    path_info = getattr(event, "path", [])

    relays = []
    for relay in path_info:
        # Cada relay pode vir como tupla (fingerprint, nickname)
        if isinstance(relay, (list, tuple)) and len(relay) >= 2:
            fingerprint, nickname = relay[0], relay[1]
            relays.append(f"{nickname} ({fingerprint})")
        else:
            relays.append(str(relay))

    # Salva no CSV
    with open(csv_filename, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([circuit_id, status_str, " | ".join(relays)])

    print(f"[OK] Circuito {circuit_id} registrado -> {relays}")

def main():
    tor_control_path = "/run/tor/control"
    if not os.path.exists(tor_control_path):
        print(f"[ERRO] Não encontrei {tor_control_path}.")
        return

    try:
        with Controller.from_socket_file(tor_control_path) as controller:
            controller.authenticate()

            print("[INFO] Conectado ao Tor. Monitorando circuitos (BUILT).")
            controller.add_event_listener(handle_circuit, "CIRC")

            print("[INFO] Abra o Tor Browser e navegue para gerar circuitos.")
            print(f"[INFO] Salvando dados em: {csv_filename}")

            # Fica esperando eventos
            while True:
                pass

    except Exception as e:
        print(f"[ERRO] {e}")

if __name__ == "__main__":
    main()
