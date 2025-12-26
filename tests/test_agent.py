import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Config
import agent

class TestAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project_dir = Path("/tmp/dummy-project")
    
    @patch('agent.create_client')
    @patch('agent.copy_spec_to_project')
    async def test_agent_first_run_init(self, mock_copy, mock_create):
        """Test agent initialization on first run (no handoff.json)."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_create.return_value = mock_client
        
        async def async_iter():
            if False: yield
            return
            
        # Fix: Use MagicMock for the method itself to avoid auto-awaiting behavior of AsyncMock
        mock_client.receive_response = MagicMock(side_effect=lambda: async_iter())
        
        # Patch Path.exists to return False (simulating fresh run)
        with patch.object(Path, 'exists', return_value=False):
            with patch('agent.get_initializer_prompt') as mock_prompt_getter:
                # We limit to 1 iteration to prevent infinite loop
                await agent.run_autonomous_agent(
                    self.project_dir, 
                    model="test-model", 
                    max_iterations=1,
                    spec_path="spec.txt"
                )
                
                # Verify copy_spec called
                mock_copy.assert_called()
                
                # Verify initializer prompt was requested
                mock_prompt_getter.assert_called_once()

    @patch('agent.create_client')
    @patch('agent.print_progress_summary')
    @patch('agent.schema.validate_handoff_file')
    async def test_agent_resume_run(self, mock_validate, mock_print, mock_create):
        """Test agent resuming an existing run."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        
        async def async_iter():
            if False: yield
            return
            
        async def async_iter():
            if False: yield
            return
            
        mock_client.receive_response = MagicMock(side_effect=lambda: async_iter())
        mock_create.return_value = mock_client
        
        mock_validate.return_value = [] # Valid schema
        
        with patch.object(Path, 'exists', return_value=True): # handoff.json exists
            with patch('agent.get_prompt_for_mode') as mock_prompt_getter:
                await agent.run_autonomous_agent(
                    self.project_dir, 
                    model="test-model", 
                    max_iterations=1
                )
                
                # Verify coding prompt was requested (NOT initializer)
                mock_prompt_getter.assert_called_once()

    @patch('agent.create_client')
    async def test_agent_handles_client_error(self, mock_create):
        """Test that agent catches errors and retries (or continues)."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_create.return_value = mock_client
        
        # First call raises error
        mock_client.query.side_effect = Exception("API Error")
        
        with patch.object(Path, 'exists', return_value=True):
            # We verify it doesn't crash the whole process
            try:
                await agent.run_autonomous_agent(
                    self.project_dir, 
                    model="test-model", 
                    max_iterations=1
                )
            except Exception as e:
                self.fail(f"Agent crashed on client error: {e}")

if __name__ == "__main__":
    unittest.main()
