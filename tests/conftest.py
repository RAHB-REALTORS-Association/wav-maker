"""
Pytest configuration for app tests
"""
import os
import pytest
from unittest.mock import patch

# Make sure we use test templates/static directories during tests
@pytest.fixture(autouse=True)
def override_template_folder():
    """Automatically override the template folder for all tests"""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(test_dir)
    
    template_dir = os.path.join(repo_dir, 'test_templates')
    static_dir = os.path.join(repo_dir, 'test_static')
    
    # Create minimal directories if they don't exist
    os.makedirs(template_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)
    
    # Patch Flask's template and static folders
    with patch('flask.Flask.template_folder', new=template_dir):
        with patch('flask.Flask.static_folder', new=static_dir):
            yield