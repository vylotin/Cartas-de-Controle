# config.py

CONFIG_INDICADORES = {
    "IPCS": {
        "num": "IPCS", 
        "den": "CVC-DIA", 
        "fase": "STAGE ICS",
        "tipo": "U (Taxas / Densidade)", 
        "mult": 1000
    },
    "ITU-CV": {
        "num": "ITU-CV", 
        "den": "CVD-DIA", 
        "fase": "STAGE ITUAC", 
        "tipo": "U (Taxas / Densidade)", 
        "mult": 1000
    },
    "PAV": {
        "num": "PAV", 
        "den": "VM-DIA", 
        "fase": "STAGE PAV", 
        "tipo": "U (Taxas / Densidade)", 
        "mult": 1000
    },
    "CVC": {
        "num": "CVC-DIA", 
        "den": "PCT-dia", 
        "fase": "STAGE CVC", 
        "tipo": "P (Proporções)", 
        "mult": 100
    },
    "CVD": {
        "num": "CVD-DIA", 
        "den": "PCT-dia", 
        "fase": "STAGE CVD", 
        "tipo": "P (Proporções)", 
        "mult": 100
    },
    "VM": {
        "num": "VM-DIA", 
        "den": "PCT-dia", 
        "fase": "STAGE VM", 
        "tipo": "P (Proporções)", 
        "mult": 100
    }
}

# Constantes SPC (Statistical Process Control) nomeadas
D2_MR_N2 = 1.128      # Constante d2 para Moving Range de amplitude 2 (Tabela SPC)
NELSON_RUN = 7        # Regra 2 de Nelson: 7 pontos consecutivos do mesmo lado da média
EPSILON = 1e-9        # Proteção matemática contra divisão por zero em denominators pequenos

ARQUIVO_SALVO = "Base_CCIH_Atualizada.xlsx"