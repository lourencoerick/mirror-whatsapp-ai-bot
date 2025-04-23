# backend/app/tests/simulation/repositories/test_simulation_repo.py

import asyncio
import pytest
import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

# Importar modelos e schemas necessários
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.simulation.schemas.persona_definition import (
    PersonaDefinition,
)  # Para usar na fixture e testes

# Importar o repositório a ser testado
from app.simulation.repositories import simulation as simulation_repo

# Importar fixtures do conftest (ou definidas aqui)
from app.models.company_profile import CompanyProfile  # Para type hint da fixture

# Marcar todos os testes como asyncio
pytestmark = pytest.mark.asyncio

# --- Test Cases ---


async def test_create_simulation_success(
    db_session: AsyncSession,
    test_simulation_company_profile: CompanyProfile,  # Fixture do conftest (ou local)
    sample_persona_def: PersonaDefinition,  # Fixture do conftest (ou local)
):
    """
    Tests successful creation of a simulation record using the repository.
    """
    profile_id_to_use = test_simulation_company_profile.id

    # --- Action ---
    simulation = await simulation_repo.create_simulation(
        db=db_session, profile_id=profile_id_to_use, persona_def=sample_persona_def
    )
    # Fixture db_session fará commit/rollback no final do teste

    # --- Assertions ---
    assert simulation is not None
    assert isinstance(simulation.id, uuid.UUID)
    assert simulation.company_profile_id == profile_id_to_use
    assert simulation.status == SimulationStatusEnum.RUNNING  # Default status
    assert simulation.persona_definition["persona_id"] == sample_persona_def.persona_id
    assert simulation.outcome is None
    assert simulation.turn_count is None
    assert simulation.simulation_duration_seconds is None
    assert simulation.fallback_used is None
    assert simulation.evaluation_metrics is None
    assert simulation.error_message is None
    assert simulation.created_at is not None
    assert simulation.updated_at is not None

    # Verifica se está na sessão (antes do commit final da fixture)
    # assert simulation in db_session.new

    # Opcional: Forçar flush para verificar persistência imediata (se necessário)
    await db_session.flush()
    await db_session.refresh(simulation)  # Carrega valores do DB (como timestamps)

    fetched = await simulation_repo.get_simulation_by_id(db_session, simulation.id)
    assert fetched is not None
    assert fetched.id == simulation.id
    assert fetched.status == SimulationStatusEnum.RUNNING


async def test_get_simulation_by_id_found(
    db_session: AsyncSession,
    test_simulation_company_profile: CompanyProfile,
    sample_persona_def: PersonaDefinition,
):
    """
    Tests retrieving an existing simulation by ID using the repository.
    """
    # Arrange: Create a simulation first
    created_sim = await simulation_repo.create_simulation(
        db=db_session,
        profile_id=test_simulation_company_profile.id,
        persona_def=sample_persona_def,
    )
    await db_session.flush()  # Ensure it gets an ID
    simulation_id = created_sim.id

    # Action: Fetch the simulation
    fetched_sim = await simulation_repo.get_simulation_by_id(db_session, simulation_id)

    # Assertions
    assert fetched_sim is not None
    assert fetched_sim.id == simulation_id
    assert fetched_sim.company_profile_id == test_simulation_company_profile.id
    assert fetched_sim.persona_definition["persona_id"] == sample_persona_def.persona_id


async def test_get_simulation_by_id_not_found(db_session: AsyncSession):
    """
    Tests retrieving a non-existent simulation by ID returns None.
    """
    non_existent_id = uuid.uuid4()
    # Action
    fetched_sim = await simulation_repo.get_simulation_by_id(
        db_session, non_existent_id
    )
    # Assertion
    assert fetched_sim is None


async def test_update_simulation_success(
    db_session: AsyncSession,
    test_simulation_company_profile: CompanyProfile,
    sample_persona_def: PersonaDefinition,
):
    """
    Tests successfully updating various fields of a simulation record.
    """
    # Arrange: Create a simulation first
    simulation = await simulation_repo.create_simulation(
        db=db_session,
        profile_id=test_simulation_company_profile.id,
        persona_def=sample_persona_def,
    )
    await db_session.commit()
    # await db_session.flush()
    await db_session.refresh(simulation)  # Get initial state from DB
    original_updated_at = simulation.updated_at

    # Ensure some time passes for updated_at check
    await asyncio.sleep(0.01)

    # Action: Prepare update data and call update function
    update_data = {
        "status": SimulationStatusEnum.COMPLETED,
        "outcome": SimulationOutcomeEnum.SALE_COMPLETED,
        "turn_count": 10,
        "simulation_duration_seconds": 120,
        "fallback_used": True,
        "evaluation_metrics": {"score": 0.8, "notes": "Good flow"},
        "error_message": None,  # Explicitly setting None if clearing error
    }
    updated_sim = await simulation_repo.update_simulation(
        db=db_session, db_simulation=simulation, update_data=update_data
    )
    await db_session.commit()
    # await db_session.flush()
    await db_session.refresh(updated_sim)  # Get final state from DB

    # Assertions
    assert updated_sim is not None
    assert updated_sim.id == simulation.id
    assert updated_sim.status == SimulationStatusEnum.COMPLETED
    assert updated_sim.outcome == SimulationOutcomeEnum.SALE_COMPLETED
    assert updated_sim.turn_count == 10
    assert updated_sim.simulation_duration_seconds == 120
    assert updated_sim.fallback_used is True
    assert updated_sim.evaluation_metrics == {"score": 0.8, "notes": "Good flow"}
    assert updated_sim.error_message is None
    assert updated_sim.updated_at > original_updated_at  # Timestamp should update


async def test_update_simulation_partial_data(
    db_session: AsyncSession,
    test_simulation_company_profile: CompanyProfile,
    sample_persona_def: PersonaDefinition,
):
    """Tests updating only a subset of fields."""
    # Arrange
    simulation = await simulation_repo.create_simulation(
        db=db_session,
        profile_id=test_simulation_company_profile.id,
        persona_def=sample_persona_def,
    )
    await db_session.flush()
    await db_session.refresh(simulation)
    original_outcome = simulation.outcome  # Should be None

    # Action
    update_data = {"status": SimulationStatusEnum.FAILED, "error_message": "Test Error"}
    updated_sim = await simulation_repo.update_simulation(
        db=db_session, db_simulation=simulation, update_data=update_data
    )
    await db_session.flush()
    await db_session.refresh(updated_sim)

    # Assertions
    assert updated_sim.status == SimulationStatusEnum.FAILED
    assert updated_sim.error_message == "Test Error"
    assert updated_sim.outcome == original_outcome  # Outcome should not have changed


# TODO: Add tests for edge cases if needed (e.g., trying to update with invalid data -
# although repo assumes data is valid dict, validation should happen before calling repo)
# TODO: Add tests for list_simulations if implemented in the repo.
