# app/services/sales_agent/tools/offering.py

from typing import Optional, List, Literal, Dict, Any
from uuid import UUID
from loguru import logger
from typing_extensions import Annotated

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.services.sales_agent.agent_state import AgentState, ShoppingCartItem
from app.api.schemas.company_profile import OfferingInfo


@tool
async def get_offering_details_by_id(
    offering_id_str: str,
    state: Annotated[AgentState, InjectedState],
) -> str:
    """
    Retrieves detailed information about a specific offering using its unique ID.

    This tool should be used when a user asks for more details about a product
    or service and an ID is available or can be inferred from the conversation.

    Args:
        offering_id_str: The unique identifier (string representation of UUID)
                         of the offering to retrieve details for.
        state: The current state of the agent, providing access to company profile
               and its offering overview.

    Returns:
        A string containing formatted details of the offering if found.
        If the offering ID is invalid or not found, an appropriate message is returned.
        If the company profile or offering overview is missing, an error message is returned.
    """
    tool_name = "get_offering_details_by_id"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(f"[{tool_name}] Received offering_id_str: '{offering_id_str}'")

    if not offering_id_str:
        logger.warning(f"[{tool_name}] No offering_id_str provided.")
        return "Please provide an offering ID to get details."

    try:
        offering_uuid = UUID(offering_id_str)
    except ValueError:
        logger.warning(
            f"[{tool_name}] Invalid UUID format for offering_id_str: '{offering_id_str}'"
        )
        return (
            f"The provided offering ID '{offering_id_str}' is not in a valid format. "
            "An offering ID should be a standard unique identifier."
        )

    company_profile = state.company_profile
    if not company_profile:
        logger.error(f"[{tool_name}] Company profile is missing from agent state.")
        return "Internal error: Company information is currently unavailable."

    if not company_profile.offering_overview:
        logger.info(
            f"[{tool_name}] No offerings listed in the company profile for account {state.account_id}."
        )
        return "There are currently no offerings listed to provide details for."

    found_offering: Optional[OfferingInfo] = None
    for offering in company_profile.offering_overview:
        if offering.id == offering_uuid:
            found_offering = offering
            break

    if found_offering:
        logger.info(
            f"[{tool_name}] Found offering: '{found_offering.name}' (ID: {offering_uuid})"
        )
        details_parts = [
            f"Here are the details for '{found_offering.name}':",
            f"- Description: {found_offering.short_description}",
        ]
        if found_offering.key_features:
            features_str = "\n  ".join(
                [f"- {feature}" for feature in found_offering.key_features]
            )
            details_parts.append(f"- Key Features:\n  {features_str}")
        if found_offering.price_info:
            details_parts.append(f"- Price: {found_offering.price_info}")
        elif found_offering.price is not None:
            details_parts.append(f"- Price: {found_offering.price}")

        if found_offering.bonus_items:
            bonus_str = "\n  ".join(
                [f"- {bonus}" for bonus in found_offering.bonus_items]
            )
            details_parts.append(f"- Bonus Items:\n  {bonus_str}")
        if found_offering.link:
            details_parts.append(f"- Checkout Link: {found_offering.link}")

        return "\n".join(details_parts)
    else:
        logger.info(
            f"[{tool_name}] Offering with ID '{offering_uuid}' not found in company profile."
        )
        return (
            f"I couldn't find an offering with the ID '{offering_uuid}'. "
            "Please double-check the ID or ask for a list of available offerings."
        )


# --- Tool: Update Shopping Cart ---
CartAction = Literal["add", "remove", "update_quantity"]


@tool
async def update_shopping_cart(
    action: CartAction,
    offering_id_str: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    quantity: Optional[int] = None,
) -> Command:
    """
    Internal tool to manage a draft list of offerings the user is interested in.
    Use this to add, remove, or update quantities of items as you understand the
    user's needs, building towards a potential order. This helps organize items
    before presenting a summary or generating a checkout link.
    The user is not directly shown the result of every single cart modification;
    instead, the cart's contents are used by you (the AI) to inform your responses
    and proposals. For example, after several interactions, you might summarize
    the cart's contents by saying, 'So, it looks like you're interested in X and Y...'.
    This tool returns a status message about the operation for your internal logging,
    but you should decide if and how to communicate changes to the user based on
    the conversational context.

    Args:
        action: 'add', 'remove', or 'update_quantity'.
        offering_id_str: The unique ID of the offering.
        state: Agent's current state.
        tool_call_id: The ID of the tool call.
        quantity: Number of items.

    Returns:
        A Command object with updates for 'shopping_cart' and a ToolMessage
        containing a status of the cart operation (primarily for agent's internal log).
    """

    tool_name = "update_shopping_cart"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")
    logger.info(
        f"[{tool_name}] Action: {action}, Offering ID: {offering_id_str}, Quantity: {quantity}"
    )

    # Create a mutable copy of the shopping cart from the current state
    current_shopping_cart: List[ShoppingCartItem] = (
        list(state.shopping_cart) if state.shopping_cart else []
    )

    tool_message_content: str = ""
    state_updates: Dict[str, Any] = {}

    # --- Validations and Setup ---
    if not offering_id_str:
        logger.warning(f"[{tool_name}] No offering_id_str provided.")
        tool_message_content = "Please provide an offering ID to update the cart."
        state_updates["messages"] = [
            ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
        ]
        return Command(update=state_updates)

    try:
        offering_uuid = UUID(offering_id_str)
    except ValueError:
        logger.warning(
            f"[{tool_name}] Invalid UUID format for offering_id_str: '{offering_id_str}'"
        )
        tool_message_content = (
            f"The provided offering ID '{offering_id_str}' is not valid. "
            "Please use a correct offering ID."
        )
        state_updates["messages"] = [
            ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
        ]
        return Command(update=state_updates)

    company_profile = state.company_profile
    if not company_profile or not company_profile.offering_overview:
        logger.error(
            f"[{tool_name}] Company profile or offering overview is missing. Account: {state.account_id}"
        )
        tool_message_content = "Internal error: Product information is currently unavailable to manage the cart."
        state_updates["messages"] = [
            ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
        ]
        return Command(update=state_updates)

    target_offering_in_profile: Optional[OfferingInfo] = None
    for item_in_profile in company_profile.offering_overview:
        if item_in_profile.id == offering_uuid:
            target_offering_in_profile = item_in_profile
            break

    # --- Find item in the current_shopping_cart (the copy) ---
    existing_cart_item_index: Optional[int] = None
    for i, cart_item_loop in enumerate(current_shopping_cart):
        if cart_item_loop.offering_id == offering_uuid:
            existing_cart_item_index = i
            break

    current_cart_item_in_copied_list: Optional[ShoppingCartItem] = None
    if existing_cart_item_index is not None:
        current_cart_item_in_copied_list = current_shopping_cart[
            existing_cart_item_index
        ]

    # --- Perform Action ---
    if action == "add":
        if not target_offering_in_profile:
            logger.warning(
                f"[{tool_name}] Offering ID '{offering_uuid}' not found in profile for 'add'."
            )
            tool_message_content = (
                f"Sorry, I couldn't find offering ID '{offering_uuid}' to add."
            )
        elif quantity is None or quantity <= 0:
            logger.warning(
                f"[{tool_name}] Invalid quantity '{quantity}' for 'add' action."
            )
            tool_message_content = (
                "To add an item, please specify a quantity greater than zero."
            )
        else:
            if current_cart_item_in_copied_list:
                current_cart_item_in_copied_list.quantity += quantity
                if current_cart_item_in_copied_list.unit_price is not None:
                    current_cart_item_in_copied_list.item_total = (
                        current_cart_item_in_copied_list.quantity
                        * current_cart_item_in_copied_list.unit_price
                    )
                logger.info(
                    f"[{tool_name}] Increased quantity of '{current_cart_item_in_copied_list.name}' to {current_cart_item_in_copied_list.quantity}."
                )
                tool_message_content = f"Updated quantity of '{current_cart_item_in_copied_list.name}' in your cart to {current_cart_item_in_copied_list.quantity}."
            else:
                new_cart_item = ShoppingCartItem(
                    offering_id=offering_uuid,
                    name=target_offering_in_profile.name,
                    checkout_link=target_offering_in_profile.link,
                    quantity=quantity,
                    unit_price=target_offering_in_profile.price,
                    item_total=(
                        (quantity * target_offering_in_profile.price)
                        if target_offering_in_profile.price is not None
                        else None
                    ),
                )
                current_shopping_cart.append(new_cart_item)
                logger.info(
                    f"[{tool_name}] Added '{new_cart_item.name}' (Qty: {quantity}) to cart."
                )
                tool_message_content = (
                    f"Added {quantity} of '{new_cart_item.name}' to your cart."
                )
            state_updates["shopping_cart"] = current_shopping_cart

    elif action == "remove":
        if current_cart_item_in_copied_list:
            item_name = current_cart_item_in_copied_list.name
            current_shopping_cart.pop(existing_cart_item_index)
            logger.info(f"[{tool_name}] Removed '{item_name}' from cart.")
            tool_message_content = f"Removed '{item_name}' from your cart."
            state_updates["shopping_cart"] = current_shopping_cart
        else:
            logger.info(
                f"[{tool_name}] Item with ID '{offering_uuid}' not found in cart to remove."
            )
            tool_message_content = f"Item with ID '{offering_uuid}' was not found in your cart, so I couldn't remove it."

    elif action == "update_quantity":
        if quantity is None:
            logger.warning(
                f"[{tool_name}] No quantity provided for 'update_quantity' action."
            )
            tool_message_content = "Please specify the new quantity for the item."
        elif not current_cart_item_in_copied_list:
            logger.info(
                f"[{tool_name}] Item ID '{offering_uuid}' not in cart to update quantity."
            )
            tool_message_content = f"Item with ID '{offering_uuid}' is not in your cart. Would you like to add it?"
        else:
            if quantity <= 0:
                item_name = current_cart_item_in_copied_list.name
                current_shopping_cart.pop(existing_cart_item_index)
                logger.info(
                    f"[{tool_name}] Quantity set to {quantity}. Removed '{item_name}' from cart."
                )
                tool_message_content = (
                    f"Set quantity to {quantity}. Removed '{item_name}' from your cart."
                )
            else:
                current_cart_item_in_copied_list.quantity = quantity
                if current_cart_item_in_copied_list.unit_price is not None:
                    current_cart_item_in_copied_list.item_total = (
                        current_cart_item_in_copied_list.quantity
                        * current_cart_item_in_copied_list.unit_price
                    )
                logger.info(
                    f"[{tool_name}] Updated quantity of '{current_cart_item_in_copied_list.name}' to {quantity}."
                )
                tool_message_content = f"Updated quantity of '{current_cart_item_in_copied_list.name}' in your cart to {quantity}."
            state_updates["shopping_cart"] = current_shopping_cart

    else:
        logger.error(f"[{tool_name}] Invalid action '{action}' received.")
        tool_message_content = f"An unexpected error occurred with the cart action '{action}'. Please try again."

    # Add the ToolMessage to the state updates
    state_updates["shopping_cart"] = [
        item.model_dump(mode="json") for item in state_updates["shopping_cart"]
    ]
    state_updates["messages"] = [
        ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
    ]

    return Command(update=state_updates)


# --- Tool: Generate Checkout Link for Cart ---
@tool
async def generate_checkout_link_for_cart(
    state: Annotated[AgentState, InjectedState],
) -> str:
    """
    Generates checkout links based on the current state of your internal draft
    shopping list (the shopping cart).
    IMPORTANT: Before calling this, ensure your internal draft list accurately
    reflects all items the user wishes to purchase. If you just updated the list,
    it's best to confirm its contents (perhaps by summarizing to the user or
    internally reviewing) before calling this tool.
    Only use this when the user is explicitly ready to proceed with payment for the
    items you've gathered in the draft list.

    Args:
        state: Agent's current state.

    Returns:
        A string with cart summary and checkout links, or an error message.
    """
    tool_name = "generate_checkout_link_for_cart"
    logger.info(f"--- Executing Tool: {tool_name} ---")

    if not state.shopping_cart:
        logger.info(f"[{tool_name}] Shopping cart is empty. No links to generate.")
        return "Your shopping cart is currently empty. Please add some items before proceeding to checkout."

    cart_summary_parts = ["Here's a summary of your cart and your checkout link(s):"]
    grand_total: float = 0.0
    checkout_links: List[str] = []

    for item in state.shopping_cart:
        cart_summary_parts.append(
            f"- {item.name} (Qty: {item.quantity})"
            f"{f', Price: ${item.unit_price:.2f}' if item.unit_price is not None else ''}"
            f"{f', Total: ${item.item_total:.2f}' if item.item_total is not None else ''}"
        )
        if item.item_total is not None:
            grand_total += item.item_total

        checkout_link_w_qty = (
            f"{item.checkout_link}?item_id={item.offering_id}&quantity={item.quantity}"
        )
        checkout_links.append(f"  Link for {item.name}: {checkout_link_w_qty}")

    if checkout_links:
        cart_summary_parts.append(
            "\nPlease use the link(s) below to complete your purchase:"
        )
        cart_summary_parts.extend(checkout_links)
    else:
        logger.error(
            f"[{tool_name}] No checkout links were generated despite non-empty cart."
        )
        return (
            "Sorry, I couldn't generate checkout links at this time. Please try again."
        )

    if grand_total > 0:
        cart_summary_parts.append(f"\nGrand Total: ${grand_total:.2f}")

    state.current_sales_stage = "checkout_link_sent"
    logger.info(
        f"[{tool_name}] Cart links generated. Sales stage updated to '{state.current_sales_stage}'."
    )

    return "\n".join(cart_summary_parts)
