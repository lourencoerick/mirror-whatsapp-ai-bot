import os
from uuid import UUID

SIMULATION_COMPANY_PROFILE_ID = UUID("11111111-aaaa-bbbb-cccc-123456789abc")
SIMULATION_ACCOUNT_ID = UUID("11111111-aaaa-bbbb-cccc-123456789abc")
SIMULATION_USER_ID = UUID("11111111-5d8f-41d3-94bc-63f20c6f3e4a")
SIMULATION_INBOX_ID = UUID("11111111-dead-beef-cafe-abcdefabcdef")
SIMULATION_CONTACT_ID = UUID("11111111-0000-4444-8888-ffffffffffff")
SIMULATION_CHANNEL_ID = "11111111-1234-5678-90ab-cdef12345678"
SIMULATION_ACCOUNT_NAME = "Simulation Account"
SIMULATION_USER_NAME = "Simulation User"
SIMULATION_INBOX_NAME = "Simulation Inbox"
SIMULATION_CONTACT_NAME = "Simulation Contact"
SIMULATION_CONTACT_PHONE_NUMBER = "5511999999999"


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERSONA_DIR = os.path.join(project_root, "data/personas")
