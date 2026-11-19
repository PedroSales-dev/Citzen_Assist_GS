"""Leitura, validação e gravação da base de conhecimento (JSON)."""
import json
from datetime import datetime
from pathlib import Path

CAMPOS_OBRIGATORIOS = ["id", "tema", "subtema", "palavras_chave", "pergunta",
                       "orientacao", "referencia", "data_verificacao"]


class BaseErro(Exception):
    """Erro fatal ao carregar a base (arquivo ausente, vazio ou corrompido)."""


def validar_registro(reg):
    """Devolve lista de problemas encontrados no registro (vazia = válido)."""
    problemas = []
    if not isinstance(reg, dict):
        return ["registro não é um objeto/dicionário"]
    for campo in CAMPOS_OBRIGATORIOS:
        valor = reg.get(campo)
        if valor is None or valor == "" or valor == []:
            problemas.append(f"campo obrigatório ausente ou vazio: '{campo}'")
    if problemas:
        return problemas
    for campo in ("id", "tema", "subtema", "pergunta", "orientacao", "referencia"):
        if not isinstance(reg[campo], str):
            problemas.append(f"'{campo}' deve ser texto")
    if not isinstance(reg["palavras_chave"], list) or not all(
            isinstance(p, str) and p.strip() for p in reg["palavras_chave"]):
        problemas.append("'palavras_chave' deve ser uma lista de textos não vazios")
    if not isinstance(reg.get("relacionados", []), list):
        problemas.append("'relacionados' deve ser uma lista de ids")
    try:
        datetime.strptime(reg["data_verificacao"], "%Y-%m-%d")
    except ValueError:
        problemas.append("'data_verificacao' deve estar no formato AAAA-MM-DD")
    return problemas


def carregar_base(caminho):
    """Carrega a base. Retorna (registros_validos, avisos).
    Lança BaseErro se arquivo ausente, vazio, ilegível ou sem registros válidos."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise BaseErro(f"Arquivo da base não encontrado: {caminho}")
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise BaseErro(f"Não foi possível ler o arquivo: {e}")
    if not texto.strip():
        raise BaseErro("O arquivo da base está vazio.")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise BaseErro(f"JSON inválido na base (linha {e.lineno}): {e.msg}")
    if not isinstance(dados, list) or not dados:
        raise BaseErro("A base deve ser uma lista não vazia de registros.")

    validos, avisos, ids = [], [], set()
    for i, reg in enumerate(dados, start=1):
        problemas = validar_registro(reg)
        if not problemas and reg["id"] in ids:
            problemas.append(f"id duplicado: {reg['id']}")
        if problemas:
            avisos.append(f"Registro #{i} ignorado: " + "; ".join(problemas))
            continue
        ids.add(reg["id"])
        validos.append(reg)
    if not validos:
        raise BaseErro("Nenhum registro válido encontrado na base.")
    for r in validos:  # referências a ids inexistentes não impedem o uso, mas são avisadas
        for viz in r.get("relacionados", []):
            if viz not in ids:
                avisos.append(f"Registro {r['id']}: relacionado inexistente '{viz}' (ignorado)")
    return validos, avisos


def salvar_base(caminho, registros):
    """Grava de forma segura: escreve em arquivo temporário e substitui o original,
    evitando corromper a base se algo falhar no meio da gravação."""
    caminho = Path(caminho)
    temp = caminho.with_suffix(caminho.suffix + ".tmp")
    temp.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    temp.replace(caminho)


def indexar_por_id(registros):
    """Dicionário id -> registro (acesso direto por identificador)."""
    return {r["id"]: r for r in registros}


def temas_disponiveis(registros):
    """Dicionário tema -> subtema -> [ids]. Representa a hierarquia de assuntos."""
    arvore = {}
    for r in registros:
        arvore.setdefault(r["tema"], {}).setdefault(r["subtema"], []).append(r["id"])
    return arvore


def construir_grafo(registros):
    """Grafo simples (não direcionado) de assuntos relacionados.
    Lista de adjacência: id -> conjunto de ids vizinhos."""
    ids = {r["id"] for r in registros}
    grafo = {i: set() for i in ids}
    for r in registros:
        for viz in r.get("relacionados", []):
            if viz in ids and viz != r["id"]:
                grafo[r["id"]].add(viz)
                grafo[viz].add(r["id"])  # simetria
    return grafo


def explorar_relacionados(grafo, origem, profundidade=1):
    """Busca em largura (BFS): ids alcançáveis a partir de 'origem'."""
    visitados, fila, resultado = {origem}, [(origem, 0)], []
    while fila:
        atual, nivel = fila.pop(0)
        if nivel == profundidade:
            continue
        for viz in sorted(grafo.get(atual, ())):
            if viz not in visitados:
                visitados.add(viz)
                resultado.append(viz)
                fila.append((viz, nivel + 1))
    return resultado
