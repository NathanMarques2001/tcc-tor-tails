import pandas as pd
import requests
import time
from tqdm import tqdm

def enriquecer_dados_com_api(input_filename, output_filename):
    """
    Enriquece o CSV de circuitos Tor com dados de geolocalização e ASN de uma API.
    - Lê o arquivo tratado.
    - Consulta a API para cada IP único.
    - Preenche as colunas 'country' e 'asn'.
    - Salva em um novo arquivo.
    """
    API_URL = "http://ip-api.com/json/"

    try:
        # Carregar o arquivo CSV tratado
        df = pd.read_csv(input_filename)
        print(f"Arquivo '{input_filename}' carregado com {len(df)} linhas.")

        # Pega todos os IPs únicos da coluna 'ip' para evitar chamadas repetidas
        ips_unicos = df['ip'].unique()
        print(f"Encontrados {len(ips_unicos)} endereços de IP únicos para consultar.")

        # Dicionário para guardar os resultados da API (cache)
        ip_cache = {}

        # Itera sobre os IPs únicos com uma barra de progresso (tqdm)
        print("\nConsultando a API para cada IP. Isso pode levar um tempo...")
        for ip in tqdm(ips_unicos):
            try:
                # Faz a requisição para a API
                response = requests.get(f"{API_URL}{ip}", timeout=5)
                
                # Verifica se a requisição foi bem-sucedida
                if response.status_code == 200:
                    data = response.json()
                    # Verifica se a API retornou sucesso na consulta
                    if data.get("status") == "success":
                        # Guarda o país e o ASN no nosso cache
                        ip_cache[ip] = {
                            'country': data.get('country', 'N/A'),
                            'asn': data.get('as', 'N/A') # A API retorna o ASN no campo 'as'
                        }
                    else:
                        # Se a API falhou para este IP específico
                        ip_cache[ip] = {'country': 'Falha na API', 'asn': 'Falha na API'}
                else:
                    # Se a requisição HTTP falhou
                    ip_cache[ip] = {'country': 'Erro HTTP', 'asn': 'Erro HTTP'}
            
            except requests.exceptions.RequestException:
                # Em caso de erro de conexão ou timeout
                ip_cache[ip] = {'country': 'Erro de Conexão', 'asn': 'Erro de Conexão'}
            
            # Pausa para não sobrecarregar a API (limite de 45 reqs/min)
            time.sleep(1.5)

        print("\nAPI consultada com sucesso. Preenchendo a planilha...")

        # --- Preenchimento das colunas usando o cache ---
        # A função .map é muito eficiente para isso
        df['country'] = df['ip'].map(lambda ip: ip_cache.get(ip, {}).get('country', 'Desconhecido'))
        df['asn'] = df['ip'].map(lambda ip: ip_cache.get(ip, {}).get('asn', 'Desconhecido'))
        
        # Salva o DataFrame final em um novo arquivo CSV
        df.to_csv(output_filename, index=False)
        
        print(f"\nDados enriquecidos foram salvos com sucesso no arquivo: '{output_filename}'")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{input_filename}' não foi encontrado. Certifique-se de que ele está na mesma pasta.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

# --- Como usar o script ---
if __name__ == "__main__":
    # Nome do arquivo gerado pelo script anterior
    arquivo_tratado = 'circuitos_tratados.csv'
    
    # Nome do novo arquivo que será gerado com os dados completos
    arquivo_enriquecido = 'circuitos_enriquecidos.csv'
    
    # Executa a função principal
    enriquecer_dados_com_api(arquivo_tratado, arquivo_enriquecido)