"""
Integration Test for Y/N Prompt Validation
Tests prompt behavior from quickstart.md Scenario 5
"""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner


class TestPrompts:
    """Integration test for y/n prompt validation"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import cli dynamically to handle module not existing initially"""
        try:
            from src.cli.main import cli
            self.cli = cli
        except ImportError:
            pytest.skip("CLI module not yet implemented")

    def test_prompt_rejects_invalid_inputs(self):
        """Test that invalid inputs are rejected and re-prompt occurs"""
        runner = CliRunner()
        # Test with multiple invalid inputs followed by valid 'n'
        result = runner.invoke(
            self.cli,
            ['uninstall'],
            input='x\n1\nyes\nn\n'  # Invalid inputs, then valid 'n'
        )
        # Should show deprecation warning and prompt
        assert "deprecated" in result.output.lower()
        assert "Continue? (y/n)" in result.output
        # Should have re-prompted for each invalid input
        assert result.output.count("Continue? (y/n)") >= 2

    def test_prompt_accepts_lowercase_y(self):
        """Test that lowercase 'y' is accepted"""
        runner = CliRunner()
        with patch('src.logic.setup.services.uninstaller.SetupUninstaller.execute', return_value=True):
            result = runner.invoke(
                self.cli,
                ['uninstall'],
                input='y\n'
            )
            # Should proceed with operation
            assert result.exit_code in (0, 2)  # Success or operation failure

    def test_prompt_accepts_uppercase_y(self):
        """Test that uppercase 'Y' is accepted"""
        runner = CliRunner()
        with patch('src.logic.setup.services.uninstaller.SetupUninstaller.execute', return_value=True):
            result = runner.invoke(
                self.cli,
                ['uninstall'],
                input='Y\n'
            )
            # Should proceed with operation
            assert result.exit_code in (0, 2)  # Success or operation failure

    def test_prompt_accepts_lowercase_n(self):
        """Test that lowercase 'n' is accepted"""
        runner = CliRunner()
        result = runner.invoke(
            self.cli,
            ['uninstall'],
            input='n\n'
        )
        # Should cancel operation
        assert result.exit_code == 1  # User cancelled

    def test_prompt_accepts_uppercase_n(self):
        """Test that uppercase 'N' is accepted"""
        runner = CliRunner()
        result = runner.invoke(
            self.cli,
            ['uninstall'],
            input='N\n'
        )
        # Should cancel operation
        assert result.exit_code == 1  # User cancelled

    def test_prompt_shows_detailed_consequences(self):
        """Test that prompts show detailed information about consequences"""
        runner = CliRunner()

        # Test uninstall prompt
        result = runner.invoke(self.cli, ['uninstall'], input='n\n')
        assert "This will remove all Bablib data and configuration" in result.output

        # Test init prompt
        result = runner.invoke(self.cli, ['init'], input='n\n')
        assert "This will initialize Bablib and create configuration files" in result.output

        # Test reset prompt
        result = runner.invoke(self.cli, ['reset'], input='n\n')
        assert "This will reset Bablib to default settings. Projects will be preserved" in result.output

    def test_no_number_options_in_yn_prompts(self):
        """Test that y/n prompts don't offer numbered options"""
        runner = CliRunner()
        result = runner.invoke(
            self.cli,
            ['uninstall'],
            input='1\nn\n'  # Try to select with '1', then cancel with 'n'
        )
        # '1' should not work as a selection
        assert result.exit_code == 1  # Cancelled with 'n'
        # Should have re-prompted after '1'
        assert result.output.count("Continue? (y/n)") >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])