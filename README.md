# Citizen Assist AI

**Equipe:** _[NOME DA EQUIPE]_
**Integrantes:** Pedro Sales — RM275709
**Global Solution 2026.2 – CitizenTech (FIAP)**
**Repositório:** https://github.com/PedroSales-dev/Citzen_Assist_GS

## 1. Problema, público e temas
Cidadãos encontram informações dispersas e termos difíceis ao buscar orientações sobre documentos, serviços e direitos. O Citizen Assist AI é um assistente textual que consulta uma base de orientações **com fonte e data de verificação**, apresenta a resposta com referência e **avisa quando não há base suficiente**.
Público: qualquer cidadão com dúvidas do cotidiano. Temas: **documentos** (CPF, identidade, título, passaporte, CNH), **serviços** (carteira de trabalho, seguro-desemprego, INSS, CadÚnico, SUS), **direitos** (consumidor, idoso, assistência jurídica) e **comunitário** (emergências, denúncias, CRAS, Conselho Tutelar). Total: 19 registros em 4 temas.

## 2. Base de conhecimento, estruturas e busca
- Arquivo `data/base_conhecimento.json`. Campos obrigatórios: `id, tema, subtema, palavras_chave, pergunta, orientacao, referencia, data_verificacao`. Opcionais: `url, aviso, relacionados`.
- **Lista de dicionários** guarda os registros; **dicionário id→registro** dá acesso direto por código; **árvore tema→subtema→ids** (dicionário aninhado) organiza a hierarquia; **grafo não direcionado** (lista de adjacência a partir de `relacionados`) permite navegar entre assuntos, com **BFS** (`explorar_relacionados`).
- Validação (`src/base.py`): arquivo ausente, vazio, JSON inválido, campos faltando ou com tipo errado, data inválida, id duplicado e relacionados inexistentes. A gravação é segura (arquivo temporário + substituição). Registros inválidos são ignorados com aviso; se nenhum for válido, o programa encerra com mensagem clara.
- Manutenção: é possível **adicionar** (menu 4) ou **corrigir** (menu 5) registros sem mexer nas regras do programa, ou editando o JSON.
- **Estratégia de busca** (`src/busca.py`): normaliza o texto (minúsculas, sem acentos), remove palavras vazias, reduz cada palavra a um radical (6 primeiras letras, sem "s" final) e pontua cada registro: **3 pontos** por termo que coincide com palavras-chave/tema/subtema e **1 ponto** por termo que só aparece na pergunta/orientação. Exige pelo menos uma palavra-chave (pontuação ≥ 3). Um pequeno **dicionário de sinônimos** (ex.: "RG" → identidade, "quebrado" → defeito) amplia a consulta, e verbos genéricos ("tirar", "pedir") são ignorados.
- **Várias correspondências:** ordena por pontuação; se há **empate no topo**, a consulta é considerada **ambígua** e o usuário escolhe entre as opções empatadas; caso contrário, responde com o primeiro e oferece os demais como alternativas.

## 3. Regras de resposta, modelos de prompt e limitações
Condicionais tratam: consulta válida, ambígua, sem correspondência, vazia, inválida e com possível dado pessoal (padrão de CPF – não é processado nem gravado).
Dois modelos documentados em `src/prompts.py` (alterne no menu 6):
- **Modelo A – Resposta direta:** *"Papel: assistente que responde de forma curta e direta. Formato: orientação em 1 parágrafo + 'Fonte'. Limite: usar somente o conteúdo da base."*
- **Modelo B – Orientação estruturada:** *"Papel: assistente informativo de orientação cidadã que NÃO representa órgãos públicos. Formato: orientação, fonte com link, data de verificação, aviso, assuntos relacionados. Regras: citar sempre a fonte; usar só a base; sem base, informar o limite sem inventar; não pedir dados pessoais; linguagem simples."*

**Comparação** (`docs/comparacao_modelos.md`, 26 respostas): A atende 1,0/6 itens do checklist (média 41 palavras); B atende 6,0/6 (média 97 palavras). **B é o padrão**, pois sempre traz fonte com link, data, aviso e continuidade; A é mais curto, porém sem data, aviso nem navegação. Limite da comparação: o checklist mede presença de elementos, não a compreensão real do usuário.
Sem informação na base, o sistema exibe aviso de limitação, lista os temas e **não inventa instruções nem se apresenta como canal oficial**.

## 4. Testes e indicadores
`python tests/executar_testes.py` executa 36 perguntas (`data/perguntas_teste.json`): 8 diretas, 7 reformuladas, 2 fora dos temas, 5 de limitação (vazia, ambígua, símbolos, sem sentido, dado pessoal) e 14 "inéditas" (paráfrases mais livres). Também verifica os requisitos mínimos do trabalho e o tratamento de base ausente, vazia, corrompida ou com id duplicado. Resultados em `docs/resultados_testes.csv`.

| Indicador | Resultado |
|---|---|
| Perguntas testadas | 36 |
| Acertos | 36 |
| Taxa de acerto | 100% (22 iniciais + 14 inéditas) |
| Tempo médio de consulta | ≈ 0,85 ms (média de 200 execuções por pergunta) |
| Facilidade de uso | _[preencher após o teste: ver `docs/teste_usabilidade.md`]_ |

**Interpretação e limitações da avaliação:** a taxa de 100% é **otimista**. As perguntas foram escritas pela própria equipe, que conhece as palavras-chave da base. Além disso, o grupo "inéditas" revelou falhas numa primeira versão da busca (por exemplo, "tirar RG" ficou ambíguo e "minha encomenda chegou quebrada" ficou sem resposta); elas foram corrigidas com sinônimos, de modo que esse grupo **não é mais independente** e não prova generalização. O tempo em milissegundos reflete uma base pequena. A comparação dos modelos A e B mede a presença de elementos (checklist), não a compreensão do usuário.
**Melhorias possíveis:** (1) ampliar a base e os sinônimos com perguntas reais de usuários; (2) trocar a busca lexical por uma comparação semântica ou por correção ortográfica; (3) realizar testes de usabilidade com mais pessoas e perfis (idosos, leitores de tela).

## 5. Como executar
```bash
python src/sistema.py              # assistente
python tests/executar_testes.py    # testes e indicadores
```
Requer Python 3.8+; não usa bibliotecas externas.

## 6. Exemplos
- **Pergunta:** "Qual o prazo para pedir o seguro-desemprego?" → orientação (7º ao 120º dia), fonte Ministério do Trabalho e Emprego, data, aviso e assuntos relacionados.
- **Fora da base:** "Como fazer bolo de cenoura?" → aviso de limitação e lista de temas.
- **Entrada vazia:** pede para digitar algo ou usar o menu. **"documentos":** pede para escolher entre as opções empatadas. **Opção inexistente:** mensagem e retorno ao menu. **CPF digitado:** aviso de privacidade.

## 7. Clareza, acessibilidade, privacidade e informação não oficial
Linguagem simples; rótulos em texto (sem depender de cores ou emojis, melhor para leitores de tela); sem coleta de dados pessoais; aviso fixo de que o sistema **não é canal oficial**; fonte e data em toda resposta; recomendação de confirmar no órgão oficial.

## 8. Conclusões e limitações
O protótipo cumpre o fluxo pergunta → busca → orientação com fonte → continuidade. Limitações: base pequena, busca lexical sem compreensão semântica, informações podem ficar desatualizadas (`data_verificacao` ajuda a revisar), sem interface gráfica. Uso de IA: ver `docs/uso_ia.md`.

## Estrutura
```
src/ (sistema.py, base.py, busca.py, prompts.py)   data/ (base e perguntas)
tests/executar_testes.py                           docs/ (resultados, comparação, uso_ia, usabilidade)
```
