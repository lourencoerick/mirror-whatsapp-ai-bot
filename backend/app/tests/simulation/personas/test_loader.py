# backend/app/tests/simulation/personas/test_loader.py

import pytest
import json
import os
from unittest import mock  # Usaremos mock para simular leitura de arquivo
from uuid import UUID

# Importar o que será testado e os schemas
from app.simulation.personas import loader as persona_loader
from app.simulation.schemas.persona_definition import PersonaDefinition, InfoRequest

# Importar a configuração para mockar PERSONA_DIR se necessário
from app.simulation import config as simulation_config

# Marcar testes como asyncio pois a função é async (embora não use await interno agora)
pytestmark = pytest.mark.asyncio

# --- Fixtures ---


@pytest.fixture
def valid_persona_data() -> dict:
    """Provides a dictionary representing valid persona JSON data."""
    return {
        "persona_id": "test_valid_persona",
        "simulation_contact_identifier": "5511911119999",
        "description": "Valid test persona",
        "initial_message": "Hello AI",
        "objective": "Get price for Widget A",
        "information_needed": [{"entity": "Widget A", "attribute": "price"}],
        "info_attribute_to_question_template": {
            "price": "What is the price of {entity}?"
        },
        "success_criteria": ["state:all_info_extracted"],
        "failure_criteria": ["turn_count > 5"],
    }


@pytest.fixture
def invalid_schema_persona_data() -> dict:
    """Provides persona data missing a required field ('objective')."""
    return {
        "persona_id": "test_invalid_schema",
        "simulation_contact_identifier": "whatsapp:+222",
        "description": "Invalid test persona",
        "initial_message": "Hi",
        # Missing "objective"
        "information_needed": [],
        "info_attribute_to_question_template": {},
        "success_criteria": [],
        "failure_criteria": [],
    }


# --- Test Cases ---


@mock.patch(
    "builtins.open", new_callable=mock.mock_open
)  # Mock a função open globalmente
@mock.patch("os.path.isdir")  # Mock os.path.isdir
async def test_load_persona_success(mock_isdir, mock_open, valid_persona_data):
    """Tests loading a valid persona JSON file successfully."""
    # Arrange
    persona_id = valid_persona_data["persona_id"]
    json_string = json.dumps(valid_persona_data)
    # Configura o mock de open para retornar o JSON quando o arquivo correto for lido
    mock_open.return_value.read.return_value = json_string
    # Configura o mock de isdir para retornar True (diretório existe)
    mock_isdir.return_value = True
    # Define o caminho esperado baseado na config (pode ser mockado também se preferir)
    expected_path = os.path.join(simulation_config.PERSONA_DIR, f"{persona_id}.json")

    # Action
    persona = await persona_loader.load_persona(persona_id)

    # Assertions
    mock_isdir.assert_called_once_with(
        simulation_config.PERSONA_DIR
    )  # Verifica se checou o diretório
    mock_open.assert_called_once_with(
        expected_path, "r", encoding="utf-8"
    )  # Verifica se abriu o arquivo correto
    assert persona is not None
    assert isinstance(persona, PersonaDefinition)
    assert persona.persona_id == persona_id
    assert persona.description == valid_persona_data["description"]
    assert len(persona.information_needed) == 1
    assert persona.information_needed[0].entity == "Widget A"


@mock.patch("os.path.isdir")
async def test_load_persona_file_not_found(mock_isdir):
    """Tests loading when the persona JSON file does not exist."""
    # Arrange
    persona_id = "non_existent_persona"
    mock_isdir.return_value = True  # Diretório existe
    # Mock open para levantar FileNotFoundError quando chamado
    with mock.patch("builtins.open", mock.mock_open()) as mock_file:
        mock_file.side_effect = FileNotFoundError

        # Action
        persona = await persona_loader.load_persona(persona_id)

        # Assertions
        assert persona is None
        # Verificar se tentou abrir o arquivo correto (opcional)
        expected_path = os.path.join(
            simulation_config.PERSONA_DIR, f"{persona_id}.json"
        )
        mock_file.assert_called_once_with(expected_path, "r", encoding="utf-8")


@mock.patch("builtins.open", new_callable=mock.mock_open)
@mock.patch("os.path.isdir")
async def test_load_persona_invalid_json(mock_isdir, mock_open):
    """Tests loading when the file contains invalid JSON."""
    # Arrange
    persona_id = "invalid_json_persona"
    invalid_json_string = (
        '{"persona_id": "test", "description": "missing quote}'  # JSON inválido
    )
    mock_open.return_value.read.return_value = invalid_json_string
    mock_isdir.return_value = True

    # Action
    persona = await persona_loader.load_persona(persona_id)

    # Assertions
    assert persona is None


@mock.patch("builtins.open", new_callable=mock.mock_open)
@mock.patch("os.path.isdir")
async def test_load_persona_invalid_schema(
    mock_isdir, mock_open, invalid_schema_persona_data
):
    """Tests loading when JSON is valid but data doesn't match Pydantic schema."""
    # Arrange
    persona_id = invalid_schema_persona_data["persona_id"]
    json_string = json.dumps(invalid_schema_persona_data)
    mock_open.return_value.read.return_value = json_string
    mock_isdir.return_value = True

    # Action
    persona = await persona_loader.load_persona(persona_id)

    # Assertions
    assert persona is None  # Deve falhar na validação Pydantic


@mock.patch("os.path.isdir")
async def test_load_persona_directory_not_found(mock_isdir):
    """Tests loading when the base persona directory does not exist."""
    # Arrange
    persona_id = "any_persona"
    mock_isdir.return_value = False  # Diretório NÃO existe

    # Action
    persona = await persona_loader.load_persona(persona_id)

    # Assertions
    assert persona is None
    mock_isdir.assert_called_once_with(simulation_config.PERSONA_DIR)
    # open não deve ser chamado se o diretório não existe
    # (Verificar isso requer um mock mais elaborado ou não usar mock.patch global)


async def test_load_persona_empty_id():
    """Tests calling load_persona with an empty ID."""
    persona = await persona_loader.load_persona("")
    assert persona is None
