from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, select, or_, and_, cast, Text, literal, func, asc
from typing import Optional, List
from loguru import logger
from app.api.schemas.conversation import ConversationSearchResult, MessageSnippet
from app.models.message import Message
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.inbox_member import InboxMember

MESSAGE_SNIPPET_LENGTH = 100


async def find_conversation_by_id(
    db: AsyncSession, conversation_id: UUID, account_id: UUID
) -> Optional[Conversation]:
    """Retrieves a conversation by ID.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        conversation_id (UUID): The ID of the conversation to retrieve.
        account_id (UUID): The ID of the account to which the conversation belongs.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.contact_inbox))
        .options(selectinload(Conversation.inbox))
        .filter_by(id=conversation_id, account_id=account_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation {conversation.id}")
    else:
        logger.warning(f"[conversation] Not found: {conversation_id}")

    return conversation


async def find_conversations_by_inbox(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """Retrieves a list of conversations for a specific inbox.

    Conversations are ordered by the timestamp of the last message
    in descending order, returning the most recent ones first.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The identifier for the inbox.
        account_id (UUID): The account identifier.
        limit (int, optional): The maximum number of records to return (default is 20).
        offset (int, optional): The number of records to skip for pagination (default is 0).

    Returns:
        List[Conversation]: A list of Conversation objects.

    Raises:
        SQLAlchemyError: If an error occurs during the database query.
    """
    try:
        query = (
            select(Conversation)
            .options(
                joinedload(Conversation.contact_inbox).joinedload(ContactInbox.contact)
            )
            .filter(
                Conversation.account_id == account_id, Conversation.inbox_id == inbox_id
            )
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database query error: {e}")
        raise e


async def find_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    contact_inbox_id: UUID,
    account_id: UUID,
) -> Optional[Conversation]:
    """Retrieves a conversation for a contact within an inbox and account.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The ID of the inbox.
        contact_inbox_id (UUID): The ID of the contact inbox.
        account_id (UUID): The ID of the account.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation).filter_by(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation (id={conversation.id})")
    else:
        logger.info(
            f"[conversation] No conversation found for contact_inbox_id {contact_inbox_id}"
        )

    return conversation


async def get_or_create_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    contact_inbox_id: UUID,
) -> Conversation:
    """Finds or creates a conversation for a given contact in an inbox.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The ID of the inbox.
        account_id (UUID): The ID of the account.
        contact_inbox_id (UUID): The ID of the contact inbox.

    Returns:
        Conversation: The conversation object.
    """
    conversation = await find_conversation(
        db=db,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        account_id=account_id,
    )

    if conversation:
        return conversation

    logger.info(
        f"[conversation] Creating new conversation for contact_inbox_id {contact_inbox_id}"
    )

    result = await db.execute(
        select(ContactInbox)
        .options(joinedload(ContactInbox.contact))
        .filter_by(
            id=contact_inbox_id,
        )
    )
    contact_inbox: ContactInbox = result.scalar_one_or_none()

    additional_attributes: dict = {}
    additional_attributes["contact_name"] = contact_inbox.contact.name
    additional_attributes["phone_number"] = contact_inbox.contact.phone_number

    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status="open",
        additional_attributes=additional_attributes,
    )
    db.add(conversation)
    await db.flush()
    await db.commit()
    await db.refresh(conversation)

    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation


async def find_conversations_by_user(
    db: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """Retrieves all conversations accessible to a given user based on inbox membership.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.
        limit (int): Pagination limit.
        offset (int): Pagination offset.

    Returns:
        List[Conversation]: Conversations accessible to the user.
    """
    inbox_ids_subquery = (
        select(InboxMember.inbox_id).filter(InboxMember.user_id == user_id)
    ).scalar_subquery()

    logger.debug(f"Founded user inbox ids: {inbox_ids_subquery}")
    query = (
        select(Conversation)
        .options(
            selectinload(Conversation.contact_inbox).selectinload(ContactInbox.contact)
        )
        .filter(
            Conversation.account_id == account_id,
            Conversation.inbox_id.in_(inbox_ids_subquery),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()
    return conversations


async def search_conversations(
    db: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    query: str,
    offset: int = 0,
    limit: int = 100,
) -> List[ConversationSearchResult]:
    """
    Asynchronously searches conversations with prioritization:
    1. Matches on contact name or phone number.
    2. Matches on message content.
    Includes the ID of the most recent matching message if found via content.

    Args:
        db: The SQLAlchemy AsyncSession.
        query: The search term.
        offset: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        A list of prioritized and paginated ConversationSearchResult objects.
    """
    search_term = f"%{query}%"

    user_inbox_ids_subquery = (
        select(InboxMember.inbox_id).filter(InboxMember.user_id == user_id)
    ).scalar_subquery()

    # --- CTE 1: Name and Phone Matches (Rank 1) ---
    name_phone_matches_cte = (
        select(
            Conversation.id.label("conversation_id"),
            literal(1).label("match_rank"),
            # This is nota a message ID for this rank, so we use a literal None
            literal(None).label("matching_message_id"),
        )
        .select_from(Conversation)
        .filter(
            or_(
                cast(Conversation.additional_attributes["contact_name"], Text).ilike(
                    search_term
                ),
                cast(Conversation.additional_attributes["phone_number"], Text).ilike(
                    search_term
                ),
            )
        )
    ).cte("name_phone_matches")

    # --- CTE 2: Message Content Matches (Rank 2) ---
    # Precisamos encontrar a *mensagem correspondente mais recente* para cada conversa
    # Usamos ROW_NUMBER() particionado por conversa, ordenado por timestamp DESC
    message_subquery = (
        select(
            Message.conversation_id,
            Message.id.label("message_id"),
            Message.sent_at,
            # Particiona por conversa, ordena por mais recente, pega a #1
            func.row_number()
            .over(
                partition_by=Message.conversation_id,
                order_by=desc(Message.sent_at),
            )
            .label("rnk"),
        )
        .select_from(Message)
        .filter(Message.content.ilike(search_term))
        .subquery("message_subquery")
    )

    # CTE final para message matches, selecionando apenas a mais recente (rnk=1)
    message_matches_cte = (
        select(
            message_subquery.c.conversation_id.label("conversation_id"),
            literal(2).label("match_rank"),
            message_subquery.c.message_id.label("matching_message_id"),
        )
        .select_from(message_subquery)
        .where(message_subquery.c.rnk == 1)
    ).cte("message_matches")

    # --- CTE 3: Combine Matches using UNION ALL ---
    combined_matches_cte = (
        select(
            name_phone_matches_cte.c.conversation_id,
            name_phone_matches_cte.c.match_rank,
            name_phone_matches_cte.c.matching_message_id,
        ).union_all(
            select(
                message_matches_cte.c.conversation_id,
                message_matches_cte.c.match_rank,
                cast(message_matches_cte.c.matching_message_id, Text).label(
                    "matching_message_id"
                ),
            )
        )
    ).cte("combined_matches")

    # --- CTE 4: Prioritize using ROW_NUMBER ---
    # Seleciona a melhor correspondência (menor rank) para cada conversation_id
    prioritized_matches_cte = (
        select(
            combined_matches_cte.c.conversation_id,
            combined_matches_cte.c.match_rank,
            combined_matches_cte.c.matching_message_id,
            # Particiona por ID da conversa, ordena pelo rank (ASC para priorizar 1), pega a #1
            func.row_number()
            .over(
                partition_by=combined_matches_cte.c.conversation_id,
                order_by=asc(
                    combined_matches_cte.c.match_rank
                ),  # Ordem crescente de rank
            )
            .label("priority_rnk"),
        ).select_from(combined_matches_cte)
    ).cte("prioritized_matches")

    # --- Final Query: Select prioritized conversations, order, and paginate ---
    final_selection_stmt = (
        select(
            prioritized_matches_cte.c.conversation_id,
            prioritized_matches_cte.c.match_rank,
            prioritized_matches_cte.c.matching_message_id,
            Conversation.last_message_at,  # Para ordenação final
        )
        .select_from(prioritized_matches_cte)
        # Junta de volta com Conversation para obter last_message_at para ordenação
        .join(
            Conversation, prioritized_matches_cte.c.conversation_id == Conversation.id
        )
        .where(
            prioritized_matches_cte.c.priority_rnk == 1
        )  # Pega apenas a melhor correspondência por conversa
        # Ordenação final: primeiro por rank (ASC), depois por atividade mais recente (DESC)
        .filter(Conversation.inbox_id.in_(user_inbox_ids_subquery))
        .order_by(
            asc(prioritized_matches_cte.c.match_rank),
            desc(Conversation.last_message_at),
        )
        .offset(offset)
        .limit(limit)
    )

    # Execute para obter os IDs e informações de rank/mensagem correspondente
    final_selection_result = await db.execute(final_selection_stmt)
    # Usar mappings para obter dicionários com nomes de coluna
    prioritized_results = final_selection_result.mappings().all()

    if not prioritized_results:
        return []

    conversation_ids_to_fetch = [res["conversation_id"] for res in prioritized_results]
    # Mapeamento para fácil acesso ao rank e matching_message_id depois
    result_info_map = {
        res["conversation_id"]: {
            "rank": res["match_rank"],
            "matching_message_id": res["matching_message_id"],
        }
        for res in prioritized_results
    }

    # === Fetch Conversation Objects ===
    conversations_stmt = (
        select(Conversation).filter(Conversation.id.in_(conversation_ids_to_fetch))
        # Tentar preservar a ordem (pode ser feito reordenando no Python depois)
    )
    conversations_result = await db.execute(conversations_stmt)
    # Criar um mapa para fácil acesso e reordenação
    conversations_map = {conv.id: conv for conv in conversations_result.scalars().all()}
    # Reordenar de acordo com a ordem priorizada original
    matched_conversations = [
        conversations_map[id_]
        for id_ in conversation_ids_to_fetch
        if id_ in conversations_map
    ]

    # === Post-process to build results (similar to before, but use rank/matching_id) ===
    results: List[ConversationSearchResult] = []
    for conv in matched_conversations:
        conv_info = result_info_map[conv.id]
        match_rank = conv_info["rank"]
        pre_fetched_matching_message_id = conv_info["matching_message_id"]

        # --- Fetch Matching Message Snippet (se rank=2 e ID existe) ---
        most_recent_matching_message: Optional[Message] = None
        if match_rank == 2 and pre_fetched_matching_message_id:
            # Busca a mensagem específica que foi identificada na CTE
            # Isso evita a necessidade de refazer a busca ILIKE aqui
            matching_message_stmt = (
                select(Message)
                .where(Message.id == pre_fetched_matching_message_id)
                .limit(1)  # Deve retornar apenas uma
            )
            matching_message_result = await db.execute(matching_message_stmt)
            most_recent_matching_message = matching_message_result.scalar_one_or_none()
            # Se, por alguma razão, a mensagem não for encontrada (improvável), ele permanecerá None

        # --- Build Result Item ---
        try:
            phone_number = conv.additional_attributes.get("phone_number")
            contact_name = conv.additional_attributes.get("contact_name")
            profile_picture_url = conv.additional_attributes.get("profile_picture_url")
            updated_at = conv.last_message_at or conv.updated_at

            last_msg_snippet = MessageSnippet(
                id=conv.additional_attributes.get("last_message")["id"],
                content=conv.additional_attributes.get("last_message")["content"],
                sent_at=conv.last_message_at,
            )

            matching_msg_snippet = None
            if most_recent_matching_message:  # Usar a mensagem buscada pelo ID
                matching_msg_snippet = MessageSnippet(
                    id=most_recent_matching_message.id,
                    content=(most_recent_matching_message.content or "")[
                        :MESSAGE_SNIPPET_LENGTH
                    ],
                    sent_at=most_recent_matching_message.sent_at,
                )

            result_item = ConversationSearchResult(
                id=conv.id,
                phone_number=str(phone_number) if phone_number is not None else None,
                contact_name=contact_name,
                profile_picture_url=profile_picture_url,
                updated_at=updated_at,
                last_message=last_msg_snippet,
                matching_message=matching_msg_snippet,
            )
            results.append(result_item)
        except Exception as e:
            logger.error(
                f"Error processing conversation {conv.id} for search results: {e}"
            )
            continue

    return results


async def get_message_context(
    db: AsyncSession,
    *,
    account_id: UUID,
    conversation_id: UUID,
    target_message_id: UUID,
    limit_before: int = 5,
    limit_after: int = 5,
) -> List[Message]:
    """
    Fetches a message and its surrounding context within a conversation.

    Retrieves a specified number of messages chronologically before and after
    a target message, including the target message itself.

    Args:
        db: The SQLAlchemy AsyncSession.
        conversation_id: The ID of the conversation.
        target_message_id: The ID of the message to center the context around.
        limit_before: Max number of messages to fetch before the target message.
        limit_after: Max number of messages to fetch after (and including) the target message.

    Returns:
        A list of Message objects representing the context, ordered chronologically.
        Returns an empty list if the target message or conversation is not found.
    """
    # 1. Fetch the target message
    target_msg_stmt = select(Message).where(
        and_(
            Message.account_id == account_id,
            Message.id == target_message_id,
            Message.conversation_id == conversation_id,
        )
    )
    target_msg_result = await db.execute(target_msg_stmt)
    target_message = target_msg_result.scalar_one_or_none()

    if not target_message:
        return []

    # 2. Fetching the context messages before the target message
    before_stmt = (
        select(Message)
        .where(
            and_(
                Message.account_id == account_id,
                Message.conversation_id == conversation_id,
                Message.sent_at < target_message.sent_at,
            )
        )
        .order_by(desc(Message.sent_at), desc(Message.created_at))
        .limit(limit_before)
    )
    before_result = await db.execute(before_stmt)
    messages_before = before_result.scalars().all()

    # 3. Fetching the context messages after the target message
    after_stmt = (
        select(Message)
        .where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sent_at >= target_message.sent_at,
            )
        )
        .order_by(asc(Message.sent_at), asc(Message.id))
        .limit(limit_after + 1)
    )
    after_result = await db.execute(after_stmt)
    messages_after = after_result.scalars().all()

    # Combina e ordena
    # Reverse 'before' list to have the chronological order
    combined_messages = list(reversed(messages_before)) + messages_after

    # Remove duplicates
    # final_message_map = {msg.id: msg for msg in combined_messages}

    # Retorna a lista final ordenada (o dicionário não garante ordem, então reordenamos pelas IDs combinadas se necessário, mas a concatenação já deve ter a ordem correta)
    # A concatenação `list(reversed(messages_before)) + messages_after` já deve estar ordenada corretamente por timestamp/id ASC.
    # return list(final_message_map.values()) -> Perde a ordem

    return combined_messages
