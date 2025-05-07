# backend/app/services/ai_reply/new_agent/components/state_updater.py

import time
from typing import Dict, List, Optional, Any, cast  # cast para type hinting
from loguru import logger
import copy  # Para fazer cópias profundas de partes do estado

# Importar definições de estado e schemas de análise
from ..state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    UserInterruption,
    IdentifiedObjectionEntry,
    IdentifiedNeedEntry,
    IdentifiedPainPointEntry,
    DynamicCustomerProfile,
    CustomerQuestionStatusType,  # Importar o tipo completo
    ObjectionStatusType,
)
from ..schemas.input_analysis import UserInputAnalysisOutput, ExtractedQuestionAnalysis


# (Opcional) Função para disparar evento (pode ir para um módulo de analytics)
async def _log_missing_information_event(account_id, conversation_id, question_core):
    """Placeholder: Logs missing information event (e.g., to DB or queue)."""
    logger.warning(
        f"[Analytics Event] MISSING_INFORMATION: Account={account_id}, Conv={conversation_id}, Question='{question_core}'"
    )
    # TODO: Implementar persistência real (async DB write ou queue)
    pass


async def update_conversation_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    LangGraph node responsible for updating the RichConversationState based on
    the analysis of the latest user input.
    """
    node_name = "update_conversation_state_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    # --- Preparar Atualizações (Trabalhar com Cópias) ---
    # É crucial fazer cópias de objetos mutáveis (listas, dicts) do estado
    # para evitar modificar o estado original diretamente de forma inesperada.
    # LangGraph pode reutilizar objetos de estado em algumas circunstâncias.
    updated_state_delta: Dict[str, Any] = (
        {}
    )  # Dicionário para armazenar apenas as mudanças

    current_turn = state.get(
        "current_turn_number", 0
    )  # Já deve ter sido incrementado? Não, incrementamos aqui.
    next_turn_number = current_turn + 1
    updated_state_delta["current_turn_number"] = next_turn_number

    # Obter a análise do nó anterior
    user_input_analysis_dict = state.get("user_input_analysis_result")
    if not user_input_analysis_dict:
        logger.warning(
            f"[{node_name}] No user_input_analysis_result found in state. Skipping state update."
        )
        # Limpar o campo de erro se ele existia do nó anterior, pois estamos apenas skipando
        return {"last_processing_error": None, "current_turn_number": next_turn_number}

    try:
        # Validar e parsear o dicionário de volta para o objeto Pydantic
        analysis = UserInputAnalysisOutput.model_validate(user_input_analysis_dict)
        logger.debug(f"[{node_name}] Successfully validated UserInputAnalysisOutput.")
    except Exception as e:
        logger.exception(
            f"[{node_name}] Failed to validate user_input_analysis_result: {e}"
        )
        return {
            "last_processing_error": f"State update failed: Invalid input analysis data. Details: {e}"
        }

    # Copiar listas e dicionários que serão modificados
    current_messages = list(state.get("messages", []))  # Cópia da lista
    current_question_log = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]  # Cópia profunda da lista de dicts
    current_interruptions = [
        interruption.copy()
        for interruption in state.get("user_interruptions_queue", [])
    ]  # Cópia
    # Copiar o perfil dinâmico para modificação segura
    current_dynamic_profile_dict = copy.deepcopy(
        state.get("customer_profile_dynamic", {})
    )
    # Validar/Recriar o objeto DynamicCustomerProfile para tipagem forte
    # (Pode ser um pouco overkill, mas garante a estrutura)
    try:
        # Tentar validar/criar o objeto a partir do dicionário copiado
        dynamic_profile = DynamicCustomerProfile(
            identified_needs=[
                IdentifiedNeedEntry(**n)
                for n in current_dynamic_profile_dict.get("identified_needs", [])
            ],
            identified_pain_points=[
                IdentifiedPainPointEntry(**p)
                for p in current_dynamic_profile_dict.get("identified_pain_points", [])
            ],
            identified_objections=[
                IdentifiedObjectionEntry(**o)
                for o in current_dynamic_profile_dict.get("identified_objections", [])
            ],
            certainty_levels=current_dynamic_profile_dict.get(
                "certainty_levels", {}
            ),  # Assumindo que certainty_levels é um dict simples
        )
    except Exception as profile_val_err:
        logger.error(
            f"[{node_name}] Failed to validate/recreate DynamicCustomerProfile: {profile_val_err}. Using empty profile."
        )
        # Criar um perfil vazio como fallback seguro
        dynamic_profile = DynamicCustomerProfile(
            identified_needs=[],
            identified_pain_points=[],
            identified_objections=[],
            certainty_levels={
                "product": None,
                "agent": None,
                "company": None,
                "last_assessed_turn": None,
            },
        )

    # --- 1. Atualizar Histórico de Mensagens ---
    # A mensagem do usuário já foi adicionada no início do turno ou pelo invoke?
    # Assumindo que o invoke adiciona a HumanMessage. Se não, adicionar aqui:
    # current_messages.append(HumanMessage(content=state.get("current_user_input_text", "")))
    # A resposta do agente será adicionada pelo nó ResponseGenerator.
    # Por enquanto, apenas passamos o histórico atualizado se ele foi modificado (raro aqui).
    # updated_state_delta["messages"] = current_messages # Apenas se modificarmos

    # --- 2. Processar Perguntas Extraídas ---
    newly_added_to_log_count = 0
    updated_log_entry_count = 0
    questions_for_interrupt_queue: List[ExtractedQuestionAnalysis] = []

    for q_analysis in analysis.extracted_questions:
        found_in_log = False
        log_entry_to_update: Optional[CustomerQuestionEntry] = None

        if q_analysis.is_repetition and q_analysis.original_question_turn is not None:
            # Tentar encontrar a entrada original no log pelo turno e talvez pelo texto core
            for i in range(
                len(current_question_log) - 1, -1, -1
            ):  # Buscar do fim para o início
                log_entry = current_question_log[i]
                if (
                    log_entry.get("turn_asked") == q_analysis.original_question_turn
                    and log_entry.get("extracted_question_core")
                    == q_analysis.original_question_core_text
                ):
                    log_entry_to_update = (
                        log_entry  # Encontrou a entrada para atualizar
                    )
                    found_in_log = True
                    break

        if log_entry_to_update:
            # Atualizar o status da entrada EXISTENTE no log
            original_status = log_entry_to_update.get("status")
            new_status: CustomerQuestionStatusType

            if q_analysis.status_of_original_answer == "answered_satisfactorily":
                new_status = "repetition_after_satisfactory_answer"
            elif q_analysis.status_of_original_answer == "answered_with_fallback":
                new_status = "repetition_after_fallback"
                # Disparar evento de informação faltante ao detectar repetição após fallback
                await _log_missing_information_event(
                    state.get("account_id"),
                    state.get("conversation_id"),
                    q_analysis.question_text,
                )
            else:  # unknown_previous_status ou None
                # Se não sabemos como foi respondido, tratar como se fosse nova? Ou um status específico?
                # Vamos manter o status original por enquanto ou marcar como repetição genérica?
                # Por segurança, vamos usar um status que indique repetição sem saber o resultado anterior.
                # Poderíamos adicionar "repetition_unknown_prior_answer" a CustomerQuestionStatusType
                # Por ora, vamos usar um status existente que indique que precisa de atenção.
                new_status = "repetition_after_fallback"  # Tratar como se não tivesse sido bem respondida

            # Atualizar apenas se o status mudar ou for relevante
            if log_entry_to_update.get("status") != new_status:
                log_entry_to_update["status"] = new_status
                updated_log_entry_count += 1
                logger.debug(
                    f"Updated question log entry (Turn {q_analysis.original_question_turn}) status to '{new_status}' for question: '{q_analysis.question_text[:50]}...'"
                )

            # Adicionar à fila de interrupções se for uma repetição que precisa ser tratada
            if new_status in [
                "repetition_after_satisfactory_answer",
                "repetition_after_fallback",
            ]:
                questions_for_interrupt_queue.append(q_analysis)

        else:
            # Adicionar nova entrada ao log
            new_log_entry = CustomerQuestionEntry(
                original_question_text=state.get(
                    "current_user_input_text", ""
                ),  # Usar o texto completo da msg atual como original? Ou só a pergunta? Melhor só a pergunta.
                extracted_question_core=q_analysis.question_text,
                turn_asked=next_turn_number,  # Pergunta feita neste turno que estamos processando
                status="newly_asked",  # Status inicial
                agent_direct_response_summary=None,
                repetition_of_turn=None,
                similarity_vector=None,  # TODO: Adicionar embedding aqui se calculado no InputProcessor
            )
            current_question_log.append(new_log_entry)
            newly_added_to_log_count += 1
            logger.debug(
                f"Added new question to log: '{q_analysis.question_text[:50]}...'"
            )
            # Adicionar à fila de interrupções para ser respondida
            questions_for_interrupt_queue.append(q_analysis)

    if newly_added_to_log_count > 0 or updated_log_entry_count > 0:
        updated_state_delta["customer_question_log"] = current_question_log
        logger.info(
            f"Customer question log updated: {newly_added_to_log_count} added, {updated_log_entry_count} updated."
        )

    # --- 3. Processar Objeções Extraídas ---
    newly_added_objections = 0
    for obj in analysis.extracted_objections:
        # Verificar se objeção similar já existe e está ativa/addressing
        # (Lógica de similaridade de objeções pode ser complexa - por ora, checar texto exato ou quase exato)
        is_duplicate = False
        for existing_obj in dynamic_profile["identified_objections"]:
            # TODO: Implementar checagem de similaridade mais robusta para objeções
            if existing_obj.get("text") == obj.objection_text and existing_obj.get(
                "status"
            ) in ["active", "addressing"]:
                is_duplicate = True
                break
        if not is_duplicate:
            new_objection_entry = IdentifiedObjectionEntry(
                text=obj.objection_text,
                status="active",  # Nova objeção está ativa
                rebuttal_attempts=0,
                source_turn=next_turn_number,
                related_to_proposal=None,  # TODO: Inferir se relacionado a proposta ativa
            )
            dynamic_profile["identified_objections"].append(new_objection_entry)
            newly_added_objections += 1
            logger.debug(f"Added new objection: '{obj.objection_text[:50]}...'")
            # Adicionar à fila de interrupções
            current_interruptions.append(
                UserInterruption(
                    type="objection",
                    text=obj.objection_text,
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )

    # --- 4. Processar Necessidades/Dores Extraídas ---
    newly_added_needs_pains = 0
    for np in analysis.extracted_needs_or_pains:
        # Verificar duplicatas (similaridade semântica seria ideal)
        target_list = (
            dynamic_profile["identified_needs"]
            if np.type == "need"
            else dynamic_profile["identified_pain_points"]
        )
        is_duplicate = any(
            existing_np.get("text") == np.text for existing_np in target_list
        )  # Checagem simples por texto

        if not is_duplicate:
            if np.type == "need":
                entry = IdentifiedNeedEntry(
                    text=np.text,
                    status="active",
                    priority=None,
                    source_turn=next_turn_number,
                )
                dynamic_profile["identified_needs"].append(entry)
            else:  # pain_point
                entry = IdentifiedPainPointEntry(
                    text=np.text, status="active", source_turn=next_turn_number
                )
                dynamic_profile["identified_pain_points"].append(entry)
            newly_added_needs_pains += 1
            logger.debug(f"Added new {np.type}: '{np.text[:50]}...'")

    # Se houve mudanças no perfil dinâmico, adicioná-lo ao delta de atualização
    if newly_added_objections > 0 or newly_added_needs_pains > 0:
        # Converter listas de TypedDicts de volta para listas de dicts para o estado
        updated_dynamic_profile_dict = {
            "identified_needs": [dict(n) for n in dynamic_profile["identified_needs"]],
            "identified_pain_points": [
                dict(p) for p in dynamic_profile["identified_pain_points"]
            ],
            "identified_objections": [
                dict(o) for o in dynamic_profile["identified_objections"]
            ],
            "certainty_levels": dynamic_profile[
                "certainty_levels"
            ],  # Assumindo que não foi modificado aqui
        }
        updated_state_delta["customer_profile_dynamic"] = updated_dynamic_profile_dict
        logger.info(
            f"Dynamic customer profile updated: {newly_added_objections} objections, {newly_added_needs_pains} needs/pains added."
        )

    # --- 5. Atualizar Fila de Interrupções ---
    # Adicionamos objeções e perguntas novas/repetidas que precisam de atenção
    for q_analysis in questions_for_interrupt_queue:
        # Evitar duplicatas na fila de interrupções para o mesmo turno
        is_already_in_queue = any(
            inter.get("text") == q_analysis.question_text
            and inter.get("type") == "direct_question"
            for inter in current_interruptions
            if inter.get("turn_detected") == next_turn_number
        )
        if not is_already_in_queue:
            current_interruptions.append(
                UserInterruption(
                    type="direct_question",
                    text=q_analysis.question_text,
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
            logger.debug(
                f"Added question to interruption queue: '{q_analysis.question_text[:50]}...'"
            )

    # Adicionar VagueStatement à fila se detectado
    if analysis.is_primarily_vague_statement:
        current_interruptions.append(
            UserInterruption(
                type="vague_statement",
                text=state.get(
                    "current_user_input_text", ""
                ),  # Usar texto completo da msg vaga
                status="pending_resolution",
                turn_detected=next_turn_number,
            )
        )
        logger.debug("Added vague statement to interruption queue.")

    # Adicionar OffTopic à fila se detectado (Planner decidirá como lidar)
    if analysis.is_primarily_off_topic:
        current_interruptions.append(
            UserInterruption(
                type="off_topic_comment",
                text=state.get("current_user_input_text", ""),
                status="pending_resolution",  # Planner decide se resolve ou ignora
                turn_detected=next_turn_number,
            )
        )
        logger.debug("Added off-topic comment to interruption queue.")

    # Se a fila de interrupções foi modificada, atualiza o estado
    if len(current_interruptions) != len(state.get("user_interruptions_queue", [])):
        updated_state_delta["user_interruptions_queue"] = current_interruptions
        logger.info(
            f"User interruption queue updated. Size: {len(current_interruptions)}"
        )

    # --- 6. Processar Análise da Resposta à Ação do Agente ---
    # Esta informação será usada principalmente pelo Planner no próximo passo.
    # Poderíamos armazená-la no estado se for útil para referência futura,
    # mas por enquanto, vamos assumir que o Planner a consumirá diretamente.
    # Ex: Se analysis.analysis_of_response_to_agent_action.user_response_to_agent_action == "ignored_agent_action",
    # o Planner pode decidir tentar a `last_agent_action` novamente.
    logger.debug(
        f"Analysis of user response to agent action: {analysis.analysis_of_response_to_agent_action.user_response_to_agent_action}"
    )
    # Poderíamos limpar state["last_agent_action"] aqui, pois já foi analisado? Talvez.
    # updated_state_delta["last_agent_action"] = None

    # --- 7. Atualizar Metadados ---
    updated_state_delta["last_interaction_timestamp"] = time.time()

    # Limpar o resultado da análise do input, pois já foi processado
    updated_state_delta["user_input_analysis_result"] = None
    # Limpar erro anterior, se houver, pois este nó rodou com sucesso (aparentemente)
    updated_state_delta["last_processing_error"] = None

    logger.info(f"[{node_name}] State update complete for Turn {next_turn_number}.")
    logger.debug(
        f"[{node_name}] State delta to be returned: {updated_state_delta.keys()}"
    )

    # Retorna apenas os campos que foram modificados
    return updated_state_delta
