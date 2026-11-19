"""Modelos de resposta (instruções de papel, formato e limites).

Como o protótipo não usa modelo de linguagem externo, cada modelo é composto por:
  - 'instrucao': prompt/instrução documentada (papel, formato, limites), que
    também serviria de system prompt caso um LLM fosse acoplado;
  - 'formatar': função que aplica o formato e as regras à orientação selecionada.
"""

ROTULOS_TEMAS = {"servicos": "Serviços", "comunitario": "Comunitário",
                 "documentos": "Documentos", "direitos": "Direitos"}


def rotulo(tema):
    """Nome de exibição do tema (com acentos)."""
    return ROTULOS_TEMAS.get(tema, tema.capitalize())


AVISO_GENERICO = "Confirme sempre os requisitos atualizados na fonte oficial."
RODAPE = "Este assistente é um protótipo educacional e NÃO é um canal oficial de órgãos públicos."

INSTRUCAO_A = (
    "Papel: assistente que responde de forma curta e direta. "
    "Formato: orientação em 1 parágrafo seguida de 'Fonte'. "
    "Limite: usar somente o conteúdo da base."
)

INSTRUCAO_B = (
    "Papel: assistente informativo de orientação cidadã, que NÃO representa órgãos públicos. "
    "Formato: (1) Orientação com tema/subtema; (2) Fonte com link; (3) Data de verificação; "
    "(4) Aviso para confirmar informações; (5) Assuntos relacionados. "
    "Regras: citar sempre a fonte; usar apenas o conteúdo da base; se não houver base, "
    "informar o limite sem inventar instruções; não pedir dados pessoais; linguagem simples."
)


def formatar_a(reg, relacionados=None):
    return f"{reg['orientacao']}\nFonte: {reg['referencia']}"


def formatar_b(reg, relacionados=None):
    linhas = [
        f"ORIENTAÇÃO ({rotulo(reg['tema'])} > {reg['subtema']})",
        reg["orientacao"],
        "",
        f"FONTE: {reg['referencia']}" + (f" - {reg['url']}" if reg.get("url") else ""),
        f"VERIFICADO EM: {reg['data_verificacao']}",
        f"ATENÇÃO: {reg.get('aviso') or AVISO_GENERICO}",
    ]
    if relacionados:
        linhas.append("VEJA TAMBÉM: " + "; ".join(f"[{r['id']}] {r['pergunta']}" for r in relacionados))
    linhas.append(RODAPE)
    return "\n".join(linhas)


MODELOS = {
    "A": {"nome": "Resposta direta", "instrucao": INSTRUCAO_A, "formatar": formatar_a},
    "B": {"nome": "Orientação estruturada", "instrucao": INSTRUCAO_B, "formatar": formatar_b},
}


def aviso_sem_resposta(registros):
    """Aviso de limitação com alternativas: um exemplo de pergunta por tema."""
    exemplos, vistos = [], set()
    for r in registros:
        if r["tema"] not in vistos:
            vistos.add(r["tema"])
            exemplos.append(f"  - ({rotulo(r['tema'])}) {r['pergunta']}")
    return ("Não encontrei essa informação na base de orientações. Para não passar "
            "informação errada, prefiro não responder. Consulte o órgão oficial responsável.\n"
            "Você pode tentar reformular ou escolher um tema no menu. Exemplos do que sei responder:\n"
            + "\n".join(sorted(exemplos)) + f"\n{RODAPE}")


def checklist_clareza(texto):
    """Itens de qualidade esperados (usados na comparação dos modelos)."""
    t = texto.lower()
    return {
        "cita_fonte": "fonte:" in t,
        "tem_link": "http" in t,
        "tem_data_verificacao": "verificado em" in t,
        "tem_aviso_confirmacao": "atenção" in t or "confirme" in t,
        "tem_relacionados": "veja também" in t,
        "avisa_nao_oficial": "não é um canal oficial" in t,
    }
