import pandas as pd
import pycountry
from babel.core import Locale

def finalizar_com_traducao_automatica(input_filename, output_filename):
    """
    Realiza a limpeza final do arquivo de circuitos Tor usando bibliotecas
    padrão para tradução de nomes de países.
    - Remove a coluna 'bandwidth'.
    - Traduz os nomes dos países de forma robusta para português.
    """
    # Cache para armazenar traduções já feitas e acelerar o processo
    cache_traducao = {}
    
    # Define o local para português do Brasil
    locale_pt_br = Locale('pt', 'BR')

    def traduzir_nome_pais(nome_em_ingles):
        """
        Recebe um nome de país em inglês, encontra seu código de 2 letras
        e retorna o nome em português.
        """
        # Se o nome não for uma string válida, retorna como está
        if not isinstance(nome_em_ingles, str):
            return nome_em_ingles

        # 1. Verifica o cache para não reprocessar o mesmo nome
        if nome_em_ingles in cache_traducao:
            return cache_traducao[nome_em_ingles]

        try:
            # 2. Usa pycountry para fazer uma busca "fuzzy" e encontrar o país
            # Isso ajuda a capturar pequenas variações no nome
            pais_obj = pycountry.countries.search_fuzzy(nome_em_ingles)[0]
            
            # 3. Pega o código alpha_2 (ex: 'DE') e usa o Babel para traduzir
            nome_em_portugues = locale_pt_br.territories.get(pais_obj.alpha_2)
            
            # 4. Armazena no cache e retorna o resultado
            cache_traducao[nome_em_ingles] = nome_em_portugues
            return nome_em_portugues

        except LookupError:
            # Se a biblioteca não encontrar o país, mantém o nome original
            # Também armazena no cache para não tentar de novo
            cache_traducao[nome_em_ingles] = nome_em_ingles
            return nome_em_ingles

    try:
        # Carregar o arquivo CSV enriquecido
        df = pd.read_csv(input_filename)
        print(f"Arquivo '{input_filename}' carregado com sucesso.")

        # --- 1. Remover a coluna 'bandwidth' ---
        if 'bandwidth' in df.columns:
            df.drop('bandwidth', axis=1, inplace=True)
            print("Coluna 'bandwidth' removida.")
        else:
            print("Coluna 'bandwidth' não encontrada.")

        # --- 2. Traduzir a coluna 'country' de forma automática ---
        print("Iniciando a tradução automática dos nomes de países...")
        
        # A função .apply executa a nossa função 'traduzir_nome_pais' para cada linha
        df['country'] = df['country'].apply(traduzir_nome_pais)
        
        print("Tradução concluída.")
        
        # Salva o DataFrame final em um novo arquivo CSV
        df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        
        print(f"\nProcesso finalizado! Seus dados estão prontos em: '{output_filename}'")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{input_filename}' não foi encontrado.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

# --- Como usar o script ---
if __name__ == "__main__":
    arquivo_enriquecido = 'circuitos_enriquecidos.csv'
    arquivo_final = 'circuitos_final_ptbr.csv'
    
    finalizar_com_traducao_automatica(arquivo_enriquecido, arquivo_final)