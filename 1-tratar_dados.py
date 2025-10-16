import pandas as pd

def tratar_circuitos_tor(input_filename, output_filename):
    """
    Carrega, trata e salva os dados de circuitos Tor.
    - Ajusta o timestamp para UTC-3.
    - Remove linhas duplicadas.
    """
    try:
        # Carregar o arquivo CSV para um DataFrame
        df = pd.read_csv(input_filename)

        # Contar as linhas antes do tratamento
        linhas_antes = len(df)
        print(f"Arquivo '{input_filename}' carregado com sucesso.")
        print(f"Número de linhas antes do tratamento: {linhas_antes}")

        # --- 1. Ajuste do Timestamp para UTC-3 ---
        print("\nIniciando ajuste de timestamp...")
        # Converte a coluna 'timestamp' para o formato datetime
        # O errors='coerce' transformará qualquer data inválida em NaT (Not a Time)
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Remove linhas que não puderam ser convertidas para data (se houver)
        df.dropna(subset=['timestamp'], inplace=True)

        # Subtrai 3 horas para ajustar para o fuso UTC-3
        df['timestamp'] = df['timestamp'] - pd.Timedelta(hours=3)
        print("Coluna 'timestamp' ajustada para UTC-3.")

        # --- 2. Remoção de Duplicatas Exatas ---
        print("\nRemovendo linhas duplicadas...")
        # Remove as linhas que são inteiramente duplicadas
        df.drop_duplicates(inplace=True)

        # Contar as linhas após o tratamento
        linhas_depois = len(df)
        print("Linhas duplicadas foram removidas.")

        # --- 3. Resultados e Salvamento ---
        linhas_removidas = linhas_antes - linhas_depois
        print(f"\nResumo do tratamento:")
        print(f" - Linhas originais: {linhas_antes}")
        print(f" - Linhas removidas: {linhas_removidas}")
        print(f" - Linhas restantes (limpas): {linhas_depois}")

        # Salva o DataFrame tratado em um novo arquivo CSV
        df.to_csv(output_filename, index=False)
        print(f"\nDados tratados foram salvos com sucesso no arquivo: '{output_filename}'")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{input_filename}' não foi encontrado. Verifique se ele está na mesma pasta que o script.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

# --- Como usar o script ---
if __name__ == "__main__":
    # Defina o nome do seu arquivo de entrada aqui
    arquivo_original = 'circuits_2025-10-16_01-54-36.csv'
    
    # Defina o nome do arquivo que será gerado com os dados limpos
    arquivo_tratado = 'circuitos_tratados.csv'
    
    # Executa a função de tratamento
    tratar_circuitos_tor(arquivo_original, arquivo_tratado)