"""Estratégia de busca: correspondência por palavras-chave com pontuação."""
import re
import unicodedata

PESO_PALAVRA_CHAVE = 3   # termo da consulta coincide com palavra-chave/tema/subtema
PESO_TEXTO = 1           # termo coincide apenas com pergunta/orientação
LIMIAR_MINIMO = 3        # exige ao menos 1 palavra-chave para responder
TAMANHO_MAXIMO = 200

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "por", "para", "pra", "com", "que", "como", "qual", "quais", "e", "ou",
    "eu", "meu", "minha", "meus", "minhas", "posso", "preciso", "quero", "onde", "quanto",
    "quando", "fazer", "faco", "tenho", "ter", "ser", "sao", "esta", "se", "ao", "mais",
    "mas", "ja", "nao", "contra", "sobre", "ate", "pode", "devo", "voce", "me", "tem",
    "sua", "seu", "isso", "esse", "essa", "uns", "umas", "ha", "so", "foi", "vai",
    "tirar", "pedir", "solicitar", "fui", "estou", "sofro", "ajuda", "gostaria",
}

# Sinônimos: palavra da consulta -> termos equivalentes presentes na base.
# Aplicados só na consulta (não nas palavras-chave), para ampliar a cobertura.
SINONIMOS = {
    "rg": ["identidade"], "quebrado": ["defeito"], "quebrada": ["defeito"],
    "estragado": ["defeito"], "estragou": ["defeito"], "danificado": ["defeito"],
    "exterior": ["passaporte"], "viajar": ["passaporte"], "golpe": ["fraude"],
    "aposentar": ["aposentadoria"], "reembolso": ["devolucao", "devolver"],
    "hospital": ["saude"], "medico": ["saude"], "remedio": ["saude"],
    "agredida": ["agressao"], "agredido": ["agressao"], "espancamento": ["agressao"],
    "onibus": ["transporte"], "gratis": ["gratuito"], "bombeiro": ["bombeiros"],
    "advogada": ["advogado"], "ambulancia": ["samu"], "motorista": ["cnh"],
}


def normalizar(texto):
    """Minúsculas e sem acentos."""
    base = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def _radical(palavra):
    """Radical simples: remove 's' final e usa os 6 primeiros caracteres."""
    if len(palavra) > 4 and palavra.endswith("s"):
        palavra = palavra[:-1]
    return palavra[:6]


def tokens(texto, expandir=False):
    """Conjunto de radicais relevantes de um texto.
    Com expandir=True, acrescenta os radicais dos sinônimos (usado nas consultas)."""
    palavras = re.findall(r"[a-z0-9]+", normalizar(texto))
    palavras = [p for p in palavras if p not in STOPWORDS and len(p) > 1]
    resultado = {_radical(p) for p in palavras}
    if expandir:
        for p in palavras:
            resultado |= {_radical(x) for x in SINONIMOS.get(p, [])}
    return resultado


def validar_consulta(consulta):
    """Retorna (status, mensagem). status 'ok' se a consulta pode ser buscada."""
    if consulta is None or not consulta.strip():
        return "vazio", "Você não digitou nada. Escreva uma pergunta ou escolha um tema no menu."
    consulta = consulta.strip()
    if len(consulta) > TAMANHO_MAXIMO:
        return "invalido", f"A pergunta está muito longa (máximo {TAMANHO_MAXIMO} caracteres)."
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", consulta):
        return "invalido", "Não consegui entender a entrada. Use palavras para descrever sua dúvida."
    if re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", consulta):
        return "dados_pessoais", ("Parece que você digitou um número de documento (CPF). "
                                  "Por privacidade, não envie dados pessoais; descreva só a sua dúvida.")
    if not tokens(consulta):
        return "invalido", "Use termos mais específicos para descrever sua dúvida."
    return "ok", ""


def pontuar(q_tokens, registro):
    """Pontua um registro para a consulta."""
    chaves = set()
    for termo in registro["palavras_chave"] + [registro["tema"], registro["subtema"]]:
        chaves |= tokens(termo)
    texto = tokens(registro["pergunta"] + " " + registro["orientacao"])
    acertos_chave = q_tokens & chaves
    acertos_texto = (q_tokens & texto) - acertos_chave
    return PESO_PALAVRA_CHAVE * len(acertos_chave) + PESO_TEXTO * len(acertos_texto)


def buscar(consulta, registros, max_alternativas=3):
    """Busca orientações. Retorna dicionário com:
    status: ok | vazio | invalido | dados_pessoais | ambiguo | sem_resposta
    registro, alternativas (lista de registros), pontuacao, mensagem.

    Várias correspondências: ordena por pontuação (desc). Se o 2º colocado empata
    com o 1º, a consulta é ambígua e o usuário escolhe entre as opções empatadas.
    Caso contrário devolve o 1º e os demais como alternativas."""
    status, msg = validar_consulta(consulta)
    if status != "ok":
        return {"status": status, "mensagem": msg, "registro": None,
                "alternativas": [], "pontuacao": 0}

    q = tokens(consulta, expandir=True)
    ranking = sorted(((pontuar(q, r), r) for r in registros),
                     key=lambda par: (-par[0], par[1]["id"]))
    ranking = [(p, r) for p, r in ranking if p >= LIMIAR_MINIMO]

    if not ranking:
        return {"status": "sem_resposta", "registro": None, "alternativas": [],
                "pontuacao": 0,
                "mensagem": "Não encontrei orientação confiável sobre isso na minha base."}

    melhor = ranking[0][0]
    if len(ranking) > 1 and ranking[1][0] == melhor:
        empatados = [r for p, r in ranking if p == melhor][:6]
        return {"status": "ambiguo", "registro": None, "alternativas": empatados,
                "pontuacao": melhor,
                "mensagem": "Sua pergunta pode se referir a mais de um assunto. Qual deles você quer?"}

    alternativas = [r for p, r in ranking[1:1 + max_alternativas]]
    return {"status": "ok", "registro": ranking[0][1], "alternativas": alternativas,
            "pontuacao": melhor, "mensagem": ""}
