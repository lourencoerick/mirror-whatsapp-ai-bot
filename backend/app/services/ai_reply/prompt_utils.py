# backend/app/services/ai_reply/prompt_utils.py

WHATSAPP_MARKDOWN_INSTRUCTIONS = """
**Instruções de Formatação no Estilo WhatsApp — SIGA COM PRECISÃO:**

Aplique os estilos conforme os exemplos abaixo. *Não use variações*. A consistência é obrigatória.

- **Negrito**: Use *um* asterisco de cada lado.  
  ✅ Exemplo correto: *texto em negrito*  
  ❌ NUNCA use dois asteriscos: **texto**

- *Itálico*: Use _um_ sublinhado de cada lado.  
  ✅ Exemplo correto: _texto em itálico_  
  ❌ NUNCA use asteriscos: *texto*

- ~Tachado~: Use ~um~ til de cada lado.  
  ✅ Exemplo correto: ~texto tachado~

- `Monoespaçado`: Use `uma crase` de cada lado.  
  ✅ Exemplo correto: `comando`, `termo técnico`

- **Listas com Marcadores**:  
  Inicie com `- ` (hífen + espaço) ou `* ` (asterisco + espaço).  
  ✅ Exemplo:  
  - Item com hífen  
  * Item com asterisco

- **Listas Numeradas**:  
  Inicie com número, ponto e espaço.  
  ✅ Exemplo:  
  1. Primeiro item  
  2. Segundo item

- **Citação**:  
  Inicie a linha com `> ` (maior que + espaço).  
  ✅ Exemplo:  
  > Texto citado aqui.

⚠️ **IMPORTANTE**:  
- Use *negrito* para nomes de produtos, termos-chave e ênfases.  
- Utilize listas para tornar o conteúdo mais claro.  
- **Evite formatação excessiva**. Siga os exemplos *à risca*.
"""
