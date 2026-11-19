"""Citizen Assist AI - assistente textual de orientação cidadã.
Executar:  python src/sistema.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import base
import busca
import prompts

CAMINHO_BASE = Path(__file__).resolve().parent.parent / "data" / "base_conhecimento.json"

BANNER = """
==============================================================
 CITIZEN ASSIST AI - orientações simples para o dia a dia
==============================================================
 Protótipo educacional. NÃO é um canal oficial de órgãos públicos.
 Não digite dados pessoais (CPF, RG, endereço, senhas).
 As orientações vêm de uma base com fontes citadas e podem estar
 desatualizadas: confirme sempre na fonte oficial.
"""


def ler(mensagem):
    try:
        return input(mensagem)
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando.")
        sys.exit(0)


class Assistente:
    def __init__(self, caminho=CAMINHO_BASE, modelo="B"):
        self.caminho = Path(caminho)
        self.modelo = modelo
        self.recarregar()

    def recarregar(self):
        self.registros, self.avisos = base.carregar_base(self.caminho)
        self.por_id = base.indexar_por_id(self.registros)
        self.arvore = base.temas_disponiveis(self.registros)
        self.grafo = base.construir_grafo(self.registros)

    def relacionados(self, reg, limite=3):
        ids = base.explorar_relacionados(self.grafo, reg["id"], 1)[:limite]
        return [self.por_id[i] for i in ids]

    def responder(self, reg):
        rel = self.relacionados(reg)
        return prompts.MODELOS[self.modelo]["formatar"](reg, rel)

    def consultar(self, texto):
        """Executa a consulta e retorna (resultado_da_busca, texto_para_exibir)."""
        res = busca.buscar(texto, self.registros)
        if res["status"] == "ok":
            return res, self.responder(res["registro"])
        if res["status"] == "ambiguo":
            opcoes = "\n".join(f"  [{r['id']}] {r['pergunta']}" for r in res["alternativas"])
            return res, f"{res['mensagem']}\n{opcoes}"
        if res["status"] == "sem_resposta":
            return res, prompts.aviso_sem_resposta(self.registros)
        return res, res["mensagem"]


def mostrar_registro(ass, reg):
    print("\n" + ass.responder(reg))
    rel = ass.relacionados(reg)
    if rel:
        print("\nContinuar a consulta? Digite o código de um assunto relacionado:")
        for r in rel:
            print(f"  [{r['id']}] {r['pergunta']}")
        cod = ler("Código (Enter para voltar ao menu): ").strip().upper()
        if cod:
            if cod in ass.por_id:
                mostrar_registro(ass, ass.por_id[cod])
            else:
                print("Código inexistente. Voltando ao menu.")


def menu_temas(ass):
    temas = sorted(ass.arvore)
    print("\nTemas disponíveis:")
    for i, t in enumerate(temas, 1):
        subs = ", ".join(sorted(ass.arvore[t]))
        print(f" {i}. {prompts.rotulo(t)}  ({subs})")
    op = ler("Escolha o número do tema (Enter para voltar): ").strip()
    if not op:
        return
    if not op.isdigit() or not 1 <= int(op) <= len(temas):
        print("Opção inexistente. Digite um dos números listados.")
        return
    tema = temas[int(op) - 1]
    regs = [r for r in ass.registros if r["tema"] == tema]
    print(f"\nAssuntos de {prompts.rotulo(tema)}:")
    for i, r in enumerate(regs, 1):
        print(f" {i}. {r['pergunta']}")
    op = ler("Escolha o assunto (Enter para voltar): ").strip()
    if not op:
        return
    if not op.isdigit() or not 1 <= int(op) <= len(regs):
        print("Opção inexistente.")
        return
    mostrar_registro(ass, regs[int(op) - 1])


def fluxo_pergunta(ass):
    texto = ler("\nDigite sua pergunta: ")
    res, saida = ass.consultar(texto)
    if res["status"] == "ok":
        mostrar_registro(ass, res["registro"])
        return
    print("\n" + saida)
    if res["status"] == "ambiguo":
        cod = ler("Digite o código do assunto desejado (Enter para voltar): ").strip().upper()
        if cod in ass.por_id:
            mostrar_registro(ass, ass.por_id[cod])
        elif cod:
            print("Código inexistente.")


def ver_por_codigo(ass):
    cod = ler("Código (ex.: D01): ").strip().upper()
    if cod in ass.por_id:
        mostrar_registro(ass, ass.por_id[cod])
    else:
        print("Código inexistente. Use o menu de temas para ver os códigos.")


def adicionar_registro(ass):
    print("\nNovo registro (todos os campos são obrigatórios, exceto aviso/url).")
    tema = ler("Tema: ").strip().lower()
    subtema = ler("Subtema: ").strip()
    pergunta = ler("Pergunta: ").strip()
    chaves = [p.strip() for p in ler("Palavras-chave (separadas por vírgula): ").split(",") if p.strip()]
    orient = ler("Orientação resumida: ").strip()
    ref = ler("Referência consultada: ").strip()
    url = ler("URL da fonte (opcional): ").strip()
    aviso = ler("Aviso (opcional): ").strip()
    rel = [c.strip().upper() for c in ler("Códigos de assuntos relacionados (opcional, separados por vírgula): ").split(",") if c.strip()]
    inexistentes = [c for c in rel if c not in ass.por_id]
    if inexistentes:
        print(f"Códigos inexistentes ignorados: {', '.join(inexistentes)}")
        rel = [c for c in rel if c in ass.por_id]
    prefixo = (tema[:1] or "X").upper()
    n = 1
    while f"{prefixo}{n:02d}" in ass.por_id:
        n += 1
    novo = {"id": f"{prefixo}{n:02d}", "tema": tema, "subtema": subtema,
            "palavras_chave": chaves, "pergunta": pergunta, "orientacao": orient,
            "referencia": ref, "data_verificacao": date.today().isoformat(), "relacionados": rel}
    if url:
        novo["url"] = url
    if aviso:
        novo["aviso"] = aviso
    problemas = base.validar_registro(novo)
    if problemas:
        print("Registro NÃO salvo:\n - " + "\n - ".join(problemas))
        return
    base.salvar_base(ass.caminho, ass.registros + [novo])
    ass.recarregar()
    print(f"Registro {novo['id']} salvo.")


def corrigir_registro(ass):
    cod = ler("Código do registro a corrigir: ").strip().upper()
    if cod not in ass.por_id:
        print("Código inexistente.")
        return
    reg = ass.por_id[cod]
    print("Orientação atual:", reg["orientacao"])
    nova = ler("Nova orientação (Enter mantém): ").strip()
    if nova:
        reg["orientacao"] = nova
        reg["data_verificacao"] = date.today().isoformat()
        base.salvar_base(ass.caminho, ass.registros)
        ass.recarregar()
        print("Registro atualizado.")


def alternar_modelo(ass):
    ass.modelo = "A" if ass.modelo == "B" else "B"
    m = prompts.MODELOS[ass.modelo]
    print(f"Modelo de resposta ativo: {ass.modelo} - {m['nome']}\nInstrução: {m['instrucao']}")


def main():
    print(BANNER)
    try:
        ass = Assistente()
    except base.BaseErro as e:
        print(f"ERRO ao carregar a base de conhecimento: {e}")
        sys.exit(1)
    for aviso in ass.avisos:
        print("AVISO:", aviso)
    print(f"Base carregada: {len(ass.registros)} orientações em {len(ass.arvore)} temas.")
    while True:
        print("\n--- MENU ---\n 1. Escolher um tema\n 2. Fazer uma pergunta\n"
              " 3. Ver assunto por código\n 4. Adicionar orientação à base\n"
              " 5. Corrigir orientação\n 6. Alternar modelo de resposta (A/B)\n 0. Sair")
        op = ler("Opção: ").strip()
        if op == "1":
            menu_temas(ass)
        elif op == "2":
            fluxo_pergunta(ass)
        elif op == "3":
            ver_por_codigo(ass)
        elif op == "4":
            adicionar_registro(ass)
        elif op == "5":
            corrigir_registro(ass)
        elif op == "6":
            alternar_modelo(ass)
        elif op == "0":
            print("Até logo! Lembre-se de confirmar as informações nas fontes oficiais.")
            break
        elif op == "":
            print("Você não digitou nada. Escolha uma opção do menu.")
        else:
            print("Opção inexistente. Digite um dos números do menu.")


if __name__ == "__main__":
    main()
