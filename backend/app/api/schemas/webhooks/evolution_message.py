# app/api/schemas/webhooks/evolution_message.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class EvolutionContextInfo(BaseModel):
    """Represents the contextInfo object, often for replies."""

    participant: Optional[str] = None  # Person who sent the original message
    quoted_message_id: Optional[str] = Field(
        None, alias="stanzaId"
    )  # Stanza ID of the message being replied to
    quoted_message_remote_jid: Optional[str] = Field(
        None, alias="remoteJid"
    )  # remoteJid of the message being replied to
    mentioned_jid: Optional[List[str]] = Field(None, alias="mentionedJid")
    # Add other relevant contextInfo fields if needed


class EvolutionMessageContent_Text(BaseModel):
    """Content for 'conversation' or 'extendedTextMessage'."""

    text: str
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Image(BaseModel):
    """Content for 'imageMessage'."""

    url: Optional[str] = None
    mimetype: str
    caption: Optional[str] = None
    file_length: Optional[str] = Field(None, alias="fileLength")  # Often a string
    height: Optional[int] = None
    width: Optional[int] = None
    media_key: Optional[str] = Field(None, alias="mediaKey")
    direct_path: Optional[str] = Field(None, alias="directPath")
    jpeg_thumbnail: Optional[str] = Field(None, alias="jpegThumbnail")  # Base64 encoded
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Video(BaseModel):
    """Content for 'videoMessage'."""

    url: Optional[str] = None
    mimetype: str
    caption: Optional[str] = None
    file_length: Optional[str] = Field(None, alias="fileLength")
    seconds: Optional[int] = None
    media_key: Optional[str] = Field(None, alias="mediaKey")
    direct_path: Optional[str] = Field(None, alias="directPath")
    jpeg_thumbnail: Optional[str] = Field(None, alias="jpegThumbnail")
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Audio(BaseModel):
    """Content for 'audioMessage'."""

    url: Optional[str] = None
    mimetype: str
    file_length: Optional[str] = Field(None, alias="fileLength")
    seconds: Optional[int] = None
    ptt: Optional[bool] = False  # True for voice note
    media_key: Optional[str] = Field(None, alias="mediaKey")
    direct_path: Optional[str] = Field(None, alias="directPath")
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Document(BaseModel):
    """Content for 'documentMessage' or 'documentWithCaptionMessage'."""

    url: Optional[str] = None
    mimetype: str
    title: Optional[str] = None  # Often the filename
    file_length: Optional[str] = Field(None, alias="fileLength")
    page_count: Optional[int] = Field(None, alias="pageCount")
    file_name: Optional[str] = Field(None, alias="fileName")
    caption: Optional[str] = None  # For documentWithCaptionMessage
    media_key: Optional[str] = Field(None, alias="mediaKey")
    direct_path: Optional[str] = Field(None, alias="directPath")
    jpeg_thumbnail: Optional[str] = Field(None, alias="jpegThumbnail")
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Sticker(BaseModel):
    """Content for 'stickerMessage'."""

    url: Optional[str] = None
    mimetype: str
    height: Optional[int] = None
    width: Optional[int] = None
    is_animated: Optional[bool] = Field(None, alias="isAnimated")
    media_key: Optional[str] = Field(None, alias="mediaKey")
    direct_path: Optional[str] = Field(None, alias="directPath")
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionMessageContent_Location(BaseModel):
    """Content for 'locationMessage'."""

    degrees_latitude: float = Field(..., alias="degreesLatitude")
    degrees_longitude: float = Field(..., alias="degreesLongitude")
    name: Optional[str] = None
    address: Optional[str] = None
    jpeg_thumbnail: Optional[str] = Field(None, alias="jpegThumbnail")
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


# For Interactive Messages (Buttons Response, List Response)
class EvolutionButtonsResponseMessage(BaseModel):
    """Content for 'buttonsResponseMessage' (user clicked a button)."""

    selected_button_id: str = Field(..., alias="selectedButtonId")
    selected_display_text: str = Field(..., alias="selectedDisplayText")
    type: Optional[int] = None  # e.g. 1 for quick reply
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionListResponseSingleSelectReply(BaseModel):
    selected_row_id: str = Field(..., alias="selectedRowId")


class EvolutionListResponseMessage(BaseModel):
    """Content for 'listResponseMessage' (user selected from a list)."""

    title: str
    description: Optional[str] = None
    single_select_reply: EvolutionListResponseSingleSelectReply = Field(
        ..., alias="singleSelectReply"
    )
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionTemplateButtonReplyMessage(BaseModel):
    """Content for 'templateButtonReplyMessage' (user clicked a template quick reply)."""

    selected_id: str = Field(
        ..., alias="selectedId"
    )  # This is the payload of the button
    selected_index: int = Field(..., alias="selectedIndex")
    selected_display_text: Optional[str] = Field(
        None, alias="selectedDisplayText"
    )  # Sometimes not present
    context_info: Optional[EvolutionContextInfo] = Field(None, alias="contextInfo")


class EvolutionReactionMessage(BaseModel):
    """Content for 'reactionMessage'."""

    text: str  # The emoji, or empty string if removing reaction
    key: Dict[str, Any]  # Key of the message being reacted to (id, remoteJid, fromMe)
    # senderTimestampMs, etc.


# --- Wrapper for the 'message' object in EvolutionWebhookData ---
# This helps get the actual content based on messageType
class EvolutionMessageObject(BaseModel):
    """
    Represents the 'message' field in the webhook data.
    It dynamically holds the specific message type content.
    """

    conversation: Optional[str] = None  # For simple text, this is the text
    extended_text_message: Optional[EvolutionMessageContent_Text] = Field(
        None, alias="extendedTextMessage"
    )
    image_message: Optional[EvolutionMessageContent_Image] = Field(
        None, alias="imageMessage"
    )
    video_message: Optional[EvolutionMessageContent_Video] = Field(
        None, alias="videoMessage"
    )
    audio_message: Optional[EvolutionMessageContent_Audio] = Field(
        None, alias="audioMessage"
    )
    document_message: Optional[EvolutionMessageContent_Document] = Field(
        None, alias="documentMessage"
    )
    document_with_caption_message: Optional[EvolutionMessageContent_Document] = Field(
        None, alias="documentWithCaptionMessage"
    )  # Shares structure
    sticker_message: Optional[EvolutionMessageContent_Sticker] = Field(
        None, alias="stickerMessage"
    )
    location_message: Optional[EvolutionMessageContent_Location] = Field(
        None, alias="locationMessage"
    )

    buttons_response_message: Optional[EvolutionButtonsResponseMessage] = Field(
        None, alias="buttonsResponseMessage"
    )
    list_response_message: Optional[EvolutionListResponseMessage] = Field(
        None, alias="listResponseMessage"
    )
    template_button_reply_message: Optional[EvolutionTemplateButtonReplyMessage] = (
        Field(None, alias="templateButtonReplyMessage")
    )

    reaction_message: Optional[EvolutionReactionMessage] = Field(
        None, alias="reactionMessage"
    )
    # Add other message types like contactsArrayMessage, productMessage etc. as needed

    # Sometimes, for simple text, the message object might just be a string.
    # Pydantic usually handles this by trying to parse. If it's just a string,
    # and 'conversation' is the field, it should work.
    # However, Evolution usually nests it, e.g., {"conversation": "hello"}.

    class Config:
        extra = "ignore"  # Ignore fields not defined in these models
