# backend/app/services/ai_reply/prompt_utils.py

WHATSAPP_MARKDOWN_INSTRUCTIONS = """
**Instruções de Formatação (Estilo WhatsApp - SEJA PRECISO):**
*   Para **Negrito**: Use *UM asterisco* de cada lado do texto. Exemplo: *texto em negrito*. **NÃO USE DOIS ASTERISCOS (`**texto**`)**.
*   Para *Itálico*: Use _UM sublinhado_ de cada lado do texto. Exemplo: _texto em itálico_. **NÃO USE UM ASTERISCO (`*texto*`)**.
*   Para ~Tachado~: Use ~UM til~ de cada lado do texto. Exemplo: ~texto tachado~.
*   Para `Monoespaçado`: Use `UMA crase` de cada lado do texto. Exemplo: `código ou termo técnico`.
*   Para Listas com Marcadores: Comece a linha com `- ` (hífen seguido de espaço) OU `* ` (asterisco seguido de espaço).
    - Exemplo de item
    * Outro exemplo de item
*   Para Listas Numeradas: Comece a linha com o número, um ponto e um espaço.
    1. Primeiro item
    2. Segundo item
*   Para Citação: Comece a linha com `> ` (sinal maior que seguido de espaço).
    > Texto citado aqui.
*   **IMPORTANTE:** Aplique a formatação *exatamente* como mostrado nos exemplos. Use negrito (*palavra*) para nomes de produtos, termos chave ou para dar ênfase importante. Use listas para clareza. Evite formatação excessiva.
"""
