"""Executa as perguntas de teste, calcula indicadores e compara os modelos A e B.
Uso:  python tests/executar_testes.py
Gera: docs/resultados_testes.csv e docs/comparacao_modelos.md
"""
import csv
import json
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
import base, busca, prompts  # noqa: E402

REPETICOES = 200  # a busca é muito rápida; mede-se a média de várias execuções


def status_obtido(res):
    return {"ok": res["registro"]["id"] if res["registro"] else "?",
            "vazio": "VAZIO", "invalido": "INVALIDO", "ambiguo": "AMBIGUO",
            "sem_resposta": "SEM_RESPOSTA", "dados_pessoais": "DADOS_PESSOAIS"}[res["status"]]


def main():
    registros, avisos = base.carregar_base(RAIZ / "data" / "base_conhecimento.json")
    por_id = base.indexar_por_id(registros)
    grafo = base.construir_grafo(registros)
    testes = json.loads((RAIZ / "data" / "perguntas_teste.json").read_text(encoding="utf-8"))

    linhas, tempos, acertos = [], [], 0
    resultados = {}
    for t in testes:
        ini = time.perf_counter()
        for _ in range(REPETICOES):
            res = busca.buscar(t["pergunta"], registros)
        ms = (time.perf_counter() - ini) / REPETICOES * 1000
        obtido = status_obtido(res)
        ok = obtido == t["esperado"]
        acertos += ok
        tempos.append(ms)
        resultados[t["id"]] = res
        linhas.append([t["id"], t["tipo"], t["pergunta"], t["esperado"], obtido,
                       "ACERTO" if ok else "ERRO", f"{ms:.3f}"])

    with open(RAIZ / "docs" / "resultados_testes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "tipo", "pergunta", "esperado", "obtido", "resultado", "tempo_ms"])
        w.writerows(linhas)

    for l in linhas:
        print(f"{l[0]} [{l[1]:<12}] esperado={l[3]:<13} obtido={l[4]:<13} {l[5]:<6} {l[6]} ms | {l[2]!r}")
    total = len(testes)
    grupos = defaultdict(lambda: [0, 0])
    for l in linhas:
        grupos[l[1]][1] += 1
        grupos[l[1]][0] += l[5] == "ACERTO"
    print("\nTaxa por tipo de pergunta:")
    for tipo, (a, n) in grupos.items():
        print(f"  {tipo:<13} {a}/{n} = {a / n * 100:.1f}%")
    taxa = acertos / total * 100
    media = sum(tempos) / total
    print(f"\nPerguntas: {total} | Acertos: {acertos} | Taxa de acerto: {taxa:.1f}%")
    print(f"Tempo médio de consulta: {media:.3f} ms")

    # ---- comparação dos modelos A e B nas perguntas respondidas ----
    resumo = {}
    for nome, m in prompts.MODELOS.items():
        pontos, palavras, n = 0, 0, 0
        for tid, res in resultados.items():
            if res["status"] != "ok":
                continue
            reg = res["registro"]
            rel = [por_id[i] for i in base.explorar_relacionados(grafo, reg["id"], 1)[:3]]
            texto = m["formatar"](reg, rel)
            pontos += sum(prompts.checklist_clareza(texto).values())
            palavras += len(texto.split())
            n += 1
        resumo[nome] = (pontos / n, palavras / n, n)
    print("\nComparação de modelos (itens do checklist de 6; média de palavras):")
    for nome, (p, w, n) in resumo.items():
        print(f" Modelo {nome} ({prompts.MODELOS[nome]['nome']}): {p:.1f}/6 itens, {w:.0f} palavras (n={n})")

    md = ["# Comparação dos modelos de resposta\n",
          "Checklist (6 itens): cita fonte, tem link, data de verificação, aviso de confirmação, "
          "assuntos relacionados, aviso de não oficial.\n",
          "| Modelo | Itens atendidos (média) | Palavras (média) | Respostas avaliadas |",
          "|---|---|---|---|"]
    for nome, (p, w, n) in resumo.items():
        md.append(f"| {nome} - {prompts.MODELOS[nome]['nome']} | {p:.1f}/6 | {w:.0f} | {n} |")
    (RAIZ / "docs" / "comparacao_modelos.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    falhas = verificar_robustez(registros, testes)
    return 0 if falhas == 0 else 1


def verificar_robustez(registros, testes):
    """Verifica requisitos mínimos do trabalho e o tratamento de bases defeituosas."""
    print("\nVerificações de requisitos e robustez:")
    falhas = 0

    def check(nome, cond):
        nonlocal falhas
        print(f"  [{'OK' if cond else 'FALHA'}] {nome}")
        falhas += not cond

    check(f"Base com >= 15 registros ({len(registros)})", len(registros) >= 15)
    check("Base com >= 3 temas", len({r['tema'] for r in registros}) >= 3)
    check(f">= 12 perguntas de teste ({len(testes)})", len(testes) >= 12)
    check(">= 3 situações de limitação",
          sum(t["tipo"] == "limitacao" for t in testes) >= 3)
    ids = {r["id"] for r in registros}
    check("Todos os 'relacionados' apontam para ids existentes",
          all(v in ids for r in registros for v in r.get("relacionados", [])))
    grafo = base.construir_grafo(registros)
    check("Grafo simétrico", all(a in grafo[b] for a in grafo for b in grafo[a]))
    check("Todo registro tem >= 1 assunto relacionado (navegação)",
          all(grafo[i] for i in grafo))
    check("Todo registro encontra a si mesmo pela própria pergunta",
          all(busca.buscar(r["pergunta"], registros)["status"] in ("ok", "ambiguo")
              for r in registros))

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)

        def erro_esperado(conteudo):
            f = d / "b.json"
            if conteudo is None:
                f = d / "inexistente.json"
            else:
                f.write_text(conteudo, encoding="utf-8")
            try:
                base.carregar_base(f)
            except base.BaseErro:
                return True
            return False

        check("Arquivo ausente tratado", erro_esperado(None))
        check("Arquivo vazio tratado", erro_esperado("   "))
        check("JSON inválido tratado", erro_esperado("{ quebrado"))
        check("Lista vazia tratada", erro_esperado("[]"))
        check("Registros sem campos essenciais tratados", erro_esperado('[{"id":"X1"}]'))
        ok = dict(registros[0])
        dup = json.dumps([ok, ok], ensure_ascii=False)
        f = d / "dup.json"
        f.write_text(dup, encoding="utf-8")
        regs, avisos = base.carregar_base(f)
        check("Id duplicado ignorado com aviso",
              len(regs) == 1 and any("duplicado" in a for a in avisos))
        f2 = d / "salvar.json"
        base.salvar_base(f2, registros)
        regs2, _ = base.carregar_base(f2)
        check("Gravação e releitura preservam os registros", len(regs2) == len(registros))
    print(f"\n{'Todas as verificações passaram.' if falhas == 0 else str(falhas) + ' verificação(ões) falharam.'}")
    return falhas


if __name__ == "__main__":
    sys.exit(main())
